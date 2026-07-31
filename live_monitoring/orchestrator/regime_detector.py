"""
📊 REGIME DETECTOR

Multi-factor market regime detection (UPTREND, DOWNTREND, CHOPPY, etc.)
"""

import logging
from datetime import datetime, time as dt_time
from typing import Dict

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Detects market regime using multiple factors."""
    
    def detect(self, current_price: float, symbol: str = 'SPY') -> str:
        """Detect market regime — DELEGATES to canonical regime_state.

        Single-source rule: exactly ONE regime computation exists
        (backend.app.signals.regime_state.compute_regime). This detector is
        retained only as a compatibility shim for callers that pass a live
        price; all logic is removed. No regime logic lives here.
        """
        try:
            from backend.app.signals import regime_state
            result = regime_state.get_regime(
                layers={"spy_price": current_price} if current_price else {},
                kill_chain_result=None,
            )
            logger.debug(f"   REGIME (canonical): {result['regime']} ({result['reason']})")
            return result["regime"]
        except Exception as e:
            logger.warning(f"   regime_state delegation failed, fallback UNKNOWN: {e}")
            return "UNKNOWN"

    def get_regime_details(self, current_price: float, symbol: str = 'SPY') -> Dict:
        """Get detailed regime information including signal counts."""
        # This would be called after detect() to get cached details
        # For now, return basic info
        regime = self.detect(current_price, symbol)
        return {
            'regime': regime,
            'symbol': symbol,
            'price': current_price
        }

