"""
DP Fetcher - Dark Pool Data Acquisition

Responsibility: Fetch DP levels with configurable thresholds.
No hardcoded values - all from config!
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DPFetcher:
    """
    Fetches Dark Pool levels with configurable volume threshold.
    
    Before: Hardcoded 500k threshold scattered everywhere
    After: Configurable threshold, single responsibility
    """
    
    def __init__(self, api_key: str, min_volume: int = 100_000):
        """
        Initialize DP Fetcher.
        
        Args:
            api_key: ChartExchange API key
            min_volume: Minimum volume threshold (default 100k, was 500k)
        """
        self.api_key = api_key
        self.min_volume = min_volume
        
        # Lazy import to avoid circular dependencies
        self._dp_client = None
        
        logger.info(f"🔒 DPFetcher initialized (min_volume={min_volume:,})")
    
    @property
    def dp_client(self):
        """Lazy load DP client"""
        if self._dp_client is None:
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            self._dp_client = UltimateChartExchangeClient(self.api_key)
        return self._dp_client
    
    def fetch_levels(
        self, 
        symbol: str, 
        date: Optional[str] = None,
        min_volume: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch DP levels for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            date: Date string (YYYY-MM-DD) or None for today
            min_volume: Override config min_volume if needed
        
        Returns:
            List of level dicts: [{'price': float, 'volume': int}, ...]
        """
        min_vol = min_volume or self.min_volume
        
        try:
            # Fetch from API
            if date:
                raw_levels = self.dp_client.get_dark_pool_levels(symbol, date)
            else:
                raw_levels = self.dp_client.get_dark_pool_levels(symbol)
            
            if not raw_levels:
                logger.debug(f"   📊 No DP levels returned for {symbol}")
                return []
            
            # Filter by volume threshold
            levels = []
            for level in raw_levels:
                try:
                    price = float(level.get('level', 0))
                    vol = int(level.get('volume', 0))
                    
                    if vol >= min_vol:
                        levels.append({
                            'price': price,
                            'volume': vol,
                            'raw': level  # Keep raw data for debugging
                        })
                except (ValueError, TypeError) as e:
                    logger.debug(f"   ⚠️ Skipping invalid level: {e}")
                    continue
            
            logger.info(f"   📊 Fetched {len(levels)} DP levels for {symbol} (vol >= {min_vol:,})")
            return levels
            
        except Exception as e:
            logger.error(f"   ❌ Failed to fetch DP levels for {symbol}: {e}")
            return []
    
    def fetch_multiple(
        self, 
        symbols: List[str],
        date: Optional[str] = None,
        min_volume: Optional[int] = None
    ) -> Dict[str, List[Dict]]:
        """
        Fetch DP levels for multiple symbols.
        
        Returns:
            Dict mapping symbol -> list of levels
        """
        result = {}
        for symbol in symbols:
            result[symbol] = self.fetch_levels(symbol, date, min_volume)
        return result
    
    def get_top_levels(
        self,
        symbol: str,
        top_n: int = 10,
        date: Optional[str] = None
    ) -> List[Dict]:
        """
        Get top N levels by volume.
        
        Useful for synthesis - get most significant levels.
        """
        levels = self.fetch_levels(symbol, date)
        
        # Sort by volume descending
        sorted_levels = sorted(levels, key=lambda x: x['volume'], reverse=True)
        
        return sorted_levels[:top_n]


