"""
📅 Trading Economics Calendar Scraper — Dynamic Economic Calendar

Why two sources for “this week”?
  - ForexFactory (FF) = full-week *spine*: every USD release on the week
    calendar (speeches, holidays, claims, ADP weekly, PMIs, etc.).
  - TE indicator pages = *enrichment*: consensus/forecast/previous/actual
    on allowlisted series, plus a few TE-only rows FF may omit.
  - They are NOT two competing calendars. Merge keeps FF dating/presence
    and fills TE numbers when names+dates match. TE-only forward/off-week
    rows stay `te_indicator`. Duplicates (same day + same event family)
    are collapsed so week_events never double-ships ADP/NFP/claims/etc.

Live sources (priority order):

  1. ForexFactory week spine
     - NFS JSON `ff_calendar_thisweek.json` (always when available)
     - NFS JSON `ff_calendar_nextweek.json` when published (often 404)
     - Fallback: Playwright load of `forexfactory.com/calendar?week=monD.YYYY`
       and extract `window.calendarComponentStates` (HTML table fallback)
  2. TE indicator SSR pages — consensus/forecast enrichment + 7–14d coverage
     beyond the FF week window (expanded slug list, not a tiny allowlist)
  3. TE main calendar — earnest attempt (SSR → curl_cffi → Playwright with
     homepage/cookies/XHR intercept/UA+timezone variants). AWS WAF captcha
     on `?partial=calendar` often blocks headless; status is recorded
     honestly via `te_main_status` (never silent-success on empty shell).

No API key required. No static April/March event dictionaries as source of truth.
Caches results for 1 hour (scraper) / brief fetcher uses a shorter TTL.
"""

from __future__ import annotations

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Process-level memory of TE main Playwright 403 so brief cold paths stay fast.
_TE_MAIN_PW_BLOCKED = False

# ── Importance classification based on event name ──
CRITICAL_EVENTS = {
    "inflation rate",
    "core inflation rate",
    "cpi",
    "cpi s.a",
    "non farm payrolls",
    "nonfarm payrolls",
    "non-farm employment",
    "employment change",
    "gdp growth rate",
    "gdp annual",
    "gdp price index",
    "prelim gdp",
    "fed interest rate decision",
    "fomc",
    "pce price index",
    "core pce price index",
    "unemployment rate",
}

HIGH_EVENTS = {
    "initial jobless claims",
    "jolts job openings",
    "jolts",
    "ppi",
    "core ppi",
    "producer price",
    "retail sales",
    "durable goods orders",
    "ism manufacturing",
    "ism services",
    "ism non-manufacturing",
    "consumer sentiment",
    "michigan consumer",
    "balance of trade",
    "trade balance",
    "personal income",
    "personal spending",
    "building permits",
    "housing starts",
    "new home sales",
    "existing home sales",
    "pending home sales",
    "adp employment",
    "adp nonfarm",
    "fomc economic projections",
    "fed press conference",
    "s&p global",
    "pmi flash",
    "pmi",
    "industrial production",
    "factory orders",
    "consumer confidence",
    "cb consumer confidence",
    "empire state manufacturing",
    "ny empire state",
    "philadelphia fed",
    "nahb housing",
    "current account",
    "average hourly earnings",
    "nfib business",
    "challenger job cuts",
}

MEDIUM_EVENTS = {
    "import prices",
    "export prices",
    "wholesale inventories",
    "retail inventories",
    "business inventories",
    "capacity utilization",
    "leading index",
    "chicago fed",
    "richmond fed",
    "kansas city fed",
    "api crude oil",
    "eia crude oil",
    "eia gasoline",
    "mba mortgage",
    "mba 30-year",
    "treasury budget",
    "monthly budget",
    "net long-term tic",
    "redbook",
    "continuing jobless",
    "crude oil stocks",
    "natural gas stocks",
}

# Expanded US indicator pages that SSR calendar tables (probed 2026-11).
# Prefer breadth over a tiny allowlist — FF fills week gaps; these extend 7–14d.
TE_INDICATOR_SLUGS: Tuple[str, ...] = (
    "inflation-cpi",
    "core-inflation-rate",
    "producer-prices",
    "gdp-growth",
    "non-farm-payrolls",
    "nonfarm-payrolls-private",
    "unemployment-rate",
    "adp-employment-change",
    "jobless-claims",
    "continuing-jobless-claims",
    "average-hourly-earnings",
    "interest-rate",
    "retail-sales",
    "retail-sales-ex-autos",
    "business-confidence",  # ISM Manufacturing PMI
    "consumer-confidence",
    "michigan-consumer-expectations",
    "existing-home-sales",
    "new-home-sales",
    "pending-home-sales",
    "housing-starts",
    "building-permits",
    "durable-goods-orders",
    "factory-orders",
    "industrial-production",
    "balance-of-trade",
    "personal-spending",
    "personal-income",
    "core-pce-price-index-mom",
    "pce-price-index-monthly-change",
    "pce-price-index-annual-change",
    "job-offers",  # JOLTS
    "philadelphia-fed-manufacturing-index",
    "ny-empire-state-manufacturing-index",
    "nahb-housing-market-index",
    "nfib-business-optimism-index",
    "current-account",
    "capacity-utilization",
    "challenger-job-cuts",
    "crude-oil-stocks-change",
    "natural-gas-stocks-change",
    "economic-optimism-index",
)

# Map common FF titles → TE indicator slugs for optional enrichment fetches.
FF_TITLE_TO_TE_SLUG: Dict[str, str] = {
    "non-farm employment change": "non-farm-payrolls",
    "nonfarm payrolls": "non-farm-payrolls",
    "unemployment rate": "unemployment-rate",
    "adp non-farm employment change": "adp-employment-change",
    "core cpi m/m": "core-inflation-rate",
    "cpi m/m": "inflation-cpi",
    "cpi y/y": "inflation-cpi",
    "core pce price index m/m": "core-pce-price-index-mom",
    "pce price index m/m": "pce-price-index-monthly-change",
    "pce price index y/y": "pce-price-index-annual-change",
    "prelim gdp q/q": "gdp-growth",
    "gdp q/q": "gdp-growth",
    "retail sales m/m": "retail-sales",
    "core retail sales m/m": "retail-sales-ex-autos",
    "durable goods orders m/m": "durable-goods-orders",
    "building permits": "building-permits",
    "housing starts": "housing-starts",
    "existing home sales": "existing-home-sales",
    "new home sales": "new-home-sales",
    "pending home sales m/m": "pending-home-sales",
    "ism manufacturing pmi": "business-confidence",
    "unemployment claims": "jobless-claims",
    "jolts job openings": "job-offers",
    "federal funds rate": "interest-rate",
    "fomc statement": "interest-rate",
    "average hourly earnings m/m": "average-hourly-earnings",
}

FF_THISWEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_NEXTWEEK_URL = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"
FF_CALENDAR_WEEK_URL = "https://www.forexfactory.com/calendar?week={week}"

