"""
📊 Economic Calendar API Endpoints

Exposes TE Calendar, FedWatch, Release Detector, and macro data
for the frontend exploitation widgets.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)
router = APIRouter()

# Lazy-init modules
_te_scraper = None
_fedwatch = None
_release_detector = None
_fed_predictor = None


def _get_te_scraper():
    global _te_scraper
    if _te_scraper is None:
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
        _te_scraper = TECalendarScraper(cache_ttl=300)
    return _te_scraper


def _get_fedwatch():
    global _fedwatch
    if _fedwatch is None:
        from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
        _fedwatch = FedWatchEngine()
    return _fedwatch


def _get_release_detector():
    global _release_detector
    if _release_detector is None:
        from live_monitoring.enrichment.apis.release_detector import ReleaseDetector
        _release_detector = ReleaseDetector()
    return _release_detector


def _get_fed_predictor():
    global _fed_predictor
    if _fed_predictor is None:
        from live_monitoring.agents.economic.fed_shift_predictor import FedShiftPredictor
        _fed_predictor = FedShiftPredictor()
    return _fed_predictor


# ── Calendar ──

@router.get("/economic/calendar")
async def get_economic_calendar(
    filter: Optional[str] = Query(None, description="Filter: 'critical', 'high', 'upcoming', 'today'"),
):
    """
    Full US economic calendar from Trading Economics.
    287 events with actual/previous/consensus/forecast/importance.
    """
    try:
        scraper = _get_te_scraper()

        if filter == "critical":
            events = scraper.get_upcoming_critical()
        elif filter == "high":
            events = scraper.get_high_impact()
        elif filter == "upcoming":
            events = scraper.get_upcoming()
        elif filter == "today":
            events = scraper.get_today()
        else:
            events = scraper.get_us_calendar()

        return {
            "events": [e.to_dict() for e in events],
            "count": len(events),
            "filter": filter or "all",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Calendar fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calendar failed: {e}")


# ── Fed Watch ──

@router.get("/economic/fedwatch")
async def get_fedwatch():
    """
    Real-time Fed Watch rate path from yfinance ZQ futures.
    Returns FOMC meeting-by-meeting probabilities.
    """
    try:
        engine = _get_fedwatch()
        result = engine.get_probabilities()

        if not result:
            return {"error": "FedWatch data unavailable", "source": "yfinance_zq"}

        return {
            "data": result,
            "source": "yfinance_zq_futures",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"FedWatch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"FedWatch failed: {e}")


# ── Release Detector ──

@router.get("/economic/releases")
async def get_releases():
    """
    Check for newly-released economic data.
    Returns surprise alerts with signal classification.
    """
    try:
        detector = _get_release_detector()
        new_alerts = detector.check_for_releases()
        all_alerts = detector.get_all_alerts()

        return {
            "new_alerts": [a.to_dict() for a in new_alerts],
            "all_alerts": [a.to_dict() for a in all_alerts],
            "new_count": len(new_alerts),
            "total_count": len(all_alerts),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Release check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Release check failed: {e}")


# ── Upcoming Critical (for signal veto display) ──

@router.get("/economic/upcoming-critical")
async def get_upcoming_critical():
    """
    Upcoming CRITICAL events that the signal veto monitors.
    Shows what the system will block/dampen signals for.
    """
    try:
        detector = _get_release_detector()
        upcoming = detector.get_upcoming_critical_from_te()

        return {
            "upcoming": upcoming,
            "count": len(upcoming),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Upcoming critical failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed: {e}")


# ── Exploit Brief (composite) ──

@router.get("/economic/exploit-brief")
async def get_exploit_brief(
    event: str = Query("CPI", description="Event to get exploit brief for"),
):
    """
    Composite exploitation briefing for a specific event.
    Combines calendar, FedWatch, FRED, and scenario analysis.
    """
    try:
        scraper = _get_te_scraper()
        predictor = _get_fed_predictor()

        # Find the target event in calendar
        all_events = scraper.get_us_calendar()
        target_events = [e for e in all_events if event.upper() in e.event.upper()]

        # Get FedWatch data
        fedwatch = None
        try:
            engine = _get_fedwatch()
            fedwatch = engine.get_probabilities()
        except Exception:
            pass

        # Build scenarios
        from live_monitoring.enrichment.apis.release_detector import _classify_category
        category = _classify_category(event)
        scenarios = predictor.get_scenario_shifts(category)

        return {
            "event": event,
            "calendar_matches": [e.to_dict() for e in target_events],
            "fedwatch": fedwatch,
            "scenarios": scenarios,
            "category": category,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Exploit brief failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Exploit brief failed: {e}")
