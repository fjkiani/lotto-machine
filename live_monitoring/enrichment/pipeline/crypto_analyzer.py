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
        - btc_change_pct: float
        - eth_change_pct: float
        - btc_price: float
        - eth_price: float
        - correlation_to_spy: float
    """
    try:
        from live_monitoring.enrichment.crypto_correlation import (
            CryptoCorrelationDetector
        )
        
        detector = CryptoCorrelationDetector(lookback_minutes=60)
        sentiment = detector.get_crypto_sentiment()
        
        if sentiment is None:
            logger.warning("CryptoCorrelationDetector returned None")
            return {
                "regime": "NEUTRAL",
                "btc_change_pct": 0.0,
                "eth_change_pct": 0.0,
                "correlation": "Unable to determine",
            }
        
        # Map CryptoSentiment dataclass to dict
        # CryptoSentiment uses `environment` (not `risk_environment`)
        regime = sentiment.environment.name if hasattr(sentiment.environment, 'name') else str(sentiment.environment)
        
        result = {
            "regime": regime,
            "btc_change_pct": sentiment.btc_change_pct * 100.0,
            "eth_change_pct": sentiment.eth_change_pct * 100.0,
            "btc_price": sentiment.btc_price,
            "eth_price": sentiment.eth_price,
            "correlation_to_spy": sentiment.correlation,
            "btc_change_10d": sentiment.btc_change_pct * 100.0,  # Alias for validation
            "eth_change_10d": sentiment.eth_change_pct * 100.0,  # Alias for validation
        }
        
        logger.info(
            "🪙 Crypto regime: %s (BTC %.2f%%, ETH %.2f%%)",
            regime, result["btc_change_pct"], result["eth_change_pct"]
        )
        
        return result
        
    except Exception as e:
        logger.error("Error analyzing crypto correlation: %s", e)
        return {
            "regime": "NEUTRAL",
            "btc_change_pct": 0.0,
            "eth_change_pct": 0.0,
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

