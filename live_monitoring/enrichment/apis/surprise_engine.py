"""
📊 Surprise Engine — Smart surprise computation with category awareness.

Replaces the hardcoded surprise logic in release_detector.py.
Handles percentage-vs-absolute detection, per-category thresholds, 
and continuous confidence scaling.

Usage:
    from surprise_engine import SurpriseEngine
    
    engine = SurpriseEngine()
    result = engine.compute('Existing Home Sales JAN', actual=3.91e6, consensus=3.93e6)
    # result.surprise_pct = -0.51%
    # result.surprise_class = MISS 
    # result.signal = DOVISH_MILD (not DOVISH — below mild threshold)
    # result.confidence = 0.10 (scaled continuously, not discrete 0.60)
"""

import logging
from dataclasses import dataclass
from typing import Optional

from live_monitoring.enrichment.apis.release_config import (
    ReleaseSignal, SurpriseClass,
    get_profile, classify_category, is_percentage_value,
)

logger = logging.getLogger(__name__)


@dataclass
class SurpriseResult:
    """Complete surprise computation result from a single layer."""
    surprise: float              # raw: actual - consensus
    surprise_pct: float          # percentage or absolute diff
    pct_method: str              # 'relative' or 'absolute_diff'
    surprise_class: SurpriseClass
    signal: ReleaseSignal
    confidence: float            # 0.0 - 1.0 (continuously scaled)
    category: str
    directions: dict             # {SPY: '↑', TLT: '↓', ...}
    symbols: list                # ['SPY', 'TLT', ...]
    fed_shift: float
    debug: dict                  # all intermediate values for backtesting
    macro_filtered: bool = False # True if macro filter suppressed this signal
    macro_reason: str = ''       # why it was filtered


