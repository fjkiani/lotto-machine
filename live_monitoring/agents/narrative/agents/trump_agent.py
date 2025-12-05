"""
🎯 TRUMP NARRATIVE AGENT
========================
Deep research on Trump policy, tariffs, market influence.

Searches:
- Executive orders
- Tariff announcements
- Trade policy changes
- Political developments with market impact
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseNarrativeAgent, AgentResult

logger = logging.getLogger(__name__)


class TrumpNarrativeAgent(BaseNarrativeAgent):
    """
    Specialized agent for Trump policy intelligence.
    
    Focuses on:
    - Tariff policy and changes
    - Trade war developments
    - Executive orders with market impact
    - Political uncertainty factors
    """
    
    def __init__(self, tavily_client):
        super().__init__(tavily_client, name="TrumpAgent", domain="TRUMP")
        
        # Key topics to track
        self.key_topics = [
            "tariffs",
            "trade war",
            "china",
            "mexico",
            "executive order",
            "IEEPA",
            "immigration",
        ]
        
        # Sectors impacted
        self.impacted_sectors = {
            "tariffs": ["XLI", "EWC", "EWW", "FXI", "GM", "F"],
            "immigration": ["XLF", "XLRE", "XLU"],
            "china": ["BABA", "JD", "PDD", "KWEB"],
            "tech": ["QQQ", "XLK", "AAPL", "NVDA"],
        }
    
    def research(self, context: Dict[str, Any]) -> AgentResult:
        """
        Research Trump policy and market impact.
        
        Args:
            context: {
                'trump_risk': str,  # LOW/MEDIUM/HIGH
                'trump_news': str,  # Latest news headline
                'symbol': str,      # Symbol being analyzed
            }
        """
        self.logger.info("🎯 TrumpAgent researching...")
        
        trump_risk = context.get('trump_risk', 'LOW')
        trump_news = context.get('trump_news', '')
        symbol = context.get('symbol', 'SPY')
        
        # Build focused queries
        queries = [
            "Trump tariff policy latest announcements market impact today",
            "Trump executive orders affecting markets stocks",
            "Trade policy China Mexico tariffs December 2025",
        ]
        
        # Add symbol-specific query if relevant
        if symbol in ['SPY', 'QQQ']:
            queries.append(f"Trump policy impact on {symbol} broader market")
        
        all_content = []
        all_sources = []
        
        for query in queries:
            try:
                result = self.tavily.search_financial(query, max_results=3)
                if result.answer:
                    all_content.append(result.answer)
                all_sources.extend(result.top_sources)
            except Exception as e:
                self.logger.warning(f"Trump query failed: {e}")
        
        # Combine and analyze
        full_context = "\n\n".join(all_content) if all_content else ""
        
        # Extract key points
        key_points = self._extract_trump_points(full_context, trump_news)
        
        # Determine bias
        bias = self._determine_trump_bias(full_context, trump_risk)
        
        # Calculate confidence
        confidence = 0.65 if all_content else 0.3
        
        # Get impacted symbols
        impacted = self._get_impacted_symbols(full_context)
        
        # Build summary
        summary = self._build_trump_summary(trump_risk, key_points, impacted)
        
        # Trade implication
        trade_implication = self._get_trump_trade_implication(bias, trump_risk, impacted)
        
        return self._create_result(
            summary=summary,
            full_context=full_context,
            key_points=key_points,
            bias=bias,
            confidence=confidence,
            impact="HIGH" if trump_risk == "HIGH" else "MEDIUM",
            trade_implication=trade_implication,
            risk_factors=["Policy uncertainty", "Tariff escalation", "Trade war risk"],
            sources=all_sources[:5]
        )
    
    def _extract_trump_points(self, text: str, trump_news: str) -> List[str]:
        """Extract key Trump-related points."""
        points = []
        text_lower = text.lower()
        
        # Check for tariff mentions
        if "tariff" in text_lower:
            if "25%" in text or "25 percent" in text_lower:
                points.append("25% tariffs announced/threatened")
            elif "increase" in text_lower or "new" in text_lower:
                points.append("New tariff measures")
            elif "exempt" in text_lower or "remove" in text_lower:
                points.append("Tariff exemptions/removals")
        
        # Check for trade war
        if "china" in text_lower:
            if "retaliation" in text_lower:
                points.append("China retaliation risk")
            elif "negotiation" in text_lower or "talk" in text_lower:
                points.append("China trade negotiations")
        
        if "mexico" in text_lower:
            points.append("Mexico trade/immigration policy")
        
        # Check for executive actions
        if "executive order" in text_lower:
            points.append("New executive orders")
        
        if "ieepa" in text_lower:
            points.append("Emergency economic powers invoked")
        
        # Add from trump_news if not captured
        if trump_news and not points:
            points.append(trump_news[:80])
        
        return points[:5]
    
    def _determine_trump_bias(self, text: str, trump_risk: str) -> str:
        """Determine market bias from Trump context."""
        if trump_risk == "HIGH":
            return "BEARISH"
        
        text_lower = text.lower()
        
        # Policy uncertainty is generally bearish
        if any(k in text_lower for k in ['tariff', 'trade war', 'uncertainty', 'escalation']):
            return "BEARISH"
        
        if any(k in text_lower for k in ['deal', 'agreement', 'resolution', 'exempt']):
            return "BULLISH"
        
        return "NEUTRAL"
    
    def _get_impacted_symbols(self, text: str) -> List[str]:
        """Get symbols likely impacted by Trump policy."""
        impacted = []
        text_lower = text.lower()
        
        for topic, symbols in self.impacted_sectors.items():
            if topic in text_lower:
                impacted.extend(symbols)
        
        # Deduplicate
        return list(dict.fromkeys(impacted))[:6]
    
    def _build_trump_summary(self, trump_risk: str, key_points: List[str], impacted: List[str]) -> str:
        """Build concise Trump summary."""
        parts = []
        
        parts.append(f"Trump risk: {trump_risk}")
        
        if key_points:
            parts.append(key_points[0])
        
        if impacted:
            parts.append(f"Watch: {', '.join(impacted[:3])}")
        
        return " | ".join(parts)
    
    def _get_trump_trade_implication(self, bias: str, trump_risk: str, impacted: List[str]) -> str:
        """Get trading implication from Trump context."""
        if bias == "BEARISH" and trump_risk == "HIGH":
            if impacted:
                return f"HIGH RISK: Consider SHORT/hedge {', '.join(impacted[:3])} - policy uncertainty elevated"
            return "HIGH RISK: Reduce equity exposure, consider VIX hedge"
        elif bias == "BEARISH":
            return "MODERATE RISK: Caution on trade-sensitive names"
        elif bias == "BULLISH":
            return "Policy uncertainty easing - risk-on positioning supported"
        return "Monitor for policy announcements - no immediate action"

