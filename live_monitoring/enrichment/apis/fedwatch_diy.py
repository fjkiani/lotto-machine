"""
FedWatch Intelligence Engine — Multi-Source FOMC Rate Probability Tracker

Sources (in priority order):
  1. Diffbot   → Scrapes financial news/data pages for FedWatch probabilities
  2. yfinance  → Calculates from 30-Day Fed Funds Futures (ZQ) using CME methodology
  3. Perplexity → Fallback AI-powered search for latest FedWatch data

No CME API key required. Updates when markets are open.

Usage:
    engine = FedWatchEngine()
    data = engine.get_probabilities()
    print(data['next_meeting'])   # Next FOMC meeting probabilities
    print(data['rate_path'])      # Full rate path
    print(engine.get_narrative()) # Narrative text for agents
"""

import logging
import json
import os
import re
import calendar
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)

# ─── Dependencies ───────────────────────────────────────────────────────────

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed — futures source disabled")


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class FOMCMeeting:
    date: str
    label: str
    month_code: str
    implied_rate: float = 0.0
    post_meeting_rate: float = 0.0
    delta_bps: float = 0.0
    p_cut_25: float = 0.0
    p_hold: float = 0.0
    p_hike_25: float = 0.0
    cumulative_bps: float = 0.0
    days_away: int = 0


# ─── FOMC Schedule ──────────────────────────────────────────────────────────

FOMC_2026 = [
    {"date": "2026-01-29", "label": "Jan 28-29",  "code": "F26"},
    {"date": "2026-03-19", "label": "Mar 18-19",  "code": "H26"},
    {"date": "2026-05-07", "label": "May 6-7",    "code": "K26"},
    {"date": "2026-06-18", "label": "Jun 17-18",  "code": "M26"},
    {"date": "2026-07-30", "label": "Jul 29-30",  "code": "N26"},
    {"date": "2026-09-17", "label": "Sep 16-17",  "code": "U26"},
    {"date": "2026-11-05", "label": "Nov 4-5",    "code": "X26"},
    {"date": "2026-12-17", "label": "Dec 16-17",  "code": "Z26"},
]


# ─── Source 1: Diffbot Scraper ──────────────────────────────────────────────

class DiffbotSource:
    """Scrapes FedWatch probabilities from financial news pages via Diffbot."""

    # Pages that commonly display FedWatch-style probability data
    TARGETS = [
        "https://www.barchart.com/economy/interest-rates/fed-funds-rate",
        "https://www.investing.com/central-banks/fed-rate-monitor",
        "https://finance.yahoo.com/markets/rates-bonds/",
    ]

    def __init__(self, token: str):
        self.token = token
        self.api_base = "https://api.diffbot.com/v3"
        logger.info("🔮 DiffbotSource initialized")

    def fetch(self) -> Optional[Dict[str, Any]]:
        """Try to extract FedWatch data from any available target."""
        if not REQUESTS_AVAILABLE:
            return None

        for url in self.TARGETS:
            try:
                data = self._scrape_page(url)
                if data and "error" not in data:
                    data["diffbot_source"] = url
                    return data
            except Exception as e:
                logger.debug(f"Diffbot failed on {url}: {e}")
                continue
        return None

    def _scrape_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a single page via Diffbot Article API."""
        api_url = f"{self.api_base}/article?token={self.token}&url={url}&timeout=12000"
        r = requests.get(api_url, timeout=15)

        if r.status_code == 429:
            logger.warning("Diffbot rate limited (429)")
            return None
        if r.status_code != 200:
            return None

        data = r.json()
        objects = data.get("objects", [])
        if not objects:
            return None

        text = objects[0].get("text", "")
        if len(text) < 50:
            return None

        # Parse probabilities from extracted text
        return self._parse_fedwatch_text(text)

    def _parse_fedwatch_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract FedWatch probability data from scraped text."""
        result = {"source": "diffbot", "raw_text": text[:500]}

        # Look for patterns like "94% probability" or "Cut: 22.4%"
        prob_pattern = re.compile(
            r'(\d{1,3}(?:\.\d{1,2})?)\s*%\s*(?:probability|chance)',
            re.IGNORECASE
        )
        cut_pattern = re.compile(r'cut.*?(\d{1,3}(?:\.\d{1,2})?)\s*%', re.IGNORECASE)
        hold_pattern = re.compile(r'hold.*?(\d{1,3}(?:\.\d{1,2})?)\s*%', re.IGNORECASE)
        rate_pattern = re.compile(r'(\d\.\d{2})\s*%?\s*-\s*(\d\.\d{2})\s*%', re.IGNORECASE)

        # Extract rate range
        rate_match = rate_pattern.search(text)
        if rate_match:
            result["current_range"] = [float(rate_match.group(1)), float(rate_match.group(2))]

        # Extract probabilities
        cuts = cut_pattern.findall(text)
        holds = hold_pattern.findall(text)
        if cuts:
            result["p_cut_25"] = float(cuts[0])
        if holds:
            result["p_hold"] = float(holds[0])

        return result if len(result) > 2 else None

    def search_news(self, query: str = "CME FedWatch probability") -> List[Dict]:
        """Search Diffbot Knowledge Graph for recent FedWatch articles."""
        if not REQUESTS_AVAILABLE:
            return []
        try:
            import urllib.parse
            q = urllib.parse.quote(f'type:Article strict:text:"{query}" sortBy:date')
            url = f"https://kg.diffbot.com/kg/v3/dql?token={self.token}&query={q}&size=5"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return data.get("data", [])
        except Exception as e:
            logger.debug(f"Diffbot KG search failed: {e}")
        return []


