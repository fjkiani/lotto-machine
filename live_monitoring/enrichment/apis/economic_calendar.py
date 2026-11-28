"""
Economic calendar helpers for brief / gates.

Live source: TECalendarScraper (TE indicator SSR tables + ForexFactory week JSON).
No hardcoded April/March event lists as source of truth.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _impact_rank(imp: str) -> int:
    return {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(str(imp or "").upper(), 9)


class EconomicCalendar:
    """Live calendar facade used by brief fetchers and risk helpers."""

    def __init__(self, scraper=None):
        self._scraper = scraper
        self._last_error: Optional[str] = None
        self._degraded = False
        self._sources: List[str] = []

    def _get_scraper(self):
        if self._scraper is None:
            from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper

            self._scraper = TECalendarScraper(cache_ttl=900)
        return self._scraper

    def _load_events(self) -> List[Any]:
        try:
            scraper = self._get_scraper()
            events = scraper.get_us_calendar()
            self._sources = list(getattr(scraper, "last_sources", []) or [])
            self._last_error = getattr(scraper, "last_error", None)
            self._degraded = not bool(events)
            if self._degraded and not self._last_error:
                self._last_error = "live calendar returned zero events"
            return events
        except Exception as e:
            self._degraded = True
            self._last_error = str(e)
            logger.warning("EconomicCalendar live load failed: %s", e)
            return []

    def build_brief_payload(self) -> Dict[str, Any]:
        """Single scrape → next_binary + risk_flag + week_events (brief-friendly)."""
        # Force one load so status/sources reflect the same scrape as week_events
        _ = self._load_events()
        return {
            "next_binary": self.get_next_binary(),
            "risk_flag": self.get_risk_flag(),
            "week_events": self.get_week_events(),
            "status": self.status(),
        }

    def _te_to_row(self, ev: Any, ref: datetime) -> Optional[Dict[str, Any]]:
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper

        dt = TECalendarScraper._parse_event_datetime(ev)
        if dt is None:
            return None
        ed = _to_utc(dt)
        hours_until = (ed - ref).total_seconds() / 3600.0
        impact = str(getattr(ev, "importance", "") or "MEDIUM").upper()
        return {
            "date": ed.isoformat(),
            "name": getattr(ev, "event", None),
            "type": "ECONOMIC_DATA",
            "impact": impact,
            "consensus": getattr(ev, "consensus", None) or None,
            "forecast": getattr(ev, "forecast", None) or None,
            "previous": getattr(ev, "previous", None) or None,
            "actual": getattr(ev, "actual", None) or None,
            "hours_until": round(hours_until, 2),
            "event_at_utc": ed.isoformat(),
            "source": getattr(ev, "source", "te"),
            "_parsed_at": ed.isoformat(),
        }

    def status(self) -> Dict[str, Any]:
        scraper = self._scraper
        out: Dict[str, Any] = {
            "degraded": self._degraded,
            "error": self._last_error,
            "sources": self._sources,
        }
        if scraper is not None:
            out["te_main_status"] = getattr(scraper, "te_main_status", None)
            out["source_notes"] = getattr(scraper, "source_notes", {}) or {}
        return out

    def get_week_events(self, reference_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        ref = _to_utc(reference_date or datetime.now(timezone.utc))
        end = ref + timedelta(days=7)
        out: List[Dict[str, Any]] = []
        for ev in self._load_events():
            row = self._te_to_row(ev, ref)
            if not row:
                continue
            ed = datetime.fromisoformat(row["date"])
            if ref <= ed <= end:
                out.append(row)
        out.sort(key=lambda x: x["date"])
        return out

    def get_all_upcoming(self, reference_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        ref = _to_utc(reference_date or datetime.now(timezone.utc))
        out: List[Dict[str, Any]] = []
        for ev in self._load_events():
            row = self._te_to_row(ev, ref)
            if not row:
                continue
            if row["hours_until"] >= 0:
                out.append(row)
        out.sort(key=lambda x: x["date"])
        return out

    def get_next_binary(self, reference_date: Optional[datetime] = None) -> Dict[str, Any]:
        ref = _to_utc(reference_date or datetime.now(timezone.utc))
        candidates: List[Dict[str, Any]] = []
        for ev in self._load_events():
            impact = str(getattr(ev, "importance", "") or "").upper()
            if impact not in ("HIGH", "CRITICAL"):
                continue
            if getattr(ev, "has_actual", False):
                continue
            row = self._te_to_row(ev, ref)
            if not row or row["hours_until"] < 0:
                continue
            candidates.append(row)
        candidates.sort(key=lambda x: (_impact_rank(x["impact"]), x["hours_until"]))
        if not candidates:
            empty = {
                "name": None,
                "impact": None,
                "hours_until": None,
                "date": None,
            }
            if self._degraded:
                empty["degraded"] = True
                empty["error"] = self._last_error
            return empty
        return candidates[0]

    def get_risk_flag(self, reference_date: Optional[datetime] = None) -> Dict[str, Any]:
        ref = _to_utc(reference_date or datetime.now(timezone.utc))
        nb = self.get_next_binary(ref)
        hours = nb.get("hours_until")
        name = nb.get("name")
        has_binary = bool(hours is not None and hours <= 48)
        risk_action = "CLEAR"
        if has_binary:
            risk_action = "REDUCE_SIZE"
        elif hours is not None and hours <= 168:
            risk_action = "WATCH"
        out = {
            "has_binary_within_48h": has_binary,
            "event_name": name,
            "hours_until": hours,
            "risk_action": risk_action,
        }
        if self._degraded:
            out["degraded"] = True
            out["error"] = self._last_error
        return out
