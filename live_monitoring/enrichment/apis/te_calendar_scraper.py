"""
📅 Trading Economics Calendar Scraper — Dynamic Economic Calendar

Live sources (priority order):

  1. ForexFactory NFS JSON — `ff_calendar_thisweek.json` +
     `ff_calendar_nextweek.json` (when published) as the dense week spine
  2. TE indicator SSR pages — consensus/forecast enrichment + 7–14d coverage
     beyond the FF week window (expanded slug list, not a tiny allowlist)
  3. TE main calendar — attempted via requests + optional Playwright;
     WAF/JS/403 failures are recorded honestly (never treated as success)

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
    source: str = "te"  # te | te_indicator | forexfactory

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

    ForexFactory week JSON is the dense spine; TE indicator SSR pages enrich
    consensus and extend beyond the FF window. Main TE calendar is WAF/JS-gated
    — attempt then degrade honestly (never silent-success on empty WAF shell).
    """

    BASE_URL = "https://tradingeconomics.com"

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
                self._te_main_status = "ok"
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
        Try SSR table, ?partial=calendar, then optional Playwright.
        Returns [] on WAF/empty and sets self._te_main_status honestly.
        """
        url = f"{self.BASE_URL}/united-states/calendar"

        # First: full page (usually empty calendar shell + sidebar noise)
        r = self._session.get(url, timeout=20)
        r.raise_for_status()
        events = self._parse_calendar_html(r.text)
        if events:
            self._te_main_status = "ok_ssr"
            return events

        # Detect JS/WAF shell honestly
        if "calendar-table" in r.text and r.text.count("<tr") <= 2:
            self._te_main_status = "js_shell_empty_rows"

        # Second: partial endpoint (often captcha/403/405)
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
                events = self._parse_calendar_html(pr.text)
                if events:
                    self._te_main_status = "ok_partial"
                    return events
            if waf or pr.status_code in (403, 405, 429):
                self._te_main_status = f"waf_blocked_status_{pr.status_code}"
            elif self._te_main_status == "not_attempted":
                self._te_main_status = f"partial_empty_status_{pr.status_code}"
            logger.debug(
                "TE main partial unavailable status=%s waf=%s",
                pr.status_code,
                waf,
            )
        except Exception as e:
            self._te_main_status = f"partial_error:{e}"
            logger.debug("TE partial fetch failed: %s", e)

        # Third: optional Playwright (often 403 to headless).
        # Skip after a known process-level 403 unless TE_CALENDAR_PLAYWRIGHT=1.
        global _TE_MAIN_PW_BLOCKED
        force_pw = os.environ.get("TE_CALENDAR_PLAYWRIGHT", "").strip() in ("1", "true", "True")
        if _TE_MAIN_PW_BLOCKED and not force_pw:
            self._te_main_status = (
                f"{self._te_main_status}|playwright_skipped_known_403"
                if self._te_main_status not in ("not_attempted",)
                else "playwright_skipped_known_403"
            )
            return []

        pw_events = self._browser_scrape_main_calendar(url)
        if pw_events:
            self._te_main_status = "ok_playwright"
            return pw_events

        if self._te_main_status in ("not_attempted",):
            self._te_main_status = "empty_no_rows"
        return []

    def _browser_scrape_main_calendar(self, url: str) -> List[TEEvent]:
        """Optional Playwright load of TE main calendar. Prefer existing pattern."""
        global _TE_MAIN_PW_BLOCKED
        # Sync Playwright cannot run inside an asyncio loop (FastAPI request threads
        # that already have a loop → RuntimeError). Skip honestly in that case.
        try:
            import asyncio

            asyncio.get_running_loop()
            self._te_main_status = (
                f"{self._te_main_status}|playwright_skipped_async_loop"
                if self._te_main_status not in ("not_attempted",)
                else "playwright_skipped_async_loop"
            )
            return []
        except RuntimeError:
            pass  # no running loop — safe for sync Playwright

        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            if not str(self._te_main_status).startswith("waf") and "js_shell" not in self._te_main_status:
                self._te_main_status = "playwright_unavailable"
            return []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent=self._session.headers["User-Agent"],
                    viewport={"width": 1280, "height": 900},
                )
                page = context.new_page()
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                status = resp.status if resp else 0
                if status == 403:
                    _TE_MAIN_PW_BLOCKED = True
                    self._te_main_status = "playwright_403_access_denied"
                    browser.close()
                    return []
                try:
                    page.wait_for_selector(
                        "#calendar table tr td, table.calendar-table tr td, table tr td",
                        timeout=12000,
                    )
                except Exception:
                    pass
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                events = self._parse_calendar_html(html)
                if not events:
                    self._te_main_status = f"playwright_empty_status_{status}"
                return events
        except Exception as e:
            self._te_main_status = f"playwright_error:{e}"
            logger.debug("Playwright TE main failed: %s", e)
            return []

    def _parse_calendar_html(self, html: str) -> List[TEEvent]:
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
                        source="te",
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

    # ── Source: ForexFactory week JSON ───────────────────────────────────

    def _fetch_forexfactory_weeks(self) -> List[TEEvent]:
        """Fetch this-week + next-week FF JSON. Label source honestly as forexfactory."""
        events: List[TEEvent] = []
        notes: List[str] = []

        for label, url in (("thisweek", FF_THISWEEK_URL), ("nextweek", FF_NEXTWEEK_URL)):
            try:
                r = self._session.get(url, timeout=15)
                if r.status_code == 404:
                    notes.append(f"{label}=404")
                    continue
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, list):
                    notes.append(f"{label}=bad_json")
                    continue
                week_events = self._parse_forexfactory_payload(data)
                events.extend(week_events)
                notes.append(f"{label}={len(week_events)}")
            except Exception as e:
                notes.append(f"{label}=err:{e}")

        self._source_notes["forexfactory"] = "; ".join(notes) if notes else "empty"
        return events

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
            imp_map = {"High": "CRITICAL", "Medium": "HIGH", "Low": "MEDIUM", "Holiday": "LOW"}
            importance = imp_map.get(impact, _classify_importance(title))
            # Prefer keyword classification when High/Medium would under-rank CPI etc.
            kw = _classify_importance(title)
            if kw == "CRITICAL":
                importance = "CRITICAL"
            elif kw == "HIGH" and importance not in ("CRITICAL",):
                importance = "HIGH"

            events.append(
                TEEvent(
                    date=iso,  # keep ISO in date; parser handles it
                    time="",
                    event=title,
                    actual=_normalize_cell(str(raw.get("actual") or "")),
                    previous=_normalize_cell(str(raw.get("previous") or "")),
                    consensus=_normalize_cell(str(raw.get("forecast") or "")),
                    forecast=_normalize_cell(str(raw.get("forecast") or "")),
                    importance=importance,
                    source="forexfactory",
                )
            )
        return events

    @staticmethod
    def _merge_events(primary: List[TEEvent], secondary: List[TEEvent]) -> List[TEEvent]:
        """Dedupe by (approx date, normalized event name); prefer richer consensus."""

        def key(e: TEEvent) -> Tuple[str, str]:
            dt = TECalendarScraper._parse_event_datetime(e)
            day = dt.strftime("%Y-%m-%d") if dt else e.date[:10]
            name = re.sub(r"\s+", " ", e.event.lower())
            name = re.sub(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*", "", name)
            name = re.sub(r"[^a-z0-9 ]", "", name).strip()
            return (day, name)

        by_key: Dict[Tuple[str, str], TEEvent] = {}
        for e in primary:
            by_key[key(e)] = e
        for e in secondary:
            k = key(e)
            if k not in by_key:
                by_key[k] = e
                continue
            existing = by_key[k]
            # Prefer entry with consensus / actual filled; prefer te_indicator consensus over FF
            if (not existing.has_consensus and e.has_consensus) or (
                not existing.has_actual and e.has_actual
            ):
                by_key[k] = e
            elif e.source == "te_indicator" and e.has_consensus and existing.source == "forexfactory":
                # Keep FF timing/name but prefer TE consensus numbers when both exist
                merged = TEEvent(
                    date=existing.date,
                    time=existing.time or e.time,
                    event=existing.event,
                    actual=existing.actual or e.actual,
                    previous=e.previous or existing.previous,
                    consensus=e.consensus or existing.consensus,
                    forecast=e.forecast or existing.forecast,
                    importance=existing.importance
                    if _classify_importance(existing.event) == existing.importance
                    else e.importance,
                    source="forexfactory+te_indicator",
                )
                by_key[k] = merged
        return list(by_key.values())


# ── Module test ──
if __name__ == "__main__":
    import json
    from collections import Counter

    logging.basicConfig(level=logging.INFO)

    scraper = TECalendarScraper()
    all_events = scraper.get_us_calendar()
    print(f"\n📅 Total US events: {len(all_events)}")
    print(f"   sources: {scraper.last_sources}")
    print(f"   te_main_status: {scraper.te_main_status}")
    print(f"   source_notes: {scraper.source_notes}")
    print(f"   error: {scraper.last_error}")

    imp_counts = Counter(e.importance for e in all_events)
    print(f"   CRITICAL: {imp_counts.get('CRITICAL', 0)}")
    print(f"   HIGH:     {imp_counts.get('HIGH', 0)}")
    print(f"   MEDIUM:   {imp_counts.get('MEDIUM', 0)}")
    print(f"   LOW:      {imp_counts.get('LOW', 0)}")
    print(f"   by_source: {Counter(e.source for e in all_events)}")

    print("\n🔥 UPCOMING CRITICAL EVENTS:")
    for e in scraper.get_upcoming_critical():
        print(f"   {e.date} {e.time} | {e.event} [{e.source}]")
        if e.has_consensus:
            print(f"     Consensus: {e.consensus} | Forecast: {e.forecast} | Previous: {e.previous}")

    print("\n📊 NEXT 14d HIGH+CRITICAL:")
    for e in scraper.get_upcoming(days=14):
        if e.importance in ("CRITICAL", "HIGH"):
            print(
                f"   {e.date} {e.time:8s} | {e.event[:40]:40s} | "
                f"C={e.consensus or '—':8s} F={e.forecast or '—':8s} [{e.source}]"
            )
