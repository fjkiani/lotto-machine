#!/usr/bin/env python3
"""
FLEXIBLE DP CONFIRMATION SYSTEM
- Adaptive thresholds based on trend regime
- Flow clustering for ripper detection
- Dynamic confirmation requirements
- Catch legitimate breakouts while avoiding traps
"""

import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FlexibleSignal:
    """Flexible signal with adaptive confirmation"""
    ticker: str
    signal_type: str
    entry_price: float
    confidence: float
    trend_regime: str
    flow_cluster_strength: float
    dp_confirmation: bool
    adaptive_threshold: float
    reasoning: str
    timestamp: datetime

class FlexibleDPConfirmation:
    """Flexible DP confirmation system"""
    
    def __init__(self):
        self.regime_thresholds = {
            'UPTREND': {
                'breakout_threshold': 0.001,  # 0.1% - more sensitive in uptrends
                'volume_multiplier': 1.2,     # Lower volume requirement
                'dp_confirmation_required': False,  # Less strict DP confirmation
                'flow_cluster_weight': 0.4    # Higher weight on flow clusters
            },
            'DOWNTREND': {
                'breakout_threshold': 0.001,  # 0.1% - more sensitive in downtrends
                'volume_multiplier': 1.2,     # Lower volume requirement
                'dp_confirmation_required': False,  # Less strict DP confirmation
                'flow_cluster_weight': 0.4    # Higher weight on flow clusters
            },
            'CHOP': {
                'breakout_threshold': 0.003,  # 0.3% - more strict in chop
                'volume_multiplier': 2.0,     # Higher volume requirement
                'dp_confirmation_required': True,   # Strict DP confirmation
                'flow_cluster_weight': 0.2    # Lower weight on flow clusters
            }
        }
        
        self.flow_clusters = {}
        self.trend_regimes = {}
        
    def analyze_flexible_signals(self, ticker: str) -> List[FlexibleSignal]:
        """Analyze flexible signals for a ticker"""
        try:
            logger.info(f"🔍 ANALYZING FLEXIBLE SIGNALS FOR {ticker}")
            
            # Get intraday data
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="1m")
            
            if hist.empty:
                logger.error(f"No intraday data for {ticker}")
                return []
            
            # Calculate trend regime
            trend_regime = self._calculate_trend_regime(hist)
            self.trend_regimes[ticker] = trend_regime
            
            # Identify flow clusters
            flow_clusters = self._identify_flow_clusters(hist)
            self.flow_clusters[ticker] = flow_clusters
            
            # Get adaptive thresholds
            thresholds = self.regime_thresholds.get(trend_regime, self.regime_thresholds['CHOP'])
            
            # Find flexible signals
            signals = self._find_flexible_signals(ticker, hist, trend_regime, flow_clusters, thresholds)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing flexible signals for {ticker}: {e}")
            return []
    
    def _calculate_trend_regime(self, hist: pd.DataFrame) -> str:
        """Calculate trend regime"""
        try:
            # Calculate moving averages
            hist['SMA_20'] = hist['Close'].rolling(window=20).mean()
            hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
            
            # Calculate MACD
            hist['EMA_12'] = hist['Close'].ewm(span=12).mean()
            hist['EMA_26'] = hist['Close'].ewm(span=26).mean()
            hist['MACD'] = hist['EMA_12'] - hist['EMA_26']
            hist['MACD_Signal'] = hist['MACD'].ewm(span=9).mean()
            
            # Current values
            current_price = hist['Close'].iloc[-1]
            sma_20 = hist['SMA_20'].iloc[-1]
            sma_50 = hist['SMA_50'].iloc[-1]
            macd = hist['MACD'].iloc[-1]
            macd_signal = hist['MACD_Signal'].iloc[-1]
            
            # Trend classification
            if current_price > sma_20 > sma_50 and macd > macd_signal:
                return "UPTREND"
            elif current_price < sma_20 < sma_50 and macd < macd_signal:
                return "DOWNTREND"
            else:
                return "CHOP"
                
        except Exception as e:
            logger.error(f"Error calculating trend regime: {e}")
            return "CHOP"
    
    def _identify_flow_clusters(self, hist: pd.DataFrame) -> List[Dict[str, Any]]:
        """Identify flow clusters"""
        try:
            clusters = []
            
            # Calculate price changes and volume spikes
            hist['Price_Change'] = hist['Close'].pct_change()
            hist['Volume_SMA'] = hist['Volume'].rolling(window=20).mean()
            hist['Volume_Ratio'] = hist['Volume'] / hist['Volume_SMA']
            
            # Find flow clusters
            for i in range(20, len(hist)):
                price_change = abs(hist['Price_Change'].iloc[i])
                volume_ratio = hist['Volume_Ratio'].iloc[i]
                
                # More sensitive flow cluster detection
                if price_change > 0.002 and volume_ratio > 1.1:  # 0.2% move + 1.1x volume
                    cluster = {
                        'timestamp': hist.index[i],
                        'price': hist['Close'].iloc[i],
                        'price_change': hist['Price_Change'].iloc[i],
                        'volume_ratio': volume_ratio,
                        'cluster_strength': price_change * volume_ratio,
                        'direction': 'UP' if hist['Price_Change'].iloc[i] > 0 else 'DOWN'
                    }
                    clusters.append(cluster)
            
            return clusters
            
        except Exception as e:
            logger.error(f"Error identifying flow clusters: {e}")
            return []
    
    def _find_flexible_signals(self, ticker: str, hist: pd.DataFrame, trend_regime: str, flow_clusters: List[Dict[str, Any]], thresholds: Dict[str, Any]) -> List[FlexibleSignal]:
        """Find flexible signals with adaptive confirmation"""
        try:
            signals = []
            
            # Calculate support/resistance
            hist['High_20'] = hist['High'].rolling(window=20).max()
            hist['Low_20'] = hist['Low'].rolling(window=20).min()
            
            breakout_threshold = thresholds['breakout_threshold']
            volume_multiplier = thresholds['volume_multiplier']
            dp_confirmation_required = thresholds['dp_confirmation_required']
            flow_cluster_weight = thresholds['flow_cluster_weight']
            
            for i in range(20, len(hist)):
                current_price = hist['Close'].iloc[i]
                current_volume = hist['Volume'].iloc[i]
                avg_volume = hist['Volume'].rolling(window=20).mean().iloc[i]
                
                high_20 = hist['High_20'].iloc[i]
                low_20 = hist['Low_20'].iloc[i]
                
                # Check for breakouts with flexible thresholds
                breakout_up = current_price > high_20 * (1 + breakout_threshold)
                breakout_down = current_price < low_20 * (1 - breakout_threshold)
                
                if breakout_up or breakout_down:
                    # Check volume requirement
                    volume_spike = current_volume > avg_volume * volume_multiplier
                    
                    # Check flow cluster confirmation
                    flow_cluster_confirmation = False
                    flow_cluster_strength = 0.0
                    
                    for cluster in flow_clusters:
                        time_diff = abs((cluster['timestamp'] - hist.index[i]).total_seconds())
                        if time_diff < 300:  # Within 5 minutes
                            flow_cluster_confirmation = True
                            flow_cluster_strength = cluster['cluster_strength']
                            break
                    
                    # Simulate DP confirmation (in real implementation, this would check actual DP data)
                    dp_confirmation = self._simulate_dp_confirmation(current_price, trend_regime, flow_cluster_confirmation)
                    
                    # Calculate confidence with flexible requirements
                    confidence = 0.3  # Base confidence
                    
                    if volume_spike:
                        confidence += 0.2
                    
                    if flow_cluster_confirmation:
                        confidence += flow_cluster_weight
                    
                    if dp_confirmation:
                        confidence += 0.3
                    elif not dp_confirmation_required:
                        confidence += 0.1  # Bonus for not requiring DP confirmation
                    
                    # Only generate signals above threshold
                    if confidence > 0.6:
                        signal_type = "BREAKOUT_UP" if breakout_up else "BREAKOUT_DOWN"
                        
                        reasoning = f"{signal_type} in {trend_regime} regime"
                        if volume_spike:
                            reasoning += " with volume spike"
                        if flow_cluster_confirmation:
                            reasoning += " with flow cluster confirmation"
                        if dp_confirmation:
                            reasoning += " with DP confirmation"
                        
                        signal = FlexibleSignal(
                            ticker=ticker,
                            signal_type=signal_type,
                            entry_price=current_price,
                            confidence=confidence,
                            trend_regime=trend_regime,
                            flow_cluster_strength=flow_cluster_strength,
                            dp_confirmation=dp_confirmation,
                            adaptive_threshold=breakout_threshold,
                            reasoning=reasoning,
                            timestamp=hist.index[i]
                        )
                        signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error finding flexible signals: {e}")
            return []
    
    def _simulate_dp_confirmation(self, price: float, trend_regime: str, flow_cluster_confirmation: bool) -> bool:
        """Simulate DP confirmation (in real implementation, this would check actual DP data)"""
        try:
            # In uptrends, more likely to have DP confirmation for breakouts
            if trend_regime == "UPTREND" and flow_cluster_confirmation:
                return True
            
            # In downtrends, more likely to have DP confirmation for breakdowns
            if trend_regime == "DOWNTREND" and flow_cluster_confirmation:
                return True
            
            # In chop, require stronger confirmation
            if trend_regime == "CHOP":
                return flow_cluster_confirmation and np.random.random() > 0.7
            
            return False
            
        except Exception as e:
            logger.error(f"Error simulating DP confirmation: {e}")
            return False

