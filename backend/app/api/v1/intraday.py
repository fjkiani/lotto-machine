"""
Intraday Snapshot API — Serves the guardian's thesis state to the frontend.

GET /api/v1/intraday/snapshot → latest /tmp/intraday_snapshot.json
"""

from fastapi import APIRouter
import json
import os

router = APIRouter(prefix="/api/v1/intraday", tags=["intraday"])

SNAPSHOT_PATH = "/tmp/intraday_snapshot.json"


@router.get("/snapshot")
async def get_snapshot():
    """Return the latest intraday snapshot written by IntradayGuardian."""
    if os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {
                "thesis_valid": True,
                "market_open": False,
                "error": f"Snapshot file corrupt: {e}",
            }
    return {
        "thesis_valid": True,
        "market_open": False,
        "error": "No snapshot yet — guardian starts at 9:30 AM ET",
    }
