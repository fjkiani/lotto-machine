#!/usr/bin/env bash
# Smoke GET /api/v1/signals with a long timeout (handler often >15s on cold path).
# Bug 4 seal: KILL_CHAIN_SCORE_DEBUG=1 PORT=8015 ./scripts/restart_api.sh 2>&1 | tee /tmp/ai-hedge-api.log
# then: grep -E 'PRE_INJECT|POST_INJECT' /tmp/ai-hedge-api.log | head -4
set -euo pipefail
PORT="${PORT:-8000}"
URL="${1:-http://127.0.0.1:${PORT}/api/v1/signals}"
echo "GET $URL (max 90s) ..."
curl -sS -m 90 "$URL" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('count:', d.get('count'), 'master_count:', d.get('master_count'),
      'us_market_rth:', d.get('us_market_rth'), 'stale:', d.get('signal_stale_count'))
if d.get('signals'):
    s = d['signals'][0]
    print('first:', s.get('source'), s.get('action'), 'kc:', s.get('kill_chain_verdict'))
"
