"""
📈 TECHNICAL NARRATIVE AGENT
============================
Deep research on price action, levels, and technical context.

Searches:
- Key technical levels
- Chart patterns
- Volume analysis
- Options flow/positioning
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseNarrativeAgent, AgentResult

logger = logging.getLogger(__name__)


class TechnicalNarrativeAgent(BaseNarrativeAgent):
    """
    Specialized agent for technical/price action intelligence.
    
    Focuses on:
    - Key technical levels being tested
    - Price action context
    - Options flow and positioning
    - Volume analysis
    """
    
    def __init__(self, tavily_client):
        super().__init__(tavily_client, name="TechnicalAgent", domain="TECHNICAL")
    
    def research(self, context: Dict[str, Any]) -> AgentResult:
        """
        Research technical context.
        
        Args:
            context: {
                'symbol': str,
                'current_price': float,
                'dp_levels': list,
            }
        """
        self.logger.info("📈 TechnicalAgent researching...")
        
        symbol = context.get('symbol', 'SPY')
        current_price = context.get('current_price')
        dp_levels = context.get('dp_levels', [])
        
        # Build focused queries
        queries = [
            f"{symbol} technical analysis key levels support resistance today",
            f"{symbol} options flow gamma exposure max pain",
            f"{symbol} volume analysis institutional activity",
        ]
        
        all_content = []
        all_sources = []
        
        for query in queries:
            try:
                result = self.tavily.search_financial(query, max_results=3)
                if result.answer:
                    all_content.append(result.answer)
                all_sources.extend(result.top_sources)
            except Exception as e:
                self.logger.warning(f"Technical query failed: {e}")
        
        # Combine and analyze
        full_context = "\n\n".join(all_content) if all_content else ""
        
        # Add our levels as context
        levels_context = self._analyze_levels(dp_levels, current_price)
        if levels_context:
            full_context = f"OUR LEVELS:\n{levels_context}\n\n{full_context}"
        
        # Extract key points
        key_points = self._extract_technical_points(full_context, dp_levels, current_price)
        
        # Determine bias from price position
        bias = self._determine_technical_bias(dp_levels, current_price, full_context)
        
        # Calculate confidence
        confidence = 0.7 if dp_levels and current_price else 0.4
        
        # Build summary
        summary = self._build_technical_summary(symbol, current_price, dp_levels, bias)
        
        # Trade implication
        trade_implication = self._get_technical_trade_implication(dp_levels, current_price, bias)
        
        return self._create_result(
            summary=summary,
            full_context=full_context,
            key_points=key_points,
            bias=bias,
            confidence=confidence,
            impact="MEDIUM",
            trade_implication=trade_implication,
            risk_factors=["Level break risk", "Options expiration risk"],
            sources=all_sources[:5]
        )
    
    def _analyze_levels(self, dp_levels: List[Dict], current_price: float) -> str:
        """Analyze price relative to levels."""
        if not dp_levels or not current_price:
            return ""
        
        parts = []
        parts.append(f"Price: ${current_price:.2f}")
        
        # Sort by distance
        levels_with_distance = []
        for l in dp_levels:
            price = l.get('price', 0)
            vol = l.get('volume', 0)
            distance = abs(current_price - price)
            distance_pct = distance / price * 100
            levels_with_distance.append({
                **l, 
                'distance': distance, 
                'distance_pct': distance_pct,
                'type': 'SUPPORT' if price < current_price else 'RESISTANCE'
            })
        
        levels_sorted = sorted(levels_with_distance, key=lambda x: x['distance'])
        
        for l in levels_sorted[:5]:
            vol_str = f"{l['volume']/1e6:.1f}M" if l['volume'] >= 1e6 else f"{l['volume']/1e3:.0f}K"
            parts.append(f"{l['type']}: ${l['price']:.2f} ({vol_str}) - {l['distance_pct']:.2f}% away")
        
        return "\n".join(parts)
    
    def _extract_technical_points(self, text: str, dp_levels: List[Dict], current_price: float) -> List[str]:
        """Extract key technical points."""
        points = []
        text_lower = text.lower()
        
        # Points from our levels
        if dp_levels and current_price:
            # Nearest level
            nearest = min(dp_levels, key=lambda x: abs(x.get('price', 0) - current_price))
            distance_pct = abs(current_price - nearest['price']) / nearest['price'] * 100
            
            if distance_pct < 0.2:
                vol_str = f"{nearest['volume']/1e6:.1f}M" if nearest['volume'] >= 1e6 else f"{nearest['volume']/1e3:.0f}K"
                level_type = 'support' if nearest['price'] < current_price else 'resistance'
                points.append(f"AT {level_type} ${nearest['price']:.2f} ({vol_str})")
            elif distance_pct < 0.5:
                points.append(f"NEAR key level ${nearest['price']:.2f}")
        
        # Points from research
        if "breakout" in text_lower:
            points.append("Breakout pattern forming")
        if "breakdown" in text_lower:
            points.append("Breakdown risk")
        if "support" in text_lower and "holding" in text_lower:
            points.append("Support holding")
        if "resistance" in text_lower and "rejecting" in text_lower:
            points.append("Resistance rejecting")
        if "max pain" in text_lower:
            points.append("Options max pain in play")
        if "gamma" in text_lower:
            points.append("Gamma exposure significant")
        
        return points[:5]
    
    def _determine_technical_bias(self, dp_levels: List[Dict], current_price: float, text: str) -> str:
        """Determine bias from technical context."""
        if not dp_levels or not current_price:
            return self._extract_bias(text)
        
        # Price position relative to levels
        supports_below = [l for l in dp_levels if l.get('price', 0) < current_price]
        resistances_above = [l for l in dp_levels if l.get('price', 0) > current_price]
        
        support_vol = sum(l.get('volume', 0) for l in supports_below)
        resistance_vol = sum(l.get('volume', 0) for l in resistances_above)
        
        # More support volume = bullish (institutions accumulated)
        if support_vol > resistance_vol * 1.3:
            return "BULLISH"
        elif resistance_vol > support_vol * 1.3:
            return "BEARISH"
        
        return "NEUTRAL"
    
    def _build_technical_summary(self, symbol: str, current_price: float, dp_levels: List[Dict], bias: str) -> str:
        """Build concise technical summary."""
        parts = []
        
        if current_price:
            parts.append(f"{symbol} ${current_price:.2f}")
        
        parts.append(f"Technical: {bias}")
        
        if dp_levels and current_price:
            # Nearest level
            nearest = min(dp_levels, key=lambda x: abs(x.get('price', 0) - current_price))
            level_type = 'support' if nearest['price'] < current_price else 'resistance'
            parts.append(f"Near {level_type} ${nearest['price']:.2f}")
        
        return " | ".join(parts)
    
    def _get_technical_trade_implication(self, dp_levels: List[Dict], current_price: float, bias: str) -> str:
        """Get trading implication from technical context."""
        if not dp_levels or not current_price:
            return "No key levels - wait for structure"
        
        # Find nearest support and resistance
        supports = sorted([l for l in dp_levels if l.get('price', 0) < current_price],
                        key=lambda x: x.get('price', 0), reverse=True)
        resistances = sorted([l for l in dp_levels if l.get('price', 0) > current_price],
                           key=lambda x: x.get('price', 0))
        
        if supports and resistances:
            sup = supports[0]
            res = resistances[0]
            return f"Range: Support ${sup['price']:.2f} | Resistance ${res['price']:.2f} - trade edges, not middle"
        elif supports:
            return f"Support at ${supports[0]['price']:.2f} - buy dips, stop below"
        elif resistances:
            return f"Resistance at ${resistances[0]['price']:.2f} - fade rallies, stop above"
        
        return "Technical setup unclear - wait for clarity"

