"""
Cleveland Fed Inflation Nowcasting Client

Source: Cleveland Fed public page (clevelandfed.org/indicators-and-data/inflation-nowcasting)
Data:   CPI, Core CPI, PCE, Core PCE — nowcasts (MoM, YoY, Quarterly)
Auth:   None — free public data, scraped from HTML tables
Update: Daily (Fed updates page with latest model estimates)

The Cleveland Fed nowcast provides a real-time estimate of what inflation
will print BEFORE the official BLS/BEA release. When:
  Cleveland nowcast > TE consensus by > 0.1% → pre-signal HOT
  Cleveland nowcast < TE consensus by > 0.1% → pre-signal COLD
"""
import logging
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NowcastSnapshot:
    """A single nowcast snapshot from Cleveland Fed."""
    # Month-over-month
    cpi_mom: Optional[float] = None
    core_cpi_mom: Optional[float] = None
    pce_mom: Optional[float] = None
    core_pce_mom: Optional[float] = None
    # Year-over-year
    cpi_yoy: Optional[float] = None
    core_cpi_yoy: Optional[float] = None
    pce_yoy: Optional[float] = None
    core_pce_yoy: Optional[float] = None
    # Quarterly annualized
    cpi_quarterly: Optional[float] = None
    core_cpi_quarterly: Optional[float] = None
    pce_quarterly: Optional[float] = None
    core_pce_quarterly: Optional[float] = None
    # Metadata
    month: str = ""
    quarter: str = ""
    updated: str = ""


class ClevelandFedNowcast:
    """
    Cleveland Fed Inflation Nowcasting client.
    
    Scrapes the public Cleveland Fed nowcasting page for real-time
    CPI/PCE estimates. Updated daily by the Fed's nowcasting model.
    """

    URL = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    def __init__(self, cache_ttl: int = 3600):
        self._cache: Optional[NowcastSnapshot] = None
        self._cache_ts: float = 0
        self._cache_ttl = cache_ttl
        logger.info("🏦 ClevelandFedNowcast initialized (clevelandfed.org scraper)")

    def get_nowcast(self, force_refresh: bool = False) -> Optional[NowcastSnapshot]:
        """Get latest inflation nowcast snapshot."""
        if not force_refresh and self._cache and (time.time() - self._cache_ts) < self._cache_ttl:
            return self._cache

        try:
            resp = requests.get(self.URL, timeout=15, headers=self.HEADERS)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            tables = soup.find_all("table")

            snapshot = NowcastSnapshot()

            if len(tables) >= 1:
                self._parse_mom_table(tables[0], snapshot)
            if len(tables) >= 2:
                self._parse_yoy_table(tables[1], snapshot)
            if len(tables) >= 3:
                self._parse_quarterly_table(tables[2], snapshot)

            self._cache = snapshot
            self._cache_ts = time.time()
            logger.info(
                f"📊 Cleveland Fed nowcast: CPI MoM={snapshot.cpi_mom}%, "
                f"Core CPI={snapshot.core_cpi_mom}%, PCE={snapshot.pce_mom}%, "
                f"Core PCE={snapshot.core_pce_mom}% (updated {snapshot.updated})"
            )
            return snapshot

        except Exception as e:
            logger.error(f"❌ Cleveland Fed nowcast scrape failed: {e}")
            return self._cache  # return stale cache if available

    def _parse_mom_table(self, table, snapshot: NowcastSnapshot):
        """Parse MoM inflation table."""
        rows = table.find_all("tr")
        for row in rows[1:]:  # skip header
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) >= 6 and cells[0] and not cells[0].startswith("Note"):
                snapshot.month = cells[0]
                snapshot.cpi_mom = self._safe_float(cells[1])
                snapshot.core_cpi_mom = self._safe_float(cells[2])
                snapshot.pce_mom = self._safe_float(cells[3])
                snapshot.core_pce_mom = self._safe_float(cells[4])
                snapshot.updated = cells[5] if len(cells) > 5 else ""
                break  # first data row is the latest nowcast

    def _parse_yoy_table(self, table, snapshot: NowcastSnapshot):
        """Parse YoY inflation table."""
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) >= 5 and cells[0] and not cells[0].startswith("Note"):
                snapshot.cpi_yoy = self._safe_float(cells[1])
                snapshot.core_cpi_yoy = self._safe_float(cells[2])
                snapshot.pce_yoy = self._safe_float(cells[3])
                snapshot.core_pce_yoy = self._safe_float(cells[4])
                break

    def _parse_quarterly_table(self, table, snapshot: NowcastSnapshot):
        """Parse quarterly annualized inflation table."""
        rows = table.find_all("tr")
        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) >= 5 and cells[0] and not cells[0].startswith("Note"):
                snapshot.quarter = cells[0]
                snapshot.cpi_quarterly = self._safe_float(cells[1])
                snapshot.core_cpi_quarterly = self._safe_float(cells[2])
                snapshot.pce_quarterly = self._safe_float(cells[3])
                snapshot.core_pce_quarterly = self._safe_float(cells[4])
                break

    @staticmethod
    def _safe_float(val: str) -> Optional[float]:
        try:
            return float(val.strip()) if val.strip() else None
        except (ValueError, AttributeError):
            return None

    def get_divergence(self, te_consensus: float, metric: str = "cpi_mom") -> Optional[Dict[str, Any]]:
        """
        Compare Cleveland Fed nowcast against TE consensus.
        
        Returns divergence signal:
          divergence > +0.1 → PRE_SIGNAL_HOT
          divergence < -0.1 → PRE_SIGNAL_COLD
          else → NEUTRAL
        """
        snapshot = self.get_nowcast()
        if not snapshot:
            return None

        nowcast_val = getattr(snapshot, metric, None)
        if nowcast_val is None or te_consensus == 0:
            return None

        divergence = nowcast_val - te_consensus
        if divergence > 0.1:
            signal = "PRE_SIGNAL_HOT"
        elif divergence < -0.1:
            signal = "PRE_SIGNAL_COLD"
        else:
            signal = "NEUTRAL"

        return {
            "metric": metric,
            "nowcast": nowcast_val,
            "te_consensus": te_consensus,
            "divergence": round(divergence, 3),
            "signal": signal,
            "updated": snapshot.updated,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Full nowcast as a flat dict for API responses."""
        snap = self.get_nowcast()
        if not snap:
            return {"status": "unavailable"}
        return {
            "status": "live",
            "month": snap.month,
            "quarter": snap.quarter,
            "updated": snap.updated,
            "mom": {
                "cpi": snap.cpi_mom,
                "core_cpi": snap.core_cpi_mom,
                "pce": snap.pce_mom,
                "core_pce": snap.core_pce_mom,
            },
            "yoy": {
                "cpi": snap.cpi_yoy,
                "core_cpi": snap.core_cpi_yoy,
                "pce": snap.pce_yoy,
                "core_pce": snap.core_pce_yoy,
            },
            "quarterly": {
                "cpi": snap.cpi_quarterly,
                "core_cpi": snap.core_cpi_quarterly,
                "pce": snap.pce_quarterly,
                "core_pce": snap.core_pce_quarterly,
            },
        }


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    client = ClevelandFedNowcast()
    snap = client.get_nowcast()
    if snap:
        print(json.dumps(client.to_dict(), indent=2))
        # Test divergence: TE consensus for March CPI MoM ~0.3%
        div = client.get_divergence(0.3, "cpi_mom")
        print(f"\nDivergence vs TE consensus 0.3%: {json.dumps(div, indent=2)}")
    else:
        print("❌ Failed to fetch nowcast")
