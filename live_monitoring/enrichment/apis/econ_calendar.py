"""
Economic Calendar — Multi-Source Release Tracker

Captures EVERY economic release using:
  1. FRED Releases API (primary — unlimited, free, structured)
  2. Hardcoded high-impact US schedule (for time-of-day + importance tagging)
  3. FRED Series data (for actual/forecast/previous surprise scoring)

Replaces: trading_economics.py (100 calls/mo free tier, currently dead)

Usage:
    cal = EconCalendar()
    upcoming = cal.get_upcoming(days=7)        # All releases next 7 days
    high_impact = cal.get_high_impact(days=3)   # Market-movers only
    surprise = cal.check_release("CPI")         # Latest CPI surprise score
    narrative = cal.get_narrative()              # Pre-market briefing text
"""

import os
import logging
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

class Importance(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"  # Market moves 0.5%+ on this


class Category(Enum):
    INFLATION = "INFLATION"
    EMPLOYMENT = "EMPLOYMENT"
    GROWTH = "GROWTH"
    FED_POLICY = "FED_POLICY"
    CONSUMER = "CONSUMER"
    MANUFACTURING = "MANUFACTURING"
    HOUSING = "HOUSING"
    TRADE = "TRADE"
    RATES = "RATES"
    OTHER = "OTHER"


@dataclass
class EconRelease:
    """A single economic data release."""
    date: str                          # YYYY-MM-DD
    name: str                          # "Consumer Price Index"
    short_name: str = ""               # "CPI"
    time: str = "08:30"                # ET release time
    importance: Importance = Importance.MEDIUM
    category: Category = Category.OTHER
    release_id: int = 0                # FRED release ID
    fred_series: str = ""              # FRED series for actual data (e.g. CPIAUCSL)
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    surprise: Optional[float] = None   # (actual - forecast) / |previous|
    source: str = "FRED"
    hours_until: float = -1

    def is_upcoming(self) -> bool:
        return self.hours_until > 0

    def is_market_mover(self) -> bool:
        return self.importance in (Importance.HIGH, Importance.CRITICAL)


# ─── High-Impact US Release Schedule ─────────────────────────────────────────
# FRED Releases API gives dates but NOT times or importance.
# We tag the known market-movers manually.

HIGH_IMPACT_RELEASES = {
    10:  {"short": "CPI",           "time": "08:30", "imp": Importance.CRITICAL, "cat": Category.INFLATION,     "series": "CPIAUCSL"},
    11:  {"short": "Core CPI",      "time": "08:30", "imp": Importance.CRITICAL, "cat": Category.INFLATION,     "series": "CPILFESL"},
    46:  {"short": "PPI",           "time": "08:30", "imp": Importance.HIGH,     "cat": Category.INFLATION,     "series": "PPIACO"},
    53:  {"short": "GDP",           "time": "08:30", "imp": Importance.CRITICAL, "cat": Category.GROWTH,        "series": "GDP"},
    50:  {"short": "Employment",    "time": "08:30", "imp": Importance.CRITICAL, "cat": Category.EMPLOYMENT,    "series": "PAYEMS"},
    101: {"short": "FOMC",          "time": "14:00", "imp": Importance.CRITICAL, "cat": Category.FED_POLICY,    "series": "FEDFUNDS"},
    21:  {"short": "H.6 Money",     "time": "16:15", "imp": Importance.MEDIUM,   "cat": Category.FED_POLICY,    "series": ""},
    18:  {"short": "Interest Rates","time": "15:15", "imp": Importance.HIGH,     "cat": Category.RATES,         "series": "DGS10"},
    35:  {"short": "Retail Sales",  "time": "08:30", "imp": Importance.HIGH,     "cat": Category.CONSUMER,      "series": "RSAFS"},
    83:  {"short": "PCE",           "time": "08:30", "imp": Importance.CRITICAL, "cat": Category.INFLATION,     "series": "PCEPI"},
    192: {"short": "JOLTS",         "time": "10:00", "imp": Importance.HIGH,     "cat": Category.EMPLOYMENT,    "series": "JTSJOL"},
    14:  {"short": "Industrial Prod","time":"09:15",  "imp": Importance.MEDIUM,   "cat": Category.MANUFACTURING, "series": "INDPRO"},
    13:  {"short": "Housing Starts","time": "08:30", "imp": Importance.MEDIUM,   "cat": Category.HOUSING,       "series": "HOUST"},
    205: {"short": "ISM Mfg",       "time": "10:00", "imp": Importance.HIGH,     "cat": Category.MANUFACTURING, "series": "MANEMP"},
    240: {"short": "Consumer Sent", "time": "10:00", "imp": Importance.HIGH,     "cat": Category.CONSUMER,      "series": "UMCSENT"},
    378: {"short": "Fed Funds",     "time": "09:00", "imp": Importance.HIGH,     "cat": Category.RATES,         "series": "DFF"},
    22:  {"short": "Bank Assets",   "time": "16:15", "imp": Importance.LOW,      "cat": Category.RATES,         "series": ""},
    200: {"short": "CBOE Stats",    "time": "16:30", "imp": Importance.MEDIUM,   "cat": Category.OTHER,         "series": "VIXCLS"},
    279: {"short": "EPU Index",     "time": "10:00", "imp": Importance.MEDIUM,   "cat": Category.OTHER,         "series": "USEPUINDXD"},
    209: {"short": "BofA Indices",  "time": "16:00", "imp": Importance.LOW,      "cat": Category.RATES,         "series": ""},
}


# ─── Economic Calendar Client ───────────────────────────────────────────────

class EconCalendar:
    """
    Multi-source economic calendar.

    Primary: FRED Releases API (unlimited, free)
    Enrichment: Hardcoded high-impact tagging for time/importance
    Data: FRED Series API for actual/previous values and surprise scoring
    """

    FRED_BASE = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 3600):
        self.api_key = api_key or os.getenv("FRED_API_KEY", "")
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl

        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — EconCalendar disabled")
        else:
            logger.info("📅 EconCalendar initialized (FRED Releases API — unlimited)")

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    # ── Core: Fetch upcoming releases from FRED ──────────────────────────

    def get_upcoming(self, days: int = 7, include_low: bool = True) -> List[EconRelease]:
        """
        Get all upcoming economic releases for the next N days.

        Args:
            days: How many days ahead to look
            include_low: Include LOW importance releases

        Returns:
            List of EconRelease, sorted by date
        """
        cache_key = f"upcoming_{days}_{include_low}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        today = date.today()
        end = today + timedelta(days=days)

        try:
            url = f"{self.FRED_BASE}/releases/dates"
            params = {
                "api_key": self.api_key,
                "file_type": "json",
                "include_release_dates_with_no_data": "true",
                "realtime_start": today.isoformat(),
                "realtime_end": end.isoformat(),
                "limit": 200,
            }
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()

            data = r.json()
            raw_releases = data.get("release_dates", [])

            releases = []
            for raw in raw_releases:
                rel_id = raw.get("release_id", 0)
                rel_name = raw.get("release_name", "Unknown")
                rel_date = raw.get("date", "")

                # Enrich with high-impact metadata if available
                meta = HIGH_IMPACT_RELEASES.get(rel_id, {})
                short_name = meta.get("short", rel_name[:30])
                release_time = meta.get("time", "")
                importance = meta.get("imp", Importance.LOW)
                category = meta.get("cat", Category.OTHER)
                series = meta.get("series", "")

                # Calculate hours until
                hours = -1
                try:
                    if release_time and rel_date:
                        rel_dt = datetime.strptime(f"{rel_date} {release_time}", "%Y-%m-%d %H:%M")
                        delta = rel_dt - datetime.now()
                        hours = delta.total_seconds() / 3600
                    elif rel_date:
                        rel_dt = datetime.strptime(f"{rel_date} 08:30", "%Y-%m-%d %H:%M")
                        delta = rel_dt - datetime.now()
                        hours = delta.total_seconds() / 3600
                except Exception:
                    pass

                release = EconRelease(
                    date=rel_date,
                    name=rel_name,
                    short_name=short_name,
                    time=release_time,
                    importance=importance,
                    category=category,
                    release_id=rel_id,
                    fred_series=series,
                    source="FRED",
                    hours_until=round(hours, 1) if hours > 0 else -1,
                )
                releases.append(release)

            # Filter
            if not include_low:
                releases = [r for r in releases if r.importance != Importance.LOW]

            # Deduplicate by (date, release_id) — FRED may return duplicates
            seen = set()
            unique = []
            for r in releases:
                key = (r.date, r.release_id)
                if key not in seen:
                    seen.add(key)
                    unique.append(r)
            releases = unique

            # Sort by date, then importance (CRITICAL first)
            imp_order = {Importance.CRITICAL: 0, Importance.HIGH: 1, Importance.MEDIUM: 2, Importance.LOW: 3}
            releases.sort(key=lambda r: (r.date, imp_order.get(r.importance, 4)))

            self._cache[cache_key] = releases
            self._cache_ts[cache_key] = time.time()
            logger.info(f"📅 Fetched {len(releases)} releases for next {days} days")
            return releases

        except Exception as e:
            logger.error(f"❌ FRED releases error: {e}")
            return self._cache.get(cache_key, [])

    def get_high_impact(self, days: int = 3) -> List[EconRelease]:
        """Get only HIGH and CRITICAL releases."""
        all_releases = self.get_upcoming(days=days, include_low=True)
        return [r for r in all_releases if r.is_market_mover()]

    def get_today(self) -> List[EconRelease]:
        """Get today's releases only."""
        all_releases = self.get_upcoming(days=1)
        today_str = date.today().isoformat()
        return [r for r in all_releases if r.date == today_str]

    def get_next_market_mover(self) -> Optional[EconRelease]:
        """Get the next upcoming market-moving release."""
        high = self.get_high_impact(days=14)
        upcoming = [r for r in high if r.hours_until > 0]
        return upcoming[0] if upcoming else None

    # ── Surprise Scoring ─────────────────────────────────────────────────

    def check_release(self, short_name: str) -> Optional[EconRelease]:
        """
        Check the latest actual vs previous for a named release.

        Args:
            short_name: e.g. "CPI", "GDP", "JOLTS", "FOMC"

        Returns:
            EconRelease with actual/previous/surprise filled in, or None
        """
        # Find the matching release metadata
        meta = None
        rel_id = None
        for rid, m in HIGH_IMPACT_RELEASES.items():
            if m["short"].upper() == short_name.upper():
                meta = m
                rel_id = rid
                break

        if not meta or not meta.get("series"):
            return None

        cache_key = f"surprise_{short_name}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        try:
            url = f"{self.FRED_BASE}/series/observations"
            params = {
                "series_id": meta["series"],
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 2,
            }
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            obs = [o for o in r.json().get("observations", []) if o.get("value", ".") != "."]

            if not obs:
                return None

            latest_val = float(obs[0]["value"])
            prev_val = float(obs[1]["value"]) if len(obs) > 1 else None

            release = EconRelease(
                date=obs[0]["date"],
                name=meta["short"],
                short_name=meta["short"],
                importance=meta["imp"],
                category=meta["cat"],
                release_id=rel_id or 0,
                fred_series=meta["series"],
                actual=latest_val,
                previous=prev_val,
            )

            if prev_val and prev_val != 0:
                release.surprise = round((latest_val - prev_val) / abs(prev_val), 4)

            self._cache[cache_key] = release
            self._cache_ts[cache_key] = time.time()
            return release

        except Exception as e:
            logger.error(f"❌ Surprise check error for {short_name}: {e}")
            return None

    # ── Narrative ─────────────────────────────────────────────────────────

    def get_narrative(self, days: int = 3) -> str:
        """Generate pre-market briefing text for agents."""
        releases = self.get_upcoming(days=days, include_low=False)
        if not releases:
            return "No upcoming economic releases found."

        lines = [f"📅 ECONOMIC CALENDAR — Next {days} days ({len(releases)} releases)"]

        # Group by date
        by_date: Dict[str, List[EconRelease]] = {}
        for r in releases:
            by_date.setdefault(r.date, []).append(r)

        for dt, events in sorted(by_date.items()):
            try:
                day_name = datetime.strptime(dt, "%Y-%m-%d").strftime("%A %b %d")
            except Exception:
                day_name = dt
            lines.append(f"\n{day_name}:")

            for e in events:
                icon = "🔴" if e.importance == Importance.CRITICAL else "🟡" if e.importance == Importance.HIGH else "⚪"
                time_str = f" {e.time} ET" if e.time else ""
                hours_str = f" ({e.hours_until:.0f}h)" if e.hours_until > 0 else ""
                lines.append(f"  {icon} {e.short_name}{time_str}{hours_str} [{e.category.value}]")

        # Add next market mover highlight
        mm = self.get_next_market_mover()
        if mm:
            lines.append(f"\n⚡ NEXT MARKET MOVER: {mm.short_name} on {mm.date} {mm.time} ET ({mm.hours_until:.0f}h)")

        return "\n".join(lines)


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")

    cal = EconCalendar()

    print("=" * 60)
    print("📅 Economic Calendar — Live Test")
    print("=" * 60)

    # All releases this week
    upcoming = cal.get_upcoming(days=7)
    print(f"\n📅 All releases (next 7 days): {len(upcoming)}")
    for r in upcoming[:20]:
        icon = "🔴" if r.importance == Importance.CRITICAL else "🟡" if r.importance == Importance.HIGH else "⚪"
        print(f"  {icon} {r.date} {r.time:>5} | {r.short_name:>20} | {r.importance.value:>8} | {r.category.value}")

    # High impact only
    high = cal.get_high_impact(days=7)
    print(f"\n🎯 High impact only: {len(high)}")
    for r in high:
        print(f"  🔴 {r.date} {r.time} | {r.short_name} ({r.category.value}) | {r.hours_until:.0f}h away")

    # Surprise check
    print("\n📊 Latest release surprises:")
    for name in ["CPI", "GDP", "Employment", "JOLTS", "Retail Sales"]:
        s = cal.check_release(name)
        if s:
            surp = f"{s.surprise:+.4f}" if s.surprise else "N/A"
            print(f"  {name:>15}: {s.actual} (prev: {s.previous}) → surprise: {surp}")

    # Narrative
    print("\n" + cal.get_narrative(days=5))
