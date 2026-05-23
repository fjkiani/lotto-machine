#!/usr/bin/env bash
# Local FastAPI — binds 127.0.0.1 so curl to localhost:$PORT works.
# Default PORT=8000 (matches frontend VITE_API_URL default). For 8015: PORT=8015 ./scripts/dev_api.sh
#
# First /api/v1/signals can take 10–25s (kill chain + sources); use curl -m 60 or scripts/smoke_signals.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$ROOT"
PORT="${PORT:-8000}"
# Fast, responsive API for probes; set to 0 for full UnifiedAlphaMonitor threads
export API_LIGHT_MODE="${API_LIGHT_MODE:-1}"

if [[ ! -x "$ROOT/venv/bin/uvicorn" ]]; then
  echo "Missing venv/bin/uvicorn — create venv and pip install -r backend/requirements.txt (or project deps)" >&2
  exit 1
fi

echo "Starting API on http://127.0.0.1:${PORT} (API_LIGHT_MODE=${API_LIGHT_MODE})"
exec "$ROOT/venv/bin/uvicorn" backend.app.main:app --host 127.0.0.1 --port "$PORT"
