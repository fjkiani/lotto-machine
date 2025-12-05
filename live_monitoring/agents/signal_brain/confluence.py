"""
🧠 Signal Brain - Confluence Scoring
====================================
Calculates overall confluence from all signal sources.

Weights:
- DP signals: 40%
- Cross-asset: 20%
- Macro (Fed/Trump): 20%
- Timing: 20%
"""

import logging
from typing import Dict, List, Optional

from .models import (
    ConfluenceScore, Bias, SignalState, MarketContext,
    CrossAssetSignal, TimeOfDay, ZoneRank
)

logger = logging.getLogger(__name__)


class ConfluenceScorer:
    """
    Calculates multi-factor confluence score.
    """
    
    # Weights
    WEIGHT_DP = 0.40
    WEIGHT_CROSS_ASSET = 0.20
    WEIGHT_MACRO = 0.20
    WEIGHT_TIMING = 0.20
    
    def calculate(
        self,
        spy_state: Optional[SignalState],
        qqq_state: Optional[SignalState],
        context: MarketContext,
        cross_asset_result: Dict,
    ) -> ConfluenceScore:
        """
        Calculate overall confluence score.
        
        Returns:
            ConfluenceScore with 0-100 score and bias
        """
        score = ConfluenceScore(score=0.0, bias=Bias.NEUTRAL)
        
        # 1. DP SCORE (40%)
        dp_score, dp_bias, dp_confirmations, dp_conflicts = self._score_dp(spy_state, qqq_state)
        score.dp_score = dp_score
        score.confirmations.extend(dp_confirmations)
        score.conflicts.extend(dp_conflicts)
        
        # 2. CROSS-ASSET SCORE (20%)
        cross_score = self._score_cross_asset(cross_asset_result)
        score.cross_asset_score = cross_score
        if cross_asset_result['signal'] == CrossAssetSignal.CONFIRMS:
            score.confirmations.append(cross_asset_result['detail'])
        elif cross_asset_result['signal'] == CrossAssetSignal.DIVERGENT:
            score.conflicts.append(cross_asset_result['detail'])
        
        # 3. MACRO SCORE (20%)
        macro_score, macro_bias = self._score_macro(context, dp_bias)
        score.macro_score = macro_score
        
        # 4. TIMING SCORE (20%)
        timing_score = self._score_timing(context)
        score.timing_score = timing_score
        
        # Calculate weighted total
        total = (
            dp_score * self.WEIGHT_DP +
            cross_score * self.WEIGHT_CROSS_ASSET +
            macro_score * self.WEIGHT_MACRO +
            timing_score * self.WEIGHT_TIMING
        )
        
        # Convert to 0-100
        score.score = round(total * 100, 1)
        
        # Determine bias
        score.bias = self._determine_bias(dp_bias, macro_bias, context, spy_state)
        
        logger.info(f"📊 Confluence: {score.score:.0f}% {score.bias.value}")
        logger.info(f"   DP: {dp_score:.2f} | Cross: {cross_score:.2f} | Macro: {macro_score:.2f} | Timing: {timing_score:.2f}")
        
        return score
    
    def _score_dp(
        self, 
        spy_state: Optional[SignalState], 
        qqq_state: Optional[SignalState]
    ) -> tuple[float, Bias, List[str], List[str]]:
        """Score dark pool signals."""
        score = 0.0
        bias = Bias.NEUTRAL
        confirmations = []
        conflicts = []
        
        if not spy_state:
            return score, bias, confirmations, conflicts
        
        # Check for strong support zones
        primary_supports = [z for z in spy_state.support_zones if z.rank == ZoneRank.PRIMARY]
        primary_resistances = [z for z in spy_state.resistance_zones if z.rank == ZoneRank.PRIMARY]
        
        # At or near PRIMARY support = bullish
        if spy_state.at_support and primary_supports:
            score = 0.9  # Strong signal
            bias = Bias.BULLISH
            confirmations.append(f"SPY at PRIMARY support ${primary_supports[0].center_price:.2f} ({primary_supports[0].volume_str})")
        elif spy_state.at_support:
            score = 0.6
            bias = Bias.BULLISH
            confirmations.append("SPY at support zone")
        
        # At or near PRIMARY resistance = bearish
        if spy_state.at_resistance and primary_resistances:
            score = 0.9
            bias = Bias.BEARISH
            confirmations.append(f"SPY at PRIMARY resistance ${primary_resistances[0].center_price:.2f} ({primary_resistances[0].volume_str})")
        elif spy_state.at_resistance:
            score = 0.6
            bias = Bias.BEARISH
            confirmations.append("SPY at resistance zone")
        
        # Multiple support zones stacked = very bullish
        if len(primary_supports) >= 2:
            score = min(1.0, score + 0.1)
            confirmations.append(f"Multiple PRIMARY support zones ({len(primary_supports)})")
        
        return score, bias, confirmations, conflicts
    
    def _score_cross_asset(self, cross_result: Dict) -> float:
        """Score cross-asset correlation."""
        if cross_result['signal'] == CrossAssetSignal.CONFIRMS:
            return 1.0
        elif cross_result['signal'] == CrossAssetSignal.DIVERGENT:
            return 0.2  # Penalty
        elif cross_result['boost'] > 0:
            return 0.6  # Partial
        return 0.4  # Neutral
    
    def _score_macro(self, context: MarketContext, dp_bias: Bias) -> tuple[float, Bias]:
        """Score macro environment (Fed, Trump)."""
        score = 0.5  # Neutral baseline
        bias = Bias.NEUTRAL
        
        # Fed sentiment
        if context.fed_sentiment == "DOVISH":
            score += 0.25
            bias = Bias.BULLISH
        elif context.fed_sentiment == "HAWKISH":
            score -= 0.15
            bias = Bias.BEARISH
        
        # Trump risk
        if context.trump_risk == "HIGH":
            score -= 0.15
        elif context.trump_risk == "LOW":
            score += 0.1
        
        # VIX level (high VIX = caution)
        if context.vix_level > 25:
            score -= 0.15
        elif context.vix_level < 15:
            score += 0.1
        
        # Align with DP bias for bonus
        if dp_bias != Bias.NEUTRAL and dp_bias == bias:
            score += 0.1  # Alignment bonus
        
        return max(0, min(1.0, score)), bias
    
    def _score_timing(self, context: MarketContext) -> float:
        """Score time-of-day timing."""
        scores = {
            TimeOfDay.PREMARKET: 0.3,
            TimeOfDay.OPEN: 0.7,       # High volume, good for breakouts
            TimeOfDay.MORNING: 0.6,
            TimeOfDay.MIDDAY: 0.4,     # Choppy
            TimeOfDay.AFTERNOON: 0.6,
            TimeOfDay.POWER_HOUR: 0.8,  # Institutional activity
            TimeOfDay.AFTER_HOURS: 0.2,
        }
        return scores.get(context.time_of_day, 0.5)
    
    def _determine_bias(
        self, 
        dp_bias: Bias, 
        macro_bias: Bias, 
        context: MarketContext,
        spy_state: Optional[SignalState]
    ) -> Bias:
        """Determine overall bias."""
        # DP bias is primary
        if dp_bias != Bias.NEUTRAL:
            return dp_bias
        
        # Fallback to macro
        if macro_bias != Bias.NEUTRAL:
            return macro_bias
        
        # Fallback to trend
        if context.spy_trend_1h != Bias.NEUTRAL:
            return context.spy_trend_1h
        
        return Bias.NEUTRAL

