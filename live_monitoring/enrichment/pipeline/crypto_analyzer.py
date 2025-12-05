"""
Crypto Correlation Analyzer

Analyzes Bitcoin/Ethereum correlation with equities to determine risk regime.
Swappable component for cross-asset risk detection.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def analyze_crypto_correlation(symbol: str, date: str) -> Dict[str, Any]:
    """
    Analyze crypto correlation with equities for risk regime detection.
    
    Args:
        symbol: Equity ticker (e.g., 'SPY')
        date: Date string in 'YYYY-MM-DD' format
        
    Returns:
        Dictionary with crypto analysis:
        - regime: str (RISK_ON, RISK_OFF, NEUTRAL)
        - btc_change_10d: float (10-day BTC change %)
        - eth_change_10d: float (10-day ETH change %)
        - correlation: str (description)
    """
    try:
        from live_monitoring.enrichment.crypto_correlation import (
            CryptoCorrelationDetector
        )
        
        detector = CryptoCorrelationDetector()
        result = detector.detect_crypto_correlation(date)
        
        logger.info(
            "🪙 Crypto regime: %s (BTC 10d: %.2f%%)",
            result.get('regime', 'UNKNOWN'),
            result.get('btc_change_10d', 0.0)
        )
        
        return result
        
    except Exception as e:
        logger.error("Error analyzing crypto correlation: %s", e)
        return {
            "regime": "NEUTRAL",
            "btc_change_10d": 0.0,
            "eth_change_10d": 0.0,
            "correlation": "Unable to determine",
        }


def extract_cross_asset_data(crypto_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract cross-asset data for validation.
    
    Args:
        crypto_result: Output from analyze_crypto_correlation
        
    Returns:
        Dictionary formatted for narrative validation
    """
    return {
        "btc_10d_change": crypto_result.get("btc_change_10d", 0.0),
        "btc_5d_losing_streak": crypto_result.get("btc_5d_losing_streak", False),
        "spy_btc_both_down": crypto_result.get("spy_btc_both_down", False),
    }

