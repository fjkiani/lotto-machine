"""
Fed Watch Shift Predictor - Phase 3

Predicts how Fed Watch probabilities change after economic releases.

Uses category-specific coefficients learned from historical data.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class FedShiftPredictor:
    """
    Predicts Fed Watch probability shift after economic release.
    
    Historical patterns:
    - Hot CPI (+0.2% surprise) → Fed Watch cut prob drops 5-8%
    - Weak NFP (-50k surprise) → Fed Watch cut prob rises 3-5%
    - Strong GDP (+0.3% surprise) → Fed Watch cut prob drops 2-4%
    """
    
    # Base coefficients (learned from historical data)
    CATEGORY_COEFFICIENTS = {
        'INFLATION': {
            'direction': -1,  # Higher inflation = lower cut probability
            'sensitivity': 25.0  # 1% surprise = 25% shift
        },
        'EMPLOYMENT': {
            'direction': -1,  # Stronger employment = lower cut probability
            'sensitivity': 15.0
        },
        'LABOR': {
            'direction': -1,  # Stronger labor = lower cut probability
            'sensitivity': 15.0  # Same as EMPLOYMENT — ADP/NFP category
        },
        'GROWTH': {
            'direction': -1,  # Stronger growth = lower cut probability
            'sensitivity': 10.0
        },
        'CONSUMER': {
            'direction': -1,
            'sensitivity': 5.0
        },
        'SENTIMENT': {
            'direction': -1,
            'sensitivity': 5.0
        },
        'MANUFACTURING': {
            'direction': -1,
            'sensitivity': 5.0
        },
        'CENTRAL_BANK': {
            'direction': 0,  # Fed decisions are direct, not inferred
            'sensitivity': 0.0
        },
        'OTHER': {
            'direction': -1,
            'sensitivity': 3.0
        }
    }
    
    def __init__(self):
        """Initialize Fed Shift Predictor"""
        logger.info("🏦 FedShiftPredictor initialized")
    
    def predict_shift(self, category: str, surprise: float) -> float:
        """
        Predict Fed Watch shift (static coefficients).
        
        Args:
            category: Event category (INFLATION, LABOR, EMPLOYMENT, etc.)
            surprise: Surprise magnitude (positive = beat, negative = miss)
        
        Returns:
            Predicted Fed Watch shift in percentage points
        """
        coef = self.CATEGORY_COEFFICIENTS.get(category.upper(), {
            'direction': -1,
            'sensitivity': 5.0
        })
        
        shift = coef['direction'] * surprise * coef['sensitivity']
        
        logger.debug(f"   Fed shift prediction: {category} surprise {surprise:+.2%} → {shift:+.1f}%")
        
        return shift
    
    def predict_shift_with_regime(self, category: str, surprise: float) -> Dict[str, float]:
        """
        Regime-aware Fed Watch shift prediction.
        
        Uses live FedWatchEngine to apply hawkish/dovish multipliers:
          p_hike > 25% → hawkish surprises hit 1.6x harder
          p_cut  > 60% → dovish surprises hit 1.6x harder
        
        Returns:
            {'shift': float, 'regime': str, 'multiplier': float}
        """
        base_shift = self.predict_shift(category, surprise)
        
        # Get live regime
        regime = 'HOLD'
        multiplier = 1.0
        try:
            from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
            fw = FedWatchEngine()
            probs = fw.get_probabilities()
            if probs and 'next_meeting' in probs:
                nm = probs['next_meeting']
                p_hike = nm.get('p_hike_25', 0)
                p_cut = nm.get('p_cut_25', 0)
                
                if p_hike > 25:
                    regime = 'HIKE_RISK'
                    # Hawkish surprises (negative shift = inflation up) hit harder
                    multiplier = 1.6 if base_shift < 0 else 0.8
                elif p_cut > 60:
                    regime = 'CUT_CYCLE'
                    # Dovish surprises (positive shift = weak data) hit harder
                    multiplier = 0.8 if base_shift < 0 else 1.6
        except Exception as e:
            logger.warning(f"FedWatch regime check failed: {e}")
        
        adjusted_shift = base_shift * multiplier
        
        return {
            'shift': round(adjusted_shift, 2),
            'base_shift': round(base_shift, 2),
            'regime': regime,
            'multiplier': multiplier,
        }
    
    def get_scenario_shifts(self, category: str) -> Dict[str, float]:
        """
        Get Fed Watch shifts for weak/strong scenarios.
        
        Returns:
            {
                'weak_shift': -3.0,  # If data is weak
                'strong_shift': 3.0   # If data is strong
            }
        """
        coef = self.CATEGORY_COEFFICIENTS.get(category.upper(), {
            'direction': -1,
            'sensitivity': 5.0
        })
        
        # Assume ±0.1 surprise for scenarios
        weak_surprise = -0.1  # Data weaker than expected
        strong_surprise = 0.1  # Data stronger than expected
        
        weak_shift = coef['direction'] * weak_surprise * coef['sensitivity']
        strong_shift = coef['direction'] * strong_surprise * coef['sensitivity']
        
        return {
            'weak_shift': weak_shift,
            'strong_shift': strong_shift
        }

