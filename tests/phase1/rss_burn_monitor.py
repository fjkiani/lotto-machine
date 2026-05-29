#!/usr/bin/env python3
"""
Phase 1 — 24-Hour RSS Burn Test Monitor (Python version)
=========================================================
Run on Render after deploying fix/phase1-leak-killers to staging.

Usage:
    python tests/phase1/rss_burn_monitor.py
    python tests/phase1/rss_burn_monitor.py --url https://lotto-machine.onrender.com
    python tests/phase1/rss_burn_monitor.py --duration 3600  # 1h quick test

Output:
    - Prints RSS reading every 5 minutes
    - Writes /tmp/rss_burn_log.tsv (tab-separated, importable to Excel/Sheets)
    - Prints BREACH alert if RSS > 420MB
    - Prints PASS/FAIL summary at end

Definition of Done:
    RSS stays strictly below 430000 kB (420MB) for the full 24-hour window.
    Phase 2 is BLOCKED until this log is verified and sent to Fahad.
"""

import os
import sys
import time
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
RSS_THRESHOLD_KB  = 430_000   # 420 MB
INTERVAL_SEC      = 300       # 5 minutes
DURATION_SEC      = 86_400    # 24 hours
LOG_FILE          = Path("/tmp/rss_burn_log.tsv")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"


