#!/usr/bin/env bash
# Hard-restart local API: free PORT, then start clean (matches typical local use on 8015).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8015}"

echo "Stopping listeners on port ${PORT} ..."
for pid in $(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true); do
  echo "  kill PID ${pid}"
  kill -9 "${pid}" 2>/dev/null || true
done

# Optional: stop stray uvicorn for this repo only
pkill -f "${ROOT}/venv/bin/uvicorn backend.app.main:app" 2>/dev/null || true

sleep 1
if lsof -tiTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "ERROR: port ${PORT} still in use" >&2
  exit 1
fi

export PORT
export API_LIGHT_MODE="${API_LIGHT_MODE:-1}"
# Propagate to uvicorn child (Bug 4 seal: PRE_INJECT_SCORE / POST_INJECT_SCORE on /api/v1/signals)
export KILL_CHAIN_SCORE_DEBUG="${KILL_CHAIN_SCORE_DEBUG:-}"
if [[ -n "${KILL_CHAIN_SCORE_DEBUG:-}" ]]; then
  echo "KILL_CHAIN_SCORE_DEBUG=${KILL_CHAIN_SCORE_DEBUG} — grep PRE_INJECT|POST_INJECT in api logs after smoke_signals.sh"
fi
echo "Starting API on http://127.0.0.1:${PORT} (API_LIGHT_MODE=${API_LIGHT_MODE}) ..."
exec "${ROOT}/scripts/dev_api.sh"
