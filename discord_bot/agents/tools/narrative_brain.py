"""
🧠 NARRATIVE BRAIN TOOL
Access to market context, storytelling, and memory
"""

import os
import logging
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class NarrativeBrainTool(BaseTool):
    """
    Narrative Brain Tool
    
    Provides access to:
    - Market context and storytelling
    - Historical memory
    - Confluence analysis
    """
    
    def __init__(self):
        """Initialize Narrative Brain tool"""
        try:
            from live_monitoring.agents.narrative_brain import NarrativeBrain
            self.narrative_brain = NarrativeBrain()
            logger.info("✅ Narrative Brain Tool initialized")
        except Exception as e:
            logger.warning(f"⚠️ Narrative Brain init failed: {e}")
            self.narrative_brain = None
    
    @property
    def name(self) -> str:
        return "narrative_brain"
    
    @property
    def description(self) -> str:
        return "Market context, storytelling, and historical memory"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "get_context - Get current market narrative",
            "get_memory - Historical context from past analyses",
            "get_confluence - Multi-factor confluence analysis"
        ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            "story", "narrative", "context", "why", "what happened",
            "explain", "history", "remember", "previous", "last time",
            "moving", "reason", "cause"
        ]
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute narrative brain query"""
        symbol = params.get("symbol", "SPY").upper()
        action = params.get("action", "context")
        
        try:
            if action == "context":
                return self._get_context(symbol)
            elif action == "memory":
                days = params.get("days", 7)
                return self._get_memory(symbol, days)
            elif action == "confluence":
                return self._get_confluence(symbol)
            else:
                return self._get_context(symbol)
                
        except Exception as e:
            logger.error(f"Narrative Brain error: {e}")
            return ToolResult(
                success=False,
                data={},
                error=str(e)
            )
    
    def _get_context(self, symbol: str) -> ToolResult:
        """Get current market context"""
        context_data = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.narrative_brain:
            try:
                # Get latest narrative
                narrative = self.narrative_brain.get_latest_narrative()
                if narrative:
                    context_data["narrative"] = narrative.get("narrative", "")
                    context_data["direction"] = narrative.get("direction", "NEUTRAL")
                    context_data["confidence"] = narrative.get("confidence", 50)
            except Exception as e:
                logger.debug(f"Could not get narrative: {e}")
        
        # Add market data context
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d', interval='1d')
            
            if not hist.empty:
                current = float(hist['Close'].iloc[-1])
                prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current
                change_pct = (current - prev) / prev * 100
                
                context_data["current_price"] = current
                context_data["daily_change_pct"] = round(change_pct, 2)
                context_data["direction"] = "BULLISH" if change_pct > 0.5 else "BEARISH" if change_pct < -0.5 else "NEUTRAL"
                
                # Simple narrative based on price action
                if change_pct > 1:
                    context_data["narrative"] = f"{symbol} is showing strong bullish momentum today, up {change_pct:.1f}%"
                elif change_pct < -1:
                    context_data["narrative"] = f"{symbol} is under pressure today, down {abs(change_pct):.1f}%"
                else:
                    context_data["narrative"] = f"{symbol} is consolidating near ${current:.2f}"
                    
        except Exception as e:
            logger.debug(f"Price data error: {e}")
        
        return ToolResult(
            success=True,
            data=context_data
        )
    
    def _get_memory(self, symbol: str, days: int) -> ToolResult:
        """Get historical memory"""
        memory_data = {
            "symbol": symbol,
            "lookback_days": days,
            "timestamp": datetime.now().isoformat(),
            "past_analyses": []
        }
        
        if self.narrative_brain:
            try:
                memories = self.narrative_brain.memory.get_recent(symbol, days)
                memory_data["past_analyses"] = memories
            except Exception as e:
                logger.debug(f"Could not get memory: {e}")
        
        return ToolResult(
            success=True,
            data=memory_data
        )
    
    def _get_confluence(self, symbol: str) -> ToolResult:
        """Get confluence analysis"""
        confluence_data = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "factors": []
        }
        
        # Try to get various data points
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d', interval='1h')
            
            if not hist.empty:
                # Price trend
                current = float(hist['Close'].iloc[-1])
                sma_20 = float(hist['Close'].rolling(20).mean().iloc[-1])
                
                confluence_data["current_price"] = current
                confluence_data["factors"].append({
                    "factor": "Price vs SMA20",
                    "signal": "BULLISH" if current > sma_20 else "BEARISH",
                    "value": f"${current:.2f} vs ${sma_20:.2f}"
                })
                
                # Volume
                avg_vol = float(hist['Volume'].mean())
                recent_vol = float(hist['Volume'].iloc[-1])
                confluence_data["factors"].append({
                    "factor": "Volume",
                    "signal": "BULLISH" if recent_vol > avg_vol * 1.5 else "NEUTRAL",
                    "value": f"{recent_vol:,.0f} vs avg {avg_vol:,.0f}"
                })
                
        except Exception as e:
            logger.debug(f"Confluence data error: {e}")
        
        # Calculate overall confluence
        bullish = len([f for f in confluence_data["factors"] if f["signal"] == "BULLISH"])
        bearish = len([f for f in confluence_data["factors"] if f["signal"] == "BEARISH"])
        total = len(confluence_data["factors"]) or 1
        
        confluence_data["confluence_score"] = round((bullish / total) * 100, 0)
        confluence_data["bias"] = "BULLISH" if bullish > bearish else "BEARISH" if bearish > bullish else "NEUTRAL"
        
        return ToolResult(
            success=True,
            data=confluence_data
        )
    
    def format_response(self, result: ToolResult) -> str:
        """Format result for Discord display"""
        if not result.success:
            return f"❌ Error: {result.error}"
        
        data = result.data
        symbol = data.get("symbol", "SPY")
        
        lines = [f"🧠 **{symbol} Market Context**\n"]
        
        if data.get("narrative"):
            lines.append(f"📊 {data['narrative']}")
        
        if data.get("direction"):
            emoji = "📈" if data["direction"] == "BULLISH" else "📉" if data["direction"] == "BEARISH" else "➡️"
            lines.append(f"\n{emoji} **Direction:** {data['direction']}")
        
        if data.get("confluence_score"):
            lines.append(f"🎯 **Confluence:** {data['confluence_score']:.0f}%")
        
        if data.get("factors"):
            lines.append("\n**Factors:**")
            for factor in data["factors"]:
                emoji = "✅" if factor["signal"] == "BULLISH" else "❌" if factor["signal"] == "BEARISH" else "⚠️"
                lines.append(f"  {emoji} {factor['factor']}: {factor['value']}")
        
        return "\n".join(lines)



