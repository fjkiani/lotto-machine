"""
🔒 DP Monitor - Battleground Analyzer
=====================================
Fetches and analyzes dark pool battlegrounds.
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import yfinance as yf

from .models import Battleground, LevelType

logger = logging.getLogger(__name__)


class BattlegroundAnalyzer:
    """
    Fetches and analyzes dark pool battlegrounds.
    
    Responsibilities:
    - Fetch battlegrounds from ChartExchange API
    - Rank by volume significance
    - Calculate distance from current price
    - Determine support/resistance
    """
    
    MIN_VOLUME = 500_000  # Minimum volume to consider
    
    def __init__(self, api_key: str = None, dp_client = None):
        """
        Args:
            api_key: ChartExchange API key (used if dp_client not provided)
            dp_client: Existing UltimateChartExchangeClient instance (preferred)
        """
        self.api_key = api_key
        self.dp_client = dp_client  # Use existing client if provided
        self.base_url = "https://api.chartexchange.com/v1"
        self._cache: Dict[str, dict] = {}  # symbol -> {date, battlegrounds}
    
    def get_battlegrounds(
        self, 
        symbol: str, 
        date: Optional[str] = None,
        top_n: int = 10
    ) -> List[Battleground]:
        """
        Get top N battlegrounds for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'SPY')
            date: Date string (YYYY-MM-DD), defaults to yesterday
            top_n: Number of top levels to return
            
        Returns:
            List of Battleground objects, sorted by volume descending
        """
        if date is None:
            # Use yesterday's date (today's DP data not available until after market)
            date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Check cache
        cache_key = f"{symbol}_{date}"
        if cache_key in self._cache:
            return self._cache[cache_key][:top_n]
        
        try:
            # Use existing client if available (handles SSL properly)
            if self.dp_client:
                levels = self.dp_client.get_dark_pool_levels(symbol, date)
            else:
                # Fallback to direct API call
                url = f"{self.base_url}/analyze/dark-pool-levels/{symbol}"
                headers = {"Authorization": f"Bearer {self.api_key}"}
                params = {"date": date}
                
                response = requests.get(url, headers=headers, params=params, timeout=10)
                
                if response.status_code != 200:
                    logger.warning(f"⚠️ DP levels API returned {response.status_code} for {symbol}")
                    return []
                
                data = response.json()
                levels = data.get('data', [])
            
            # Convert to Battleground objects
            battlegrounds = []
            if not levels:
                return []
                
            for level in levels:
                # Handle different response formats
                price = level.get('level', level.get('price', 0))
                vol = level.get('total_vol', level.get('volume', 0))
                
                # Convert strings to numbers
                if isinstance(price, str):
                    try:
                        price = float(price)
                    except:
                        continue
                if isinstance(vol, str):
                    try:
                        vol = float(vol.replace(',', ''))
                    except:
                        vol = 0
                
                if vol >= self.MIN_VOLUME:
                    bg = Battleground(
                        symbol=symbol,
                        price=float(price),
                        volume=int(vol),
                        date=date
                    )
                    battlegrounds.append(bg)
            
            # Sort by volume descending
            battlegrounds.sort(key=lambda x: x.volume, reverse=True)
            
            # Cache
            self._cache[cache_key] = battlegrounds
            
            logger.info(f"📊 Fetched {len(battlegrounds)} battlegrounds for {symbol} ({date})")
            return battlegrounds[:top_n]
            
        except Exception as e:
            logger.error(f"❌ Error fetching battlegrounds for {symbol}: {e}")
            return []
    
    def analyze_proximity(
        self, 
        battlegrounds: List[Battleground], 
        current_price: float
    ) -> List[Battleground]:
        """
        Analyze battlegrounds relative to current price.
        
        Updates each battleground with:
        - level_type (SUPPORT/RESISTANCE)
        - distance_pct
        - current_price
        
        Args:
            battlegrounds: List of battlegrounds
            current_price: Current market price
            
        Returns:
            Updated battlegrounds, sorted by distance ascending
        """
        for bg in battlegrounds:
            bg.current_price = current_price
            bg.distance_pct = abs(current_price - bg.price) / bg.price * 100
            
            # Determine support/resistance
            if current_price > bg.price:
                bg.level_type = LevelType.SUPPORT
            else:
                bg.level_type = LevelType.RESISTANCE
        
        # Sort by distance (closest first)
        battlegrounds.sort(key=lambda x: x.distance_pct)
        
        return battlegrounds
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.debug(f"Price fetch error for {symbol}: {e}")
        return None
    
    def get_nearby_battlegrounds(
        self, 
        symbol: str, 
        max_distance_pct: float = 0.5
    ) -> List[Battleground]:
        """
        Get battlegrounds within a certain distance of current price.
        
        Args:
            symbol: Stock symbol
            max_distance_pct: Maximum distance in percent (default 0.5%)
            
        Returns:
            List of nearby battlegrounds with analysis applied
        """
        # Get current price
        current_price = self.get_current_price(symbol)
        if current_price is None:
            logger.warning(f"⚠️ Could not get current price for {symbol}")
            return []
        
        # Get battlegrounds
        battlegrounds = self.get_battlegrounds(symbol)
        if not battlegrounds:
            return []
        
        # Analyze proximity
        battlegrounds = self.analyze_proximity(battlegrounds, current_price)
        
        # Filter by distance
        nearby = [bg for bg in battlegrounds if bg.distance_pct <= max_distance_pct]
        
        return nearby
    
    def clear_cache(self, symbol: Optional[str] = None):
        """Clear cached battlegrounds."""
        if symbol:
            keys_to_remove = [k for k in self._cache if k.startswith(symbol)]
            for k in keys_to_remove:
                del self._cache[k]
        else:
            self._cache.clear()

