#!/usr/bin/env python3
"""
DATA FETCHER - Modular data acquisition
- Fetch DP data, price data, institutional intelligence
- Handle errors gracefully
- Cache for fallback
"""

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
import pickle
from pathlib import Path
import sys

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent / 'core' / 'data'))
sys.path.append(str(Path(__file__).parent.parent.parent / 'core'))

from ultimate_chartexchange_client import UltimateChartExchangeClient
from ultra_institutional_engine import UltraInstitutionalEngine

logger = logging.getLogger(__name__)

class DataFetcher:
    """Modular data fetching with caching and error handling"""
    
    def __init__(self, api_key: str, use_cache: bool = True, cache_dir: str = "cache"):
        self.api_key = api_key
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize clients
        self.cx_client = UltimateChartExchangeClient(api_key, tier=3)
        self.inst_engine = UltraInstitutionalEngine(api_key)
        
        logger.info("📊 Data Fetcher initialized")
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d', interval='1m')
            if not data.empty:
                return float(data['Close'].iloc[-1])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        return None
    
    def get_institutional_context(self, symbol: str, use_yesterday: bool = True) -> Optional[Any]:
        """
        Get institutional intelligence
        
        Args:
            symbol: Ticker
            use_yesterday: If True, use yesterday's date for DP data (today's not available yet)
        """
        try:
            # Use yesterday's date for DP data (today's levels form EOD)
            if use_yesterday:
                date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # Try cache first
            if self.use_cache:
                cached = self._load_from_cache(symbol, date)
                if cached:
                    logger.debug(f"Using cached institutional context for {symbol}")
                    return cached
            
            # Fetch fresh data
            logger.info(f"Fetching institutional context for {symbol} (date: {date})...")
            context = self.inst_engine.build_institutional_context(symbol, date)
            
            # Cache it
            if self.use_cache:
                self._save_to_cache(symbol, date, context)
            
            return context
            
        except Exception as e:
            logger.error(f"Error fetching institutional context for {symbol}: {e}")
            
            # Try cache as fallback
            if self.use_cache:
                logger.warning("Attempting to use cached data as fallback...")
                cached = self._load_from_cache(symbol, date, max_age_hours=48)
                if cached:
                    return cached
            
            return None
    
    def get_minute_bars(self, symbol: str, lookback_minutes: int = 30) -> Optional[pd.DataFrame]:
        """Get recent minute bars for volume/momentum calculation"""
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period='1d', interval='1m')
            
            if not df.empty:
                # Get last N minutes
                return df.tail(lookback_minutes)
            
        except Exception as e:
            logger.error(f"Error fetching minute bars for {symbol}: {e}")
        
        return None
    
    def _cache_filename(self, symbol: str, date: str) -> Path:
        """Generate cache filename"""
        return self.cache_dir / f"inst_context_{symbol}_{date}.pkl"
    
    def _save_to_cache(self, symbol: str, date: str, context: Any):
        """Save institutional context to cache"""
        try:
            filename = self._cache_filename(symbol, date)
            with open(filename, 'wb') as f:
                pickle.dump({
                    'context': context,
                    'cached_at': datetime.now(),
                    'symbol': symbol,
                    'date': date
                }, f)
            logger.debug(f"Cached institutional context: {filename}")
        except Exception as e:
            logger.warning(f"Failed to cache data: {e}")
    
    def _load_from_cache(self, symbol: str, date: str, max_age_hours: int = 24) -> Optional[Any]:
        """Load institutional context from cache"""
        try:
            filename = self._cache_filename(symbol, date)
            
            if not filename.exists():
                return None
            
            with open(filename, 'rb') as f:
                cached = pickle.load(f)
            
            # Check age
            age = datetime.now() - cached['cached_at']
            if age.total_seconds() / 3600 > max_age_hours:
                logger.debug(f"Cache too old ({age.total_seconds()/3600:.1f}h), skipping")
                return None
            
            return cached['context']
            
        except Exception as e:
            logger.warning(f"Failed to load from cache: {e}")
            return None
    
    def clear_cache(self, symbol: Optional[str] = None):
        """Clear cache for symbol or all"""
        if symbol:
            pattern = f"inst_context_{symbol}_*.pkl"
        else:
            pattern = "inst_context_*.pkl"
        
        count = 0
        for file in self.cache_dir.glob(pattern):
            file.unlink()
            count += 1
        
        logger.info(f"Cleared {count} cache files")



