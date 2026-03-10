"""
🎯 Release Detector — Thin Orchestrator

Polls TECalendarScraper for newly-released actuals,
delegates all intelligence to modular components:

  - release_config.py:  category profiles, thresholds, direction maps
  - surprise_engine.py: surprise computation, signal classification, confidence

This file is ONLY responsible for:
  1. Polling TE calendar
  2. Tracking seen/unseen actuals
  3. Delegating to SurpriseEngine
  4. Returning ReleaseAlert objects

No hardcoded thresholds, confidence values, or direction logic lives here.

Usage:
    detector = ReleaseDetector()
    alerts = detector.check_for_releases()
    detector.run_polling_loop(interval_seconds=120, max_minutes=30)
"""

import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

logger = logging.getLogger(__name__)

# Re-export from config for backward compatibility
from live_monitoring.enrichment.apis.release_config import (
    ReleaseSignal, SurpriseClass, CATEGORY_MAP, CATEGORY_PROFILES,
    classify_category as _classify_category, get_profile,
)


@dataclass
class ReleaseAlert:
    """A detected economic release with computed surprise."""
    event_name: str
    date: str
    time: str
    actual: float
    consensus: float
    previous: float
    surprise: float
    surprise_pct: float
    surprise_class: SurpriseClass
    signal: ReleaseSignal
    fed_shift: float
    confidence: float
    importance: str
    category: str
    symbols: List[str]
    directions: Dict[str, str]
    detected_at: str
    # New fields from modular engine
    pct_method: str = ''
    debug: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            'event': self.event_name,
            'date': self.date,
            'time': self.time,
            'actual': self.actual,
            'consensus': self.consensus,
            'previous': self.previous,
            'surprise': self.surprise,
            'surprise_pct': self.surprise_pct,
            'surprise_class': self.surprise_class.value,
            'signal': self.signal.value,
            'fed_shift': self.fed_shift,
            'confidence': self.confidence,
            'importance': self.importance,
            'category': self.category,
            'symbols': self.symbols,
            'directions': self.directions,
            'detected_at': self.detected_at,
            'pct_method': self.pct_method,
        }


def _parse_value(text: str) -> Optional[float]:
    """Parse a TE value string like '326.7', '0.4%', '-$70.3B', '1.35M'."""
    if not text or text.strip() in ('', '—', '-'):
        return None
    clean = text.strip().replace(',', '').replace('$', '').replace('%', '')
    
    multiplier = 1.0
    if clean.endswith('K'):
        multiplier = 1e3
        clean = clean[:-1]
    elif clean.endswith('M'):
        multiplier = 1e6
        clean = clean[:-1]
    elif clean.endswith('B'):
        multiplier = 1e9
        clean = clean[:-1]
    elif clean.endswith('T'):
        multiplier = 1e12
        clean = clean[:-1]
    
    try:
        return float(clean) * multiplier
    except (ValueError, TypeError):
        return None


# Legacy compatibility — keep SIGNAL_DIRECTIONS for external callers
SIGNAL_DIRECTIONS = {
    ReleaseSignal.HAWKISH: {'SPY': '↓', 'TLT': '↓', 'DXY': '↑'},
    ReleaseSignal.HAWKISH_MILD: {'SPY': '↓', 'TLT': '↓'},
    ReleaseSignal.NEUTRAL: {},
    ReleaseSignal.DOVISH_MILD: {'SPY': '↑', 'TLT': '↑'},
    ReleaseSignal.DOVISH: {'SPY': '↑', 'TLT': '↑', 'DXY': '↓'},
}