# ─── Source 2: Futures Calculator (CME Methodology) ─────────────────────────

class FuturesSource:
    """Calculates FedWatch probabilities from Fed Funds Futures via yfinance."""

    def __init__(self):
        logger.info("📊 FuturesSource initialized")

    def fetch(self) -> Optional[Dict[str, Any]]:
        """Calculate probabilities from ZQ futures prices."""
        if not YFINANCE_AVAILABLE:
            return None

        today = date.today()
        today_str = today.strftime("%Y-%m-%d")

        # Filter to future meetings
        future_meetings = [m for m in FOMC_2026 if m["date"] >= today_str]
        if not future_meetings:
            return None

        # Fetch all futures prices
        prices = {}
        for mtg in future_meetings:
            price = self._get_price(mtg["code"])
            if price:
                prices[mtg["code"]] = price

        if not prices:
            return None

        # Get current rate from front month
        front_code = future_meetings[0]["code"]
        if front_code not in prices:
            return None

        current_implied = round(100.0 - prices[front_code], 4)
        current_range = self._infer_range(current_implied)
        current_mid = (current_range[0] + current_range[1]) / 2

        # Calculate per-meeting probabilities using CME day-weighted formula
        meetings = []
        prev_rate = current_mid

        for mtg in future_meetings:
            code = mtg["code"]
            if code not in prices:
                continue

            d = date.fromisoformat(mtg["date"])
            days_in_month = calendar.monthrange(d.year, d.month)[1]
            meeting_day = d.day
            days_before = meeting_day - 1
            days_after = days_in_month - meeting_day + 1

            futures_implied = round(100.0 - prices[code], 4)

            # CME formula: extract post-meeting rate
            post_rate = (futures_implied * days_in_month - days_before * prev_rate) / days_after
            post_rate = round(post_rate, 4)

            # Clamp unreasonable values from edge cases (meeting near month end)
            if days_after <= 3:
                # Late-month meeting: use simple difference instead
                post_rate = futures_implied
                change_bps = round((prev_rate - futures_implied) * 100, 1)
            else:
                change_bps = round((prev_rate - post_rate) * 100, 1)

            # Probability calculation
            if abs(change_bps) < 2:
                p_cut_25, p_hold, p_hike_25 = 0, 100, 0
            elif change_bps > 0:
                p_cut_25 = min(round(change_bps / 25 * 100, 1), 100)
                p_hold = round(100 - p_cut_25, 1)
                p_hike_25 = 0
            else:
                p_hike_25 = min(round(-change_bps / 25 * 100, 1), 100)
                p_hold = round(100 - p_hike_25, 1)
                p_cut_25 = 0

            cumul = round((current_mid - post_rate) * 100, 1)
            days_away = (d - today).days

            meeting = FOMCMeeting(
                date=mtg["date"],
                label=mtg["label"],
                month_code=code,
                implied_rate=futures_implied,
                post_meeting_rate=post_rate,
                delta_bps=change_bps,
                p_cut_25=max(p_cut_25, 0),
                p_hold=max(p_hold, 0),
                p_hike_25=max(p_hike_25, 0),
                cumulative_bps=cumul,
                days_away=days_away,
            )
            meetings.append(meeting)
            prev_rate = post_rate

        if not meetings:
            return None

        # Summary
        total_cuts_bps = meetings[-1].cumulative_bps
        n_cuts = round(total_cuts_bps / 25, 1)
        direction = "cuts" if total_cuts_bps > 0 else "hikes" if total_cuts_bps < 0 else "no change"

        return {
            "source": "yfinance_futures",
            "current_rate": current_implied,
            "current_range": list(current_range),
            "current_midpoint": current_mid,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "next_meeting": asdict(meetings[0]),
            "rate_path": [asdict(m) for m in meetings],
            "total_cuts_bps": total_cuts_bps,
            "total_cuts_count": n_cuts,
            "summary": f"Market pricing {abs(total_cuts_bps):.0f}bp of {direction} ({abs(n_cuts):.1f} moves) through {meetings[-1].label}",
        }

    def _get_price(self, month_code: str) -> Optional[float]:
        try:
            t = yf.Ticker(f"ZQ{month_code}.CBT")
            h = t.history(period="5d")
            return float(h["Close"].iloc[-1]) if not h.empty else None
        except:
            return None

    def _infer_range(self, rate: float) -> tuple:
        ranges = [(i * 0.25, (i + 1) * 0.25) for i in range(8, 22)]
        for lo, hi in ranges:
            if lo <= rate <= hi:
                return (lo, hi)
        return (3.50, 3.75)


