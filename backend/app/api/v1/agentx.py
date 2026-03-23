"""
🧠 Agent X API Endpoints — Fed Officials Brain Intelligence

Exposes the FedOfficialsBrain to the frontend:
- Brain report (Fed tone + Hidden hands + Tavily research + Divergence boost)
- On-demand Tavily enrichment for any ticker
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)
router = APIRouter()

# Use the singleton BrainManager — one brain, one cache, one DB connection
_brain_manager = None


def _get_manager():
    """Return BrainManager singleton (NOT the raw brain — use .get_report())."""
    global _brain_manager
    if _brain_manager is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            from live_monitoring.core.brain_manager import BrainManager
            _brain_manager = BrainManager()
            logger.info("🧠 BrainManager singleton connected to API")
        except Exception as e:
            logger.error(f"Failed to initialize BrainManager: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"Agent X Brain unavailable: {e}")
    return _brain_manager


@router.get("/agentx/report")
async def agent_x_report():
    """
    Full brain report — Fed tone, hidden hands, Tavily context, divergence boost.
    This is the single endpoint the Agent X page consumes.
    Uses BrainManager.get_report() which handles None brain gracefully.
    """
    manager = _get_manager()

    try:
        import time as _time
        t0 = _time.time()
        report = manager.get_report()
        scan_time = _time.time() - t0

        return {
            "status": report.get("error", "ok"),
            "scan_time_seconds": round(scan_time, 1),
            **report,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent X brain report failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Brain report failed: {e}")


@router.get("/agentx/enrich")
async def agent_x_enrich(
    tickers: str = Query(..., description="Comma-separated tickers to research"),
    politician: str = Query(None, description="Optional politician name for context"),
):
    """
    On-demand Tavily enrichment for specific tickers.
    """
    brain = _get_manager().get_brain()
    if not brain:
        raise HTTPException(status_code=503, detail="Brain unavailable — cannot enrich")

    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No tickers provided")

    try:
        result = brain.enrich_with_tavily(
            hot_tickers=ticker_list,
            politician_name=politician,
        )
        return {
            "status": "ok",
            "tickers": ticker_list,
            "enrichment": result,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Tavily enrichment failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {e}")
