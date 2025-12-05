"""
📊 MACRO NARRATIVE AGENT
========================
Deep research on economic data, global macro, market regime.

Searches:
- Economic releases (NFP, CPI, etc.)
- Global macro events
- Market regime analysis
- Intermarket correlations
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseNarrativeAgent, AgentResult

logger = logging.getLogger(__name__)


class MacroNarrativeAgent(BaseNarrativeAgent):
    """
    Specialized agent for macro/economic intelligence.
    
    Focuses on:
    - Today's economic releases and impact
    - Global macro events
    - Market regime (risk-on/risk-off)
    - Intermarket signals (bonds, dollar, VIX)
    """
    
    def __init__(self, tavily_client):
        super().__init__(tavily_client, name="MacroAgent", domain="MACRO")
        
        # Key economic indicators
        self.key_indicators = [
            "NFP", "CPI", "PPI", "PCE", "GDP", 
            "Retail Sales", "Industrial Production",
            "Jobless Claims", "ISM", "Consumer Confidence"
        ]
    
    def research(self, context: Dict[str, Any]) -> AgentResult:
        """
        Research macro/economic context.
        
        Args:
            context: {
                'symbol': str,
                'fed_sentiment': str,
                'recent_event': dict,  # Recent economic event
            }
        """
        self.logger.info("📊 MacroAgent researching...")
        
        symbol = context.get('symbol', 'SPY')
        fed_sentiment = context.get('fed_sentiment', 'NEUTRAL')
        recent_event = context.get('recent_event', {})
        
        # Build focused queries
        queries = [
            "US economic data releases today market impact",
            "risk on risk off market regime December 2025",
            "Treasury yields dollar VIX intermarket signals",
        ]
        
        # Add event-specific query if we have one
        if recent_event:
            event_name = recent_event.get('name', '')
            if event_name:
                queries.append(f"{event_name} market reaction analysis")
        
        all_content = []
        all_sources = []
        
        for query in queries:
            try:
                result = self.tavily.search_financial(query, max_results=3)
                if result.answer:
                    all_content.append(result.answer)
                all_sources.extend(result.top_sources)
            except Exception as e:
                self.logger.warning(f"Macro query failed: {e}")
        
        # Combine and analyze
        full_context = "\n\n".join(all_content) if all_content else ""
        
        # Extract key points
        key_points = self._extract_macro_points(full_context, recent_event)
        
        # Determine regime
        regime = self._determine_regime(full_context, fed_sentiment)
        bias = "BULLISH" if regime == "RISK_ON" else "BEARISH" if regime == "RISK_OFF" else "NEUTRAL"
        
        # Calculate confidence
        confidence = 0.6 if all_content else 0.3
        
        # Build summary
        summary = self._build_macro_summary(regime, key_points, recent_event)
        
        # Trade implication
        trade_implication = self._get_macro_trade_implication(regime, fed_sentiment)
        
        return self._create_result(
            summary=summary,
            full_context=full_context,
            key_points=key_points,
            bias=bias,
            confidence=confidence,
            impact="MEDIUM",
            trade_implication=trade_implication,
            risk_factors=["Economic data surprise", "Global macro shock"],
            sources=all_sources[:5]
        )
    
    def _extract_macro_points(self, text: str, recent_event: Dict) -> List[str]:
        """Extract key macro points."""
        points = []
        text_lower = text.lower()
        
        # Add recent event if available
        if recent_event:
            event_name = recent_event.get('name', '')
            actual = recent_event.get('actual')
            forecast = recent_event.get('forecast')
            if event_name and actual is not None and forecast is not None:
                diff = actual - forecast
                if diff > 0:
                    points.append(f"{event_name} BEAT: {actual:.1f} vs {forecast:.1f} expected")
                elif diff < 0:
                    points.append(f"{event_name} MISS: {actual:.1f} vs {forecast:.1f} expected")
                else:
                    points.append(f"{event_name} IN-LINE: {actual:.1f}")
        
        # Check for market regime keywords
        if "risk on" in text_lower or "risk-on" in text_lower:
            points.append("Market regime: RISK ON")
        elif "risk off" in text_lower or "risk-off" in text_lower:
            points.append("Market regime: RISK OFF")
        
        # Check for VIX
        if "vix" in text_lower:
            if "spike" in text_lower or "elevated" in text_lower:
                points.append("VIX elevated - fear in market")
            elif "low" in text_lower or "calm" in text_lower:
                points.append("VIX low - complacency")
        
        # Check for treasury/bonds
        if "treasury" in text_lower or "yields" in text_lower:
            if "rising" in text_lower or "higher" in text_lower:
                points.append("Treasury yields rising")
            elif "falling" in text_lower or "lower" in text_lower:
                points.append("Treasury yields falling")
        
        # Check for dollar
        if "dollar" in text_lower or "usd" in text_lower:
            if "strong" in text_lower:
                points.append("USD strength")
            elif "weak" in text_lower:
                points.append("USD weakness")
        
        return points[:5]
    
    def _determine_regime(self, text: str, fed_sentiment: str) -> str:
        """Determine market regime."""
        text_lower = text.lower()
        
        risk_on_score = 0
        risk_off_score = 0
        
        # Check keywords
        risk_on_keywords = ['risk on', 'bullish', 'rally', 'optimism', 'growth']
        risk_off_keywords = ['risk off', 'bearish', 'selloff', 'fear', 'recession']
        
        for k in risk_on_keywords:
            if k in text_lower:
                risk_on_score += 1
        
        for k in risk_off_keywords:
            if k in text_lower:
                risk_off_score += 1
        
        # Fed sentiment impacts regime
        if fed_sentiment == "DOVISH":
            risk_on_score += 1
        elif fed_sentiment == "HAWKISH":
            risk_off_score += 1
        
        if risk_on_score > risk_off_score:
            return "RISK_ON"
        elif risk_off_score > risk_on_score:
            return "RISK_OFF"
        return "NEUTRAL"
    
    def _build_macro_summary(self, regime: str, key_points: List[str], recent_event: Dict) -> str:
        """Build concise macro summary."""
        parts = []
        
        parts.append(f"Regime: {regime}")
        
        if recent_event:
            event_name = recent_event.get('name', '')
            if event_name:
                parts.append(f"Today: {event_name}")
        
        if key_points:
            parts.append(key_points[0])
        
        return " | ".join(parts)
    
    def _get_macro_trade_implication(self, regime: str, fed_sentiment: str) -> str:
        """Get trading implication from macro context."""
        if regime == "RISK_ON":
            return "RISK ON regime - favor LONG equities, SHORT bonds/gold"
        elif regime == "RISK_OFF":
            return "RISK OFF regime - reduce equity exposure, consider TLT/GLD/VIX hedge"
        return "Neutral regime - focus on individual setups, not macro bets"

