#!/usr/bin/env python3
"""
ALPHA VANTAGE CLIENT - Direct API Integration
==============================================
Fetches 1-minute intraday data for replay and live monitoring.
Replaces yfinance to avoid rate limits.

API Key: DWUGOPJJ75DPU39D
Rate Limits: 5 calls/minute, 500 calls/day (free tier)

Author: Alpha's AI Hedge Fund
Date: 2025-11-21
"""

import os
import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class AlphaVantageClient:
    """Direct Alpha Vantage API client for intraday data"""
    
    def __init__(self, api_key: str, cache_dir: str = "cache/alpha_vantage"):
        """
        Initialize Alpha Vantage client
        
        Args:
            api_key: Direct Alpha Vantage API key
            cache_dir: Directory for caching responses
        """
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate limiting: 5 calls/minute
        self.last_call_time = 0
        self.min_call_interval = 12  # seconds (5 calls/min = 12s between calls)
        
        logger.info(f"🚀 AlphaVantageClient initialized")
        logger.info(f"   API Key: {api_key[:8]}...")
        logger.info(f"   Cache dir: {self.cache_dir}")
    
    def _rate_limit(self):
        """Enforce rate limiting: 5 calls/minute"""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_call_interval:
            wait_time = self.min_call_interval - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        self.last_call_time = time.time()
    
    def _get_cache_path(self, symbol: str, interval: str, outputsize: str) -> Path:
        """Generate cache file path"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.cache_dir / f"{symbol}_{interval}_{outputsize}_{date_str}.json"
    
    def _load_from_cache(self, cache_path: Path, max_age_minutes: int = 5) -> Optional[Dict]:
        """Load data from cache if fresh"""
        if not cache_path.exists():
            return None
        
        try:
            # Check file age
            file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
            age = (datetime.now() - file_time).total_seconds() / 60
            
            if age > max_age_minutes:
                logger.debug(f"Cache expired ({age:.1f} min old)")
                return None
            
            with open(cache_path, 'r') as f:
                data = json.load(f)
            
            logger.info(f"✅ Cache hit: {cache_path.name} ({age:.1f} min old)")
            return data
            
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
            return None
    
    def _save_to_cache(self, cache_path: Path, data: Dict):
        """Save data to cache"""
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            logger.debug(f"Cached response: {cache_path.name}")
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    def get_intraday_1min(self, symbol: str, outputsize: str = "full") -> pd.DataFrame:
        """
        Fetch 1-minute intraday data from Alpha Vantage
        
        Args:
            symbol: Ticker symbol (e.g., "SPY")
            outputsize: "compact" (100 bars) or "full" (~20k bars, ~15 days)
        
        Returns:
            DataFrame with columns: [open, high, low, close, volume]
            Index: DatetimeIndex (timezone-naive)
        """
        cache_path = self._get_cache_path(symbol, "1min", outputsize)
        
        # Try cache first
        cached_data = self._load_from_cache(cache_path, max_age_minutes=5)
        if cached_data:
            return self._parse_time_series(cached_data)
        
        # Fetch from API
        logger.info(f"📡 Fetching 1min data for {symbol} (outputsize={outputsize})")
        
        self._rate_limit()
        
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": "1min",
            "outputsize": outputsize,
            "apikey": self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"API error: HTTP {response.status_code}")
            
            data = response.json()
            
            # Check for error messages
            if "Error Message" in data:
                raise Exception(f"API error: {data['Error Message']}")
            
            if "Note" in data:
                # Rate limit hit
                logger.warning(f"⚠️  Rate limit: {data['Note']}")
                raise Exception("Rate limit exceeded")
            
            if "Time Series (1min)" not in data:
                raise Exception(f"No time series data in response: {list(data.keys())}")
            
            # Cache the response
            self._save_to_cache(cache_path, data)
            
            # Parse and return
            return self._parse_time_series(data)
            
        except Exception as e:
            logger.error(f"❌ Alpha Vantage API error for {symbol}: {e}")
            raise
    
    def _parse_time_series(self, data: Dict) -> pd.DataFrame:
        """
        Parse Alpha Vantage time series response into DataFrame
        
        Response format:
        {
            "Time Series (1min)": {
                "2025-11-20 20:00:00": {
                    "1. open": "662.50",
                    "2. high": "662.75",
                    "3. low": "662.40",
                    "4. close": "662.65",
                    "5. volume": "1234567"
                },
                ...
            }
        }
        """
        time_series = data.get("Time Series (1min)", {})
        
        if not time_series:
            raise ValueError("No time series data found")
        
        # Convert to DataFrame
        df = pd.DataFrame.from_dict(time_series, orient='index')
        
        # Rename columns (remove numbering)
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Convert to numeric
        df = df.astype(float)
        
        # Parse index as datetime
        df.index = pd.to_datetime(df.index)
        
        # Sort by time (oldest first)
        df = df.sort_index()
        
        logger.info(f"   Parsed {len(df)} bars: {df.index.min()} to {df.index.max()}")
        
        return df
    
    def get_quote(self, symbol: str) -> Dict:
        """
        Get current quote for symbol
        
        Returns:
            Dict with keys: price, change, change_percent, volume
        """
        self._rate_limit()
        
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            data = response.json()
            
            quote = data.get("Global Quote", {})
            
            return {
                'price': float(quote.get("05. price", 0)),
                'change': float(quote.get("09. change", 0)),
                'change_percent': float(quote.get("10. change percent", "0%").rstrip('%')),
                'volume': int(quote.get("06. volume", 0))
            }
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return {}


def _demo():
    """Test the client"""
    client = AlphaVantageClient(api_key="DWUGOPJJ75DPU39D")
    
    print("\n" + "="*60)
    print("ALPHA VANTAGE CLIENT DEMO")
    print("="*60)
    
    # Test SPY 1-minute data
    print("\n📊 Fetching SPY 1-minute data...")
    df = client.get_intraday_1min("SPY", outputsize="full")
    
    print(f"\n✅ Loaded {len(df)} bars")
    print(f"   Time range: {df.index.min()} to {df.index.max()}")
    print(f"\n   Latest 5 bars:")
    print(df.tail(5))
    
    # Filter for 11/20/25
    nov20 = df[df.index.date == pd.to_datetime("2025-11-20").date()]
    print(f"\n📅 11/20/25 data: {len(nov20)} bars")
    if not nov20.empty:
        print(f"   Time range: {nov20.index.min()} to {nov20.index.max()}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _demo()

