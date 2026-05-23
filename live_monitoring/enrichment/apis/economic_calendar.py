"""
Hardcoded high-impact economic events (baseline). Avoids missing-module import failures.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EVENTS: List[Dict[str, Any]] = [
    {
        "date": "2026-04-06T20:00:00",
        "name": "Trump Energy Pause Expires",
        "type": "BINARY_POLICY",
        "impact": "HIGH",
        "symbol_impact": {"SPY": "BEARISH", "XLE": "BEARISH", "USO": "BULLISH"},
        "probability_bearish": 0.65,
        "notes": "Drilling pause on federal lands expires. Execution uncertainty high.",
    },
    {
        "date": "2026-04-10T08:30:00",
        "name": "CPI March 2026",
        "type": "INFLATION_DATA",
        "impact": "CRITICAL",
        "symbol_impact": {"SPY": "UNKNOWN", "TLT": "INVERSE"},
        "consensus": 3.1,
        "hot_threshold": 3.4,
        "notes": "Hot print (>3.4%) → STAGFLATION signal. Cool print (<2.8%) → rally fuel.",
    },
    {
        "date": "2026-04-17T08:30:00",
        "name": "Retail Sales March 2026",
        "type": "ECONOMIC_DATA",
        "impact": "MEDIUM",
        "symbol_impact": {"SPY": "BULLISH_IF_BEAT"},
    },
    {
        "date": "2026-04-30T14:00:00",
        "name": "FOMC Rate Decision",
        "type": "FED_DECISION",
        "impact": "CRITICAL",
        "symbol_impact": {"SPY": "UNKNOWN"},
        "notes": "Hold expected. Any cut = risk-on. Any hike = selloff.",
    },
]


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class EconomicCalendar:
    """April 2026 baseline calendar + helpers for brief/gates."""

    EVENTS = EVENTS

    def get_week_events(self, reference_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        ref = reference_date or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        end = ref + timedelta(days=7)
        out: List[Dict[str, Any]] = []
        for ev in self.EVENTS:
            try:
                ed = _parse_dt(str(ev["date"]))
            except (ValueError, KeyError):
                continue
            if ref <= ed <= end:
                out.append(dict(ev))
        out.sort(key=lambda x: _parse_dt(str(x["date"])))
        return out

    def get_all_upcoming(self, reference_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        ref = reference_date or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        out: List[Dict[str, Any]] = []
        for ev in self.EVENTS:
            try:
                ed = _parse_dt(str(ev["date"]))
            except (ValueError, KeyError):
                continue
            if ed >= ref:
                e2 = dict(ev)
                e2["_parsed_at"] = ed.isoformat()
                out.append(e2)
        out.sort(key=lambda x: _parse_dt(str(x["date"])))
        return out

    def get_next_binary(self, reference_date: Optional[datetime] = None) -> Dict[str, Any]:
        ref = reference_date or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        candidates: List[Dict[str, Any]] = []
        for ev in self.EVENTS:
            imp = str(ev.get("impact") or "").upper()
            if imp not in ("HIGH", "CRITICAL"):
                continue
            try:
                ed = _parse_dt(str(ev["date"]))
            except (ValueError, KeyError):
                continue
            if ed < ref:
                continue
            hours_until = (ed - ref).total_seconds() / 3600.0
            row = dict(ev)
            row["hours_until"] = round(hours_until, 2)
            row["event_at_utc"] = ed.isoformat()
            candidates.append(row)
        candidates.sort(key=lambda x: x["hours_until"])
        if not candidates:
            return {"name": None, "impact": None, "hours_until": None, "date": None}
        return candidates[0]

    def get_risk_flag(self, reference_date: Optional[datetime] = None) -> Dict[str, Any]:
        ref = reference_date or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        nb = self.get_next_binary(ref)
        hours = nb.get("hours_until")
        name = nb.get("name")
        has_binary = bool(hours is not None and hours <= 48)
        risk_action = "CLEAR"
        if has_binary:
            risk_action = "REDUCE_SIZE"
        elif hours is not None and hours <= 168:
            risk_action = "WATCH"
        return {
            "has_binary_within_48h": has_binary,
            "event_name": name,
            "hours_until": hours,
            "risk_action": risk_action,
        }
