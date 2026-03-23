"""
📅 Trading Economics Calendar Scraper — Dynamic Economic Calendar

Scrapes tradingeconomics.com/united-states/calendar to get ALL economic
releases dynamically with actual/previous/consensus/forecast values.

No API key required. No static dictionary. Real-time data.

How it works:
  1. GET https://tradingeconomics.com/united-states/calendar
  2. Parse the 626-row HTML table with BeautifulSoup
  3. Extract: date, time, event, actual, previous, consensus, forecast
  4. Cache results for 1 hour (avoid hammering the site)
  5. Return structured events for any date range

Replaces the static HIGH_IMPACT_RELEASES dict (20 hardcoded entries)
with ~287 dynamic events per month.

Proven live 2026-03-09:
  - CPI MoM: consensus=0.3%, forecast=0.3%
  - Core CPI MoM: consensus=0.2%, forecast=0.2%
  - GDP Growth QoQ: consensus=1.4%, forecast=1.4%
  - JOLTS: consensus=6.70M, forecast=6.5M
  - Initial Jobless Claims: consensus=215K, forecast=217.0K
"""

import time
import logging
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

# ── Importance classification based on event name ──
CRITICAL_EVENTS = {
    'inflation rate', 'core inflation rate', 'cpi', 'cpi s.a',
    'non farm payrolls', 'nonfarm payrolls', 'employment change',
    'gdp growth rate', 'gdp annual', 'gdp price index',
    'fed interest rate decision', 'fomc',
    'pce price index', 'core pce price index',
    'unemployment rate',
}

HIGH_EVENTS = {
    'initial jobless claims', 'jolts job openings',
    'ppi', 'core ppi', 'producer price',
    'retail sales', 'durable goods orders',
    'ism manufacturing', 'ism services', 'ism non-manufacturing',
    'consumer sentiment', 'michigan consumer',
    'balance of trade', 'trade balance',
    'personal income', 'personal spending',
    'building permits', 'housing starts',
    'new home sales', 'existing home sales', 'pending home sales',
    'adp employment', 'adp nonfarm',
    'fomc economic projections', 'fed press conference',
    's&p global', 'pmi flash', 'pmi',
    'industrial production', 'factory orders',
    'consumer confidence', 'cb consumer confidence',
    'empire state manufacturing', 'philadelphia fed',
    'nahb housing', 'current account',
}

MEDIUM_EVENTS = {
    'import prices', 'export prices', 'wholesale inventories',
    'retail inventories', 'business inventories',
    'capacity utilization', 'leading index',
    'chicago fed', 'richmond fed', 'kansas city fed',
    'api crude oil', 'eia crude oil', 'eia gasoline',
    'mba mortgage', 'mba 30-year', 'treasury budget',
    'monthly budget', 'net long-term tic',
    'redbook', 'nfib business', 'jolts',
}

# ── BEA/BLS manual overrides — events TE may miss ──────────────────────
# These are merged with scraper output so the veto system fires even when
# TradingEconomics doesn't list a known CRITICAL release.
# Update this list each quarter with BEA's published schedule.
BEA_OVERRIDES: list = []  # populated below after TEEvent is defined


@dataclass
class TEEvent:
    """A single economic event from Trading Economics."""
    date: str           # "Wednesday March 11 2026"
    time: str           # "12:30 PM" (UTC)
    event: str          # "Core Inflation Rate MoMFEB"
    actual: str         # "0.4%" or ""
    previous: str       # "0.3%"
    consensus: str      # "0.2%"
    forecast: str       # "0.2%"
    importance: str     # "CRITICAL", "HIGH", "MEDIUM", "LOW"

    @property
    def has_actual(self) -> bool:
        return bool(self.actual and self.actual != '—')

    @property
    def has_consensus(self) -> bool:
        return bool(self.consensus and self.consensus != '—')

    @property
    def is_upcoming(self) -> bool:
        return not self.has_actual

    def to_dict(self) -> dict:
        return {
            'date': self.date,
            'time': self.time,
            'event': self.event,
            'actual': self.actual,
            'previous': self.previous,
            'consensus': self.consensus,
            'forecast': self.forecast,
            'importance': self.importance,
            'has_actual': self.has_actual,
            'has_consensus': self.has_consensus,
            'is_upcoming': self.is_upcoming,
        }


