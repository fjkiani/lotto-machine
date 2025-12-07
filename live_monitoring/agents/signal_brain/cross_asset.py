"""
🧠 Signal Brain - Cross-Asset Correlation
=========================================
Detects when SPY and QQQ give same or conflicting signals.

SPY at support + QQQ at support = STRONG CONFIRMATION
"""

import logging
from typing import Dict, Optional

from .models import SignalState, CrossAssetSignal, Bias

logger = logging.getLogger(__name__)


class CrossAssetAnalyzer:
    """
    Analyzes correlation between SPY and QQQ signals.
    """
    
    # Distance threshold - "at support" if within 0.5%
    AT_LEVEL_THRESHOLD = 0.50
    
    def analyze(
        self,
        spy_state: Optional[SignalState],
        qqq_state: Optional[SignalState]
    ) -> Dict:
        """
        Analyze cross-asset correlation.
        
        Returns:
            {
                'signal': CrossAssetSignal,
                'detail': str,
                'boost': float,  # Add to confluence score
            }
        """
        if not spy_state or not qqq_state:
            return {
                'signal': CrossAssetSignal.NEUTRAL,
                'detail': "Missing data for one or both assets",
                'boost': 0.0,
            }
        
        # Check if both at support
        spy_at_support = spy_state.at_support
        qqq_at_support = qqq_state.at_support
        
        spy_at_resistance = spy_state.at_resistance
        qqq_at_resistance = qqq_state.at_resistance
        
        # BULLISH CONFIRMATION: Both at support
        if spy_at_support and qqq_at_support:
            return {
                'signal': CrossAssetSignal.CONFIRMS,
                'detail': "Both SPY and QQQ at support zones = STRONG bullish confirmation",
                'boost': 0.20,  # +20% confluence boost
            }
        
        # BEARISH CONFIRMATION: Both at resistance
        if spy_at_resistance and qqq_at_resistance:
            return {
                'signal': CrossAssetSignal.CONFIRMS,
                'detail': "Both SPY and QQQ at resistance zones = STRONG bearish confirmation",
                'boost': 0.20,
            }
        
        # DIVERGENCE: One at support, one at resistance
        if (spy_at_support and qqq_at_resistance) or (spy_at_resistance and qqq_at_support):
            return {
                'signal': CrossAssetSignal.DIVERGENT,
                'detail': "SPY and QQQ showing opposite signals - CAUTION",
                'boost': -0.15,  # Penalty
            }
        
        # PARTIAL: One at level, one not
        if spy_at_support or qqq_at_support:
            which = "SPY" if spy_at_support else "QQQ"
            return {
                'signal': CrossAssetSignal.NEUTRAL,
                'detail': f"Only {which} at support - partial signal",
                'boost': 0.05,
            }
        
        if spy_at_resistance or qqq_at_resistance:
            which = "SPY" if spy_at_resistance else "QQQ"
            return {
                'signal': CrossAssetSignal.NEUTRAL,
                'detail': f"Only {which} at resistance - partial signal",
                'boost': 0.05,
            }
        
        return {
            'signal': CrossAssetSignal.NEUTRAL,
            'detail': "Neither asset at key levels",
            'boost': 0.0,
        }
    
    def check_at_level(self, state: SignalState) -> tuple[bool, bool]:
        """
        Check if symbol is at support or resistance.
        
        Returns: (at_support, at_resistance)
        """
        at_support = False
        at_resistance = False
        
        # Check support zones
        if state.support_zones:
            nearest = state.support_zones[0]  # Sorted by distance
            if nearest.distance_pct <= self.AT_LEVEL_THRESHOLD:
                at_support = True
        
        # Check resistance zones
        if state.resistance_zones:
            nearest = state.resistance_zones[0]
            if nearest.distance_pct <= self.AT_LEVEL_THRESHOLD:
                at_resistance = True
        
        return at_support, at_resistance