# Canonical family aliases so FF titles merge with TE indicator titles.
# Keys/values are post-normalization tokens (see `_normalize_event_name`).
EVENT_NAME_ALIASES: Dict[str, str] = {
    "unemployment claims": "initial jobless claims",
    "jobless claims": "initial jobless claims",
    "initial claims": "initial jobless claims",
    "adp employment change": "adp nonfarm employment change",
    "adp non farm employment change": "adp nonfarm employment change",
    "adp nonfarm employment change": "adp nonfarm employment change",
    "adp weekly employment change": "adp weekly employment change",
    "non farm employment change": "nonfarm payrolls",
    "nonfarm payrolls": "nonfarm payrolls",
    "non farm payrolls": "nonfarm payrolls",
    "prelim gdp": "gdp",
    "gdp": "gdp",
    "gdp qoq": "gdp qoq",
    "qoq 2nd est": "gdp qoq",
    "qoq 2nd": "gdp qoq",
    "gdp growth rate": "gdp qoq",
    "gdp growth": "gdp qoq",
    "crude oil inventories": "crude oil stocks",
    "eia crude oil stocks change": "crude oil stocks",
    "crude oil stocks change": "crude oil stocks",
    "natural gas storage": "natural gas stocks",
    "eia natural gas stocks change": "natural gas stocks",
    "natural gas stocks change": "natural gas stocks",
    "cb consumer confidence": "consumer confidence",
    "ism manufacturing pmi": "ism manufacturing",
    "business confidence": "ism manufacturing",
    "fed interest rate decision": "federal funds rate",
    "federal funds rate": "federal funds rate",
    "fomc rate decision": "federal funds rate",
}


