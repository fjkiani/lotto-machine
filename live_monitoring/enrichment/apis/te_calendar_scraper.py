"""
📅 Trading Economics Calendar Scraper — Dynamic Economic Calendar

Primary path (2026-11+): TE main calendar is JS/WAF-gated (`?partial=calendar`
returns captcha). Live events come from:

  1. TE indicator pages (SSR calendar tables — Actual/Previous/Consensus/TEForecast)
  2. ForexFactory NFS JSON (`ff_calendar_thisweek.json`) for the current week
  3. Legacy HTML table parse if TE ever re-enables SSR rows

No API key required. No static April/March event dictionaries as source of truth.
Caches results for 1 hour.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Importance classification based on event name ──
CRITICAL_EVENTS = {
    "inflation rate",
    "core inflation rate",
    "cpi",
    "cpi s.a",
    "non farm payrolls",
    "nonfarm payrolls",
    "employment change",
    "gdp growth rate",
    "gdp annual",
    "gdp price index",
    "fed interest rate decision",
    "fomc",
    "pce price index",
    "core pce price index",
    "unemployment rate",
}

HIGH_EVENTS = {
    "initial jobless claims",
    "jolts job openings",
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
    "philadelphia fed",
    "nahb housing",
    "current account",
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
    "nfib business",
    "jolts",
    "continuing jobless",
}

# High-impact TE indicator pages that still SSR a calendar table.
TE_INDICATOR_SLUGS: Tuple[str, ...] = (
    "inflation-cpi",
    "core-inflation-rate",
    "producer-prices",
    "gdp-growth",
    "non-farm-payrolls",
    "unemployment-rate",
    "adp-employment-change",
    "jobless-claims",
    "continuing-jobless-claims",
    "interest-rate",
    "retail-sales",
    "business-confidence",  # ISM Manufacturing PMI
    "consumer-confidence",  # Michigan / CB variants
    "existing-home-sales",
    "housing-starts",
    "building-permits",
    "durable-goods-orders",
    "factory-orders",
    "industrial-production",
    "balance-of-trade",
    "personal-spending",
    "personal-income",
)

FF_THISWEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


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

    Prefer live TE indicator SSR tables + ForexFactory week JSON.
    Main TE calendar page is WAF/partial-gated — attempt then degrade honestly.
    """

    BASE_URL = "https://tradingeconomics.com"

    def __init__(self, cache_ttl: int = 3600):
        self._cache: Dict[str, List[TEEvent]] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        self._last_error: Optional[str] = None
        self._last_sources: List[str] = []
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
        logger.info("📅 TECalendarScraper initialized (indicator pages + FF fallback)")

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_sources(self) -> List[str]:
        return list(self._last_sources)

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def get_us_calendar(self) -> List[TEEvent]:
        """Get US economic events (merged live sources)."""
        cache_key = "us_calendar"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        self._last_error = None
        self._last_sources = []
        events: List[TEEvent] = []
        errors: List[str] = []

        # 1) Attempt legacy / partial main calendar (usually WAF-blocked now)
        try:
            main = self._scrape_main_calendar()
            if main:
                events.extend(main)
                self._last_sources.append("te_main")
        except Exception as e:
            errors.append(f"te_main:{e}")

        # 2) Indicator SSR pages (reliable as of 2026-11)
        try:
            indicator_events = self._scrape_indicator_calendars()
            if indicator_events:
                events = self._merge_events(events, indicator_events)
                self._last_sources.append("te_indicator")
        except Exception as e:
            errors.append(f"te_indicator:{e}")

        # 3) ForexFactory this-week JSON
        try:
            ff = self._fetch_forexfactory_week()
            if ff:
                events = self._merge_events(events, ff)
                self._last_sources.append("forexfactory")
        except Exception as e:
            errors.append(f"forexfactory:{e}")

        if not events:
            self._last_error = "; ".join(errors) if errors else "no calendar sources returned events"
            logger.error("❌ Calendar scrape empty: %s", self._last_error)
        else:
            logger.info(
                "📅 Scraped %d US economic events via %s",
                len(events),
                ",".join(self._last_sources) or "unknown",
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
        """Try SSR table or ?partial=calendar; return [] on WAF/empty."""
        url = f"{self.BASE_URL}/united-states/calendar"
        # First: full page (usually empty body now)
        r = self._session.get(url, timeout=20)
        r.raise_for_status()
        events = self._parse_calendar_html(r.text)
        if events:
            return events

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
            if pr.status_code == 200 and pr.headers.get("X-TE-Partial") == "calendar":
                events = self._parse_calendar_html(pr.text)
                if events:
                    return events
            logger.debug(
                "TE main partial unavailable status=%s waf=%s (expected; using indicator/FF fallbacks)",
                pr.status_code,
                pr.headers.get("x-amzn-waf-action"),
            )
        except Exception as e:
            logger.debug("TE partial fetch failed: %s", e)
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

    def _scrape_indicator_calendars(self) -> List[TEEvent]:
        """Scrape SSR calendar tables from key US indicator pages."""
        events: List[TEEvent] = []
        for slug in TE_INDICATOR_SLUGS:
            try:
                url = f"{self.BASE_URL}/united-states/{slug}"
                r = self._session.get(url, timeout=18)
                if r.status_code != 200:
                    continue
                page_events = self._parse_indicator_calendar_table(r.text)
                events.extend(page_events)
            except Exception as e:
                logger.debug("Indicator scrape failed for %s: %s", slug, e)
        return events

    def _parse_indicator_calendar_table(self, html: str) -> List[TEEvent]:
        soup = BeautifulSoup(html, "html.parser")
        events: List[TEEvent] = []
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            header_blob = " ".join(headers)
            if "consensus" not in header_blob and "teforecast" not in header_blob:
                continue
            if "actual" not in header_blob:
                continue

            for tr in table.find_all("tr")[1:]:
                cells = [_normalize_cell(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
                if len(cells) < 4:
                    continue
                # Typical: [date, time, event, reference?, actual, previous, consensus, teforecast]
                # Some pages fold reference into a separate column.
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

    def _fetch_forexfactory_week(self) -> List[TEEvent]:
        r = self._session.get(FF_THISWEEK_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
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
            # Prefer entry with consensus / actual filled
            if (not existing.has_consensus and e.has_consensus) or (
                not existing.has_actual and e.has_actual
            ):
                by_key[k] = e
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
    print(f"   error: {scraper.last_error}")

    imp_counts = Counter(e.importance for e in all_events)
    print(f"   CRITICAL: {imp_counts.get('CRITICAL', 0)}")
    print(f"   HIGH:     {imp_counts.get('HIGH', 0)}")
    print(f"   MEDIUM:   {imp_counts.get('MEDIUM', 0)}")
    print(f"   LOW:      {imp_counts.get('LOW', 0)}")

    print("\n🔥 UPCOMING CRITICAL EVENTS:")
    for e in scraper.get_upcoming_critical():
        print(f"   {e.date} {e.time} | {e.event} [{e.source}]")
        if e.has_consensus:
            print(f"     Consensus: {e.consensus} | Forecast: {e.forecast} | Previous: {e.previous}")

    print("\n📊 NEXT 7d HIGH+CRITICAL:")
    for e in scraper.get_upcoming(days=14):
        if e.importance in ("CRITICAL", "HIGH"):
            print(
                f"   {e.date} {e.time:8s} | {e.event[:40]:40s} | "
                f"C={e.consensus or '—':8s} F={e.forecast or '—':8s}"
            )