# ─── Main Engine ────────────────────────────────────────────────────────────

class FedWatchEngine:
    """
    Multi-source FedWatch Intelligence Engine.
    
    Tries sources in priority order:
      1. Diffbot (if token available) — scrapes real probability numbers
      2. Futures calculator           — derives from live ZQ prices
    
    Usage:
        engine = FedWatchEngine()
        data = engine.get_probabilities()
        text = engine.get_narrative()
    """

    CACHE_TTL = 300  # 5 minutes

    def __init__(self, diffbot_token: Optional[str] = None):
        self.diffbot_token = diffbot_token or os.environ.get("DIFFBOT_TOKEN", "")
        self.sources = []

        # Initialize sources
        if self.diffbot_token:
            self.sources.append(("diffbot", DiffbotSource(self.diffbot_token)))
        self.sources.append(("futures", FuturesSource()))

        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0
        logger.info(f"🏦 FedWatchEngine initialized with {len(self.sources)} sources")

    def get_probabilities(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get FedWatch probabilities from the best available source.

        Returns dict with keys:
            current_rate, current_range, next_meeting, rate_path, summary, source
        """
        now = datetime.now().timestamp()
        if not force_refresh and self._cache and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache

        for name, source in self.sources:
            try:
                data = source.fetch()
                if data and "error" not in data:
                    data["engine_source"] = name
                    self._cache = data
                    self._cache_time = now
                    logger.info(f"🏦 FedWatch data from {name}: {data.get('summary', 'OK')}")
                    return data
            except Exception as e:
                logger.warning(f"Source {name} failed: {e}")
                continue

        return {"error": "All FedWatch sources failed", "sources_tried": [n for n, _ in self.sources]}

    def get_cut_probability(self, meeting_index: int = 0) -> Optional[float]:
        """Get probability of a 25bp cut at the next (or Nth) FOMC meeting."""
        data = self.get_probabilities()
        path = data.get("rate_path", [])
        if meeting_index < len(path):
            return path[meeting_index].get("p_cut_25", 0)
        return None

    def get_narrative(self) -> str:
        """Generate narrative-ready text for the SavageAgents."""
        data = self.get_probabilities()
        if "error" in data:
            return f"⚠️ FedWatch data unavailable: {data['error']}"

        lines = []
        cr = data.get("current_range", [])
        if cr:
            lines.append(f"Fed Funds Rate: {data.get('current_rate', '?'):.2f}% (range: {cr[0]:.2f}-{cr[1]:.2f}%)")

        lines.append(f"Market Outlook: {data.get('summary', 'N/A')}")
        lines.append(f"Source: {data.get('engine_source', 'unknown')}")

        next_mtg = data.get("next_meeting")
        if next_mtg:
            lines.append(
                f"Next FOMC ({next_mtg['label']}, {next_mtg['days_away']}d): "
                f"Hold {next_mtg['p_hold']:.0f}% | Cut {next_mtg['p_cut_25']:.0f}% | Hike {next_mtg['p_hike_25']:.0f}%"
            )

        for m in data.get("rate_path", [])[1:4]:
            lines.append(
                f"  {m['label']} ({m['days_away']}d): "
                f"Hold {m['p_hold']:.0f}% | Cut {m['p_cut_25']:.0f}% | Cumul: {m['cumulative_bps']:+.0f}bp"
            )

        return "\n".join(lines)


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    token = os.environ.get("DIFFBOT_TOKEN", "a70dd1af6e654f5dbb12f3cd2d1406bb")
    engine = FedWatchEngine(diffbot_token=token)

    print("=" * 60)
    print("🏦 FedWatch Intelligence Engine — Live Test")
    print("=" * 60)

    data = engine.get_probabilities()
    print(json.dumps(data, indent=2))

    print("\n--- Narrative ---")
    print(engine.get_narrative())

    print(f"\nP(cut) at next meeting: {engine.get_cut_probability()}")