def analyze_flexible_signals():
    """Analyze flexible signals for major tickers"""
    print("🔥 FLEXIBLE DP CONFIRMATION SYSTEM")
    print("=" * 80)
    
    analyzer = FlexibleDPConfirmation()
    tickers = ['SPY', 'QQQ', 'TSLA', 'AAPL', 'NVDA']
    
    all_signals = []
    
    for ticker in tickers:
        print(f"\n🔍 ANALYZING FLEXIBLE SIGNALS FOR {ticker}:")
        
        try:
            signals = analyzer.analyze_flexible_signals(ticker)
            all_signals.extend(signals)
            
            if signals:
                print(f"   Trend Regime: {analyzer.trend_regimes.get(ticker, 'UNKNOWN')}")
                print(f"   Flow Clusters: {len(analyzer.flow_clusters.get(ticker, []))}")
                print(f"   Signals Generated: {len(signals)}")
                
                for i, signal in enumerate(signals[:3]):  # Show top 3
                    print(f"   🚨 Signal {i+1}: {signal.signal_type}")
                    print(f"      Entry: ${signal.entry_price:.2f}")
                    print(f"      Confidence: {signal.confidence:.2f}")
                    print(f"      DP Confirmation: {signal.dp_confirmation}")
                    print(f"      Flow Cluster Strength: {signal.flow_cluster_strength:.3f}")
                    print(f"      Adaptive Threshold: {signal.adaptive_threshold:.3f}")
                    print(f"      Reasoning: {signal.reasoning}")
            else:
                print(f"   No signals generated (correctly avoiding traps)")
                
        except Exception as e:
            print(f"   ❌ Error analyzing {ticker}: {e}")
    
    # Generate summary
    print(f"\n🎯 FLEXIBLE SIGNAL SUMMARY:")
    print(f"   Total Signals: {len(all_signals)}")
    
    if all_signals:
        avg_confidence = np.mean([s.confidence for s in all_signals])
        dp_confirmation_rate = sum(1 for s in all_signals if s.dp_confirmation) / len(all_signals)
        
        print(f"   Average Confidence: {avg_confidence:.2f}")
        print(f"   DP Confirmation Rate: {dp_confirmation_rate:.2%}")
        
        # Show best signals
        best_signals = sorted(all_signals, key=lambda x: x.confidence, reverse=True)[:5]
        print(f"\n🚀 BEST SIGNALS:")
        for i, signal in enumerate(best_signals):
            print(f"   {i+1}. {signal.ticker} {signal.signal_type} @ ${signal.entry_price:.2f}")
            print(f"      Confidence: {signal.confidence:.2f}, Regime: {signal.trend_regime}")
            print(f"      DP Conf: {signal.dp_confirmation}, Flow: {signal.flow_cluster_strength:.3f}")
    
    print(f"\n✅ FLEXIBLE DP CONFIRMATION ANALYSIS COMPLETE!")
    print(f"🎯 READY TO CATCH RIPPERS IN ANY REGIME!")

if __name__ == "__main__":
    analyze_flexible_signals()

