"""
FRED Client — Federal Reserve Economic Data (St. Louis Fed)

Source: FRED API (api.stlouisfed.org) — Truly unlimited, free, no card
Data:   CPI, Core CPI, PCE, GDP, Unemployment, Nonfarm Payrolls, Fed Funds Rate, SOFR
Auth:   Free API key (FRED_API_KEY in .env)

Replaces: Alpha Vantage CPI (which was rate-limited and empty)
"""
import os
import logging
import time
import requests
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class FREDRelease:
    """A single economic indicator release from FRED."""
    series_id: str
    name: str
    value: float
    date: str
    previous_value: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    units: str = ""
    frequency: str = ""


class FREDClient:
    """
    Federal Reserve Economic Data client.
    
    Free, unlimited API. No credit card needed.
    Covers: CPI, Core CPI, PCE, GDP, Unemployment, Payrolls, Fed Funds, SOFR, Treasury yields.
    """

    BASE_URL = "https://api.stlouisfed.org/fred"

    # Key economic series
    SERIES = {
        "CPI":           {"id": "CPIAUCSL",  "name": "CPI (All Urban Consumers)",     "units": "Index"},
        "CORE_CPI":      {"id": "CPILFESL",  "name": "Core CPI (excl Food & Energy)", "units": "Index"},
        "PCE":           {"id": "PCEPI",     "name": "PCE Price Index",                "units": "Index"},
        "CORE_PCE":      {"id": "PCEPILFE",  "name": "Core PCE (excl Food & Energy)",  "units": "Index"},
        "UNEMPLOYMENT":  {"id": "UNRATE",    "name": "Unemployment Rate",              "units": "%"},
        "NONFARM":       {"id": "PAYEMS",    "name": "Nonfarm Payrolls",               "units": "Thousands"},
        "GDP":           {"id": "GDP",       "name": "Gross Domestic Product",          "units": "Billions $"},
        "FED_FUNDS":     {"id": "FEDFUNDS",  "name": "Federal Funds Rate",             "units": "%"},
        "SOFR":          {"id": "SOFR",      "name": "Secured Overnight Financing Rate","units": "%"},
        "T10Y":          {"id": "DGS10",     "name": "10-Year Treasury Yield",          "units": "%"},
        "T2Y":           {"id": "DGS2",      "name": "2-Year Treasury Yield",           "units": "%"},
        "SPREAD_10Y2Y":  {"id": "T10Y2Y",    "name": "10Y-2Y Treasury Spread",          "units": "%"},
    }

    def __init__(self, api_key: Optional[str] = None, cache_ttl: int = 3600):
        self.api_key = api_key or os.getenv("FRED_API_KEY", "")
        self._cache: Dict[str, Any] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl

        if not self.api_key:
            logger.warning("⚠️ FRED_API_KEY not set — FRED client disabled")
        else:
            logger.info("📊 FREDClient initialized (unlimited free API)")

    def _is_cached(self, key: str) -> bool:
        return key in self._cache and (time.time() - self._cache_ts.get(key, 0)) < self._cache_ttl

    def _fetch_series(self, series_id: str, limit: int = 2) -> Optional[List[Dict]]:
        """Fetch latest observations for a FRED series."""
        if not self.api_key:
            return None

        try:
            url = f"{self.BASE_URL}/series/observations"
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            }
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()

            data = r.json()
            obs = data.get("observations", [])
            return [o for o in obs if o.get("value", ".") != "."]

        except Exception as e:
            logger.error(f"❌ FRED fetch error for {series_id}: {e}")
            return None

    def get_indicator(self, key: str) -> Optional[FREDRelease]:
        """
        Get latest value for a named indicator.
        
        Args:
            key: One of: CPI, CORE_CPI, PCE, CORE_PCE, UNEMPLOYMENT, 
                 NONFARM, GDP, FED_FUNDS, SOFR, T10Y, T2Y, SPREAD_10Y2Y
        """
        if key not in self.SERIES:
            logger.error(f"Unknown FRED series key: {key}")
            return None

        cache_key = f"fred_{key}"
        if self._is_cached(cache_key):
            return self._cache[cache_key]

        series = self.SERIES[key]
        obs = self._fetch_series(series["id"], limit=2)
        if not obs:
            return None

        latest = obs[0]
        value = float(latest["value"])
        date_str = latest["date"]

        previous_value = float(obs[1]["value"]) if len(obs) > 1 else 0.0
        change = value - previous_value
        change_pct = (change / previous_value * 100) if previous_value else 0.0

        release = FREDRelease(
            series_id=series["id"],
            name=series["name"],
            value=value,
            date=date_str,
            previous_value=previous_value,
            change=change,
            change_pct=change_pct,
            units=series["units"],
        )

        self._cache[cache_key] = release
        self._cache_ts[cache_key] = time.time()
        return release

    # ── Convenience Methods ──────────────────────────────────────────────

    def get_cpi(self) -> Optional[FREDRelease]:
        return self.get_indicator("CPI")

    def get_core_cpi(self) -> Optional[FREDRelease]:
        return self.get_indicator("CORE_CPI")

    def get_pce(self) -> Optional[FREDRelease]:
        return self.get_indicator("PCE")

    def get_unemployment(self) -> Optional[FREDRelease]:
        return self.get_indicator("UNEMPLOYMENT")

    def get_nonfarm_payrolls(self) -> Optional[FREDRelease]:
        return self.get_indicator("NONFARM")

    def get_fed_funds_rate(self) -> Optional[FREDRelease]:
        return self.get_indicator("FED_FUNDS")

    def get_treasury_10y(self) -> Optional[FREDRelease]:
        return self.get_indicator("T10Y")

    def get_yield_spread(self) -> Optional[FREDRelease]:
        return self.get_indicator("SPREAD_10Y2Y")

    # ── Summary ──────────────────────────────────────────────────────────

    def get_macro_snapshot(self) -> Dict[str, Any]:
        """Get a full macro snapshot with all key indicators."""
        snapshot = {"timestamp": datetime.utcnow().isoformat(), "indicators": {}}

        for key in ["CPI", "CORE_CPI", "PCE", "UNEMPLOYMENT", "FED_FUNDS", "T10Y", "SPREAD_10Y2Y"]:
            r = self.get_indicator(key)
            if r:
                snapshot["indicators"][key] = {
                    "value": r.value,
                    "date": r.date,
                    "change": round(r.change, 4),
                    "change_pct": round(r.change_pct, 2),
                    "units": r.units,
                }

        return snapshot

    def get_narrative(self) -> str:
        """Generate narrative-ready text for SavageAgents."""
        snapshot = self.get_macro_snapshot()
        ind = snapshot.get("indicators", {})

        parts = []
        if "CPI" in ind:
            parts.append(f"CPI: {ind['CPI']['value']:.1f} ({ind['CPI']['change_pct']:+.2f}% MoM)")
        if "CORE_CPI" in ind:
            parts.append(f"Core CPI: {ind['CORE_CPI']['value']:.1f}")
        if "FED_FUNDS" in ind:
            parts.append(f"Fed Funds: {ind['FED_FUNDS']['value']:.2f}%")
        if "UNEMPLOYMENT" in ind:
            parts.append(f"Unemployment: {ind['UNEMPLOYMENT']['value']:.1f}%")
        if "T10Y" in ind:
            parts.append(f"10Y: {ind['T10Y']['value']:.2f}%")
        if "SPREAD_10Y2Y" in ind:
            spread = ind["SPREAD_10Y2Y"]["value"]
            inv = " ⚠️ INVERTED" if spread < 0 else ""
            parts.append(f"10Y-2Y Spread: {spread:.2f}%{inv}")

        return " | ".join(parts) if parts else "FRED macro data unavailable"


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)
    client = FREDClient()

    print("=" * 60)
    print("📊 FRED Client — Live Test")
    print("=" * 60)

    for key in ["CPI", "CORE_CPI", "UNEMPLOYMENT", "FED_FUNDS", "T10Y", "SPREAD_10Y2Y"]:
        r = client.get_indicator(key)
        if r:
            print(f"  {r.name:>35}: {r.value:>8.2f} {r.units} ({r.change_pct:+.2f}%) | {r.date}")

    print(f"\n--- Narrative ---")
    print(client.get_narrative())
