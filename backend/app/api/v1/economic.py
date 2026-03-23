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
_threshold_engine = None
_nowcast_client = None
_macro_regime = None


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


def _get_threshold_engine():
    global _threshold_engine
    if _threshold_engine is None:
        from live_monitoring.enrichment.apis.dynamic_threshold_engine import DynamicThresholdEngine
        _threshold_engine = DynamicThresholdEngine()
    return _threshold_engine


def _get_nowcast_client():
    global _nowcast_client
    if _nowcast_client is None:
        from live_monitoring.enrichment.apis.cleveland_fed_nowcast import ClevelandFedNowcast
        _nowcast_client = ClevelandFedNowcast()
    return _nowcast_client


def _get_macro_regime():
    global _macro_regime
    if _macro_regime is None:
        from live_monitoring.agents.economic.macro_regime_detector import MacroRegimeDetector
        _macro_regime = MacroRegimeDetector()
    return _macro_regime


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

        if not result or (isinstance(result, dict) and 'error' in result):
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


# ── Macro Regime ──

@router.get("/economic/macro-regime")
async def get_macro_regime():
    """
    Current macroeconomic regime classification.
    Returns: STAGFLATION, GOLDILOCKS, INFLATIONARY_BOOM, etc.
    """
    try:
        detector = _get_macro_regime()
        regime = detector.get_regime()
        return {
            "regime": regime,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Macro regime failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Macro regime failed: {e}")


# ── Nowcast ──

@router.get("/economic/nowcast")
async def get_nowcast():
    """
    Cleveland Fed Inflation Nowcast — real-time CPI/PCE estimates.
    Updated daily by the Fed's model. Pre-release intelligence.
    """
    try:
        client = _get_nowcast_client()
        data = client.to_dict()
        return {
            "nowcast": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Nowcast failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Nowcast failed: {e}")


# ── Exploit Brief (composite) ──

@router.get("/economic/exploit-brief")
async def get_exploit_brief(
    event: str = Query("CPI", description="Event to get exploit brief for"),
):
    """
    Composite exploitation briefing for a specific event.
    Four data layers:
      1. TE Calendar — consensus, previous, forecast
      2. FedWatch — rate path, regime classification
      3. Dynamic Thresholds — FRED std_dev calibrated bands
      4. Cleveland Fed Nowcast — pre-signal divergence (inflation only)
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

        # Build category + base scenarios
        from live_monitoring.enrichment.apis.release_detector import _classify_category
        category = _classify_category(event)
        scenarios = predictor.get_scenario_shifts(category)

        # ── Layer 3: Dynamic Thresholds (FRED std_dev calibrated) ──
        thresholds_data = {}
        try:
            dte = _get_threshold_engine()
            # Extract consensus from first matching event
            consensus_val = None
            if target_events:
                raw_cons = target_events[0].consensus
                if raw_cons:
                    cleaned = raw_cons.strip('%').replace(',', '').replace('K', '').replace('M', '').replace('B', '')
                    try:
                        consensus_val = float(cleaned)
                    except ValueError:
                        pass
            dt = dte.get_dynamic_thresholds(event, te_consensus=consensus_val)
            if dt:
                thresholds_data = {
                    "consensus": dt.consensus,
                    "std_dev": dt.std_dev,
                    "HOT": dt.thresholds.get("HOT"),
                    "WARM": dt.thresholds.get("WARM"),
                    "IN_LINE": dt.thresholds.get("IN_LINE"),
                    "COOL": dt.thresholds.get("COOL"),
                    "COLD": dt.thresholds.get("COLD"),
                    "fred_latest": dt.fred_latest,
                    "fred_date": dt.fred_date,
                    "category": dt.category,
                }
        except Exception as exc:
            logger.warning(f"Dynamic thresholds failed for {event}: {exc}")
            thresholds_data = {"error": str(exc)}

        # ── Layer 4: Cleveland Fed Nowcast (inflation events only) ──
        nowcast_data = {}
        try:
            cn = _get_nowcast_client()
            nowcast = cn.get_nowcast()
            if nowcast and category == "INFLATION":
                # Map event to nowcast metric
                event_lower = event.lower()
                if "core cpi" in event_lower:
                    metric, now_val = "core_cpi_mom", nowcast.core_cpi_mom
                elif "cpi" in event_lower or "inflation" in event_lower:
                    metric, now_val = "cpi_mom", nowcast.cpi_mom
                elif "core pce" in event_lower:
                    metric, now_val = "core_pce_mom", nowcast.core_pce_mom
                elif "pce" in event_lower:
                    metric, now_val = "pce_mom", nowcast.pce_mom
                else:
                    metric, now_val = None, None

                if now_val is not None:
                    consensus_mom = thresholds_data.get("consensus") or 0
                    divergence = now_val - consensus_mom if consensus_mom else 0
                    nowcast_data = {
                        "metric": metric,
                        "cpi_nowcast_mom": nowcast.cpi_mom,
                        "core_cpi_nowcast_mom": nowcast.core_cpi_mom,
                        "pce_nowcast_mom": nowcast.pce_mom,
                        "core_pce_nowcast_mom": nowcast.core_pce_mom,
                        "vs_consensus": round(divergence, 3) if consensus_mom else None,
                        "pre_signal": (
                            "PRE_HOT" if divergence > 0.1
                            else "PRE_COLD" if divergence < -0.1
                            else "NEUTRAL"
                        ) if consensus_mom else "NO_CONSENSUS",
                        "edge": (
                            f"Cleveland nowcast {now_val}% vs consensus "
                            f"{consensus_mom}% → {'+' if divergence > 0 else ''}"
                            f"{round(divergence, 2)}%"
                        ) if consensus_mom else None,
                        "updated": nowcast.updated,
                    }
        except Exception as exc:
            logger.warning(f"Nowcast failed for {event}: {exc}")
            nowcast_data = {"error": str(exc)}

        # ── Regime-aware shifts ──
        regime_shifts = {}
        try:
            dte = _get_threshold_engine()
            regime_shifts = dte.get_regime_adjusted_shifts(category)
        except Exception as exc:
            logger.warning(f"Regime shifts failed: {exc}")

        # ── Macro regime ──
        macro_regime = {}
        try:
            mr = _get_macro_regime()
            macro_regime = mr.get_regime()
        except Exception as exc:
            logger.warning(f"Macro regime failed: {exc}")

        return {
            "event": event,
            "category": category,
            "calendar_matches": [e.to_dict() for e in target_events],
            "fedwatch": fedwatch,
            "scenarios": scenarios,
            "thresholds": thresholds_data,
            "nowcast": nowcast_data,
            "regime_shifts": regime_shifts,
            "macro_regime": macro_regime,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Exploit brief failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Exploit brief failed: {e}")
