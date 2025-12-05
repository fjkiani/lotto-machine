"""
🏛️ INSTITUTIONAL NARRATIVE AGENT
=================================
Deep research on smart money positioning, fund flows, institutional activity.

Searches:
- 13F filings
- Hedge fund positioning
- Dark pool activity analysis
- Institutional flow data
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseNarrativeAgent, AgentResult

logger = logging.getLogger(__name__)


class InstitutionalNarrativeAgent(BaseNarrativeAgent):
    """
    Specialized agent for institutional/smart money intelligence.
    
    Focuses on:
    - What institutions are ACTUALLY doing (not saying)
    - Dark pool activity vs. lit markets
    - Fund positioning changes
    - Smart money vs. retail divergence
    """
    
    def __init__(self, tavily_client):
        super().__init__(tavily_client, name="InstitutionalAgent", domain="INSTITUTIONAL")
    
    def research(self, context: Dict[str, Any]) -> AgentResult:
        """
        Research institutional positioning and activity.
        
        Args:
            context: {
                'dp_levels': list,      # Dark pool battlegrounds
                'current_price': float, # Current price
                'symbol': str,          # Symbol being analyzed
            }
        """
        self.logger.info("🏛️ InstitutionalAgent researching...")
        
        dp_levels = context.get('dp_levels', [])
        current_price = context.get('current_price')
        symbol = context.get('symbol', 'SPY')
        
        # Build focused queries
        queries = [
            f"institutional positioning {symbol} hedge funds December 2025",
            f"dark pool activity {symbol} smart money flow",
            f"13F filings major hedge funds SPY positions",
        ]
        
        all_content = []
        all_sources = []
        
        for query in queries:
            try:
                result = self.tavily.search_institutional(query, max_results=3)
                if result.answer:
                    all_content.append(result.answer)
                all_sources.extend(result.top_sources)
            except Exception as e:
                self.logger.warning(f"Institutional query failed: {e}")
        
        # Combine and analyze
        full_context = "\n\n".join(all_content) if all_content else ""
        
        # Add our DP data as context
        dp_context = self._analyze_dp_levels(dp_levels, current_price)
        if dp_context:
            full_context = f"OUR DARK POOL DATA:\n{dp_context}\n\n{full_context}"
        
        # Extract key points
        key_points = self._extract_institutional_points(full_context, dp_levels, current_price)
        
        # Determine bias from DP positioning
        bias = self._determine_institutional_bias(dp_levels, current_price, full_context)
        
        # Calculate confidence
        confidence = 0.8 if dp_levels else 0.4  # High confidence if we have DP data
        
        # Build summary
        summary = self._build_institutional_summary(dp_levels, current_price, bias)
        
        # Trade implication
        trade_implication = self._get_institutional_trade_implication(dp_levels, current_price, bias)
        
        return self._create_result(
            summary=summary,
            full_context=full_context,
            key_points=key_points,
            bias=bias,
            confidence=confidence,
            impact="HIGH" if dp_levels else "MEDIUM",
            trade_implication=trade_implication,
            risk_factors=["Institutional distribution risk", "Dark pool level break risk"],
            sources=all_sources[:5]
        )
    
    def _analyze_dp_levels(self, dp_levels: List[Dict], current_price: float) -> str:
        """Analyze our dark pool data."""
        if not dp_levels or not current_price:
            return ""
        
        parts = []
        
        # Separate supports and resistances
        supports = [l for l in dp_levels if l.get('price', 0) < current_price]
        resistances = [l for l in dp_levels if l.get('price', 0) > current_price]
        
        # Total volume
        total_vol = sum(l.get('volume', 0) for l in dp_levels)
        support_vol = sum(l.get('volume', 0) for l in supports)
        resistance_vol = sum(l.get('volume', 0) for l in resistances)
        
        parts.append(f"Current price: ${current_price:.2f}")
        parts.append(f"Total DP volume: {total_vol/1e6:.1f}M shares across {len(dp_levels)} levels")
        parts.append(f"Support volume: {support_vol/1e6:.1f}M shares ({len(supports)} levels)")
        parts.append(f"Resistance volume: {resistance_vol/1e6:.1f}M shares ({len(resistances)} levels)")
        
        # Key levels
        if dp_levels:
            max_vol_level = max(dp_levels, key=lambda x: x.get('volume', 0))
            parts.append(f"MAJOR LEVEL: ${max_vol_level['price']:.2f} ({max_vol_level['volume']/1e6:.1f}M shares)")
        
        return "\n".join(parts)
    
    def _extract_institutional_points(self, text: str, dp_levels: List[Dict], current_price: float) -> List[str]:
        """Extract key institutional points."""
        points = []
        
        # Points from our DP data
        if dp_levels and current_price:
            supports = [l for l in dp_levels if l.get('price', 0) < current_price]
            resistances = [l for l in dp_levels if l.get('price', 0) > current_price]
            
            if len(supports) > len(resistances):
                points.append(f"More DP support ({len(supports)}) than resistance ({len(resistances)}) - institutions accumulated")
            elif len(resistances) > len(supports):
                points.append(f"More DP resistance ({len(resistances)}) than support ({len(supports)}) - distribution possible")
            
            # Major level
            if dp_levels:
                max_vol = max(dp_levels, key=lambda x: x.get('volume', 0))
                vol_str = f"{max_vol['volume']/1e6:.1f}M"
                points.append(f"Major institutional level: ${max_vol['price']:.2f} ({vol_str})")
        
        # Points from research
        text_lower = text.lower()
        
        if "accumulating" in text_lower or "buying" in text_lower:
            points.append("Institutions accumulating")
        if "distributing" in text_lower or "selling" in text_lower:
            points.append("Institutions distributing")
        if "hedge" in text_lower:
            points.append("Hedging activity noted")
        
        return points[:5]
    
    def _determine_institutional_bias(self, dp_levels: List[Dict], current_price: float, text: str) -> str:
        """Determine bias from institutional positioning."""
        if not dp_levels or not current_price:
            return self._extract_bias(text)
        
        # Calculate support vs resistance
        support_vol = sum(l.get('volume', 0) for l in dp_levels if l.get('price', 0) < current_price)
        resistance_vol = sum(l.get('volume', 0) for l in dp_levels if l.get('price', 0) > current_price)
        
        if support_vol > resistance_vol * 1.5:
            return "BULLISH"  # More support = institutions accumulated below
        elif resistance_vol > support_vol * 1.5:
            return "BEARISH"  # More resistance = institutions selling above
        
        return "NEUTRAL"
    
    def _build_institutional_summary(self, dp_levels: List[Dict], current_price: float, bias: str) -> str:
        """Build concise institutional summary."""
        if not dp_levels or not current_price:
            return "No DP data - limited institutional visibility"
        
        parts = []
        
        # Position relative to levels
        supports = [l for l in dp_levels if l.get('price', 0) < current_price]
        
        parts.append(f"Institutions: {bias}")
        parts.append(f"{len(supports)} support levels below")
        
        # Nearest major level
        if dp_levels:
            max_vol = max(dp_levels, key=lambda x: x.get('volume', 0))
            vol_str = f"{max_vol['volume']/1e6:.1f}M"
            if max_vol['price'] < current_price:
                parts.append(f"Key support ${max_vol['price']:.2f} ({vol_str})")
            else:
                parts.append(f"Key resistance ${max_vol['price']:.2f} ({vol_str})")
        
        return " | ".join(parts)
    
    def _get_institutional_trade_implication(self, dp_levels: List[Dict], current_price: float, bias: str) -> str:
        """Get trading implication from institutional context."""
        if not dp_levels:
            return "No DP data - trade with caution"
        
        if bias == "BULLISH":
            supports = sorted([l for l in dp_levels if l.get('price', 0) < current_price], 
                            key=lambda x: x.get('price', 0), reverse=True)
            if supports:
                nearest = supports[0]
                return f"BULLISH: Institutions accumulated. Buy dips to ${nearest['price']:.2f} support"
        
        elif bias == "BEARISH":
            resistances = sorted([l for l in dp_levels if l.get('price', 0) > current_price],
                               key=lambda x: x.get('price', 0))
            if resistances:
                nearest = resistances[0]
                return f"BEARISH: Distribution pattern. Fade rallies to ${nearest['price']:.2f} resistance"
        
        return "NEUTRAL: Wait for price to test a major DP level before acting"

