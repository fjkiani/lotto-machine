"""
📅 Economic Calendar API Endpoints

Exposes the EconCalendar engine to the frontend.
Uses FRED Releases API (unlimited, free).
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

# Lazy-init (same pattern as killchain.py)
_cal = None


def _get_cal():
    global _cal
    if _cal is None:
        try:
            from live_monitoring.enrichment.apis.econ_calendar import EconCalendar
            _cal = EconCalendar()
            logger.info("📅 EconCalendar initialized")
        except Exception as e:
            logger.error(f"Failed to initialize EconCalendar: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"EconCalendar unavailable: {e}")
    return _cal


@router.get("/calendar/upcoming")
async def calendar_upcoming(
    days: int = Query(7, ge=1, le=30, description="Days ahead to look"),
    high_impact_only: bool = Query(False, description="Only CRITICAL + HIGH releases"),
):
    """
    Get upcoming economic releases.

    Returns up to 200 releases per week from FRED.
    Each release includes: date, time, importance, category, hours_until countdown.

    NOTE: `forecast` is always null — FRED does not provide consensus forecasts.
    Surprise scoring uses actual vs previous (not actual vs forecast).
    """
    cal = _get_cal()
    try:
        raw = cal.get_high_impact(days) if high_impact_only else cal.get_upcoming(days)
        # Filter out past releases (hours_until < 0) — LIABILITY fix
        releases = [r for r in raw if r.hours_until > 0]
        return {
            "count": len(releases),
            "timestamp": datetime.utcnow().isoformat(),
            "forecast_available": False,
            "releases": [
                {
                    "date": r.date,
                    "time": r.time,
                    "name": r.name,
                    "short_name": r.short_name,
                    "importance": r.importance.value,
                    "category": r.category.value,
                    "hours_until": r.hours_until,
                    "actual": r.actual,
                    "forecast": r.forecast,
                    "previous": r.previous,
                    "surprise": r.surprise,
                }
                for r in releases
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Calendar fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calendar failed: {e}")


@router.get("/calendar/next-mover")
async def calendar_next_mover():
    """
    Get the single next market-moving release (CRITICAL or HIGH importance).
    Use this for the countdown badge in KillChainDashboard header.
    """
    cal = _get_cal()
    try:
        mm = cal.get_next_market_mover()
        if not mm:
            return {"next_mover": None}
        return {
            "next_mover": {
                "short_name": mm.short_name,
                "date": mm.date,
                "time": mm.time,
                "importance": mm.importance.value,
                "category": mm.category.value,
                "hours_until": mm.hours_until,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Next mover failed: {e}")


@router.get("/calendar/surprises")
async def calendar_surprises():
    """
    Get latest surprise scores for major releases.

    WARNING: These are actual vs previous (change %), NOT actual vs consensus.
    A proper surprise score requires forecast data from FMP or Bloomberg.
    """
    cal = _get_cal()
    names = ["CPI", "GDP", "Employment", "JOLTS", "Retail Sales", "PCE", "PPI", "ISM Mfg"]
    results = {}
    for name in names:
        try:
            s = cal.check_release(name)
            if s:
                results[name] = {
                    "actual": s.actual,
                    "previous": s.previous,
                    "surprise": s.surprise,
                    "date": s.date,
                    "category": s.category.value,
                    "is_true_surprise": False,
                }
        except Exception:
            pass
    return {"surprises": results, "note": "surprise = (actual - previous) / |previous|, NOT actual vs forecast"}


@router.get("/calendar/narrative")
async def calendar_narrative(days: int = Query(3, ge=1, le=14)):
    """Pre-market briefing text for NarrativeBrain widget."""
    cal = _get_cal()
    return {
        "narrative": cal.get_narrative(days),
        "timestamp": datetime.utcnow().isoformat(),
    }
