"""
🛡️ INTRADAY SNAPSHOT API
Serves /tmp/intraday_snapshot.json to the frontend.
"""

from fastapi import APIRouter
import json
import os

router = APIRouter(prefix="/intraday", tags=["intraday"])

SNAPSHOT_PATH = "/tmp/intraday_snapshot.json"


@router.get("/snapshot")
async def get_snapshot():
    """Return current intraday snapshot (written by IntradayGuardian every 15 min)."""
    if os.path.exists(SNAPSHOT_PATH):
        with open(SNAPSHOT_PATH) as f:
            return json.load(f)
    return {
        "thesis_valid": True,
        "market_open": False,
        "error": "No snapshot yet — guardian starts at 9:30 AM ET",
    }