class SurpriseEngine:
    """
    Computes surprise, classifies signal, maps directions.
    All thresholds come from release_config.py — nothing hardcoded here.
    """
    
    def __init__(self):
        from live_monitoring.agents.economic.fed_shift_predictor import FedShiftPredictor
        self.predictor = FedShiftPredictor()
    
    def compute(
        self,
        event_name: str,
        actual: float,
        consensus: float,
        previous: Optional[float] = None,
        importance: str = 'HIGH',
    ) -> SurpriseResult:
        """
        Full surprise computation through all layers.
        
        Returns a SurpriseResult with signal, confidence, directions — ready to trade.
        """
        profile = get_profile(event_name)
        category = profile['category']
        
        # ── Layer 1: Surprise magnitude ──
        surprise = actual - consensus
        surprise_pct, pct_method = self._compute_surprise_pct(
            event_name, actual, consensus, profile
        )
        
        # ── Layer 2: Surprise classification ──
        surprise_class = self._classify_surprise(surprise_pct, profile)
        
        # ── Layer 3: Signal classification (per-category thresholds) ──
        signal = self._classify_signal(surprise_pct, profile)
        
        # ── Layer 4: Confidence (continuous scaling) ──
        confidence = self._compute_confidence(
            surprise_pct, importance, profile
        )
        
        # ── Layer 5: Direction mapping ──
        directions = self._map_directions(signal, profile)
        symbols = list(directions.keys())
        
        # ── Layer 6: FedShift ──
        fed_shift = self.predictor.predict_shift(category, surprise_pct)
        
        debug = {
            'neutral_threshold': profile['neutral_threshold'],
            'mild_threshold': profile['mild_threshold'],
            'confidence_scale': profile['confidence_scale'],
            'direction_mode': profile['direction_mode'],
            'value_type': profile['value_type'],
            'abs_surprise': abs(surprise_pct),
            'importance': importance,
        }
        
        result = SurpriseResult(
            surprise=surprise,
            surprise_pct=surprise_pct,
            pct_method=pct_method,
            surprise_class=surprise_class,
            signal=signal,
            confidence=confidence,
            category=category,
            directions=directions,
            symbols=symbols,
            fed_shift=fed_shift,
            debug=debug,
        )
        
        logger.info(
            f"{'🔥' if surprise_class != SurpriseClass.IN_LINE else '➖'} "
            f"{event_name} | surp={surprise_pct:+.2f}% | {signal.value} "
            f"| conf={confidence:.2f} | FS={fed_shift:+.1f} | {directions}"
        )
        
        return result
    
    def compute_with_macro(
        self,
        event_name: str,
        actual: float,
        consensus: float,
        previous: Optional[float] = None,
        importance: str = 'HIGH',
        vix: Optional[float] = None,
        cpi_yoy: Optional[float] = None,
    ) -> SurpriseResult:
        """
        Layer 7: Macro Context Filter (V3 — post gate-grid audit).
        
        Wraps compute() and applies ONLY filters that survived OOS testing
        on 49 CPI + 50 Housing releases across 2022-2026.
        
        SURVIVING FILTER:
          1. DOVISH SUPPRESSION — CPI DOVISH→SPY↑ was 30% (N=10),
             Housing MISS→SPY↓ was 50% (N=10), TLT DOVISH 0/9.
             Direction: suppress all DOVISH signals.
        
        RETIRED (2026-03-10):
          - Static VIX gate (VIX≤20): Overfit to 2024. 80% CPI HAWKISH
            OOS achieved WITHOUT any VIX gate. Adaptive gate made Housing
            OOS worse (27% vs 39% unfiltered). Simplest wins.
        
        EVIDENCE (Gate Grid, 2022-2026):
          - CPI HAWKISH OOS (daily): 80% (4/5), 95% CI [37.6%-96.4%]
          - Housing daily: 39% OOS, 42% IS — NO EDGE, PARKED
          - Housing 30m: 63% IS — edge is resolution, not filter
          - N<15 on all CPI buckets — paper trade before capital
        
        REGIME (info only, not gating):
          elevated_inflation: CPI ≥ 4.0% (2022-2023)
          last_mile: CPI < 4.0% (2024-2026)
        """
        result = self.compute(event_name, actual, consensus, previous, importance)
        
        # ── Regime tag (info only — NOT used for gating) ──
        if cpi_yoy is not None:
            result.debug['regime'] = 'elevated_inflation' if cpi_yoy >= 4.0 else 'last_mile'
        if vix is not None:
            result.debug['vix'] = vix
        
        # ── Gate 1: DOVISH suppression (confirmed OOS) ──
        # DOVISH CPI → SPY↑: 30% OOS (broken, N=10)
        # DOVISH Housing → SPY↓: 50% OOS (coin flip, N=10)
        # DOVISH → TLT↑: 0/9 (completely broken)
        is_dovish = result.signal in (ReleaseSignal.DOVISH, ReleaseSignal.DOVISH_MILD)
        if is_dovish:
            result.macro_filtered = True
            result.macro_reason = 'DOVISH_SUPPRESSED'
            result.confidence *= 0.25  # near-zero confidence
            # Remove TLT from directions — 0/9 accuracy
            if 'TLT' in result.directions:
                del result.directions['TLT']
                result.symbols = list(result.directions.keys())
            result.debug['macro_dovish_suppressed'] = True
            logger.info(f"🛑 DOVISH SUPPRESSED: {event_name} — dovish signals unreliable")
        
        # ── Gate 2: Mark clean HAWKISH signals ──
        if not result.macro_filtered and result.signal != ReleaseSignal.NEUTRAL:
            result.debug['macro_clean'] = True
            logger.info(f"🟢 CLEAN SIGNAL: {event_name} {result.signal.value} conf={result.confidence:.2f}")
        
        return result
    
    def _compute_surprise_pct(
        self, event_name: str, actual: float, consensus: float, profile: dict
    ) -> tuple:
        """
        Smart surprise percentage computation.
        
        - Percentage data (CPI 0.3%): use absolute difference (pp)
        - Absolute data (Home Sales 3.91M): use relative % change
        """
        surprise = actual - consensus
        
        # Check if this event reports percentage values
        if profile['value_type'] == 'percentage' or is_percentage_value(event_name, consensus):
            # Percentage-on-percentage: use absolute difference
            # CPI: 0.5% vs 0.3% → 0.2 (percentage points), NOT 66.67%
            # Round to 6dp to avoid floating point edge cases
            # e.g. 3.2 - 3.1 = 0.10000000000000009, not 0.1
            return round(surprise, 6), 'absolute_diff'
        else:
            # Absolute values: use relative change
            # Housing: 3.91M vs 3.93M → -0.51%
            if consensus != 0:
                return round(surprise / abs(consensus) * 100, 6), 'relative'
            return 0.0, 'relative'
    
    def _classify_surprise(self, surprise_pct: float, profile: dict) -> SurpriseClass:
        """Classify as BEAT/MISS/IN-LINE using category-specific thresholds."""
        surprise_pct = round(surprise_pct, 6) # Round to 6dp to avoid floating point edge cases
        threshold = profile['neutral_threshold']
        if surprise_pct > threshold:
            return SurpriseClass.BEAT
        elif surprise_pct < -threshold:
            return SurpriseClass.MISS
        return SurpriseClass.IN_LINE
    
    def _classify_signal(self, surprise_pct: float, profile: dict) -> ReleaseSignal:
        """
        Classify signal using per-category thresholds.
        
        - Below neutral_threshold → NEUTRAL
        - Between neutral and mild → MILD
        - Above mild → FULL
        """
        abs_s = abs(surprise_pct)
        neutral = profile['neutral_threshold']
        mild = profile['mild_threshold']
        
        if abs_s <= neutral:
            return ReleaseSignal.NEUTRAL
        
        is_positive = surprise_pct > 0
        is_strong = abs_s > mild
        
        if is_positive:
            return ReleaseSignal.HAWKISH if is_strong else ReleaseSignal.HAWKISH_MILD
        else:
            return ReleaseSignal.DOVISH if is_strong else ReleaseSignal.DOVISH_MILD
    
    def _compute_confidence(
        self, surprise_pct: float, importance: str, profile: dict
    ) -> float:
        """
        Continuous confidence scaling — no more discrete 0.8/0.6/0.4/0.2 steps.
        
        Formula: conf = min(0.95, |surprise| × scale_factor × importance_multiplier)
        
        Backtested calibration (GROWTH/housing):
          -0.51% → 0.10 (barely trade)
          -0.98% → 0.20 (caution)  ← Oct was 0.60 before, now correctly low
          +2.44% → 0.49 (medium)
          -4.10% → 0.82 (strong)   ← Dec was 0.60 before, now correctly high
        """
        abs_s = abs(surprise_pct)
        scale = profile['confidence_scale']
        neutral = profile['neutral_threshold']
        
        # Below neutral → minimal confidence
        if abs_s <= neutral:
            return 0.10
        
        # Continuous scaling from neutral threshold
        effective_surprise = abs_s - neutral  # only count surprise ABOVE noise
        raw_conf = effective_surprise * scale
        
        # Importance multiplier
        if importance == 'CRITICAL':
            raw_conf *= 1.5
        elif importance == 'HIGH':
            raw_conf *= 1.2
        elif importance == 'MEDIUM':
            raw_conf *= 0.8
        else:
            raw_conf *= 0.5
        
        # Clamp to [0.15, 0.95]
        return max(0.15, min(0.95, raw_conf))
    
    def _map_directions(self, signal: ReleaseSignal, profile: dict) -> dict:
        """Get direction map from category profile — no inline overrides."""
        if signal == ReleaseSignal.NEUTRAL:
            return {}
        
        dir_map = profile.get('directions', {})
        return dict(dir_map.get(signal.value, {}))
