"""
🚦 GATE API ROUTER

Exposes Gate Health, signals, outcomes, and morning brief via REST API.
"""

import json
import logging
from pathlib import Path
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/gate", tags=["Gate"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


@router.get("/health")
async def get_gate_health(n: int = 20):
    """Gate Health metric: win rate, blocked/allowed, avg R."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
        from live_monitoring.orchestrator.gate_outcome_tracker import GateOutcomeTracker
        tracker = GateOutcomeTracker()
        return tracker.get_health(n=n)
    except Exception as e:
        logger.error(f"Gate health error: {e}")
        return {"error": str(e)}


@router.get("/signals/today")
async def get_signals_today():
    """Today's gated signals that passed."""
    return _read_json(DATA_DIR / "gate_signals_today.json")


@router.get("/signals/blocked")
async def get_blocked_today():
    """Today's blocked signals."""
    return _read_json(DATA_DIR / "gate_blocked_today.json")


@router.get("/outcomes")
async def get_outcomes(n: int = 20):
    """Last N gate outcomes."""
    outcomes = _read_json(DATA_DIR / "gate_outcomes.json")
    return outcomes[-n:] if len(outcomes) > n else outcomes


@router.get("/brief")
async def get_brief():
    """Latest morning brief."""
    return _read_json(DATA_DIR / "morning_brief.json", is_dict=True)


def _read_json(path: Path, is_dict: bool = False):
    """Read a JSON file, return empty list/dict on error."""
    try:
        if path.exists() and path.stat().st_size > 0:
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {} if is_dict else []
