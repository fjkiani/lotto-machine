#!/usr/bin/env python3
"""
Crypto Correlation Detector - Risk-On/Risk-Off Indicator

Purpose: Use Bitcoin/Ethereum as leading indicators for equity market sentiment
- Bitcoin DOWN + SPY DOWN = RISK_OFF (bearish confirmation)
- Bitcoin UP + SPY UP = RISK_ON (bullish)
- Bitcoin UP + SPY DOWN = DIVERGENCE (investigate/veto)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import logging

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / 'models'))
from enriched_signal import CryptoSentiment, RiskEnvironment, EnrichedSignal

logger = logging.getLogger(__name__)


class CryptoCorrelationDetector:
    """
    Tracks crypto correlation to identify risk-on/risk-off environments
    
    Key Insight: Bitcoin often leads equities by 1-6 hours
    - When BTC breaks down, SPY follows
    - When BTC rallies, risk appetite returns
    
    This is THE edge for timing entries.
    """
    
    def __init__(self, lookback_minutes: int = 30, cache_ttl_seconds: int = 300):
        """
        Args:
            lookback_minutes: How far back to look for 1m bars
            cache_ttl_seconds: Cache lifetime for yfinance data to avoid rate limits
        """
        self.lookback_minutes = lookback_minutes
        self.cache_ttl_seconds = cache_ttl_seconds
        self.btc_ticker = yf.Ticker('BTC-USD')
        self.eth_ticker = yf.Ticker('ETH-USD')

        # Simple in-memory cache so we don't hammer yfinance
        # {
        #   "timestamp": datetime,
        #   "sentiment": CryptoSentiment
        # }
        self._cache: Dict[str, Any] = {}
        
        logger.info("₿ Crypto Correlation Detector initialized")
        logger.info(f"   Lookback: {lookback_minutes} minutes, cache TTL: {cache_ttl_seconds}s")
    
    def get_crypto_sentiment(self) -> Optional[CryptoSentiment]:
        """
        Get real-time crypto sentiment
        
        Returns:
            CryptoSentiment with BTC/ETH prices, changes, correlation, environment
        """
        # First try cache
        try:
            cache_entry = self._cache.get("sentiment")
            if cache_entry:
                ts = cache_entry.get("timestamp")
                if ts and (datetime.utcnow() - ts).total_seconds() < self.cache_ttl_seconds:
                    logger.debug("₿ Using cached crypto sentiment")
                    return cache_entry.get("sentiment")
        except Exception:
            # Cache failures should never kill the pipeline
            self._cache = {}

        try:
            # Fetch 1-minute data for BTC and ETH
            # NOTE: yfinance does not expose a timeout param, so we control
            # load by caching + tight lookback window instead of hammering it.
            btc_df = self.btc_ticker.history(period='1d', interval='1m')
            eth_df = self.eth_ticker.history(period='1d', interval='1m')
            
            if btc_df.empty or eth_df.empty:
                logger.warning("No crypto data available")
                return None
            
            # Get lookback window
            lookback_bars = min(self.lookback_minutes, len(btc_df))
            btc_recent = btc_df.tail(lookback_bars)
            eth_recent = eth_df.tail(lookback_bars)
            
            # Calculate price changes
            btc_start = float(btc_recent['Close'].iloc[0])
            btc_current = float(btc_recent['Close'].iloc[-1])
            btc_change_pct = (btc_current - btc_start) / btc_start
            
            eth_start = float(eth_recent['Close'].iloc[0])
            eth_current = float(eth_recent['Close'].iloc[-1])
            eth_change_pct = (eth_current - eth_start) / eth_start
            
            # Calculate correlation
            btc_returns = btc_recent['Close'].pct_change().dropna()
            eth_returns = eth_recent['Close'].pct_change().dropna()
            
            if len(btc_returns) > 5 and len(eth_returns) > 5:
                correlation = float(btc_returns.corr(eth_returns))
            else:
                correlation = 0.0
            
            # Classify risk environment
            environment = self._classify_environment(btc_change_pct, eth_change_pct)
            
            sentiment = CryptoSentiment(
                btc_price=btc_current,
                btc_change_pct=btc_change_pct,
                eth_price=eth_current,
                eth_change_pct=eth_change_pct,
                correlation=correlation,
                environment=environment
            )

            # Update cache
            try:
                self._cache["sentiment"] = {
                    "timestamp": datetime.utcnow(),
                    "sentiment": sentiment,
                }
            except Exception:
                # Cache write failure is non-fatal
                self._cache = {}
            
            logger.info(f"₿ Crypto Sentiment: BTC {btc_change_pct*100:+.2f}%, ETH {eth_change_pct*100:+.2f}%, {environment.value}")
            
            return sentiment
            
        except Exception as e:
            logger.error(f"Error fetching crypto sentiment: {e}")
            return None
    
    def _classify_environment(self, btc_change: float, eth_change: float) -> RiskEnvironment:
        """
        Classify risk environment based on crypto movements
        
        Logic:
        - Both down >2%: RISK_OFF (bearish)
        - Both up >2%: RISK_ON (bullish)
        - Mixed: NEUTRAL
        """
        threshold = 0.02  # 2% threshold
        
        if btc_change < -threshold and eth_change < -threshold:
            return RiskEnvironment.RISK_OFF
        elif btc_change > threshold and eth_change > threshold:
            return RiskEnvironment.RISK_ON
        else:
            return RiskEnvironment.NEUTRAL
    
    def check_correlation_confirmation(
        self, 
        signal: EnrichedSignal, 
        crypto_sentiment: CryptoSentiment
    ) -> Tuple[bool, float, str]:
        """
        Check if crypto confirms the equity signal
        
        Args:
            signal: The equity signal (SELLOFF, BREAKOUT, etc.)
            crypto_sentiment: Current crypto environment
        
        Returns:
            (confirmed, confidence_boost, rationale)
            
        Logic:
        - SELLOFF + RISK_OFF = CONFIRMED (+15% confidence)
        - SELLOFF + RISK_ON = VETO (-20% confidence)
        - BREAKOUT + RISK_ON = CONFIRMED (+15%)
        - BREAKOUT + RISK_OFF = VETO (-20%)
        """
        from lottery_signals import SignalAction, SignalType
        
        rationale = f"BTC {crypto_sentiment.btc_change_pct*100:+.1f}%, ETH {crypto_sentiment.eth_change_pct*100:+.1f}%"
        
        # SELLOFF signals
        if signal.action == SignalAction.SELL or signal.signal_type == SignalType.SELLOFF:
            if crypto_sentiment.environment == RiskEnvironment.RISK_OFF:
                # Crypto confirms equity weakness - strong bearish signal
                return True, 0.15, rationale + " - RISK-OFF confirmed"
            elif crypto_sentiment.environment == RiskEnvironment.RISK_ON:
                # Crypto rallying while equities selling - divergence (VETO)
                logger.warning(f"   ⚠️ VETO: Crypto divergence (crypto up, equities down)")
                return False, -0.20, rationale + " - DIVERGENCE (VETO)"
            else:
                # Neutral - slight boost
                return True, 0.05, rationale + " - neutral"
        
        # BREAKOUT/BUY signals
        elif signal.action == SignalAction.BUY:
            if crypto_sentiment.environment == RiskEnvironment.RISK_ON:
                # Crypto confirms equity strength - strong bullish signal
                return True, 0.15, rationale + " - RISK-ON confirmed"
            elif crypto_sentiment.environment == RiskEnvironment.RISK_OFF:
                # Crypto selling while equities buying - divergence (VETO)
                logger.warning(f"   ⚠️ VETO: Crypto divergence (crypto down, equities up)")
                return False, -0.20, rationale + " - DIVERGENCE (VETO)"
            else:
                # Neutral - slight boost
                return True, 0.05, rationale + " - neutral"
        
        # Default
        return True, 0.0, rationale
    
    def enrich_signal(self, signal: EnrichedSignal) -> EnrichedSignal:
        """
        Enrich signal with crypto correlation analysis
        
        This is the main entry point for the enrichment pipeline.
        """
        # Get crypto sentiment
        crypto_sentiment = self.get_crypto_sentiment()
        
        if not crypto_sentiment:
            logger.warning("   ⏭️  Skipping crypto enrichment (no data)")
            return signal
        
        # Check correlation confirmation
        confirmed, boost, rationale = self.check_correlation_confirmation(signal, crypto_sentiment)
        
        # Add to signal
        signal.crypto_sentiment = crypto_sentiment
        
        if confirmed:
            signal.add_enrichment('crypto_correlation', boost, rationale)
            logger.info(f"   ✅ Crypto enrichment: {boost*100:+.0f}% confidence")
        else:
            # VETO - mark signal as not actionable
            signal.is_actionable = False
            signal.warnings.append(f"VETO: {rationale}")
            logger.warning(f"   ❌ Crypto VETO: {rationale}")
        
        return signal


def test_crypto_correlation():
    """
    Test crypto correlation detector
    
    Usage:
        python3 -m live_monitoring.enrichment.crypto_correlation
    """
    import sys
    sys.path.append('/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main')
    
    from live_monitoring.core.lottery_signals import LiveSignal, SignalAction, SignalType
    
    print("=" * 80)
    print("🧪 TESTING CRYPTO CORRELATION DETECTOR")
    print("=" * 80)
    print()
    
    # Initialize detector
    detector = CryptoCorrelationDetector(lookback_minutes=30)
    
    # Get current crypto sentiment
    print("📊 Fetching crypto sentiment...")
    sentiment = detector.get_crypto_sentiment()
    
    if sentiment:
        print(f"✅ Crypto Sentiment Retrieved:")
        print(f"   BTC: ${sentiment.btc_price:,.2f} ({sentiment.btc_change_pct*100:+.2f}%)")
        print(f"   ETH: ${sentiment.eth_price:,.2f} ({sentiment.eth_change_pct*100:+.2f}%)")
        print(f"   Correlation: {sentiment.correlation:.2f}")
        print(f"   Environment: {sentiment.environment.value}")
        print()
        
        # Test with SELLOFF signal
        print("🧪 Testing SELLOFF signal enrichment...")
        test_signal = EnrichedSignal.from_base_signal(LiveSignal(
            symbol='SPY',
            action=SignalAction.SELL,
            signal_type=SignalType.SELLOFF,
            entry_price=669.10,
            stop_price=676.17,
            target_price=659.44,
            confidence=0.66,
            rationale="REAL-TIME SELLOFF: -0.65% in last 20 min, volume spike 2.4x"
        ))
        
        print(f"   Base confidence: {test_signal.confidence*100:.0f}%")
        
        # Enrich
        enriched = detector.enrich_signal(test_signal)
        
        print(f"   Enriched confidence: {enriched.confidence*100:.0f}%")
        print(f"   Boost: {enriched.enrichment_boost*100:+.0f}%")
        print(f"   Rationale: {enriched.rationale}")
        print(f"   Actionable: {enriched.is_actionable}")
        print()
    else:
        print("❌ Could not fetch crypto sentiment")
    
    print("=" * 80)
    print("✅ Test complete!")
    print("=" * 80)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_crypto_correlation()

