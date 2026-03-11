"""
🔍 Enrichment API Endpoints

Tavily search (replaces dead Perplexity), FRED macro data, budget tracking.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazy-init clients
_tavily = None
_fred = None


def _get_tavily():
    global _tavily
    if _tavily is None:
        from live_monitoring.enrichment.apis.tavily_client import TavilySearchClient
        _tavily = TavilySearchClient()
    return _tavily


def _get_fred():
    global _fred
    if _fred is None:
        from live_monitoring.enrichment.apis.fred_client import FREDClient
        _fred = FREDClient()
    return _fred


@router.get("/enrichment/search")
async def enrichment_search(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(5, ge=1, le=10),
):
    """
    Tavily-powered web search. 30 calls/day budget.
    Returns same format as old PerplexitySearchClient: {answer, citations, related_queries}
    """
    tc = _get_tavily()
    try:
        return tc.search(query, max_results=max_results)
    except Exception as e:
        if "budget" in str(e).lower():
            raise HTTPException(status_code=429, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/enrichment/enrich-tickers")
async def enrich_tickers(
    tickers: str = Query(..., description="Comma-separated ticker symbols"),
    context: str = Query("", description="Additional context"),
):
    """
    Research why specific tickers are seeing unusual activity.
    Uses 1 Tavily call from budget.
    """
    tc = _get_tavily()
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No tickers provided")
    try:
        return tc.enrich_hot_tickers(ticker_list, context)
    except Exception as e:
        if "budget" in str(e).lower():
            raise HTTPException(status_code=429, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {e}")


@router.get("/enrichment/macro")
async def enrichment_macro():
    """
    FRED macro snapshot: CPI, unemployment, Fed Funds, 10Y yield, yield spread.
    Unlimited calls. Includes regime classification (HAWKISH/DOVISH/RECESSIONARY/TRANSITIONAL).
    """
    fc = _get_fred()
    try:
        snap = fc.get_macro_snapshot()

        # Regime classification based on macro data
        regime = "UNKNOWN"
        try:
            yield_spread = snap.get("10Y-2Y Spread", {}).get("value")
            fed_rate = snap.get("Fed Funds Rate", {}).get("value")
            cpi_change = snap.get("CPI", {}).get("change_pct")

            if cpi_change is not None and yield_spread is not None:
                if cpi_change > 0.3 and fed_rate and fed_rate > 4.0:
                    regime = "HAWKISH"
                elif cpi_change < 0.1 and yield_spread < 0:
                    regime = "RECESSIONARY"
                elif cpi_change <= 0.3 and yield_spread > 0:
                    regime = "DOVISH"
                else:
                    regime = "TRANSITIONAL"
        except Exception:
            pass

        return {
            "snapshot": snap,
            "regime": regime,
            "narrative": fc.get_narrative(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Macro snapshot failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Macro snapshot failed: {e}")


@router.get("/enrichment/budget")
async def enrichment_budget():
    """Tavily daily budget status."""
    try:
        from live_monitoring.enrichment.apis.tavily_client import TavilySearchClient
        remaining = TavilySearchClient.get_budget_remaining()
        return {
            "tavily_remaining": remaining,
            "tavily_limit": 30,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {
            "tavily_remaining": -1,
            "tavily_limit": 30,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
