#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — 24-Hour RSS Burn Test Monitor
# Run this on Render after deploying fix/phase1-leak-killers to staging.
#
# Usage:
#   chmod +x tests/phase1/rss_burn_monitor.sh
#   ./tests/phase1/rss_burn_monitor.sh [RENDER_URL]
#
# Example:
#   ./tests/phase1/rss_burn_monitor.sh https://lotto-machine.onrender.com
#
# Output:
#   - Prints RSS reading every 5 minutes to stdout
#   - Writes structured log to /tmp/rss_burn_log.tsv
#   - Prints BREACH alert if RSS > 420MB
#   - Prints PASS/FAIL summary at end of 24h window
#
# Definition of Done:
#   RSS stays strictly below 430000 kB (420MB) for the full 24-hour window.
#   Phase 2 is BLOCKED until this log is verified.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

RENDER_URL="${1:-}"
RSS_THRESHOLD_KB=430000   # 420 MB in kB
INTERVAL_SEC=300          # 5 minutes
DURATION_SEC=86400        # 24 hours
LOG_FILE="/tmp/rss_burn_log.tsv"
START_TS=$(date -u +%s)
END_TS=$(( START_TS + DURATION_SEC ))
BREACH_COUNT=0
READING_COUNT=0
MAX_RSS=0

# ── Find uvicorn PID ─────────────────────────────────────────────────────────
find_pid() {
    pgrep -f "uvicorn" | head -1 || true
}

PID=$(find_pid)
if [ -z "$PID" ]; then
    echo "ERROR: No uvicorn process found. Is the app running?"
    exit 1
fi
echo "uvicorn PID: $PID"

# ── Init log file ─────────────────────────────────────────────────────────────
echo -e "timestamp_utc\telapsed_min\trss_kb\trss_mb\tstatus\tpid" > "$LOG_FILE"
echo "Log: $LOG_FILE"
echo "Threshold: ${RSS_THRESHOLD_KB} kB (420 MB)"
echo "Duration: 24 hours ($(( DURATION_SEC / 3600 ))h)"
echo "Interval: ${INTERVAL_SEC}s (5 min)"
echo "─────────────────────────────────────────────────────────────────────"
echo "  TIME(UTC)   ELAPSED   RSS(kB)   RSS(MB)   STATUS"
echo "─────────────────────────────────────────────────────────────────────"

# ── FD baseline (before traffic) ─────────────────────────────────────────────
FD_BASELINE=$(ls -la /proc/$PID/fd 2>/dev/null | grep -c "\.db" || echo "N/A")
echo "FD baseline (SQLite .db): $FD_BASELINE"

# ── Optional: send 10 warm-up requests ───────────────────────────────────────
if [ -n "$RENDER_URL" ]; then
    echo "Sending 10 warm-up requests to $RENDER_URL/signals/master..."
    for i in $(seq 1 10); do
        curl -s --max-time 10 "$RENDER_URL/signals/master?symbol=SPY" > /dev/null 2>&1 || true
    done
    FD_AFTER_WARMUP=$(ls -la /proc/$PID/fd 2>/dev/null | grep -c "\.db" || echo "N/A")
    echo "FD after 10 requests (SQLite .db): $FD_AFTER_WARMUP"
    if [ "$FD_AFTER_WARMUP" != "N/A" ] && [ "$FD_BASELINE" != "N/A" ]; then
        FD_DELTA=$(( FD_AFTER_WARMUP - FD_BASELINE ))
        if [ "$FD_DELTA" -gt 2 ]; then
            echo "WARNING: FD leak detected after warm-up! delta=$FD_DELTA"
        else
            echo "FD check PASS: delta=$FD_DELTA (expected ≤2)"
        fi
    fi
fi

echo "─────────────────────────────────────────────────────────────────────"

# ── Main monitoring loop ──────────────────────────────────────────────────────
while true; do
    NOW=$(date -u +%s)
    ELAPSED_SEC=$(( NOW - START_TS ))
    ELAPSED_MIN=$(( ELAPSED_SEC / 60 ))
    TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S")

    # Re-find PID in case of restart
    CURRENT_PID=$(find_pid)
    if [ -z "$CURRENT_PID" ]; then
        echo "  $TIMESTAMP  ${ELAPSED_MIN}m  PROCESS DIED — uvicorn not found"
        echo -e "$TIMESTAMP\t$ELAPSED_MIN\tN/A\tN/A\tPROCESS_DIED\t$PID" >> "$LOG_FILE"
        sleep "$INTERVAL_SEC"
        continue
    fi
    PID="$CURRENT_PID"

    # Read RSS from /proc
    RSS_KB=$(grep VmRSS /proc/$PID/status 2>/dev/null | awk '{print $2}' || echo "0")
    RSS_MB=$(( RSS_KB / 1024 ))

    # Track max
    if [ "$RSS_KB" -gt "$MAX_RSS" ]; then
        MAX_RSS="$RSS_KB"
    fi

    READING_COUNT=$(( READING_COUNT + 1 ))

    # Threshold check
    if [ "$RSS_KB" -gt "$RSS_THRESHOLD_KB" ]; then
        STATUS="BREACH"
        BREACH_COUNT=$(( BREACH_COUNT + 1 ))
        echo "  $TIMESTAMP  ${ELAPSED_MIN}m  ${RSS_KB}kB  ${RSS_MB}MB  *** BREACH *** (>${RSS_THRESHOLD_KB}kB)"
    else
        STATUS="OK"
        echo "  $TIMESTAMP  ${ELAPSED_MIN}m  ${RSS_KB}kB  ${RSS_MB}MB  OK"
    fi

    # Write to log
    echo -e "$TIMESTAMP\t$ELAPSED_MIN\t$RSS_KB\t$RSS_MB\t$STATUS\t$PID" >> "$LOG_FILE"

    # Check if 24h window is complete
    if [ "$NOW" -ge "$END_TS" ]; then
        break
    fi

    sleep "$INTERVAL_SEC"
done

# ── Final summary ─────────────────────────────────────────────────────────────
echo "─────────────────────────────────────────────────────────────────────"
echo "  24-HOUR BURN TEST COMPLETE"
echo "─────────────────────────────────────────────────────────────────────"
echo "  Readings:      $READING_COUNT"
echo "  Breaches:      $BREACH_COUNT  (RSS > 420MB)"
echo "  Max RSS:       ${MAX_RSS}kB  ($(( MAX_RSS / 1024 ))MB)"
echo "  Threshold:     ${RSS_THRESHOLD_KB}kB  (420MB)"
echo "  Log:           $LOG_FILE"
echo ""

if [ "$BREACH_COUNT" -eq 0 ]; then
    echo "  RESULT: PASS — RSS stayed below 420MB for 24 hours"
    echo "  Phase 2 authorization: READY TO REQUEST"
    exit 0
else
    echo "  RESULT: FAIL — $BREACH_COUNT breach(es) detected"
    echo "  Phase 2 authorization: BLOCKED"
    echo "  Action: review log, identify spike source, fix before re-test"
    exit 1
fi