def find_uvicorn_pid() -> int | None:
    """Find the uvicorn process PID."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "uvicorn"],
            capture_output=True, text=True
        )
        pids = [int(p) for p in result.stdout.strip().splitlines() if p.strip()]
        return pids[0] if pids else None
    except Exception:
        return None


def read_rss_kb(pid: int) -> int | None:
    """Read VmRSS from /proc/<pid>/status."""
    try:
        status = Path(f"/proc/{pid}/status").read_text()
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except Exception:
        pass
    return None


def count_sqlite_fds(pid: int) -> int:
    """Count open file descriptors pointing to .db files."""
    count = 0
    fd_dir = Path(f"/proc/{pid}/fd")
    if not fd_dir.exists():
        return -1
    for fd in fd_dir.iterdir():
        try:
            target = os.readlink(fd)
            if target.endswith(".db"):
                count += 1
        except (OSError, PermissionError):
            pass
    return count


def send_warmup_requests(url: str, n: int = 50):
    """Send warm-up requests to populate the cache and exercise the DB paths."""
    try:
        import urllib.request
        print(f"  Sending {n} warm-up requests to {url}/signals/master...")
        ok = 0
        for i in range(n):
            try:
                req = urllib.request.urlopen(
                    f"{url}/signals/master?symbol=SPY", timeout=15
                )
                req.read()
                ok += 1
            except Exception:
                pass
        print(f"  Warm-up complete: {ok}/{n} requests succeeded")
    except Exception as e:
        print(f"  Warm-up skipped: {e}")


def main():
    parser = argparse.ArgumentParser(description="Phase 1 RSS Burn Test Monitor")
    parser.add_argument("--url", default="", help="Render app URL for warm-up requests")
    parser.add_argument("--duration", type=int, default=DURATION_SEC,
                        help=f"Test duration in seconds (default: {DURATION_SEC} = 24h)")
    parser.add_argument("--interval", type=int, default=INTERVAL_SEC,
                        help=f"Polling interval in seconds (default: {INTERVAL_SEC} = 5min)")
    parser.add_argument("--threshold", type=int, default=RSS_THRESHOLD_KB,
                        help=f"RSS breach threshold in kB (default: {RSS_THRESHOLD_KB} = 420MB)")
    args = parser.parse_args()

    duration    = args.duration
    interval    = args.interval
    threshold   = args.threshold
    render_url  = args.url.rstrip("/")

    # ── Find PID ──────────────────────────────────────────────────────────────
    pid = find_uvicorn_pid()
    if pid is None:
        print(f"{RED}ERROR: No uvicorn process found. Is the app running?{RESET}")
        sys.exit(1)

    start_ts  = time.time()
    end_ts    = start_ts + duration

    print(f"\n{'═'*65}")
    print(f"  PHASE 1 — 24-HOUR RSS BURN TEST")
    print(f"  Branch: fix/phase1-leak-killers")
    print(f"  Start:  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  PID:    {pid}")
    print(f"  Threshold: {threshold:,} kB ({threshold // 1024} MB)")
    print(f"  Duration:  {duration // 3600}h ({duration}s)")
    print(f"  Interval:  {interval}s ({interval // 60}min)")
    print(f"  Log:       {LOG_FILE}")
    print(f"{'═'*65}")

    # ── FD baseline ───────────────────────────────────────────────────────────
    fd_baseline = count_sqlite_fds(pid)
    if fd_baseline >= 0:
        print(f"  FD baseline (SQLite .db open): {fd_baseline}")
    else:
        print(f"  FD check: /proc not available (not Linux)")

    # ── Warm-up ───────────────────────────────────────────────────────────────
    if render_url:
        send_warmup_requests(render_url, n=50)
        fd_after = count_sqlite_fds(pid)
        if fd_baseline >= 0 and fd_after >= 0:
            delta = fd_after - fd_baseline
            if delta > 2:
                print(f"  {RED}FD LEAK after warm-up: delta={delta} (expected ≤2){RESET}")
            else:
                print(f"  {GREEN}FD check PASS: delta={delta} after 50 requests{RESET}")

    # ── Init log ──────────────────────────────────────────────────────────────
    LOG_FILE.write_text(
        "timestamp_utc\telapsed_min\trss_kb\trss_mb\tstatus\tpid\n"
    )

    print(f"\n  {'TIME(UTC)':<22} {'ELAPSED':>8} {'RSS(kB)':>10} {'RSS(MB)':>8}  STATUS")
    print(f"  {'─'*63}")

    # ── Monitoring loop ───────────────────────────────────────────────────────
    breach_count  = 0
    reading_count = 0
    max_rss_kb    = 0
    readings      = []

    while True:
        now          = time.time()
        elapsed_sec  = int(now - start_ts)
        elapsed_min  = elapsed_sec // 60
        ts           = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Re-find PID in case of restart
        current_pid = find_uvicorn_pid()
        if current_pid is None:
            print(f"  {ts}  {elapsed_min:>6}m  {'N/A':>10}  {'N/A':>7}  {RED}PROCESS DIED{RESET}")
            with LOG_FILE.open("a") as f:
                f.write(f"{ts}\t{elapsed_min}\tN/A\tN/A\tPROCESS_DIED\t{pid}\n")
            time.sleep(interval)
            continue
        pid = current_pid

        rss_kb = read_rss_kb(pid)
        if rss_kb is None:
            print(f"  {ts}  {elapsed_min:>6}m  {'ERR':>10}  {'ERR':>7}  READ_ERROR")
            time.sleep(interval)
            continue

        rss_mb = rss_kb // 1024
        reading_count += 1
        max_rss_kb = max(max_rss_kb, rss_kb)
        readings.append(rss_kb)

        if rss_kb > threshold:
            breach_count += 1
            status = "BREACH"
            line = (f"  {ts}  {elapsed_min:>6}m  {rss_kb:>10,}  {rss_mb:>7}  "
                    f"{RED}*** BREACH *** (>{threshold:,}kB){RESET}")
        else:
            status = "OK"
            # Color: green if well below, yellow if within 50MB of threshold
            color = YELLOW if rss_kb > (threshold - 51_200) else GREEN
            line = (f"  {ts}  {elapsed_min:>6}m  {rss_kb:>10,}  {rss_mb:>7}  "
                    f"{color}OK{RESET}")

        print(line)

        with LOG_FILE.open("a") as f:
            f.write(f"{ts}\t{elapsed_min}\t{rss_kb}\t{rss_mb}\t{status}\t{pid}\n")

        if now >= end_ts:
            break

        time.sleep(interval)

    # ── Summary ───────────────────────────────────────────────────────────────
    avg_rss = sum(readings) // len(readings) if readings else 0

    print(f"\n{'═'*65}")
    print(f"  24-HOUR BURN TEST COMPLETE")
    print(f"{'═'*65}")
    print(f"  Readings:    {reading_count}")
    print(f"  Breaches:    {breach_count}  (RSS > {threshold // 1024}MB)")
    print(f"  Max RSS:     {max_rss_kb:,} kB  ({max_rss_kb // 1024} MB)")
    print(f"  Avg RSS:     {avg_rss:,} kB  ({avg_rss // 1024} MB)")
    print(f"  Threshold:   {threshold:,} kB  ({threshold // 1024} MB)")
    print(f"  Log:         {LOG_FILE}")
    print(f"{'─'*65}")

    if breach_count == 0:
        print(f"  {GREEN}RESULT: PASS — RSS stayed below {threshold // 1024}MB for {duration // 3600}h{RESET}")
        print(f"  Phase 2 authorization: READY TO REQUEST")
        print(f"  Send {LOG_FILE} to Fahad to unlock Phase 2.")
        sys.exit(0)
    else:
        print(f"  {RED}RESULT: FAIL — {breach_count} breach(es) detected{RESET}")
        print(f"  Phase 2 authorization: BLOCKED")
        print(f"  Action: review {LOG_FILE}, identify spike source, fix before re-test.")
        sys.exit(1)


if __name__ == "__main__":
    main()