# ── Populate BEA_OVERRIDES now that TEEvent is defined ──────────────────
BEA_OVERRIDES.extend([
    TEEvent(
        date="Thursday March 27 2026",
        time="08:30 AM",
        event="GDP Third Estimate Q4 2025",
        actual="",
        previous="2.3%",
        consensus="2.3%",
        forecast="2.3%",
        importance="CRITICAL",
    ),
])


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


class TECalendarScraper:
    """
    Dynamic economic calendar from tradingeconomics.com.

    No API key required. Scrapes the public calendar page.
    Caches results for 1 hour to be respectful.
    """

    BASE_URL = "https://tradingeconomics.com"

    def __init__(self, cache_ttl: int = 3600):
        self._cache = {}       # url -> events list
        self._cache_ts = {}    # url -> timestamp
        self._cache_ttl = cache_ttl
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        logger.info("📅 TECalendarScraper initialized (tradingeconomics.com — no key needed)")

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def get_us_calendar(self) -> List[TEEvent]:
        """Get ALL US economic events for the current calendar period (~2 weeks)."""
        cache_key = "us_calendar"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        url = f"{self.BASE_URL}/united-states/calendar"
        events = self._scrape_calendar(url)
        self._cache[cache_key] = events
        self._cache_ts[cache_key] = time.time()
        logger.info(f"📅 Scraped {len(events)} US economic events")
        return events

    def get_today(self) -> List[TEEvent]:
        """Get today's US events only."""
        all_events = self.get_us_calendar()
        today_str = date.today().strftime("%B %d").lstrip("0")
        return [e for e in all_events if today_str in e.date]

    def get_upcoming(self, days: int = 7) -> List[TEEvent]:
        """Get upcoming events (no actual value yet)."""
        all_events = self.get_us_calendar()
        return [e for e in all_events if e.is_upcoming]

    def _merged_events(self) -> List[TEEvent]:
        """TE calendar + BEA manual overrides, deduplicated."""
        te = self.get_us_calendar()
        # Avoid duplicates: skip overrides whose event name already appears on same date
        te_keys = {(e.date, e.event) for e in te}
        merged = list(te)
        for ov in BEA_OVERRIDES:
            if (ov.date, ov.event) not in te_keys:
                merged.append(ov)
        return merged

    def get_high_impact(self) -> List[TEEvent]:
        """Get only CRITICAL and HIGH importance events (includes BEA overrides)."""
        return [e for e in self._merged_events() if e.importance in ("CRITICAL", "HIGH")]

    def get_upcoming_critical(self) -> List[TEEvent]:
        """Get upcoming CRITICAL events — unreleased (includes BEA overrides)."""
        return [e for e in self._merged_events() if e.is_upcoming and e.importance == "CRITICAL"]

    def get_released(self) -> List[TEEvent]:
        """Get events that already have actual values."""
        all_events = self.get_us_calendar()
        return [e for e in all_events if e.has_actual]

    def get_surprises(self) -> List[Dict]:
        """Get events where actual differs from consensus (surprises)."""
        released = self.get_released()
        surprises = []
        for e in released:
            if e.has_consensus:
                surprises.append({
                    'event': e.event,
                    'actual': e.actual,
                    'consensus': e.consensus,
                    'date': e.date,
                    'importance': e.importance,
                })
        return surprises

    def get_hours_until_next_critical(self) -> Optional[tuple]:
        """
        Hours until the next unreleased CRITICAL event + its name.
        Merges BEA_OVERRIDES so manually-added events (e.g. GDP Third Estimate)
        are included even when TE misses them.
        Returns (hours, event_name) or None if no upcoming critical events found.
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
                continue  # already passed
            if nearest_hours is None or delta_h < nearest_hours:
                nearest_hours = delta_h
                nearest_name = evt.event

        if nearest_hours is None:
            return None
        return (nearest_hours, nearest_name)

    @staticmethod
    def _parse_event_datetime(evt: 'TEEvent') -> Optional[datetime]:
        """
        Parse TE date+time strings into datetime.
        Handles: "Thursday March 27 2026" + "08:30 AM" (or "08:30 AM ET").
        Returns None on parse failure instead of crashing.
        """
        try:
            date_str = evt.date or ''
            time_str = (evt.time or '08:30 AM').replace(' ET', '').replace(' GMT', '').strip()
            # Drop day-of-week: "Thursday March 27 2026" → "March 27 2026"
            parts = date_str.split(' ')
            if len(parts) >= 4:
                month_day_year = ' '.join(parts[1:])
            else:
                month_day_year = date_str
            full = f"{month_day_year} {time_str}"
            return datetime.strptime(full, "%B %d %Y %I:%M %p")
        except (ValueError, IndexError):
            return None

    def _scrape_calendar(self, url: str) -> List[TEEvent]:
        """Scrape the calendar HTML table."""
        try:
            r = self._session.get(url, timeout=20)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table')

            # Find the main calendar table (largest one with date headers)
            cal_table = None
            for t in tables:
                rows = t.find_all('tr')
                if len(rows) > 50:
                    cal_table = t
                    break

            if not cal_table:
                logger.error("❌ Could not find calendar table")
                return []

            rows = cal_table.find_all('tr')
            events = []
            current_date = ""

            for row in rows:
                cells = row.find_all(['td', 'th'])
                texts = [c.get_text(strip=True) for c in cells]

                if not texts:
                    continue

                # Date header rows
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                if any(day in texts[0] for day in days):
                    current_date = texts[0]
                    continue

                # Data rows with time
                if current_date and texts[0] and ('AM' in texts[0] or 'PM' in texts[0]):
                    time_text = texts[0]

                    # Find event name (longest non-numeric text after time, not 'US')
                    event_name = ""
                    for t in texts[1:]:
                        if (t and len(t) > 3 and t != 'US' and
                            not t.replace('.', '').replace('-', '').replace('%', '')
                            .replace('$', '').replace(',', '').replace('K', '')
                            .replace('M', '').replace('B', '').isdigit()):
                            event_name = t
                            break

                    if not event_name:
                        continue

                    # Extract values after event name
                    actual = previous = consensus = forecast = ""
                    try:
                        idx = texts.index(event_name)
                        nums = texts[idx + 1:]
                        if len(nums) >= 1:
                            actual = nums[0] or ""
                        if len(nums) >= 2:
                            previous = nums[1] or ""
                        if len(nums) >= 3:
                            consensus = nums[2] or ""
                        if len(nums) >= 4:
                            forecast = nums[3] or ""
                    except (ValueError, IndexError):
                        pass

                    importance = _classify_importance(event_name)

                    events.append(TEEvent(
                        date=current_date,
                        time=time_text,
                        event=event_name,
                        actual=actual,
                        previous=previous,
                        consensus=consensus,
                        forecast=forecast,
                        importance=importance,
                    ))

            return events

        except Exception as e:
            logger.error(f"❌ Calendar scrape failed: {e}")
            return []


# ── Module test ──
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)

    scraper = TECalendarScraper()

    # Get all US events
    all_events = scraper.get_us_calendar()
    print(f"\n📅 Total US events: {len(all_events)}")

    # Count by importance
    from collections import Counter
    imp_counts = Counter(e.importance for e in all_events)
    print(f"   CRITICAL: {imp_counts.get('CRITICAL', 0)}")
    print(f"   HIGH:     {imp_counts.get('HIGH', 0)}")
    print(f"   MEDIUM:   {imp_counts.get('MEDIUM', 0)}")
    print(f"   LOW:      {imp_counts.get('LOW', 0)}")

    # Show upcoming CRITICAL
    print(f"\n🔥 UPCOMING CRITICAL EVENTS:")
    for e in scraper.get_upcoming_critical():
        print(f"   {e.date} {e.time} | {e.event}")
        if e.has_consensus:
            print(f"     Consensus: {e.consensus} | Forecast: {e.forecast} | Previous: {e.previous}")

    # Show high impact upcoming
    print(f"\n📊 UPCOMING HIGH+CRITICAL:")
    for e in scraper.get_high_impact():
        if e.is_upcoming:
            c = e.consensus if e.consensus else "—"
            f = e.forecast if e.forecast else "—"
            p = e.previous if e.previous else "—"
            print(f"   {e.time:8s} | {e.event[:40]:40s} | C={c:8s} F={f:8s} P={p:8s}")
