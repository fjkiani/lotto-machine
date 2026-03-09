"""
🔒 DP Monitor - Battleground Analyzer
=====================================
Fetches and analyzes dark pool battlegrounds via StockgridClient.
Legacy ChartExchange scrapers purged.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import yfinance as yf

from .models import Battleground, LevelType
from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

logger = logging.getLogger(__name__)


class BattlegroundAnalyzer:
    """
    Fetches and analyzes dark pool battlegrounds using Stockgrid data.
    
    Responsibilities:
    - Fetch net dark pool positions from Stockgrid
    - Derives battleground levels from top positions
    - Calculate distance from current price
    - Determine support/resistance based on short volume %
    """
    
    MIN_VOLUME = 500_000  # Minimum volume to consider
    
    def __init__(self, api_key: str = None, dp_client: Optional[StockgridClient] = None):
        """
        Args:
            api_key: Legacy/Ignored (Stockgrid is free)
            dp_client: StockgridClient instance
        """
        self.dp_client = dp_client or StockgridClient(cache_ttl=300)
        self._cache: Dict[str, dict] = {}  # symbol -> {date, battlegrounds}
    
    def get_battlegrounds(
        self, 
        symbol: str, 
        date: Optional[str] = None,
        top_n: int = 15
    ) -> List[Battleground]:
        """
        Get top N battlegrounds for a symbol from Stockgrid.
        
        Note: Stockgrid returns net positions. We map these to battleground levels.
        """
        symbol = symbol.upper()
        
        # Check cache
        cache_key = f"{symbol}"
        if cache_key in self._cache:
            return self._cache[cache_key][:top_n]
        
        try:
            # Get ticker detail and top positions
            detail = self.dp_client.get_ticker_detail(symbol)
            top_positions = self.dp_client.get_top_positions(limit=50)
            
            battlegrounds = []
            
            # 1. Add the ticker's own detail as a primary battleground
            if detail and detail.dp_position_dollars and detail.dp_position_shares:
                price = abs(detail.dp_position_dollars / detail.dp_position_shares)
                vol = abs(int(detail.dp_position_shares))
                
                if vol >= self.MIN_VOLUME:
                    bg = Battleground(
                        symbol=symbol,
                        price=price,
                        volume=vol,
                        date=detail.date or datetime.now().strftime('%Y-%m-%d')
                    )
                    battlegrounds.append(bg)

            # 2. Derive context levels from top overall DP positions
            # This helps the UI show relative sentiment/levels
            for pos in top_positions:
                if not pos.dp_position_dollars or not pos.dp_position_shares:
                    continue
                
                price = abs(pos.dp_position_dollars / pos.dp_position_shares)
                vol = abs(int(pos.dp_position_shares))
                
                if vol >= self.MIN_VOLUME:
                    battlegrounds.append(Battleground(
                        symbol=pos.ticker,
                        price=price,
                        volume=vol,
                        date=pos.date or datetime.now().strftime('%Y-%m-%d')
                    ))
            
            # Sort by volume descending
            battlegrounds.sort(key=lambda x: x.volume, reverse=True)
            
            # Cache
            self._cache[cache_key] = battlegrounds
            
            logger.info(f"📊 Stockgrid: Derived {len(battlegrounds)} battlegrounds for {symbol}")
            return battlegrounds[:top_n]
            
        except Exception as e:
            logger.error(f"❌ Stockgrid fetch failure for {symbol}: {e}")
            return []
    
    def analyze_proximity(
        self, 
        battlegrounds: List[Battleground], 
        current_price: float
    ) -> List[Battleground]:
        """Analyze battlegrounds relative to current price."""
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
        """Get current market price via yfinance."""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.debug(f"Price fetch error: {e}")
        return None
    
    def get_nearby_battlegrounds(
        self, 
        symbol: str, 
        max_distance_pct: float = 0.5
    ) -> List[Battleground]:
        """Get battlegrounds within a certain distance."""
        current_price = self.get_current_price(symbol)
        if current_price is None:
            return []
        
        battlegrounds = self.get_battlegrounds(symbol)
        if not battlegrounds:
            return []
        
        battlegrounds = self.analyze_proximity(battlegrounds, current_price)
        return [bg for bg in battlegrounds if bg.distance_pct <= max_distance_pct]
    
    def clear_cache(self, symbol: Optional[str] = None):
        if symbol:
            self._cache.pop(symbol, None)
        else:
            self._cache.clear()
