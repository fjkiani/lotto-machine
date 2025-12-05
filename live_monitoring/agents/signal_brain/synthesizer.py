"""
🧠 Signal Brain - Synthesizer
=============================
Generates ONE unified alert from all inputs.

Takes 7 siloed alerts → 1 actionable synthesis with full reasoning.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    SynthesisResult, SignalState, MarketContext, ConfluenceScore,
    TradeRecommendation, CrossAssetSignal, Bias, SupportZone, ZoneRank
)

logger = logging.getLogger(__name__)


class SignalSynthesizer:
    """
    Synthesizes all signals into ONE unified output.
    """
    
    # Confluence thresholds
    THRESHOLD_STRONG = 75  # Take full position
    THRESHOLD_MEDIUM = 55  # Take half position
    THRESHOLD_WEAK = 40    # Take quarter position
    
    def synthesize(
        self,
        spy_state: Optional[SignalState],
        qqq_state: Optional[SignalState],
        context: MarketContext,
        confluence: ConfluenceScore,
        cross_asset_result: Dict,
    ) -> SynthesisResult:
        """
        Create unified synthesis from all inputs.
        """
        result = SynthesisResult(
            timestamp=datetime.now(),
            symbols=["SPY", "QQQ"],
            context=context,
        )
        
        if spy_state:
            result.states["SPY"] = spy_state
        if qqq_state:
            result.states["QQQ"] = qqq_state
        
        result.cross_asset = cross_asset_result['signal']
        result.cross_asset_detail = cross_asset_result['detail']
        result.confluence = confluence
        
        # Generate thinking/reasoning
        result.thinking = self._generate_thinking(spy_state, qqq_state, context, confluence)
        
        # Generate trade recommendation
        result.recommendation = self._generate_recommendation(
            spy_state, qqq_state, context, confluence
        )
        
        return result
    
    def _generate_thinking(
        self,
        spy_state: Optional[SignalState],
        qqq_state: Optional[SignalState],
        context: MarketContext,
        confluence: ConfluenceScore,
    ) -> str:
        """Generate the reasoning narrative."""
        lines = []
        
        # Support structure analysis
        if spy_state and spy_state.support_zones:
            primary = [z for z in spy_state.support_zones if z.rank == ZoneRank.PRIMARY]
            secondary = [z for z in spy_state.support_zones if z.rank == ZoneRank.SECONDARY]
            
            if primary:
                total_vol = sum(z.combined_volume for z in primary)
                lines.append(f"SPY has {len(primary)} PRIMARY support zone(s) with {total_vol/1e6:.1f}M total institutional volume.")
            
            if len(primary) >= 2:
                lines.append(f"Multiple strong support zones stacked - this is LAYERED PROTECTION.")
            
            if spy_state.at_support:
                nearest = spy_state.support_zones[0]
                lines.append(f"Currently testing {nearest.range_str} support ({nearest.volume_str} shares).")
        
        # Cross-asset
        if confluence.cross_asset_score > 0.8:
            lines.append("QQQ showing same pattern - CROSS-ASSET CONFIRMATION increases confidence.")
        
        # Macro headwinds/tailwinds
        if context.fed_sentiment == "DOVISH":
            lines.append("Fed dovish stance provides macro tailwind.")
        elif context.fed_sentiment == "HAWKISH":
            lines.append("Fed hawkish stance is a headwind - consider smaller size.")
        
        if context.trump_risk == "HIGH":
            lines.append("Elevated Trump policy risk - be ready to exit quickly.")
        
        # VIX
        if context.vix_level > 20:
            lines.append(f"VIX at {context.vix_level:.1f} indicates elevated volatility - wider stops needed.")
        
        # Timing
        if context.time_of_day.value in ["POWER_HOUR", "OPEN"]:
            lines.append(f"Good timing - {context.time_of_day.value} has high institutional participation.")
        elif context.time_of_day.value == "MIDDAY":
            lines.append("Midday session typically choppy - consider waiting for Power Hour.")
        
        return " ".join(lines) if lines else "Standard market conditions."
    
    def _generate_recommendation(
        self,
        spy_state: Optional[SignalState],
        qqq_state: Optional[SignalState],
        context: MarketContext,
        confluence: ConfluenceScore,
    ) -> TradeRecommendation:
        """Generate ONE clear trade recommendation."""
        
        # Default: WAIT
        rec = TradeRecommendation(
            action="WAIT",
            symbol="SPY",
            entry_price=0.0,
            stop_price=0.0,
            target_price=0.0,
            size="NONE",
            risk_reward=0.0,
            primary_reason="Insufficient confluence",
            why_this_level="",
            risks=[],
        )
        
        if not spy_state or confluence.score < self.THRESHOLD_WEAK:
            rec.primary_reason = f"Confluence {confluence.score:.0f}% below {self.THRESHOLD_WEAK}% threshold"
            return rec
        
        # Determine size based on confluence
        if confluence.score >= self.THRESHOLD_STRONG:
            size = "FULL"
        elif confluence.score >= self.THRESHOLD_MEDIUM:
            size = "HALF"
        else:
            size = "QUARTER"
        
        # BULLISH setup at support
        if confluence.bias == Bias.BULLISH and spy_state.support_zones:
            target_zone = self._find_best_zone(spy_state.support_zones, context.spy_price)
            
            if target_zone:
                entry = round(target_zone.center_price + 0.10, 2)
                stop = round(target_zone.center_price - (target_zone.max_price - target_zone.min_price) - 0.50, 2)
                risk = entry - stop
                target = round(entry + (risk * 2.5), 2)  # 2.5:1 R/R
                
                rec = TradeRecommendation(
                    action="LONG",
                    symbol="SPY",
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    size=size,
                    risk_reward=round((target - entry) / (entry - stop), 1),
                    primary_reason=f"Bullish confluence at {target_zone.rank.value} support",
                    why_this_level=f"{target_zone.volume_str} institutional volume at {target_zone.range_str}",
                    risks=confluence.conflicts.copy(),
                )
                
                # Check if we need to wait
                distance = abs(context.spy_price - target_zone.center_price)
                if distance / context.spy_price * 100 > 0.15:
                    rec.wait_for = f"Wait for price to test {target_zone.range_str}"
                    rec.action = "WAIT"
        
        # BEARISH setup at resistance
        elif confluence.bias == Bias.BEARISH and spy_state.resistance_zones:
            target_zone = self._find_best_zone(spy_state.resistance_zones, context.spy_price)
            
            if target_zone:
                entry = round(target_zone.center_price - 0.10, 2)
                stop = round(target_zone.center_price + (target_zone.max_price - target_zone.min_price) + 0.50, 2)
                risk = stop - entry
                target = round(entry - (risk * 2.5), 2)
                
                rec = TradeRecommendation(
                    action="SHORT",
                    symbol="SPY",
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    size=size,
                    risk_reward=round((entry - target) / (stop - entry), 1),
                    primary_reason=f"Bearish confluence at {target_zone.rank.value} resistance",
                    why_this_level=f"{target_zone.volume_str} institutional volume at {target_zone.range_str}",
                    risks=confluence.conflicts.copy(),
                )
        
        return rec
    
    def _find_best_zone(self, zones: List[SupportZone], current_price: float) -> Optional[SupportZone]:
        """Find the best zone to trade - prioritize PRIMARY rank and proximity."""
        if not zones:
            return None
        
        # Primary zones first
        primary = [z for z in zones if z.rank == ZoneRank.PRIMARY]
        if primary:
            # Closest primary
            return min(primary, key=lambda z: z.distance_pct)
        
        # Secondary zones
        secondary = [z for z in zones if z.rank == ZoneRank.SECONDARY]
        if secondary:
            return min(secondary, key=lambda z: z.distance_pct)
        
        # Any zone
        return min(zones, key=lambda z: z.distance_pct)
    
    def to_discord_embed(self, result: SynthesisResult) -> Dict:
        """Convert synthesis to Discord embed format."""
        # Color based on bias
        color_map = {
            Bias.BULLISH: 0x00FF00,  # Green
            Bias.BEARISH: 0xFF0000,  # Red
            Bias.NEUTRAL: 0xFFFF00,  # Yellow
        }
        
        # Build support structure text
        support_text = ""
        if "SPY" in result.states:
            spy = result.states["SPY"]
            for z in spy.support_zones[:3]:  # Top 3
                icon = "🔥" if z.rank == ZoneRank.PRIMARY else "⚡" if z.rank == ZoneRank.SECONDARY else "📍"
                support_text += f"{icon} {z.rank.value}: {z.range_str} ({z.volume_str})\n"
        
        # Build trade text
        trade_text = ""
        rec = result.recommendation
        if rec and rec.action != "WAIT":
            trade_text = f"Direction: {'📈 LONG' if rec.action == 'LONG' else '📉 SHORT'}\n"
            trade_text += f"Entry: ${rec.entry_price:.2f}\n"
            trade_text += f"Stop: ${rec.stop_price:.2f}\n"
            trade_text += f"Target: ${rec.target_price:.2f}\n"
            trade_text += f"R/R: {rec.risk_reward}:1\n"
            trade_text += f"Size: {rec.size}"
        elif rec and rec.wait_for:
            trade_text = f"⏳ {rec.wait_for}\n"
            trade_text += f"Setup: {'📈 LONG' if result.confluence.bias == Bias.BULLISH else '📉 SHORT'}"
        
        # Cross-asset text
        cross_text = f"{'✅' if result.cross_asset == CrossAssetSignal.CONFIRMS else '⚠️' if result.cross_asset == CrossAssetSignal.DIVERGENT else '➖'} {result.cross_asset_detail}"
        
        embed = {
            "title": f"🧠 MARKET SYNTHESIS | {result.confluence.score:.0f}% {result.confluence.bias.value}",
            "color": color_map.get(result.confluence.bias, 0x808080),
            "fields": [
                {
                    "name": "📍 SUPPORT STRUCTURE",
                    "value": support_text or "No zones detected",
                    "inline": False
                },
                {
                    "name": "🔗 CROSS-ASSET",
                    "value": cross_text,
                    "inline": False
                },
                {
                    "name": "💭 THE THINKING",
                    "value": result.thinking[:1000] if result.thinking else "Standard conditions",
                    "inline": False
                },
                {
                    "name": "🎯 THE TRADE",
                    "value": trade_text or "No actionable setup",
                    "inline": False
                },
            ],
            "footer": {
                "text": f"SPY ${result.context.spy_price:.2f} | VIX {result.context.vix_level:.1f} | {result.context.time_of_day.value}"
            },
            "timestamp": result.timestamp.isoformat(),
        }
        
        # Add risks if any
        if rec and rec.risks:
            embed["fields"].append({
                "name": "⚠️ RISKS",
                "value": "\n".join(f"• {r}" for r in rec.risks[:3]),
                "inline": False
            })
        
        return embed

