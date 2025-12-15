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
        'GROWTH': {
            'direction': -1,  # Stronger growth = lower cut probability
            'sensitivity': 10.0
        },
        'CONSUMER': {
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
        Predict Fed Watch shift.
        
        Args:
            category: Event category (INFLATION, EMPLOYMENT, etc.)
            surprise: Surprise magnitude (positive = beat, negative = miss)
        
        Returns:
            Predicted Fed Watch shift in percentage points
        
        Example:
            category='INFLATION', surprise=0.2 (hot CPI)
            → shift = -1 * 0.2 * 25 = -5% (cut probability drops)
        """
        coef = self.CATEGORY_COEFFICIENTS.get(category.upper(), {
            'direction': -1,
            'sensitivity': 5.0
        })
        
        shift = coef['direction'] * surprise * coef['sensitivity']
        
        logger.debug(f"   Fed shift prediction: {category} surprise {surprise:+.2%} → {shift:+.1f}%")
        
        return shift
    
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