class ReleaseDetector:
    """
    Thin orchestrator. Detects new releases and delegates to SurpriseEngine.
    
    Workflow:
    1. Scrape TE calendar for events with actual AND consensus
    2. Skip already-detected actuals
    3. Delegate surprise computation to SurpriseEngine
    4. Return ReleaseAlert objects
    """
    
    def __init__(self):
        """Initialize with TE scraper and SurpriseEngine."""
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
        from live_monitoring.enrichment.apis.surprise_engine import SurpriseEngine
        
        self.scraper = TECalendarScraper(cache_ttl=120)
        self.engine = SurpriseEngine()
        self.predictor = self.engine.predictor  # backward compat
        self._seen_actuals: Dict[str, float] = {}
        self._alerts: List[ReleaseAlert] = []
        
        logger.info("🎯 ReleaseDetector initialized (modular: config + engine)")
    
    def check_for_releases(self) -> List[ReleaseAlert]:
        """
        Check for new releases. Returns list of NEW alerts only.
        Delegates ALL intelligence to SurpriseEngine.
        """
        new_alerts = []
        
        try:
            events = self.scraper.get_us_calendar()
        except Exception as e:
            logger.error(f"❌ TE scraper failed: {e}")
            return []
        
        for event in events:
            if not event.has_actual or not event.has_consensus:
                continue
            
            event_key = f"{event.date}_{event.event}"
            actual_val = _parse_value(event.actual)
            if actual_val is None:
                continue
            
            if event_key in self._seen_actuals:
                continue
            
            self._seen_actuals[event_key] = actual_val
            
            consensus_val = _parse_value(event.consensus)
            previous_val = _parse_value(event.previous)
            if consensus_val is None:
                continue
            
            # ── Delegate to SurpriseEngine ──
            result = self.engine.compute(
                event_name=event.event,
                actual=actual_val,
                consensus=consensus_val,
                previous=previous_val,
                importance=event.importance,
            )
            
            alert = ReleaseAlert(
                event_name=event.event,
                date=event.date or '',
                time=event.time or '',
                actual=actual_val,
                consensus=consensus_val,
                previous=previous_val or 0.0,
                surprise=result.surprise,
                surprise_pct=result.surprise_pct,
                surprise_class=result.surprise_class,
                signal=result.signal,
                fed_shift=result.fed_shift,
                confidence=result.confidence,
                importance=event.importance,
                category=result.category,
                symbols=result.symbols,
                directions=result.directions,
                detected_at=datetime.now(timezone.utc).isoformat(),
                pct_method=result.pct_method,
                debug=result.debug,
            )
            
            new_alerts.append(alert)
            self._alerts.append(alert)
        
        return new_alerts
    
    def _classify_signal(self, category: str, surprise_pct: float, importance: str) -> tuple:
        """
        Legacy compatibility wrapper. Delegates to SurpriseEngine.
        
        Old callers (backtest scripts, signal_generator) call this directly.
        Now routes through the modular engine with proper per-category thresholds.
        """
        profile = get_profile(category)  # will use category as event_name — close enough
        
        from live_monitoring.enrichment.apis.surprise_engine import SurpriseEngine
        engine = SurpriseEngine()
        
        signal = engine._classify_signal(surprise_pct, profile)
        confidence = engine._compute_confidence(surprise_pct, importance, profile)
        
        return signal, confidence
    
    def get_all_alerts(self) -> List[ReleaseAlert]:
        """Get all alerts generated since initialization."""
        return self._alerts
    
    def get_latest_for_event(self, event_keyword: str) -> Optional[ReleaseAlert]:
        """Get the latest alert matching a keyword (e.g., 'CPI')."""
        for alert in reversed(self._alerts):
            if event_keyword.upper() in alert.event_name.upper():
                return alert
        return None
    
    def run_polling_loop(
        self,
        interval_seconds: int = 120,
        max_minutes: int = 30,
        target_event: Optional[str] = None,
    ) -> List[ReleaseAlert]:
        """
        Poll TE calendar at regular intervals for new releases.
        """
        logger.info(
            f"🎯 Starting polling loop — every {interval_seconds}s for up to {max_minutes}min"
            + (f" — watching for '{target_event}'" if target_event else "")
        )
        
        all_new = []
        start = time.time()
        max_secs = max_minutes * 60
        poll_count = 0
        
        while time.time() - start < max_secs:
            poll_count += 1
            elapsed = (time.time() - start) / 60
            logger.info(f"📡 Poll #{poll_count} ({elapsed:.1f}min elapsed)")
            
            new_alerts = self.check_for_releases()
            all_new.extend(new_alerts)
            
            if target_event and new_alerts:
                found = any(target_event.upper() in a.event_name.upper() for a in new_alerts)
                if found:
                    logger.info(f"🎯 Target event '{target_event}' detected! Stopping poll.")
                    break
            
            time.sleep(interval_seconds)
        
        logger.info(f"🏁 Polling complete. {len(all_new)} new alerts across {poll_count} polls.")
        return all_new
    
    def get_upcoming_critical_from_te(self) -> List[dict]:
        """
        Get upcoming CRITICAL + HIGH events with times converted to ET.
        """
        try:
            from live_monitoring.utils.tz_mapper import te_display_time
            has_tz = True
        except ImportError:
            has_tz = False
        
        upcoming = [e for e in self.scraper.get_high_impact() if not e.has_actual]
        results = []
        for e in upcoming:
            time_str = e.time
            if has_tz:
                time_str = te_display_time(e.date, e.time)
            results.append({
                'event': e.event,
                'date': e.date,
                'time': time_str,
                'time_gmt': e.time,
                'consensus': e.consensus,
                'importance': e.importance,
                'time_zone': 'ET',
            })
        return results


# ── Module test ──
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-7s | %(message)s'
    )
    
    detector = ReleaseDetector()
    
    print("\n═══ Release Detector — Modular Engine Test ═══\n")
    
    alerts = detector.check_for_releases()
    print(f"\nDetected {len(alerts)} releases:\n")
    
    for a in alerts:
        print(f"  {a.event_name}")
        print(f"    A={a.actual} C={a.consensus}")
        print(f"    Surprise={a.surprise:+.4f} ({a.surprise_pct:+.2f}%) [{a.pct_method}]")
        print(f"    Signal={a.signal.value} Conf={a.confidence:.2f}")
        print(f"    FedShift={a.fed_shift:+.3f}")
        print(f"    {a.directions}")
        print()
    
    print("\n═══ Upcoming Events ═══\n")
    for u in detector.get_upcoming_critical_from_te()[:10]:
        print(f"  {u['date']} | {u['event']:40s} | {u['time']}")
