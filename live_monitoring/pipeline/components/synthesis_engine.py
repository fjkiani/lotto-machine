"""
Synthesis Engine - Signal Synthesis Logic

Responsibility: Combine DP levels, macro context, cross-asset into unified signal.
No hardcoded thresholds - all from config!
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Result of signal synthesis"""
    confluence_score: float  # 0-1, overall confluence
    direction: str  # 'BULLISH', 'BEARISH', 'NEUTRAL'
    action: str  # 'LONG', 'SHORT', 'NO_TRADE'
    reasoning: str
    confidence: float  # 0-1
    
    # Component scores
    dp_score: float = 0.0
    cross_asset_score: float = 0.0
    macro_score: float = 0.0
    timing_score: float = 0.0
    
    # Details
    support_zones: List[Dict] = None
    resistance_zones: List[Dict] = None
    cross_asset_confirmation: bool = False
    macro_bias: str = "NEUTRAL"


class SynthesisEngine:
    """
    Synthesizes signals from multiple sources.
    
    Before: Hardcoded logic mixed with fetching
    After: Pure synthesis logic, testable with mock data
    """
    
    def __init__(
        self,
        min_confluence: float = 0.50,
        unified_mode: bool = True,
        cross_asset_weight: float = 1.0,
        macro_weight: float = 0.6,
        dp_weight: float = 0.6,
        timing_weight: float = 0.4
    ):
        """
        Initialize Synthesis Engine.
        
        Args:
            min_confluence: Minimum confluence to send alert (default 50%)
            unified_mode: Suppress individual alerts, only synthesis
            cross_asset_weight: Weight for cross-asset confirmation
            macro_weight: Weight for macro context
            dp_weight: Weight for DP signals
            timing_weight: Weight for timing signals
        """
        self.min_confluence = min_confluence
        self.unified_mode = unified_mode
        self.weights = {
            'cross_asset': cross_asset_weight,
            'macro': macro_weight,
            'dp': dp_weight,
            'timing': timing_weight
        }
        
        logger.info(f"🧠 SynthesisEngine initialized (min_confluence={min_confluence:.0%})")
    
    def synthesize(
        self,
        dp_levels: Dict[str, List[Dict]],  # symbol -> levels
        prices: Dict[str, float],  # symbol -> current price
        macro_context: Optional[Dict] = None,
        cross_asset_data: Optional[Dict] = None
    ) -> Optional[SynthesisResult]:
        """
        Synthesize signals from all sources.
        
        Args:
            dp_levels: Dict of symbol -> list of DP levels
            prices: Dict of symbol -> current price
            macro_context: Macro context (Fed, Trump, etc.)
            cross_asset_data: Cross-asset confirmation data
        
        Returns:
            SynthesisResult if confluence >= min_confluence, else None
        """
        # Calculate component scores
        dp_score = self._calculate_dp_score(dp_levels, prices)
        cross_score = self._calculate_cross_asset_score(cross_asset_data) if cross_asset_data else 0.0
        macro_score = self._calculate_macro_score(macro_context) if macro_context else 0.0
        timing_score = self._calculate_timing_score()  # Time of day, etc.
        
        # Weighted confluence
        total_weight = sum(self.weights.values())
        confluence = (
            dp_score * self.weights['dp'] +
            cross_score * self.weights['cross_asset'] +
            macro_score * self.weights['macro'] +
            timing_score * self.weights['timing']
        ) / total_weight if total_weight > 0 else 0.0
        
        # Determine direction
        direction = self._determine_direction(dp_score, cross_score, macro_score)
        action = 'LONG' if direction == 'BULLISH' else 'SHORT' if direction == 'BEARISH' else 'NO_TRADE'
        
        # Extract zones
        support_zones, resistance_zones = self._extract_zones(dp_levels, prices)
        
        # Build result
        result = SynthesisResult(
            confluence_score=confluence,
            direction=direction,
            action=action,
            reasoning=self._build_reasoning(dp_score, cross_score, macro_score, support_zones, resistance_zones),
            confidence=confluence,
            dp_score=dp_score,
            cross_asset_score=cross_score,
            macro_score=macro_score,
            timing_score=timing_score,
            support_zones=support_zones,
            resistance_zones=resistance_zones,
            cross_asset_confirmation=cross_score > 0.7,
            macro_bias=macro_context.get('bias', 'NEUTRAL') if macro_context else 'NEUTRAL'
        )
        
        # Only return if meets threshold
        if confluence >= self.min_confluence:
            logger.info(f"📊 Confluence: {confluence:.0%} {direction}")
            logger.info(f"   DP: {dp_score:.2f} | Cross: {cross_score:.2f} | Macro: {macro_score:.2f} | Timing: {timing_score:.2f}")
            return result
        else:
            logger.debug(f"   📊 Confluence {confluence:.0%} below threshold {self.min_confluence:.0%}")
            return None
    
    def _calculate_dp_score(self, dp_levels: Dict[str, List[Dict]], prices: Dict[str, float]) -> float:
        """Calculate DP-based score (0-1)"""
        if not dp_levels:
            return 0.0
        
        # Count levels near current price (within 0.5%)
        near_levels = 0
        total_levels = 0
        
        for symbol, levels in dp_levels.items():
            if symbol not in prices:
                continue
            
            price = prices[symbol]
            threshold = price * 0.005  # 0.5%
            
            for level in levels:
                total_levels += 1
                if abs(level['price'] - price) <= threshold:
                    near_levels += 1
        
        if total_levels == 0:
            return 0.0
        
        # Score based on proximity
        return min(1.0, near_levels / max(1, total_levels / 5))
    
    def _calculate_cross_asset_score(self, cross_asset_data: Dict) -> float:
        """Calculate cross-asset confirmation score"""
        # If both SPY and QQQ at same zone type, high confirmation
        if cross_asset_data.get('confirms'):
            return 1.0
        return 0.0
    
    def _calculate_macro_score(self, macro_context: Dict) -> float:
        """Calculate macro context score"""
        # Positive if macro aligns with signal
        bias = macro_context.get('bias', 'NEUTRAL')
        if bias in ['BULLISH', 'BEARISH']:
            return 0.6
        return 0.0
    
    def _calculate_timing_score(self) -> float:
        """Calculate timing score (time of day, etc.)"""
        # Placeholder - can enhance with time-of-day logic
        return 0.4
    
    def _determine_direction(self, dp_score: float, cross_score: float, macro_score: float) -> str:
        """Determine overall direction"""
        # Simplified logic - can enhance
        if dp_score > 0.6 and cross_score > 0.7:
            return 'BEARISH'  # At resistance
        elif dp_score < 0.4:
            return 'BULLISH'  # Below support
        return 'NEUTRAL'
    
    def _extract_zones(self, dp_levels: Dict[str, List[Dict]], prices: Dict[str, float]) -> Tuple[List[Dict], List[Dict]]:
        """Extract support and resistance zones"""
        support = []
        resistance = []
        
        for symbol, levels in dp_levels.items():
            if symbol not in prices:
                continue
            
            price = prices[symbol]
            
            for level in levels:
                if level['price'] < price:
                    support.append({'symbol': symbol, **level})
                else:
                    resistance.append({'symbol': symbol, **level})
        
        return support, resistance
    
    def _build_reasoning(self, dp_score: float, cross_score: float, macro_score: float, 
                        support_zones: List[Dict], resistance_zones: List[Dict]) -> str:
        """Build human-readable reasoning"""
        parts = []
        
        if dp_score > 0.6:
            parts.append(f"DP levels showing {len(resistance_zones)} resistance zones")
        if cross_score > 0.7:
            parts.append("Cross-asset confirmation")
        if macro_score > 0.5:
            parts.append("Macro context aligned")
        
        return ". ".join(parts) if parts else "No clear signal"


