"""
🏦 FED WATCH TOOL
Access to Fed rate probabilities and official comments
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class FedWatchTool(BaseTool):
    """
    Fed Watch Tool
    
    Provides:
    - Rate cut/hike probabilities
    - Fed official comments
    - Overall Fed sentiment
    """
    
    def __init__(self):
        """Initialize Fed Watch tool"""
        try:
            from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
            from live_monitoring.agents.fed_officials.engine import FedOfficialsEngine
            self.fed_watch = FedWatchMonitor()
            self.fed_officials = FedOfficialsEngine()
            logger.info("✅ Fed Watch Tool initialized")
        except Exception as e:
            logger.warning(f"⚠️ Fed Watch init failed: {e}")
            self.fed_watch = None
            self.fed_officials = None
    
    @property
    def name(self) -> str:
        return "fed_watch"
    
    @property
    def description(self) -> str:
        return "Fed rate probabilities, official comments, and sentiment"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "get_probabilities - Rate cut/hike probabilities",
            "get_comments - Recent Fed official comments",
            "get_sentiment - Overall Fed sentiment"
        ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            "fed", "rate", "cut", "hike", "powell", "fomc",
            "interest", "meeting", "hawkish", "dovish",
            "monetary", "policy", "federal reserve"
        ]
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute Fed Watch query"""
        action = params.get("action", "probabilities")
        
        try:
            if action == "probabilities":
                return self._get_probabilities()
            elif action == "comments":
                return self._get_comments()
            elif action == "sentiment":
                return self._get_sentiment()
            else:
                return self._get_probabilities()
                
        except Exception as e:
            logger.error(f"Fed Watch error: {e}")
            return ToolResult(
                success=False,
                data={},
                error=str(e)
            )
    
    def _get_probabilities(self) -> ToolResult:
        """Get Fed rate probabilities"""
        prob_data = {
            "timestamp": datetime.now().isoformat()
        }
        
        if self.fed_watch:
            try:
                status = self.fed_watch.check()
                if status:
                    prob_data["cut_probability"] = getattr(status, 'prob_cut', 50)
                    prob_data["hold_probability"] = getattr(status, 'prob_hold', 50)
                    prob_data["hike_probability"] = getattr(status, 'prob_hike', 0)
            except Exception as e:
                logger.debug(f"Fed Watch check error: {e}")
        
        # Determine sentiment
        cut_prob = prob_data.get("cut_probability", 50)
        if cut_prob > 70:
            prob_data["sentiment"] = "DOVISH"
            prob_data["market_impact"] = "BULLISH"
        elif cut_prob < 30:
            prob_data["sentiment"] = "HAWKISH"
            prob_data["market_impact"] = "BEARISH"
        else:
            prob_data["sentiment"] = "NEUTRAL"
            prob_data["market_impact"] = "NEUTRAL"
        
        return ToolResult(
            success=True,
            data=prob_data
        )
    
    def _get_comments(self) -> ToolResult:
        """Get recent Fed official comments"""
        comments_data = {
            "timestamp": datetime.now().isoformat(),
            "comments": []
        }
        
        if self.fed_officials:
            try:
                comments = self.fed_officials.fetch_comments()
                if comments:
                    comments_data["comments"] = comments[:5]  # Top 5
            except Exception as e:
                logger.debug(f"Fed comments error: {e}")
        
        return ToolResult(
            success=True,
            data=comments_data
        )
    
    def _get_sentiment(self) -> ToolResult:
        """Get overall Fed sentiment"""
        prob_result = self._get_probabilities()
        return prob_result
    
    def format_response(self, result: ToolResult) -> str:
        """Format result for Discord display"""
        if not result.success:
            return f"❌ Error: {result.error}"
        
        data = result.data
        
        lines = ["🏦 **Fed Watch**\n"]
        
        # Probabilities
        if data.get("cut_probability"):
            lines.append(f"📉 **Rate Cut:** {data['cut_probability']:.0f}%")
        if data.get("hold_probability"):
            lines.append(f"➡️ **Hold:** {data['hold_probability']:.0f}%")
        if data.get("hike_probability"):
            lines.append(f"📈 **Rate Hike:** {data['hike_probability']:.0f}%")
        
        # Sentiment
        if data.get("sentiment"):
            sent_emoji = "🕊️" if data["sentiment"] == "DOVISH" else "🦅" if data["sentiment"] == "HAWKISH" else "⚖️"
            lines.append(f"\n{sent_emoji} **Sentiment:** {data['sentiment']}")
        
        # Market impact
        if data.get("market_impact"):
            impact_emoji = "📈" if data["market_impact"] == "BULLISH" else "📉" if data["market_impact"] == "BEARISH" else "➡️"
            lines.append(f"{impact_emoji} **Market Impact:** {data['market_impact']}")
        
        # Comments
        if data.get("comments"):
            lines.append("\n**Recent Comments:**")
            for comment in data["comments"][:3]:
                # comment is a FedComment object
                official = getattr(comment, "official_name", "Fed Official")
                snippet = getattr(comment, "content", "")[:100]
                lines.append(f"  • {official}: \"{snippet}...\"")
        
        return "\n".join(lines)



