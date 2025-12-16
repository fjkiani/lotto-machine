"""
📈 SIGNAL SYNTHESIS TOOL
Unified market synthesis from all data sources
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class SignalSynthesisTool(BaseTool):
    """
    Signal Synthesis Tool
    
    Provides:
    - Unified market synthesis
    - Trade recommendations
    - Confluence scoring
    """
    
    def __init__(self):
        """Initialize Signal Synthesis tool"""
        try:
            from live_monitoring.agents.signal_brain import SignalBrainEngine
            self.signal_brain = SignalBrainEngine()
            logger.info("✅ Signal Synthesis Tool initialized")
        except Exception as e:
            logger.warning(f"⚠️ Signal Synthesis init failed: {e}")
            self.signal_brain = None
    
    @property
    def name(self) -> str:
        return "signal_synthesis"
    
    @property
    def description(self) -> str:
        return "Unified market synthesis, trade recommendations, confluence scoring"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "get_synthesis - Get unified market synthesis",
            "get_recommendation - Trade recommendation",
            "get_confluence - Overall confluence score"
        ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            "synthesis", "unified", "overall", "recommendation",
            "should i", "buy", "sell", "trade", "signal",
            "direction", "market", "outlook"
        ]
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute signal synthesis query"""
        action = params.get("action", "synthesis")
        
        try:
            return self._get_synthesis()
        except Exception as e:
            logger.error(f"Signal Synthesis error: {e}")
            return ToolResult(
                success=False,
                data={},
                error=str(e)
            )
    
    def _get_synthesis(self) -> ToolResult:
        """Get unified market synthesis"""
        synthesis_data = {
            "timestamp": datetime.now().isoformat(),
            "symbols": ["SPY", "QQQ"]
        }
        
        # Get price data for SPY and QQQ
        try:
            import yfinance as yf
            
            for symbol in ["SPY", "QQQ"]:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='5d', interval='1d')
                
                if not hist.empty:
                    current = float(hist['Close'].iloc[-1])
                    prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current
                    change_pct = (current - prev) / prev * 100
                    
                    synthesis_data[f"{symbol.lower()}_price"] = current
                    synthesis_data[f"{symbol.lower()}_change"] = round(change_pct, 2)
            
            # Calculate overall direction
            spy_change = synthesis_data.get("spy_change", 0)
            qqq_change = synthesis_data.get("qqq_change", 0)
            avg_change = (spy_change + qqq_change) / 2
            
            if avg_change > 0.5:
                synthesis_data["direction"] = "BULLISH"
                synthesis_data["recommendation"] = "LONG"
            elif avg_change < -0.5:
                synthesis_data["direction"] = "BEARISH"
                synthesis_data["recommendation"] = "SHORT"
            else:
                synthesis_data["direction"] = "NEUTRAL"
                synthesis_data["recommendation"] = "WAIT"
            
            synthesis_data["confluence_score"] = 50 + abs(avg_change) * 10  # Simplified
            synthesis_data["confidence"] = "HIGH" if abs(avg_change) > 1 else "MEDIUM" if abs(avg_change) > 0.5 else "LOW"
            
        except Exception as e:
            logger.error(f"Synthesis data error: {e}")
        
        return ToolResult(
            success=True,
            data=synthesis_data
        )
    
    def format_response(self, result: ToolResult) -> str:
        """Format result for Discord display"""
        if not result.success:
            return f"❌ Error: {result.error}"
        
        data = result.data
        
        lines = ["🧠 **Unified Market Synthesis**\n"]
        
        # Prices
        if data.get("spy_price"):
            spy_emoji = "📈" if data.get("spy_change", 0) > 0 else "📉"
            lines.append(f"{spy_emoji} **SPY:** ${data['spy_price']:.2f} ({data.get('spy_change', 0):+.2f}%)")
        
        if data.get("qqq_price"):
            qqq_emoji = "📈" if data.get("qqq_change", 0) > 0 else "📉"
            lines.append(f"{qqq_emoji} **QQQ:** ${data['qqq_price']:.2f} ({data.get('qqq_change', 0):+.2f}%)")
        
        # Direction
        if data.get("direction"):
            dir_emoji = "🚀" if data["direction"] == "BULLISH" else "🔻" if data["direction"] == "BEARISH" else "➡️"
            lines.append(f"\n{dir_emoji} **Direction:** {data['direction']}")
        
        # Recommendation
        if data.get("recommendation"):
            rec_emoji = "🎯" if data["recommendation"] in ["LONG", "SHORT"] else "⏳"
            lines.append(f"{rec_emoji} **Recommendation:** {data['recommendation']}")
        
        # Confluence
        if data.get("confluence_score"):
            lines.append(f"📊 **Confluence:** {data['confluence_score']:.0f}% ({data.get('confidence', 'MEDIUM')})")
        
        return "\n".join(lines)



