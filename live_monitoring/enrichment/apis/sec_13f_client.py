"""
SEC 13F Client — Institutional Holdings Intelligence from SEC EDGAR

Source: SEC EDGAR (data.sec.gov) — Free public API
Data:   13F-HR filings (quarterly institutional holdings > $100M AUM)
Auth:   None required (just User-Agent header)
Freshness: Quarterly (filed 45 days after quarter-end)

Tracks major hedge funds: Bridgewater, Soros, Citadel, Renaissance,
Point72, Two Sigma, D.E. Shaw, Millennium, Jane Street, AQR.
"""
import logging
import time
import requests
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Filing13F:
    """A single 13F filing record."""
    fund_name: str
    cik: str
    filing_date: str
    form_type: str  # 13F-HR, 13F-HR/A
    accession_number: str = ""


@dataclass
class InstitutionalSummary:
    """Summary of tracked fund filings."""
    filings: List[Filing13F] = field(default_factory=list)
    timestamp: str = ""
    source: str = "sec-edgar"


# ─── Fund Watchlist ─────────────────────────────────────────────────────────

# CIK numbers for major institutional investors
FUND_WATCHLIST = {
    "Bridgewater Associates": "0001350694",
    "Soros Fund Management": "0001029160",
    "Citadel Advisors": "0001423053",
    "Renaissance Technologies": "0001037389",
    "Point72 Asset Management": "0001603466",
    "Two Sigma Investments": "0001179392",
    "D.E. Shaw": "0001009207",
    "Millennium Management": "0001273087",
    "AQR Capital Management": "0001167557",
    "Tiger Global Management": "0001167483",
    "Appaloosa Management": "0001656456",
    "Baupost Group": "0001061768",
    "Elliott Management": "0001048445",
    "Pershing Square": "0001336528",
    "Berkshire Hathaway": "0001067983",
}


# ─── SEC 13F Client ─────────────────────────────────────────────────────────

class SEC13FClient:
    """
    SEC EDGAR 13F institutional holdings client.
    
    Pulls filing metadata for major hedge funds from SEC EDGAR.
    No API key needed — just a User-Agent header (SEC requires it).
    """

    BASE_URL = "https://data.sec.gov"
    HEADERS = {
        "User-Agent": "KillChainEngine/1.0 research@killchain.dev",
        "Accept": "application/json",
    }

    def __init__(self, cache_ttl: int = 3600):
        """
        Args:
            cache_ttl: Cache TTL in seconds (default 1 hour — 13F is quarterly).
        """
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        logger.info(f"📊 SEC13FClient initialized ({len(FUND_WATCHLIST)} funds tracked)")

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    # ── Individual Fund Lookup ───────────────────────────────────────────

    def get_latest_filing(self, fund_name: str = "Bridgewater Associates") -> Optional[Filing13F]:
        """
        Get the most recent 13F filing for a fund.
        
        Args:
            fund_name: Name from FUND_WATCHLIST (e.g., "Bridgewater Associates").
        
        Returns:
            Filing13F with filing date and accession number, or None.
        """
        cache_key = f"filing_{fund_name}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        
        cik = FUND_WATCHLIST.get(fund_name)
        if not cik:
            logger.error(f"❌ Unknown fund: {fund_name}. Known: {list(FUND_WATCHLIST.keys())}")
            return None
        
        try:
            url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            r = requests.get(url, headers=self.HEADERS, timeout=15)
            r.raise_for_status()
            
            data = r.json()
            name = data.get("name", fund_name)
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            
            # Find most recent 13F-HR
            for f, d, a in zip(forms, dates, accessions):
                if "13F" in f:
                    filing = Filing13F(
                        fund_name=name,
                        cik=cik,
                        filing_date=d,
                        form_type=f,
                        accession_number=a,
                    )
                    self._cache[cache_key] = filing
                    self._cache_ts[cache_key] = time.time()
                    logger.info(f"✅ {name}: Latest 13F filed {d}")
                    return filing
            
            logger.warning(f"⚠️ No 13F filings found for {name}")
            return None
            
        except Exception as e:
            logger.error(f"❌ SEC EDGAR error for {fund_name}: {e}")
            return self._cache.get(cache_key)

    # ── Batch Fund Tracking ──────────────────────────────────────────────

    def track_all_funds(self) -> List[Filing13F]:
        """
        Get latest 13F filing for all tracked funds.
        
        Rate limit: SEC EDGAR allows ~10 req/sec with proper User-Agent.
        
        Returns:
            List of Filing13F objects sorted by filing date (newest first).
        """
        cache_key = "all_funds"
        if self._is_cached(cache_key):
            return self._cache[cache_key]
        
        filings = []
        for name in FUND_WATCHLIST:
            filing = self.get_latest_filing(name)
            if filing:
                filings.append(filing)
            time.sleep(0.15)  # Be nice to SEC servers
        
        filings.sort(key=lambda f: f.filing_date, reverse=True)
        
        self._cache[cache_key] = filings
        self._cache_ts[cache_key] = time.time()
        logger.info(f"✅ Tracked {len(filings)}/{len(FUND_WATCHLIST)} funds")
        return filings

    # ── Narrative ────────────────────────────────────────────────────────

    def get_narrative(self) -> str:
        """Generate narrative-ready text for SavageAgents."""
        try:
            filings = self.track_all_funds()
            if not filings:
                return "No 13F filings available"
            
            latest = filings[0]
            parts = [
                f"Latest 13F: {latest.fund_name} filed {latest.filing_date}",
                f"Tracked {len(filings)} major funds",
            ]
            
            # Show 3 most recent filers
            recent = [f"{f.fund_name} ({f.filing_date})" for f in filings[:3]]
            parts.append(f"Recent filers: {', '.join(recent)}")
            
            return " | ".join(parts)
        except Exception as e:
            logger.error(f"❌ 13F narrative error: {e}")
            return "13F institutional data unavailable"


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = SEC13FClient()
    
    print("=" * 60)
    print("🐺 SEC 13F Client — Live Test")
    print("=" * 60)
    
    # Test specific funds
    for name in ["Bridgewater Associates", "Soros Fund Management", "Citadel Advisors", "Berkshire Hathaway"]:
        filing = client.get_latest_filing(name)
        if filing:
            print(f"  {filing.fund_name:>30}: {filing.form_type} filed {filing.filing_date}")
    
    print(f"\n--- Narrative ---")
    print(client.get_narrative())
