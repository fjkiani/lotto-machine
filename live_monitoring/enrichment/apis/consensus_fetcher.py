"""
📊 Consensus Forecast Fetcher — Tavily-Powered

Solves the forecast gap: FRED has actuals but NO consensus forecasts.
This module uses Tavily to scrape Wall Street consensus numbers
from financial news BEFORE each CRITICAL release.

How it works:
  1. Called 24h before a CRITICAL release (CPI, GDP, FOMC, NFP)
  2. Queries Tavily: "CPI consensus forecast estimate March 2026 economists expect"
  3. Extracts the numeric estimate from the answer
  4. Caches in SQLite — one query per CRITICAL release per month
  5. Returns the consensus for true surprise scoring: (actual - consensus)

Budget: ~5-6 Tavily calls/month (only CRITICAL releases)
"""

import os
import re
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache DB path
_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "consensus_cache.db"


class ConsensusFetcher:
    """Fetch and cache Wall Street consensus forecasts using Tavily."""

    # Map release short_names to specific search queries
    QUERY_TEMPLATES = {
        "CPI": "CPI consensus forecast estimate {month} {year} economists expect month over month core inflation",
        "GDP": "GDP growth estimate {quarter} {year} economists forecast consensus annualized",
        "NFP": "non-farm payrolls forecast consensus {month} {year} jobs added economists expect",
        "Employment": "unemployment rate forecast consensus {month} {year} economists expect",
        "JOLTS": "JOLTS job openings forecast consensus {month} {year} economists expect",
        "Retail Sales": "retail sales forecast consensus {month} {year} month over month change",
        "PCE": "PCE price index forecast consensus {month} {year} economists expect month over month",
        "PPI": "PPI producer price index forecast consensus {month} {year} month over month",
        "FOMC": "FOMC interest rate decision forecast {month} {year} market expects hold cut",
    }

    # Regex patterns to extract numeric consensus from Tavily answer
    EXTRACT_PATTERNS = [
        r'(\d+\.?\d*)%\s*(?:month.over.month|MoM|m/m)',
        r'(?:expect|forecast|consensus|estimate)[^\d]*(\d+\.?\d*)%',
        r'(\d+\.?\d*)%\s*(?:increase|decrease|growth|decline)',
        r'(\d{1,3}(?:,\d{3})*)\s*(?:jobs|openings|positions)',
    ]

    def __init__(self):
        self._init_db()
        self._tavily = None

    def _init_db(self):
        """Initialize SQLite cache for consensus forecasts."""
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS consensus_cache (
                release_name TEXT,
                release_date TEXT,
                consensus_value TEXT,
                raw_answer TEXT,
                source_url TEXT,
                source_score REAL,
                fetched_at TEXT,
                PRIMARY KEY (release_name, release_date)
            )
        """)
        conn.commit()
        conn.close()

    def _get_tavily(self):
        if self._tavily is None:
            from live_monitoring.enrichment.apis.tavily_client import TavilySearchClient
            self._tavily = TavilySearchClient()
        return self._tavily

    def get_consensus(self, release_name: str, release_date: str) -> dict:
        """
        Get consensus forecast for a release.

        Args:
            release_name: Short name (CPI, GDP, NFP, FOMC, etc.)
            release_date: Date string (YYYY-MM-DD)

        Returns:
            {
                "consensus": "0.3%",
                "raw_answer": "Economists expect...",
                "source": "morningstar.com",
                "score": 0.999,
                "cached": True/False,
            }
        """
        # Check cache first
        cached = self._check_cache(release_name, release_date)
        if cached:
            logger.info(f"📊 Consensus cache HIT: {release_name} {release_date} = {cached['consensus']}")
            return {**cached, "cached": True}

        # Query Tavily
        result = self._fetch_from_tavily(release_name, release_date)
        if result:
            self._save_cache(release_name, release_date, result)
            logger.info(f"📊 Consensus FETCHED: {release_name} {release_date} = {result['consensus']}")
            return {**result, "cached": False}

        return {"consensus": None, "raw_answer": None, "source": None, "score": 0, "cached": False}

    def _check_cache(self, release_name: str, release_date: str) -> Optional[dict]:
        conn = sqlite3.connect(str(_DB_PATH))
        row = conn.execute(
            "SELECT consensus_value, raw_answer, source_url, source_score FROM consensus_cache WHERE release_name=? AND release_date=?",
            (release_name, release_date),
        ).fetchone()
        conn.close()
        if row:
            return {"consensus": row[0], "raw_answer": row[1], "source": row[2], "score": row[3]}
        return None

    def _save_cache(self, release_name: str, release_date: str, result: dict):
        conn = sqlite3.connect(str(_DB_PATH))
        conn.execute(
            "INSERT OR REPLACE INTO consensus_cache (release_name, release_date, consensus_value, raw_answer, source_url, source_score, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (release_name, release_date, result["consensus"], result["raw_answer"], result["source"], result["score"], datetime.utcnow().isoformat()),
        )
        conn.commit()
        conn.close()

    def _fetch_from_tavily(self, release_name: str, release_date: str) -> Optional[dict]:
        """Query Tavily for consensus forecast."""
        tc = self._get_tavily()

        # Build query from template
        dt = datetime.strptime(release_date, "%Y-%m-%d")
        month = dt.strftime("%B")
        year = dt.strftime("%Y")
        quarter = f"Q{(dt.month - 1) // 3 + 1}"

        template = self.QUERY_TEMPLATES.get(release_name)
        if not template:
            query = f"{release_name} economic release forecast consensus {month} {year} economists expect"
        else:
            query = template.format(month=month, year=year, quarter=quarter)

        try:
            result = tc.search(query, max_results=3)
            answer = result.get("answer", "")
            citations = result.get("citations", [])

            # Extract numeric consensus from answer
            consensus = self._extract_number(answer, release_name)

            top_source = citations[0] if citations else {}
            return {
                "consensus": consensus,
                "raw_answer": answer[:500],
                "source": top_source.get("url", ""),
                "score": top_source.get("score", 0),
            }
        except Exception as e:
            logger.error(f"Tavily consensus fetch failed for {release_name}: {e}")
            return None

    def _extract_number(self, text: str, release_name: str) -> Optional[str]:
        """Extract the consensus number from Tavily's answer text."""
        if not text:
            return None

        for pattern in self.EXTRACT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        # Fallback: return first percentage found
        pct = re.search(r'(\d+\.?\d*)%', text)
        if pct:
            return pct.group(0)

        return None


# ── Module test ──
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()

    cf = ConsensusFetcher()

    # Test: Get CPI consensus for upcoming release
    result = cf.get_consensus("CPI", "2026-03-12")
    print(f"\n📊 CPI Consensus for 2026-03-12:")
    print(f"   Consensus: {result['consensus']}")
    print(f"   Answer: {result['raw_answer'][:200]}")
    print(f"   Source: {result['source']}")
    print(f"   Score: {result['score']}")
    print(f"   Cached: {result['cached']}")
