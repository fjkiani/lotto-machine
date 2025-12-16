"""
📊 DARK POOL INTELLIGENCE TOOL
Access to dark pool levels, battlegrounds, and support/resistance
"""

import os
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class DPIntelligenceTool(BaseTool):
    """
    Dark Pool Intelligence Tool
    
    Provides access to:
    - Current DP levels
    - Battleground zones
    - Support/Resistance
    - Volume analysis
    """
    
    def __init__(self):
        """Initialize DP Intelligence tool"""
        self.api_key = os.getenv('CHARTEXCHANGE_API_KEY')
        self.dp_client = None
        self.dp_engine = None
        
        if self.api_key:
            try:
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                from core.ultra_institutional_engine import UltraInstitutionalEngine
                self.dp_client = UltimateChartExchangeClient(self.api_key)
                self.dp_engine = UltraInstitutionalEngine(self.api_key)
                logger.info("✅ DP Intelligence Tool initialized")
            except Exception as e:
                logger.error(f"❌ DP Intelligence init failed: {e}")
        else:
            logger.warning("⚠️ CHARTEXCHANGE_API_KEY not set - DP Intelligence limited")
    
    @property
    def name(self) -> str:
        return "dp_intelligence"
    
    @property
    def description(self) -> str:
        return "Dark pool levels, battlegrounds, support/resistance zones"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "get_levels - Get current DP levels for a symbol",
            "get_battlegrounds - Get battleground zones",
            "get_support_resistance - Get support and resistance levels",
            "check_proximity - Check if price is near a DP level"
        ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            "level", "levels", "support", "resistance", 
            "battleground", "dark pool", "dp", "where",
            "price", "watch", "zone", "institutional"
        ]
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute DP intelligence query.
        
        Params:
            symbol: Ticker symbol (default: SPY)
            action: Specific action (levels, battlegrounds, proximity)
        """
        symbol = params.get("symbol", "SPY").upper()
        action = params.get("action", "levels")
        
        try:
            if action == "levels":
                return self._get_levels(symbol)
            elif action == "battlegrounds":
                return self._get_battlegrounds(symbol)
            elif action == "proximity":
                price = params.get("price", 0)
                return self._check_proximity(symbol, price)
            else:
                return self._get_levels(symbol)  # Default
                
        except Exception as e:
            logger.error(f"DP Intelligence error: {e}")
            return ToolResult(
                success=False,
                data={},
                error=str(e)
            )
    
    def _get_levels(self, symbol: str) -> ToolResult:
        """Get current DP levels"""
        if not self.dp_client:
            return self._get_fallback_levels(symbol)
        
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            dp_levels = self.dp_client.get_dark_pool_levels(symbol, yesterday)
            
            if not dp_levels:
                return self._get_fallback_levels(symbol)
            
            # Get current price
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            current_price = float(hist['Close'].iloc[-1]) if not hist.empty else 0
            
            # Process levels
            processed_levels = []
            for level in dp_levels[:10]:  # Top 10 levels
                price = float(level.get('level', 0))
                volume = int(level.get('volume', 0))
                
                if volume >= 500000:  # Only significant levels
                    level_type = "SUPPORT" if price < current_price else "RESISTANCE"
                    distance_pct = abs(price - current_price) / current_price * 100
                    
                    # Volume tier
                    if volume >= 2_000_000:
                        tier = "MAJOR"
                    elif volume >= 1_000_000:
                        tier = "STRONG"
                    else:
                        tier = "MODERATE"
                    
                    processed_levels.append({
                        "price": price,
                        "volume": volume,
                        "type": level_type,
                        "tier": tier,
                        "distance_pct": round(distance_pct, 2)
                    })
            
            # Sort by distance
            processed_levels.sort(key=lambda x: x["distance_pct"])
            
            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "current_price": current_price,
                    "levels": processed_levels,
                    "support_levels": [l for l in processed_levels if l["type"] == "SUPPORT"],
                    "resistance_levels": [l for l in processed_levels if l["type"] == "RESISTANCE"],
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error fetching DP levels: {e}")
            return self._get_fallback_levels(symbol)
    
    def _get_battlegrounds(self, symbol: str) -> ToolResult:
        """Get battleground zones where institutions are active"""
        levels_result = self._get_levels(symbol)
        
        if not levels_result.success:
            return levels_result
        
        # Battlegrounds are levels with high volume activity
        levels = levels_result.data.get("levels", [])
        battlegrounds = [l for l in levels if l.get("tier") in ["MAJOR", "STRONG"]]
        
        return ToolResult(
            success=True,
            data={
                "symbol": symbol,
                "current_price": levels_result.data.get("current_price"),
                "battlegrounds": battlegrounds,
                "count": len(battlegrounds),
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def _check_proximity(self, symbol: str, price: float) -> ToolResult:
        """Check if price is near any DP level"""
        levels_result = self._get_levels(symbol)
        
        if not levels_result.success:
            return levels_result
        
        levels = levels_result.data.get("levels", [])
        current_price = levels_result.data.get("current_price", price)
        
        # Check proximity (within 0.3%)
        nearby = []
        for level in levels:
            distance = abs(level["price"] - current_price) / current_price * 100
            if distance <= 0.3:
                nearby.append({
                    **level,
                    "proximity": "AT_LEVEL" if distance <= 0.1 else "APPROACHING"
                })
        
        return ToolResult(
            success=True,
            data={
                "symbol": symbol,
                "current_price": current_price,
                "nearby_levels": nearby,
                "at_level": len([l for l in nearby if l["proximity"] == "AT_LEVEL"]) > 0,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def _get_fallback_levels(self, symbol: str) -> ToolResult:
        """Fallback when API not available"""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d', interval='1h')
            
            if hist.empty:
                return ToolResult(
                    success=False,
                    data={},
                    error="Could not fetch price data"
                )
            
            current_price = float(hist['Close'].iloc[-1])
            high_5d = float(hist['High'].max())
            low_5d = float(hist['Low'].min())
            
            # Simple levels based on price range
            levels = [
                {"price": round(low_5d, 2), "volume": 500000, "type": "SUPPORT", "tier": "MODERATE", "distance_pct": round(abs(low_5d - current_price) / current_price * 100, 2)},
                {"price": round(high_5d, 2), "volume": 500000, "type": "RESISTANCE", "tier": "MODERATE", "distance_pct": round(abs(high_5d - current_price) / current_price * 100, 2)},
            ]
            
            return ToolResult(
                success=True,
                data={
                    "symbol": symbol,
                    "current_price": current_price,
                    "levels": levels,
                    "support_levels": [l for l in levels if l["type"] == "SUPPORT"],
                    "resistance_levels": [l for l in levels if l["type"] == "RESISTANCE"],
                    "note": "Using fallback data (DP API unavailable)",
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"Fallback also failed: {e}"
            )
    
    def format_response(self, result: ToolResult) -> str:
        """Format result for Discord display"""
        if not result.success:
            return f"❌ Error: {result.error}"
        
        data = result.data
        symbol = data.get("symbol", "SPY")
        current_price = data.get("current_price", 0)
        
        lines = [f"🔒 **{symbol} Dark Pool Levels** | Current: ${current_price:.2f}\n"]
        
        # Support levels
        support = data.get("support_levels", [])[:3]
        if support:
            lines.append("**📉 Support:**")
            for level in support:
                tier_emoji = "🔥" if level["tier"] == "MAJOR" else "💪" if level["tier"] == "STRONG" else "📊"
                lines.append(f"  {tier_emoji} ${level['price']:.2f} ({level['volume']:,} shares) - {level['distance_pct']:.1f}% away")
        
        # Resistance levels
        resistance = data.get("resistance_levels", [])[:3]
        if resistance:
            lines.append("\n**📈 Resistance:**")
            for level in resistance:
                tier_emoji = "🔥" if level["tier"] == "MAJOR" else "💪" if level["tier"] == "STRONG" else "📊"
                lines.append(f"  {tier_emoji} ${level['price']:.2f} ({level['volume']:,} shares) - {level['distance_pct']:.1f}% away")
        
        if data.get("note"):
            lines.append(f"\n⚠️ {data['note']}")
        
        return "\n".join(lines)