def _normalize_event_name(name: str) -> str:
    """Normalize event titles for merge keys (FF ↔ TE indicator)."""
    n = re.sub(r"\s+", " ", (name or "").lower()).strip()
    # Drop trailing reference month glued to name (TE sometimes appends FEB)
    n = re.sub(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b",
        " ",
        n,
    )
    # Period suffixes → canonical tokens
    n = re.sub(r"\b(m/m|mom|m-o-m)\b", " mom", n)
    n = re.sub(r"\b(y/y|yoy|y-o-y)\b", " yoy", n)
    n = re.sub(r"\b(q/q|qoq|q-o-q)\b", " qoq", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    # Drop noise words that differ across sources
    n = re.sub(r"\b(final|prelim|preliminary|flash|sa|saar|est|estimate)\b", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    # Alias → canonical family
    if n in EVENT_NAME_ALIASES:
        return EVENT_NAME_ALIASES[n]
    # Try without mom/yoy/qoq for alias lookup, then re-attach period
    period = ""
    base = n
    for p in (" mom", " yoy", " qoq"):
        if n.endswith(p):
            period = p
            base = n[: -len(p)].strip()
            break
    if base in EVENT_NAME_ALIASES:
        return (EVENT_NAME_ALIASES[base] + period).strip()
    return n


@dataclass
class TEEvent:
    """A single economic event from Trading Economics / ForexFactory."""

    date: str  # "Wednesday March 11 2026" or ISO date string
    time: str  # "12:30 PM" (often GMT on TE)
    event: str  # "Core Inflation Rate MoM"
    actual: str  # "0.4%" or ""
    previous: str  # "0.3%"
    consensus: str  # "0.2%"
    forecast: str  # "0.2%"
    importance: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    source: str = "te"  # forexfactory | te_indicator | te_main | forexfactory+te_*

    @property
    def has_actual(self) -> bool:
        return bool(self.actual and self.actual not in ("—", "-", "N/A"))

    @property
    def has_consensus(self) -> bool:
        return bool(self.consensus and self.consensus not in ("—", "-", "N/A", ""))

    @property
    def is_upcoming(self) -> bool:
        """Unreleased AND not in the past (when datetime is parseable)."""
        if self.has_actual:
            return False
        dt = TECalendarScraper._parse_event_datetime(self)
        if dt is None:
            return True  # unknown time → treat as upcoming candidate
        return dt >= datetime.now()

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "time": self.time,
            "event": self.event,
            "actual": self.actual,
            "previous": self.previous,
            "consensus": self.consensus,
            "forecast": self.forecast,
            "importance": self.importance,
            "has_actual": self.has_actual,
            "has_consensus": self.has_consensus,
            "is_upcoming": self.is_upcoming,
            "source": self.source,
        }


def _classify_importance(event_name: str) -> str:
    """Classify event importance based on name matching."""
    lower = event_name.lower()
    for keyword in CRITICAL_EVENTS:
        if keyword in lower:
            return "CRITICAL"
    for keyword in HIGH_EVENTS:
        if keyword in lower:
            return "HIGH"
    for keyword in MEDIUM_EVENTS:
        if keyword in lower:
            return "MEDIUM"
    return "LOW"


def _normalize_cell(val: str) -> str:
    v = (val or "").strip()
    if v in ("—", "–", "-", "N/A", "n/a"):
        return ""
    return v


class TECalendarScraper:
    """
    Dynamic economic calendar.

    ForexFactory = week spine (dating/presence). TE indicators = consensus
    enrichment + forward coverage. TE main calendar attempted earnestly but
    often AWS-WAF/captcha blocked — status via te_main_status, never fake OK.
    """

    BASE_URL = "https://tradingeconomics.com"
    TE_MAIN_PATHS = (
        "/united-states/calendar",
        "/united-states/calendar?timezone=eastern",
        "/united-states/calendar?timezone=America/New_York",
    )

    def __init__(self, cache_ttl: int = 3600):
        self._cache: Dict[str, List[TEEvent]] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        self._last_error: Optional[str] = None
        self._last_sources: List[str] = []
        self._te_main_status: str = "not_attempted"
        self._source_notes: Dict[str, str] = {}
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/134.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/json",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        logger.info("📅 TECalendarScraper initialized (FF spine + TE indicators)")

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_sources(self) -> List[str]:
        return list(self._last_sources)

    @property
    def te_main_status(self) -> str:
        return self._te_main_status

    @property
    def source_notes(self) -> Dict[str, str]:
        return dict(self._source_notes)

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def get_us_calendar(self) -> List[TEEvent]:
        """Get US economic events (FF spine + TE indicator enrichment)."""
        cache_key = "us_calendar"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        self._last_error = None
        self._last_sources = []
        self._source_notes = {}
        self._te_main_status = "not_attempted"
        events: List[TEEvent] = []
        errors: List[str] = []

        # 1) ForexFactory this week + next week — dense calendar spine
        try:
            ff = self._fetch_forexfactory_weeks()
            if ff:
                events.extend(ff)
                self._last_sources.append("forexfactory")
        except Exception as e:
            errors.append(f"forexfactory:{e}")
            self._source_notes["forexfactory"] = str(e)

        # 2) TE indicator SSR pages (consensus enrichment + forward coverage)
        try:
            extra_slugs = self._slugs_from_ff_titles(events)
            indicator_events = self._scrape_indicator_calendars(extra_slugs=extra_slugs)
            if indicator_events:
                events = self._merge_events(events, indicator_events)
                self._last_sources.append("te_indicator")
        except Exception as e:
            errors.append(f"te_indicator:{e}")
            self._source_notes["te_indicator"] = str(e)

        # 3) Attempt TE main calendar (usually WAF/JS/403 — degrade honestly)
        try:
            main = self._scrape_main_calendar()
            if main:
                events = self._merge_events(events, main)
                self._last_sources.append("te_main")
                # Keep detailed ok_* status from scraper; never collapse to bare "ok"
                if not str(self._te_main_status).startswith("ok"):
                    self._te_main_status = "ok"
                self._source_notes["te_main"] = (
                    f"{self._te_main_status}; events={len(main)}"
                )
            else:
                # status already set inside _scrape_main_calendar
                self._source_notes["te_main"] = self._te_main_status
                logger.warning(
                    "TE main calendar unavailable (%s) — using FF + te_indicator",
                    self._te_main_status,
                )
        except Exception as e:
            self._te_main_status = f"error:{e}"
            errors.append(f"te_main:{e}")
            self._source_notes["te_main"] = str(e)
            logger.warning("TE main calendar failed: %s", e)

        if not events:
            self._last_error = "; ".join(errors) if errors else "no calendar sources returned events"
            logger.error("❌ Calendar scrape empty: %s", self._last_error)
        else:
            logger.info(
                "📅 Scraped %d US economic events via %s (te_main=%s)",
                len(events),
                ",".join(self._last_sources) or "unknown",
                self._te_main_status,
            )

        self._cache[cache_key] = events
        self._cache_ts[cache_key] = time.time()
        return events

    def get_today(self) -> List[TEEvent]:
        """Get today's US events only."""
        today = date.today()
        out: List[TEEvent] = []
        for e in self.get_us_calendar():
            dt = self._parse_event_datetime(e)
            if dt and dt.date() == today:
                out.append(e)
                continue
            # Fallback fuzzy match on date string
            today_str = today.strftime("%B %d").lstrip("0").replace(" 0", " ")
            if today_str in e.date or today.isoformat() in e.date:
                out.append(e)
        return out

    def get_upcoming(self, days: int = 7) -> List[TEEvent]:
        """Get upcoming unreleased events within the next N days (future-only)."""
        now = datetime.now()
        end = now + timedelta(days=days)
        out: List[TEEvent] = []
        for e in self.get_us_calendar():
            if e.has_actual:
                continue
            dt = self._parse_event_datetime(e)
            if dt is None:
                if e.is_upcoming:
                    out.append(e)
                continue
            if now <= dt <= end:
                out.append(e)
        return out

    def get_upcoming_events(self, days: int = 14) -> List[dict]:
        """Dict form used by PMIPredictor / older callers."""
        return [e.to_dict() for e in self.get_upcoming(days=days)]

    def _merged_events(self) -> List[TEEvent]:
        """All scraped events (no hardcoded BEA overrides)."""
        return self.get_us_calendar()

    def get_high_impact(self) -> List[TEEvent]:
        """Get only CRITICAL and HIGH importance events."""
        return [e for e in self._merged_events() if e.importance in ("CRITICAL", "HIGH")]

    def get_upcoming_critical(self) -> List[TEEvent]:
        """Upcoming CRITICAL events — unreleased and still in the future."""
        now = datetime.now()
        out: List[TEEvent] = []
        for e in self._merged_events():
            if e.importance != "CRITICAL":
                continue
            if e.has_actual:
                continue
            dt = self._parse_event_datetime(e)
            if dt is not None and dt < now:
                continue
            out.append(e)
        return out

    def get_released(self) -> List[TEEvent]:
        """Get events that already have actual values."""
        return [e for e in self.get_us_calendar() if e.has_actual]

    def get_surprises(self) -> List[Dict]:
        """Get events where actual differs from consensus (surprises)."""
        surprises = []
        for e in self.get_released():
            if e.has_consensus:
                surprises.append(
                    {
                        "event": e.event,
                        "actual": e.actual,
                        "consensus": e.consensus,
                        "date": e.date,
                        "importance": e.importance,
                    }
                )
        return surprises

    def get_hours_until_next_critical(self) -> Optional[tuple]:
        """
        Hours until the next unreleased CRITICAL event + its name.
        Returns (hours, event_name) or None.
        """
        critical = self.get_upcoming_critical()
        if not critical:
            return None

        now = datetime.now()
        nearest_hours = None
        nearest_name = None

        for evt in critical:
            dt = self._parse_event_datetime(evt)
            if dt is None:
                continue
            delta_h = (dt - now).total_seconds() / 3600.0
            if delta_h < 0:
                continue
            if nearest_hours is None or delta_h < nearest_hours:
                nearest_hours = delta_h
                nearest_name = evt.event

        if nearest_hours is None:
            return None
        return (nearest_hours, nearest_name)

    @staticmethod
    def _parse_event_datetime(evt: "TEEvent") -> Optional[datetime]:
        """
        Parse TE/FF date+time strings into naive local-ish datetime.
        Handles:
          - "Thursday March 27 2026" + "08:30 AM"
          - "2026-12-10" + "01:30 PM"
          - ISO "2026-11-23T09:45:00-05:00" stored in date field
        """
        try:
            date_str = (evt.date or "").strip()
            time_str = (evt.time or "08:30 AM").replace(" ET", "").replace(" GMT", "").strip()

            # ISO datetime already in date field (ForexFactory)
            if "T" in date_str and re.match(r"\d{4}-\d{2}-\d{2}T", date_str):
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    dt = dt.astimezone().replace(tzinfo=None)
                return dt

            # ISO date + time
            if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                full = f"{date_str} {time_str}"
                for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(full, fmt)
                    except ValueError:
                        continue
                return datetime.strptime(date_str, "%Y-%m-%d")

            # "Thursday March 27 2026"
            parts = date_str.split(" ")
            if len(parts) >= 4:
                month_day_year = " ".join(parts[1:])
            else:
                month_day_year = date_str
            full = f"{month_day_year} {time_str}"
            for fmt in ("%B %d %Y %I:%M %p", "%B %d %Y %H:%M"):
                try:
                    return datetime.strptime(full, fmt)
                except ValueError:
                    continue
            return None
        except (ValueError, IndexError, TypeError):
            return None

    # ── Source: main TE calendar ─────────────────────────────────────────

    def _scrape_main_calendar(self) -> List[TEEvent]:
        """
        Earnest TE main calendar attempt:
          1) requests SSR (+ homepage warm) / ?partial=calendar
          2) curl_cffi chrome impersonation (same paths)
          3) Playwright: homepage → cookies → calendar (+ timezone/UA) with
             XHR/fetch intercept for partial JSON/HTML

        Returns [] on WAF/captcha/empty and sets te_main_status honestly.
        Never claims success on a JS shell with empty rows.
        """
        url = f"{self.BASE_URL}/united-states/calendar"
        attempt_notes: List[str] = []

        # Warm homepage (sets any soft cookies TE expects before calendar)
        try:
            self._session.get(f"{self.BASE_URL}/", timeout=15)
        except Exception as e:
            attempt_notes.append(f"home_warm_err:{e}")

        # 1) Full page SSR for each timezone variant
        for path in self.TE_MAIN_PATHS:
            full = f"{self.BASE_URL}{path}"
            try:
                r = self._session.get(full, timeout=20)
                if r.status_code != 200:
                    attempt_notes.append(f"ssr_{path.split('?')[-1] or 'base'}:{r.status_code}")
                    continue
                events = self._parse_calendar_html(r.text, source="te_main")
                if events:
                    self._te_main_status = "ok_ssr"
                    return events
                if "calendar-table" in r.text and r.text.count("<tr") <= 2:
                    self._te_main_status = "js_shell_empty_rows"
            except Exception as e:
                attempt_notes.append(f"ssr_err:{e}")

        # 2) Partial endpoint (AWS WAF often 403/405 + captcha widget)
        try:
            pr = self._session.get(
                f"{url}?partial=calendar",
                headers={
                    "Referer": url,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                },
                timeout=20,
            )
            waf = pr.headers.get("x-amzn-waf-action")
            if pr.status_code == 200 and pr.headers.get("X-TE-Partial") == "calendar":
                events = self._parse_calendar_html(pr.text, source="te_main")
                if events:
                    self._te_main_status = "ok_partial"
                    return events
            if waf or pr.status_code in (403, 405, 429):
                self._te_main_status = f"waf_blocked_status_{pr.status_code}"
                if waf:
                    attempt_notes.append(f"waf_action:{waf}")
            elif self._te_main_status in ("not_attempted", "js_shell_empty_rows"):
                self._te_main_status = f"partial_empty_status_{pr.status_code}"
        except Exception as e:
            self._te_main_status = f"partial_error:{e}"
            attempt_notes.append(f"partial_err:{e}")

        # 3) curl_cffi TLS fingerprint (sometimes clears soft WAF; still often
        #    hits captcha on partial — record honestly either way)
        cffi_events = self._curl_cffi_scrape_main_calendar(url, attempt_notes)
        if cffi_events:
            self._te_main_status = "ok_curl_cffi"
            return cffi_events

        # 4) Playwright earnest path (homepage → cookies → intercept)
        global _TE_MAIN_PW_BLOCKED
        force_pw = os.environ.get("TE_CALENDAR_PLAYWRIGHT", "").strip() in ("1", "true", "True")
        if _TE_MAIN_PW_BLOCKED and not force_pw:
            self._te_main_status = (
                f"{self._te_main_status}|playwright_skipped_known_403"
                if self._te_main_status not in ("not_attempted",)
                else "playwright_skipped_known_403"
            )
            if attempt_notes:
                self._source_notes["te_main_attempts"] = "; ".join(attempt_notes[-8:])
            return []

        pw_events = self._browser_scrape_main_calendar(url)
        if pw_events:
            if not str(self._te_main_status).startswith("ok_"):
                self._te_main_status = "ok_playwright"
            return pw_events

        if self._te_main_status in ("not_attempted",):
            self._te_main_status = "empty_no_rows"
        if attempt_notes:
            self._source_notes["te_main_attempts"] = "; ".join(attempt_notes[-8:])
        return []

    def _curl_cffi_scrape_main_calendar(
        self, url: str, attempt_notes: List[str]
    ) -> List[TEEvent]:
        """Try TE main via curl_cffi chrome impersonation."""
        try:
            from curl_cffi import requests as creq
        except Exception:
            attempt_notes.append("curl_cffi_unavailable")
            return []

        try:
            sess = creq.Session(impersonate="chrome131")
            sess.get(f"{self.BASE_URL}/", timeout=20)
            for path in self.TE_MAIN_PATHS:
                full = f"{self.BASE_URL}{path}"
                r = sess.get(full, timeout=25)
                if r.status_code != 200:
                    attempt_notes.append(f"cffi_{path}:{r.status_code}")
                    continue
                events = self._parse_calendar_html(r.text, source="te_main")
                if events:
                    return events
            pr = sess.get(
                f"{url}?partial=calendar",
                headers={
                    "Referer": url,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "*/*",
                },
                timeout=25,
            )
            waf = pr.headers.get("x-amzn-waf-action")
            attempt_notes.append(
                f"cffi_partial:{pr.status_code}:waf={waf or 'none'}:te={pr.headers.get('X-TE-Partial')}"
            )
            if pr.status_code == 200 and pr.headers.get("X-TE-Partial") == "calendar":
                events = self._parse_calendar_html(pr.text, source="te_main")
                if events:
                    return events
            if waf or pr.status_code in (403, 405, 429):
                # Prefer more specific WAF status if requests already set js_shell
                if not str(self._te_main_status).startswith("waf"):
                    self._te_main_status = f"waf_blocked_cffi_{pr.status_code}"
        except Exception as e:
            attempt_notes.append(f"cffi_err:{e}")
        return []

    def _browser_scrape_main_calendar(self, url: str) -> List[TEEvent]:
        """
        Playwright TE main: homepage warm-up, cookie accept, calendar paths,
        wait for rows / network idle, intercept XHR/fetch for calendar JSON.
        Runs in a worker thread so FastAPI asyncio loops stay safe.
        """
        global _TE_MAIN_PW_BLOCKED

        def _run() -> List[TEEvent]:
            try:
                from playwright.sync_api import sync_playwright
            except Exception:
                if not str(self._te_main_status).startswith("waf") and "js_shell" not in str(
                    self._te_main_status
                ):
                    self._te_main_status = "playwright_unavailable"
                return []

            profiles = [
                {
                    "label": "desktop",
                    "ua": self._session.headers["User-Agent"],
                    "viewport": {"width": 1440, "height": 900},
                    "channel": "chrome",
                },
                {
                    "label": "mobile",
                    "ua": (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
                        "Mobile/15E148 Safari/604.1"
                    ),
                    "viewport": {"width": 390, "height": 844},
                    "channel": None,
                },
            ]

            try:
                with sync_playwright() as p:
                    for profile in profiles:
                        events = self._pw_try_profile(p, url, profile)
                        if events:
                            return events
            except Exception as e:
                self._te_main_status = f"playwright_error:{e}"
                logger.debug("Playwright TE main failed: %s", e)
            return []

        # Always worker-thread — sync Playwright cannot nest in asyncio.
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(_run).result(timeout=150)
        except Exception as e:
            self._te_main_status = f"playwright_error:{e}"
            return []

    def _pw_try_profile(self, p, url: str, profile: dict) -> List[TEEvent]:
        """One Playwright UA/channel profile against TE main calendar."""
        global _TE_MAIN_PW_BLOCKED
        launch_kwargs = {
            "headless": True,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if profile.get("channel"):
            try:
                browser = p.chromium.launch(channel=profile["channel"], **launch_kwargs)
            except Exception:
                browser = p.chromium.launch(**launch_kwargs)
        else:
            browser = p.chromium.launch(**launch_kwargs)

        captured_bodies: List[str] = []

        def _on_response(resp) -> None:
            try:
                rurl = resp.url or ""
                ct = (resp.headers.get("content-type") or "").lower()
                if not (
                    "partial=calendar" in rurl
                    or "calendar" in rurl.lower()
                    or "json" in ct
                    or resp.headers.get("X-TE-Partial") == "calendar"
                ):
                    return
                if resp.status != 200:
                    return
                text = resp.text()
                if text and len(text) > 200:
                    captured_bodies.append(text)
            except Exception:
                return

        try:
            context = browser.new_context(
                user_agent=profile["ua"],
                viewport=profile["viewport"],
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = context.new_page()
            page.on("response", _on_response)

            home = page.goto(
                f"{self.BASE_URL}/", wait_until="domcontentloaded", timeout=45000
            )
            if home and home.status == 403:
                _TE_MAIN_PW_BLOCKED = True
                self._te_main_status = "playwright_403_access_denied"
                browser.close()
                return []
            page.wait_for_timeout(1500)
            for sel in (
                "button:has-text('Accept')",
                "button:has-text('I Agree')",
                "button:has-text('Agree')",
                "#onetrust-accept-btn-handler",
                ".cc-btn",
            ):
                try:
                    loc = page.locator(sel).first
                    if loc.count() and loc.is_visible(timeout=600):
                        loc.click(timeout=2000)
                        page.wait_for_timeout(800)
                        break
                except Exception:
                    pass

            last_status = 0
            for path in self.TE_MAIN_PATHS:
                full = f"{self.BASE_URL}{path}"
                try:
                    resp = page.goto(full, wait_until="domcontentloaded", timeout=60000)
                except Exception:
                    continue
                last_status = resp.status if resp else 0
                if last_status == 403:
                    _TE_MAIN_PW_BLOCKED = True
                    self._te_main_status = "playwright_403_access_denied"
                    browser.close()
                    return []
                # Wait for table rows OR intercepted partial body
                for wait_sel in (
                    "tr[data-event]",
                    "table.calendar-table tr td",
                    "#calendar table tr td",
                    "#te-calendar-body table tr",
                ):
                    try:
                        page.wait_for_selector(wait_sel, timeout=8000)
                        break
                    except Exception:
                        pass
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    page.wait_for_timeout(2500)

                # Prefer intercepted XHR/fetch bodies (JSON or HTML partial)
                for body in captured_bodies:
                    if body.lstrip().startswith(("{", "[")):
                        parsed = self._parse_te_main_json(body)
                        if parsed:
                            self._te_main_status = f"ok_playwright_xhr_{profile['label']}"
                            browser.close()
                            return parsed
                    parsed = self._parse_calendar_html(body, source="te_main")
                    if parsed:
                        self._te_main_status = f"ok_playwright_xhr_{profile['label']}"
                        browser.close()
                        return parsed

                html = page.content()
                events = self._parse_calendar_html(html, source="te_main")
                if events:
                    self._te_main_status = f"ok_playwright_{profile['label']}"
                    browser.close()
                    return events

            self._te_main_status = f"playwright_empty_status_{last_status}"
            browser.close()
            return []
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            self._te_main_status = f"playwright_error:{e}"
            return []

    def _parse_te_main_json(self, raw: str) -> List[TEEvent]:
        """Parse TE calendar JSON payloads captured from network (best-effort)."""
        import json

        try:
            data = json.loads(raw)
        except Exception:
            return []

        rows: list = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("calendar", "events", "data", "rows", "Items", "items"):
                if isinstance(data.get(key), list):
                    rows = data[key]
                    break
        events: List[TEEvent] = []
        for raw_ev in rows:
            if not isinstance(raw_ev, dict):
                continue
            country = str(
                raw_ev.get("Country")
                or raw_ev.get("country")
                or raw_ev.get("Currency")
                or ""
            ).upper()
            if country and country not in ("UNITED STATES", "US", "USA", "USD"):
                continue
            name = str(
                raw_ev.get("Event")
                or raw_ev.get("event")
                or raw_ev.get("Name")
                or raw_ev.get("name")
                or ""
            ).strip()
            if not name:
                continue
            date_raw = str(
                raw_ev.get("Date")
                or raw_ev.get("date")
                or raw_ev.get("DateUtc")
                or raw_ev.get("datetime")
                or ""
            ).strip()
            if not date_raw:
                continue
            time_raw = str(raw_ev.get("Time") or raw_ev.get("time") or "").strip()
            actual = _normalize_cell(str(raw_ev.get("Actual") or raw_ev.get("actual") or ""))
            previous = _normalize_cell(
                str(raw_ev.get("Previous") or raw_ev.get("previous") or "")
            )
            consensus = _normalize_cell(
                str(
                    raw_ev.get("Consensus")
                    or raw_ev.get("consensus")
                    or raw_ev.get("Forecast")
                    or raw_ev.get("forecast")
                    or ""
                )
            )
            forecast = _normalize_cell(
                str(
                    raw_ev.get("TEForecast")
                    or raw_ev.get("teforecast")
                    or raw_ev.get("Forecast")
                    or raw_ev.get("forecast")
                    or ""
                )
            )
            events.append(
                TEEvent(
                    date=date_raw,
                    time=time_raw,
                    event=name,
                    actual=actual,
                    previous=previous,
                    consensus=consensus or forecast,
                    forecast=forecast,
                    importance=_classify_importance(name),
                    source="te_main",
                )
            )
        return events

    def _parse_calendar_html(self, html: str, source: str = "te_main") -> List[TEEvent]:
        """Parse classic multi-row calendar HTML table if present."""
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")

        cal_table = None
        for t in tables:
            rows = t.find_all("tr")
            if len(rows) > 50:
                cal_table = t
                break
            # Newer markup: calendar-table with many data rows
            cls = " ".join(t.get("class") or [])
            if "calendar" in cls and len(rows) > 5:
                cal_table = t
                break
            # data-event rows (JS-hydrated markup if captcha cleared)
            if t.select("tr[data-event]") and len(rows) > 5:
                cal_table = t
                break

        if not cal_table:
            return []

        rows = cal_table.find_all("tr")
        events: List[TEEvent] = []
        current_date = ""
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True) for c in cells]
            if not texts:
                continue

            if any(day in texts[0] for day in days):
                current_date = texts[0]
                continue

            if current_date and texts[0] and ("AM" in texts[0] or "PM" in texts[0]):
                time_text = texts[0]
                event_name = ""
                for t in texts[1:]:
                    if (
                        t
                        and len(t) > 3
                        and t != "US"
                        and not t.replace(".", "")
                        .replace("-", "")
                        .replace("%", "")
                        .replace("$", "")
                        .replace(",", "")
                        .replace("K", "")
                        .replace("M", "")
                        .replace("B", "")
                        .isdigit()
                    ):
                        event_name = t
                        break
                if not event_name:
                    continue

                actual = previous = consensus = forecast = ""
                try:
                    idx = texts.index(event_name)
                    nums = texts[idx + 1 :]
                    if len(nums) >= 1:
                        actual = _normalize_cell(nums[0])
                    if len(nums) >= 2:
                        previous = _normalize_cell(nums[1])
                    if len(nums) >= 3:
                        consensus = _normalize_cell(nums[2])
                    if len(nums) >= 4:
                        forecast = _normalize_cell(nums[3])
                except (ValueError, IndexError):
                    pass

                events.append(
                    TEEvent(
                        date=current_date,
                        time=time_text,
                        event=event_name,
                        actual=actual,
                        previous=previous,
                        consensus=consensus,
                        forecast=forecast,
                        importance=_classify_importance(event_name),
                        source=source,
                    )
                )
        return events

    # ── Source: TE indicator pages ───────────────────────────────────────

    def _slugs_from_ff_titles(self, events: List[TEEvent]) -> List[str]:
        """Grow indicator fetch list from FF event titles when mappable."""
        extra: List[str] = []
        for e in events:
            if e.source != "forexfactory":
                continue
            key = re.sub(r"\s+", " ", (e.event or "").lower()).strip()
            slug = FF_TITLE_TO_TE_SLUG.get(key)
            if not slug:
                # fuzzy: strip m/m y/y q/q suffixes
                key2 = re.sub(r"\b(m/m|y/y|q/q|mom|yoy|qoq)\b", "", key).strip()
                slug = FF_TITLE_TO_TE_SLUG.get(key2)
            if slug and slug not in TE_INDICATOR_SLUGS and slug not in extra:
                extra.append(slug)
        return extra

    def _scrape_indicator_calendars(self, extra_slugs: Optional[List[str]] = None) -> List[TEEvent]:
        """Scrape SSR calendar tables from key US indicator pages (parallel)."""
        slugs = list(TE_INDICATOR_SLUGS)
        for s in extra_slugs or []:
            if s not in slugs:
                slugs.append(s)

        events: List[TEEvent] = []
        errors = 0

        def _one(slug: str) -> List[TEEvent]:
            url = f"{self.BASE_URL}/united-states/{slug}"
            r = self._session.get(url, timeout=18)
            if r.status_code != 200:
                return []
            return self._parse_indicator_calendar_table(r.text)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(_one, slug): slug for slug in slugs}
            for fut in as_completed(futs):
                slug = futs[fut]
                try:
                    page_events = fut.result()
                    events.extend(page_events)
                except Exception as e:
                    errors += 1
                    logger.debug("Indicator scrape failed for %s: %s", slug, e)

        self._source_notes["te_indicator"] = (
            f"slugs={len(slugs)} events={len(events)} errors={errors}"
        )
        return events

    def _parse_indicator_calendar_table(self, html: str) -> List[TEEvent]:
        soup = BeautifulSoup(html, "html.parser")
        events: List[TEEvent] = []
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            header_blob = " ".join(headers)
            if "actual" not in header_blob:
                continue
            if "consensus" not in header_blob and "teforecast" not in header_blob and "previous" not in header_blob:
                continue

            for tr in table.find_all("tr")[1:]:
                cells = [_normalize_cell(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
                if len(cells) < 4:
                    continue
                # Typical: [date, time, event, reference?, actual, previous, consensus, teforecast]
                date_raw = cells[0]
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_raw):
                    continue
                time_raw = cells[1] if len(cells) > 1 else "08:30 AM"
                # Find event name: first non-empty alpha cell after time that isn't a month abbrev alone
                event_name = ""
                value_start = 2
                for i, cell in enumerate(cells[2:], start=2):
                    if not cell:
                        continue
                    # Skip pure reference labels like "Nov", "Q3", "Oct"
                    if re.fullmatch(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Q[1-4])(/?\d+)?", cell):
                        continue
                    if re.search(r"[A-Za-z]{3,}", cell) and not re.fullmatch(
                        r"[\d\.\-%$KMB,/]+", cell.replace(" ", "")
                    ):
                        event_name = cell
                        value_start = i + 1
                        # If next cell looks like reference period, skip it
                        if value_start < len(cells) and re.fullmatch(
                            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Q[1-4])(/\d+)?",
                            cells[value_start],
                        ):
                            value_start += 1
                        break
                if not event_name:
                    continue

                vals = cells[value_start:]
                actual = vals[0] if len(vals) >= 1 else ""
                previous = vals[1] if len(vals) >= 2 else ""
                consensus = vals[2] if len(vals) >= 3 else ""
                forecast = vals[3] if len(vals) >= 4 else ""

                # Some rows put TEForecast where consensus is empty — promote forecast
                if not consensus and forecast:
                    consensus = forecast

                events.append(
                    TEEvent(
                        date=date_raw,
                        time=time_raw,
                        event=event_name,
                        actual=actual,
                        previous=previous,
                        consensus=consensus,
                        forecast=forecast,
                        importance=_classify_importance(event_name),
                        source="te_indicator",
                    )
                )
        return events

    # ── Source: ForexFactory week JSON (+ HTML next-week fallback) ───────

    def _fetch_forexfactory_weeks(self) -> List[TEEvent]:
        """
        Fetch this-week + next-week FF events.

        Prefer NFS JSON when published. `ff_calendar_nextweek.json` often 404s
        (FairEconomy only reliably serves thisweek.*) — in that case scrape
        ForexFactory `?week=monD.YYYY` via Playwright and read calendar state.
        """
        events: List[TEEvent] = []
        notes: List[str] = []
        thisweek_raw: List[dict] = []

        # 1) thisweek JSON
        try:
            r = self._session.get(FF_THISWEEK_URL, timeout=15)
            if r.status_code == 404:
                notes.append("thisweek=404")
            else:
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, list):
                    notes.append("thisweek=bad_json")
                else:
                    thisweek_raw = data
                    week_events = self._parse_forexfactory_payload(data)
                    events.extend(week_events)
                    notes.append(f"thisweek={len(week_events)}")
        except Exception as e:
            notes.append(f"thisweek=err:{e}")

        # 2) nextweek JSON (frequently unpublished → 404)
        nextweek_ok = False
        try:
            r = self._session.get(FF_NEXTWEEK_URL, timeout=15)
            if r.status_code == 404:
                notes.append("nextweek=404")
            else:
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, list):
                    notes.append("nextweek=bad_json")
                else:
                    week_events = self._parse_forexfactory_payload(data)
                    events.extend(week_events)
                    notes.append(f"nextweek={len(week_events)}")
                    nextweek_ok = True
        except Exception as e:
            notes.append(f"nextweek=err:{e}")

        # 3) HTML/JS week scrape when nextweek JSON missing or empty
        if not nextweek_ok:
            try:
                week_monday = self._ff_next_week_monday(thisweek_raw)
                html_events = self._fetch_forexfactory_week_html(week_monday)
                if html_events:
                    events.extend(html_events)
                    notes.append(
                        f"nextweek=html_week:{week_monday.isoformat()}:{len(html_events)}"
                    )
                else:
                    notes.append(
                        f"nextweek=html_week:{week_monday.isoformat()}:0"
                    )
            except Exception as e:
                notes.append(f"nextweek=html_err:{e}")

        self._source_notes["forexfactory"] = "; ".join(notes) if notes else "empty"
        return events

    @staticmethod
    def _ff_week_param(monday: date) -> str:
        """ForexFactory week selector: `nov30.2026` (lowercase month + day + year)."""
        return f"{monday.strftime('%b').lower()}{monday.day}.{monday.year}"

    @staticmethod
    def _ff_next_week_monday(thisweek_raw: Optional[List[dict]] = None) -> date:
        """
        Monday of the week AFTER the NFS thisweek window.

        Prefer max date from thisweek JSON; else Monday after today's week.
        """
        max_d: Optional[date] = None
        for raw in thisweek_raw or []:
            iso = str(raw.get("date") or "")
            if not iso:
                continue
            try:
                dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                d = dt.date()
                if max_d is None or d > max_d:
                    max_d = d
            except ValueError:
                continue
        if max_d is not None:
            # Day after thisweek end, then snap forward to Monday
            cursor = max_d + timedelta(days=1)
            while cursor.weekday() != 0:  # Monday=0
                cursor += timedelta(days=1)
            return cursor
        today = date.today()
        # Next Monday strictly after this week's Sunday
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        return today + timedelta(days=days_until_monday)

    def _fetch_forexfactory_week_html(self, week_monday: date) -> List[TEEvent]:
        """
        Load FF calendar HTML for a week and extract USD events from
        `window.calendarComponentStates` (table parse as fallback).
        Runs Playwright in a worker thread so FastAPI async loops stay safe.
        """
        week = self._ff_week_param(week_monday)
        url = FF_CALENDAR_WEEK_URL.format(week=week)
        logger.info("FF nextweek HTML fallback: %s", url)

        def _run() -> List[TEEvent]:
            try:
                from playwright.sync_api import sync_playwright
            except Exception as e:
                logger.warning("Playwright unavailable for FF week scrape: %s", e)
                return []

            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled"],
                    )
                    context = browser.new_context(
                        user_agent=self._session.headers["User-Agent"],
                        viewport={"width": 1400, "height": 900},
                    )
                    page = context.new_page()
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    status = resp.status if resp else 0
                    if status >= 400:
                        browser.close()
                        logger.warning("FF week page HTTP %s for %s", status, url)
                        return []
                    try:
                        page.wait_for_function(
                            "() => !!(window.calendarComponentStates "
                            "&& window.calendarComponentStates[1] "
                            "&& window.calendarComponentStates[1].days)",
                            timeout=15000,
                        )
                    except Exception:
                        page.wait_for_timeout(2500)

                    days = page.evaluate(
                        """() => {
                          const st = window.calendarComponentStates
                            && window.calendarComponentStates[1];
                          if (!st || !Array.isArray(st.days)) return null;
                          return st.days.map(d => ({
                            date: String(d.date || '').replace(/<[^>]+>/g, ''),
                            dateline: d.dateline,
                            events: (d.events || []).map(e => ({
                              name: e.name || e.prefixedName || '',
                              currency: e.currency || '',
                              country: e.country || '',
                              dateline: e.dateline,
                              impact: e.impactName || e.impact || '',
                              actual: e.actual || '',
                              forecast: e.forecast || '',
                              previous: e.previous || '',
                            })),
                          }));
                        }"""
                    )
                    html = page.content() if not days else ""
                    browser.close()

                if days:
                    return self._parse_forexfactory_component_days(days)
                return self._parse_forexfactory_html_table(html)
            except Exception as e:
                logger.warning("FF week Playwright scrape failed: %s", e)
                return []

        # Always run in a worker thread — sync Playwright cannot nest in asyncio.
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run).result(timeout=90)

    def _parse_forexfactory_component_days(self, days: list) -> List[TEEvent]:
        """Parse Playwright-evaluated calendarComponentStates day list → TEEvent."""
        events: List[TEEvent] = []
        for day in days or []:
            for raw in day.get("events") or []:
                currency = str(raw.get("currency") or "").upper()
                country = str(raw.get("country") or "").upper()
                if currency not in ("USD", "US") and country not in ("US", "USA"):
                    continue
                title = str(raw.get("name") or "").strip()
                if not title:
                    continue
                iso = ""
                dateline = raw.get("dateline")
                if dateline is not None:
                    try:
                        # FF datelines are US/Eastern epoch seconds
                        dt = datetime.fromtimestamp(int(dateline))
                        iso = dt.strftime("%Y-%m-%dT%H:%M:%S")
                    except (TypeError, ValueError, OSError):
                        iso = ""
                if not iso:
                    # Fallback: day label "Mon Nov 30" + year from week context
                    label = str(day.get("date") or "").strip()
                    iso = self._ff_day_label_to_iso(label) or label

                impact_raw = str(raw.get("impact") or "low").lower()
                if "high" in impact_raw:
                    impact = "High"
                elif "medium" in impact_raw or "ora" in impact_raw:
                    impact = "Medium"
                elif "holiday" in impact_raw:
                    impact = "Holiday"
                else:
                    impact = "Low"

                events.append(
                    self._ff_event_from_fields(
                        title=title,
                        iso_date=iso,
                        impact=impact,
                        actual=str(raw.get("actual") or ""),
                        previous=str(raw.get("previous") or ""),
                        forecast=str(raw.get("forecast") or ""),
                    )
                )
        return events

    def _parse_forexfactory_html_table(self, html: str) -> List[TEEvent]:
        """Fallback parse of FF calendar__row table markup."""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        events: List[TEEvent] = []
        current_label = ""
        current_year = date.today().year

        for tr in soup.select("tr.calendar__row"):
            classes = tr.get("class") or []
            if "calendar__row--day-breaker" in classes:
                current_label = tr.get_text(" ", strip=True)
                continue

            currency_el = tr.select_one(".calendar__currency")
            if not currency_el or currency_el.get_text(strip=True).upper() != "USD":
                continue

            date_el = tr.select_one(".calendar__date")
            if date_el and date_el.get_text(strip=True):
                current_label = date_el.get_text(strip=True)

            title_el = tr.select_one(".calendar__event")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            if not title:
                continue

            time_el = tr.select_one(".calendar__time")
            time_raw = time_el.get_text(strip=True) if time_el else ""
            iso = self._ff_day_label_to_iso(current_label, time_raw, year=current_year)

            impact_span = tr.select_one(".calendar__impact span[title]")
            impact_title = (impact_span.get("title") or "").lower() if impact_span else ""
            if "high" in impact_title:
                impact = "High"
            elif "medium" in impact_title:
                impact = "Medium"
            elif "holiday" in impact_title:
                impact = "Holiday"
            else:
                impact = "Low"

            def _cell(sel: str) -> str:
                el = tr.select_one(sel)
                return el.get_text(strip=True) if el else ""

            events.append(
                self._ff_event_from_fields(
                    title=title,
                    iso_date=iso or current_label,
                    impact=impact,
                    actual=_cell(".calendar__actual"),
                    previous=_cell(".calendar__previous"),
                    forecast=_cell(".calendar__forecast"),
                )
            )
        return events

    @staticmethod
    def _ff_day_label_to_iso(
        label: str,
        time_raw: str = "",
        year: Optional[int] = None,
    ) -> str:
        """Convert 'Mon Nov 30' + '10:00am' → ISO-ish local datetime string."""
        label = (label or "").strip()
        if not label:
            return ""
        year = year or date.today().year
        # Strip weekday if present: "Mon Nov 30" / "Tue Dec 1"
        parts = label.split()
        if len(parts) >= 3 and parts[0][:3].isalpha():
            md = " ".join(parts[1:3])
        elif len(parts) >= 2:
            md = " ".join(parts[:2])
        else:
            return ""
        time_raw = (time_raw or "").strip()
        if not time_raw or time_raw.lower() in ("all day", "tentative", "day"):
            time_raw = "8:00am"
        for fmt in ("%b %d %Y %I:%M%p", "%b %d %Y %I:%M %p"):
            try:
                dt = datetime.strptime(f"{md} {year} {time_raw}", fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        try:
            dt = datetime.strptime(f"{md} {year}", "%b %d %Y")
            return dt.strftime("%Y-%m-%dT08:00:00")
        except ValueError:
            return ""

    def _ff_event_from_fields(
        self,
        *,
        title: str,
        iso_date: str,
        impact: str,
        actual: str,
        previous: str,
        forecast: str,
    ) -> TEEvent:
        imp_map = {"High": "CRITICAL", "Medium": "HIGH", "Low": "MEDIUM", "Holiday": "LOW"}
        importance = imp_map.get(impact, _classify_importance(title))
        kw = _classify_importance(title)
        if kw == "CRITICAL":
            importance = "CRITICAL"
        elif kw == "HIGH" and importance not in ("CRITICAL",):
            importance = "HIGH"
        forecast_n = _normalize_cell(forecast)
        return TEEvent(
            date=iso_date,
            time="",
            event=title,
            actual=_normalize_cell(actual),
            previous=_normalize_cell(previous),
            consensus=forecast_n,
            forecast=forecast_n,
            importance=importance,
            source="forexfactory",
        )

    def _parse_forexfactory_payload(self, data: list) -> List[TEEvent]:
        events: List[TEEvent] = []
        for raw in data:
            if str(raw.get("country", "")).upper() not in ("USD", "US", "UNITED STATES"):
                continue
            title = str(raw.get("title") or "").strip()
            if not title:
                continue
            iso = str(raw.get("date") or "")
            impact = str(raw.get("impact") or "Low").title()
            events.append(
                self._ff_event_from_fields(
                    title=title,
                    iso_date=iso,
                    impact=impact,
                    actual=str(raw.get("actual") or ""),
                    previous=str(raw.get("previous") or ""),
                    forecast=str(raw.get("forecast") or ""),
                )
            )
        return events

    @staticmethod
    def _event_day_key(e: TEEvent) -> str:
        dt = TECalendarScraper._parse_event_datetime(e)
        if dt:
            return dt.strftime("%Y-%m-%d")
        # ISO date prefix or raw
        raw = (e.date or "")[:10]
        return raw if re.match(r"^\d{4}-\d{2}-\d{2}$", raw) else (e.date or "")

    @staticmethod
    def _merge_key(e: TEEvent) -> Tuple[str, str]:
        return (TECalendarScraper._event_day_key(e), _normalize_event_name(e.event))

    @staticmethod
    def _is_ff_source(source: str) -> bool:
        return "forexfactory" in (source or "")

    @staticmethod
    def _is_te_enrich_source(source: str) -> bool:
        return source in ("te_indicator", "te_main", "te") or (
            source or ""
        ).startswith("te_")

    @staticmethod
    def _merge_pair(ff_or_existing: TEEvent, te_or_other: TEEvent) -> TEEvent:
        """
        Keep FF dating/name when present; fill consensus/forecast/previous/actual
        from TE. Source becomes forexfactory+te_indicator (or +te_main).
        """
        a, b = ff_or_existing, te_or_other
        a_is_ff = TECalendarScraper._is_ff_source(a.source)
        b_is_ff = TECalendarScraper._is_ff_source(b.source)

        if a_is_ff and not b_is_ff:
            spine, enrich = a, b
        elif b_is_ff and not a_is_ff:
            spine, enrich = b, a
        elif "te_main" in (b.source or "") and "te_main" not in (a.source or ""):
            # Prefer te_main numbers onto te_indicator (or other) spine
            spine, enrich = a, b
        elif "te_main" in (a.source or "") and "te_main" not in (b.source or ""):
            spine, enrich = b, a
        else:
            # Prefer richer consensus; keep first's date/name
            spine, enrich = a, b

        enrich_tag = enrich.source
        if enrich_tag == "te":
            enrich_tag = "te_main"
        if TECalendarScraper._is_ff_source(spine.source):
            if "te_indicator" in enrich_tag:
                new_source = "forexfactory+te_indicator"
            elif "te_main" in enrich_tag or enrich_tag == "te":
                new_source = "forexfactory+te_main"
            else:
                new_source = f"forexfactory+{enrich_tag}"
        else:
            new_source = spine.source

        # Prefer TE consensus/forecast/previous when present; keep FF actual if both
        consensus = enrich.consensus if enrich.has_consensus else spine.consensus
        forecast = enrich.forecast or spine.forecast
        previous = enrich.previous or spine.previous
        if enrich.has_actual and not spine.has_actual:
            actual = enrich.actual
        else:
            actual = spine.actual or enrich.actual

        return TEEvent(
            date=spine.date,
            time=spine.time or enrich.time,
            event=spine.event,
            actual=actual,
            previous=previous,
            consensus=consensus,
            forecast=forecast,
            importance=spine.importance
            if spine.importance in ("CRITICAL", "HIGH")
            else (enrich.importance or spine.importance),
            source=new_source,
        )

    @staticmethod
    def _merge_events(primary: List[TEEvent], secondary: List[TEEvent]) -> List[TEEvent]:
        """
        Merge rules:
          1. Primary spine for dating/presence is ForexFactory (passed first).
          2. Matching TE rows enrich consensus/forecast/previous/actual →
             source `forexfactory+te_indicator` (or +te_main).
          3. TE-only events FF lacks stay `te_indicator` / `te_main`.
          4. Same day + same normalized event family → one row (no double ADP/NFP/claims).
        """
        by_key: Dict[Tuple[str, str], TEEvent] = {}
        for e in primary:
            by_key[TECalendarScraper._merge_key(e)] = e
        for e in secondary:
            k = TECalendarScraper._merge_key(e)
            if k not in by_key:
                by_key[k] = e
                continue
            by_key[k] = TECalendarScraper._merge_pair(by_key[k], e)
        return list(by_key.values())

    @staticmethod
    def _events_in_week(events: List[TEEvent], week_start: Optional[date] = None) -> List[TEEvent]:
        """Filter events to Mon–Sun of week_start (defaults to current week)."""
        today = date.today()
        mon = week_start or (today - timedelta(days=today.weekday()))
        sun = mon + timedelta(days=6)
        out: List[TEEvent] = []
        for e in events:
            dt = TECalendarScraper._parse_event_datetime(e)
            if dt is None:
                continue
            if mon <= dt.date() <= sun:
                out.append(e)
        out.sort(key=lambda ev: TECalendarScraper._parse_event_datetime(ev) or datetime.min)
        return out


# ── Module test ──
if __name__ == "__main__":
    from collections import Counter

    logging.basicConfig(level=logging.INFO)

    scraper = TECalendarScraper(cache_ttl=0)

    # Isolated source pulls for the “why 2?” proof table
    ff_raw = scraper._fetch_forexfactory_weeks()
    te_raw = scraper._scrape_indicator_calendars()
    # Full pipeline (includes TE main attempt + merge)
    all_events = scraper.get_us_calendar()

    today = date.today()
    mon = today - timedelta(days=today.weekday())
    ff_week = TECalendarScraper._events_in_week(ff_raw, mon)
    te_week = TECalendarScraper._events_in_week(te_raw, mon)
    merged_week = TECalendarScraper._events_in_week(all_events, mon)
    te_main_week = [
        e for e in merged_week if e.source in ("te_main",) or "te_main" in e.source
    ]

    print("\n══════════════════════════════════════════════════")
    print("WHY TWO SOURCES THIS WEEK?")
    print("  FF           = full USD week spine (dating/presence)")
    print("  TE indicator = consensus enrichment + a few TE-only rows")
    print("  Merge        = FF spine + TE numbers; no duplicate name+date")
    print("══════════════════════════════════════════════════")

    print(f"\n📅 Total US events (merged): {len(all_events)}")
    print(f"   sources: {scraper.last_sources}")
    print(f"   te_main_status: {scraper.te_main_status}")
    print(f"   source_notes: {scraper.source_notes}")
    print(f"   error: {scraper.last_error}")
    print(f"   by_source (all): {Counter(e.source for e in all_events)}")

    print(f"\n📆 THIS WEEK ({mon.isoformat()} → {(mon + timedelta(days=6)).isoformat()})")
    print(f"   counts: ff={len(ff_week)}  te_indicator={len(te_week)}  "
          f"merged={len(merged_week)}  te_main={len(te_main_week)}")

    def _print_week(label: str, events: List[TEEvent], limit: int = 40) -> None:
        print(f"\n── {label} ({len(events)}) ──")
        seen = set()
        dups = 0
        for e in events:
            k = TECalendarScraper._merge_key(e)
            if k in seen:
                dups += 1
            seen.add(k)
            day = k[0]
            print(
                f"   {day} | {e.event[:42]:42s} | "
                f"C={e.consensus or '—':8s} P={e.previous or '—':8s} "
                f"A={e.actual or '—':8s} [{e.source}]"
            )
            if len(seen) >= limit:
                break
        print(f"   dedupe_check: unique_keys={len(seen)} duplicate_rows={dups}")

    _print_week("FOREXFACTORY ONLY (this week)", ff_week)
    _print_week("TE INDICATOR ONLY (this week)", te_week)
    _print_week("MERGED AFTER DEDUPE (this week)", merged_week)

    enriched = [e for e in merged_week if "+" in e.source]
    print(f"\n✨ Enrichment samples (forexfactory+te_*): {len(enriched)}")
    for e in enriched[:12]:
        day = TECalendarScraper._event_day_key(e)
        print(
            f"   {day} | {e.event[:42]:42s} | "
            f"C={e.consensus or '—':8s} F={e.forecast or '—':8s} [{e.source}]"
        )

    next_mon = TECalendarScraper._ff_next_week_monday()
    nextweek_ff = [
        e
        for e in all_events
        if TECalendarScraper._is_ff_source(e.source)
        and (TECalendarScraper._parse_event_datetime(e) or datetime.min).date() >= next_mon
    ]
    print(f"\n📆 FF nextweek (from {next_mon.isoformat()}): {len(nextweek_ff)} events")
    for e in nextweek_ff[:12]:
        dt = TECalendarScraper._parse_event_datetime(e)
        print(
            f"   {(dt.isoformat() if dt else e.date)} | {e.event[:42]:42s} "
            f"C={e.consensus or '—'} [{e.source}]"
        )

    print("\n🔥 UPCOMING CRITICAL EVENTS:")
    for e in scraper.get_upcoming_critical():
        print(f"   {e.date} {e.time} | {e.event} [{e.source}]")
        if e.has_consensus:
            print(
                f"     Consensus: {e.consensus} | Forecast: {e.forecast} | "
                f"Previous: {e.previous}"
            )
