"""
📊 Alpha Vantage Economic Indicators Client
============================================
Lean, modular client for fetching economic data.

Indicators supported:
- CPI (Consumer Price Index)
- NFP (Nonfarm Payrolls)
- Unemployment Rate
- Federal Funds Rate
- Inflation
- Retail Sales
- Durable Goods
- Treasury Yield
- Real GDP
"""

import os
import logging
import requests
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class EconomicRelease:
    """Single economic data release."""
    name: str
    date: str  # YYYY-MM-DD
    value: float
    unit: str
    previous: Optional[float] = None
    change: Optional[float] = None  # % change from previous
    
    @property
    def change_direction(self) -> str:
        if self.change is None:
            return "UNCHANGED"
        if self.change > 0:
            return "UP"
        elif self.change < 0:
            return "DOWN"
        return "UNCHANGED"


class AlphaVantageEcon:
    """
    Alpha Vantage Economic Data Client.
    
    Usage:
        client = AlphaVantageEcon(api_key="YOUR_KEY")
        nfp = client.get_nfp()
        cpi = client.get_cpi()
        all_data = client.get_all_indicators()
    """
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    # Indicator configurations: (function, interval, extra_params, unit)
    INDICATORS = {
        "CPI": ("CPI", "monthly", {}, "index"),
        "NFP": ("NONFARM_PAYROLL", None, {}, "thousands"),
        "UNEMPLOYMENT": ("UNEMPLOYMENT", None, {}, "percent"),
        "FED_FUNDS_RATE": ("FEDERAL_FUNDS_RATE", "monthly", {}, "percent"),
        "INFLATION": ("INFLATION", None, {}, "percent"),
        "RETAIL_SALES": ("RETAIL_SALES", None, {}, "millions USD"),
        "DURABLES": ("DURABLES", None, {}, "millions USD"),
        "TREASURY_10Y": ("TREASURY_YIELD", "monthly", {"maturity": "10year"}, "percent"),
        "REAL_GDP": ("REAL_GDP", "quarterly", {}, "billions USD"),
        "GDP_PER_CAPITA": ("REAL_GDP_PER_CAPITA", None, {}, "dollars"),
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY", "demo")
        self._cache: Dict[str, EconomicRelease] = {}
        self._cache_time: Dict[str, datetime] = {}
    
    def _fetch(self, function: str, interval: Optional[str] = None, 
               extra_params: Optional[Dict] = None) -> Optional[Dict]:
        """Fetch data from Alpha Vantage."""
        params = {
            "function": function,
            "apikey": self.api_key,
        }
        if interval:
            params["interval"] = interval
        if extra_params:
            params.update(extra_params)
        
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors
            if "Error Message" in data or "Note" in data:
                logger.warning(f"Alpha Vantage API issue: {data}")
                return None
            
            return data
        except Exception as e:
            logger.warning(f"Alpha Vantage fetch error: {e}")
            return None
    
    def _get_indicator(self, indicator_key: str) -> Optional[EconomicRelease]:
        """Get a specific indicator."""
        if indicator_key not in self.INDICATORS:
            logger.error(f"Unknown indicator: {indicator_key}")
            return None
        
        function, interval, extra_params, unit = self.INDICATORS[indicator_key]
        data = self._fetch(function, interval, extra_params)
        
        if not data or "data" not in data:
            return None
        
        releases = data["data"]
        if not releases:
            return None
        
        # Get latest and previous
        latest = releases[0]
        previous = releases[1] if len(releases) > 1 else None
        
        try:
            value = float(latest["value"])
            prev_value = float(previous["value"]) if previous else None
            
            # Calculate change
            change = None
            if prev_value and prev_value != 0:
                change = ((value - prev_value) / prev_value) * 100
            
            release = EconomicRelease(
                name=indicator_key,
                date=latest["date"],
                value=value,
                unit=unit,
                previous=prev_value,
                change=change,
            )
            
            # Cache it
            self._cache[indicator_key] = release
            self._cache_time[indicator_key] = datetime.now()
            
            return release
        except (KeyError, ValueError) as e:
            logger.warning(f"Error parsing {indicator_key}: {e}")
            return None
    
    # Convenience methods for each indicator
    def get_cpi(self) -> Optional[EconomicRelease]:
        """Get Consumer Price Index."""
        return self._get_indicator("CPI")
    
    def get_nfp(self) -> Optional[EconomicRelease]:
        """Get Nonfarm Payrolls."""
        return self._get_indicator("NFP")
    
    def get_unemployment(self) -> Optional[EconomicRelease]:
        """Get Unemployment Rate."""
        return self._get_indicator("UNEMPLOYMENT")
    
    def get_fed_funds_rate(self) -> Optional[EconomicRelease]:
        """Get Federal Funds Rate."""
        return self._get_indicator("FED_FUNDS_RATE")
    
    def get_inflation(self) -> Optional[EconomicRelease]:
        """Get Inflation Rate."""
        return self._get_indicator("INFLATION")
    
    def get_retail_sales(self) -> Optional[EconomicRelease]:
        """Get Retail Sales."""
        return self._get_indicator("RETAIL_SALES")
    
    def get_durables(self) -> Optional[EconomicRelease]:
        """Get Durable Goods Orders."""
        return self._get_indicator("DURABLES")
    
    def get_treasury_10y(self) -> Optional[EconomicRelease]:
        """Get 10-Year Treasury Yield."""
        return self._get_indicator("TREASURY_10Y")
    
    def get_real_gdp(self) -> Optional[EconomicRelease]:
        """Get Real GDP."""
        return self._get_indicator("REAL_GDP")
    
    def get_gdp_per_capita(self) -> Optional[EconomicRelease]:
        """Get GDP Per Capita."""
        return self._get_indicator("GDP_PER_CAPITA")
    
    def get_all_indicators(self) -> Dict[str, EconomicRelease]:
        """Get all supported indicators."""
        results = {}
        for key in self.INDICATORS.keys():
            release = self._get_indicator(key)
            if release:
                results[key] = release
        return results
    
    def get_market_moving(self) -> Dict[str, EconomicRelease]:
        """Get key market-moving indicators only."""
        keys = ["CPI", "NFP", "UNEMPLOYMENT", "FED_FUNDS_RATE", "INFLATION"]
        results = {}
        for key in keys:
            release = self._get_indicator(key)
            if release:
                results[key] = release
        return results


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    client = AlphaVantageEcon()
    
    print("=" * 60)
    print("📊 ALPHA VANTAGE ECONOMIC DATA")
    print("=" * 60)
    print()
    
    # Get market-moving indicators
    indicators = client.get_market_moving()
    
    for name, release in indicators.items():
        direction = "↑" if release.change_direction == "UP" else "↓" if release.change_direction == "DOWN" else "→"
        print(f"{name}:")
        print(f"   Value: {release.value} {release.unit}")
        print(f"   Date: {release.date}")
        print(f"   Change: {release.change:.2f}% {direction}" if release.change else "   Change: N/A")
        print()




