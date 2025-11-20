#!/usr/bin/env python3
"""
TREND REGIME & FLOW CLUSTERING ANALYZER
- Analyze today's session minute-by-minute
- Identify true breakouts vs chop
- Incorporate trend regime detection
- Build flexible DP confirmation for rippers
"""

import logging
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import matplotlib.pyplot as plt

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TrendRegimeAnalyzer:
    """Analyze trend regimes and flow clustering for breakout detection"""
    
    def __init__(self):
        self.trend_regimes = {}
        self.flow_clusters = {}
        self.breakout_points = {}
        
    def analyze_todays_session(self, ticker: str) -> Dict[str, Any]:
        """Analyze today's session minute-by-minute"""
        try:
            logger.info(f"🔍 ANALYZING TODAY'S SESSION FOR {ticker}")
            
            # Get intraday data
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d", interval="1m")
            
            if hist.empty:
                logger.error(f"No intraday data for {ticker}")
                return {}
            
            # Calculate trend regime indicators
            trend_analysis = self._calculate_trend_regime(hist)
            
            # Identify flow clusters
            flow_clusters = self._identify_flow_clusters(hist)
            
            # Find true breakout points
            breakout_points = self._find_true_breakouts(hist, trend_analysis, flow_clusters)
            
            # Generate analysis
            analysis = {
                'ticker': ticker,
                'session_data': hist,
                'trend_regime': trend_analysis,
                'flow_clusters': flow_clusters,
                'breakout_points': breakout_points,
                'summary': self._generate_session_summary(hist, trend_analysis, flow_clusters, breakout_points)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing session for {ticker}: {e}")
            return {}
    
    def _calculate_trend_regime(self, hist: pd.DataFrame) -> Dict[str, Any]:
        """Calculate trend regime indicators"""
        try:
            # Calculate moving averages
            hist['SMA_20'] = hist['Close'].rolling(window=20).mean()
            hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
            hist['EMA_12'] = hist['Close'].ewm(span=12).mean()
            hist['EMA_26'] = hist['Close'].ewm(span=26).mean()
            
            # Calculate MACD
            hist['MACD'] = hist['EMA_12'] - hist['EMA_26']
            hist['MACD_Signal'] = hist['MACD'].ewm(span=9).mean()
            hist['MACD_Histogram'] = hist['MACD'] - hist['MACD_Signal']
            
            # Calculate RSI
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            hist['RSI'] = 100 - (100 / (1 + rs))
            
            # Calculate Bollinger Bands
            hist['BB_Middle'] = hist['Close'].rolling(window=20).mean()
            bb_std = hist['Close'].rolling(window=20).std()
            hist['BB_Upper'] = hist['BB_Middle'] + (bb_std * 2)
            hist['BB_Lower'] = hist['BB_Middle'] - (bb_std * 2)
            
            # Calculate Volume indicators
            hist['Volume_SMA'] = hist['Volume'].rolling(window=20).mean()
            hist['Volume_Ratio'] = hist['Volume'] / hist['Volume_SMA']
            
            # Determine trend regime
            current_price = hist['Close'].iloc[-1]
            sma_20 = hist['SMA_20'].iloc[-1]
            sma_50 = hist['SMA_50'].iloc[-1]
            macd = hist['MACD'].iloc[-1]
            macd_signal = hist['MACD_Signal'].iloc[-1]
            rsi = hist['RSI'].iloc[-1]
            bb_upper = hist['BB_Upper'].iloc[-1]
            bb_lower = hist['BB_Lower'].iloc[-1]
            volume_ratio = hist['Volume_Ratio'].iloc[-1]
            
            # Trend regime classification
            trend_regime = "CHOP"
            trend_strength = 0.0
            
            if current_price > sma_20 > sma_50 and macd > macd_signal:
                trend_regime = "UPTREND"
                trend_strength = min(1.0, (current_price - sma_50) / sma_50 * 10)
            elif current_price < sma_20 < sma_50 and macd < macd_signal:
                trend_regime = "DOWNTREND"
                trend_strength = min(1.0, (sma_50 - current_price) / sma_50 * 10)
            
            # Volatility regime
            volatility_regime = "LOW"
            if rsi > 70 or rsi < 30:
                volatility_regime = "HIGH"
            elif rsi > 60 or rsi < 40:
                volatility_regime = "MEDIUM"
            
            # Volume regime
            volume_regime = "NORMAL"
            if volume_ratio > 2.0:
                volume_regime = "HIGH"
            elif volume_ratio < 0.5:
                volume_regime = "LOW"
            
            return {
                'trend_regime': trend_regime,
                'trend_strength': trend_strength,
                'volatility_regime': volatility_regime,
                'volume_regime': volume_regime,
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'bb_position': (current_price - bb_lower) / (bb_upper - bb_lower),
                'volume_ratio': volume_ratio,
                'price_vs_sma20': (current_price - sma_20) / sma_20,
                'price_vs_sma50': (current_price - sma_50) / sma_50
            }
            
        except Exception as e:
            logger.error(f"Error calculating trend regime: {e}")
            return {}
    
    def _identify_flow_clusters(self, hist: pd.DataFrame) -> List[Dict[str, Any]]:
        """Identify flow clusters (volume + price movement)"""
        try:
            clusters = []
            
            # Calculate price changes and volume spikes
            hist['Price_Change'] = hist['Close'].pct_change()
            hist['Volume_Spike'] = hist['Volume'] / hist['Volume'].rolling(window=20).mean()
            
            # Find significant flow events
            for i in range(20, len(hist)):
                price_change = abs(hist['Price_Change'].iloc[i])
                volume_spike = hist['Volume_Spike'].iloc[i]
                
                # Flow cluster criteria
                if price_change > 0.005 and volume_spike > 1.5:  # 0.5% move + 1.5x volume
                    cluster = {
                        'timestamp': hist.index[i],
                        'price': hist['Close'].iloc[i],
                        'price_change': hist['Price_Change'].iloc[i],
                        'volume_spike': volume_spike,
                        'cluster_strength': price_change * volume_spike,
                        'direction': 'UP' if hist['Price_Change'].iloc[i] > 0 else 'DOWN'
                    }
                    clusters.append(cluster)
            
            # Sort by cluster strength
            clusters.sort(key=lambda x: x['cluster_strength'], reverse=True)
            
            return clusters[:10]  # Top 10 flow clusters
            
        except Exception as e:
            logger.error(f"Error identifying flow clusters: {e}")
            return []
    
    def _find_true_breakouts(self, hist: pd.DataFrame, trend_analysis: Dict[str, Any], flow_clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find true breakout points vs chop"""
        try:
            breakouts = []
            
            # Calculate support/resistance levels
            hist['High_20'] = hist['High'].rolling(window=20).max()
            hist['Low_20'] = hist['Low'].rolling(window=20).min()
            
            for i in range(20, len(hist)):
                current_price = hist['Close'].iloc[i]
                high_20 = hist['High_20'].iloc[i]
                low_20 = hist['Low_20'].iloc[i]
                
                # Breakout criteria
                breakout_up = current_price > high_20 * 1.002  # 0.2% above 20-day high
                breakout_down = current_price < low_20 * 0.998  # 0.2% below 20-day low
                
                if breakout_up or breakout_down:
                    # Check if this aligns with flow clusters
                    cluster_confirmation = False
                    for cluster in flow_clusters:
                        if abs((cluster['timestamp'] - hist.index[i]).total_seconds()) < 300:  # Within 5 minutes
                            cluster_confirmation = True
                            break
                    
                    # Check trend regime alignment
                    trend_confirmation = False
                    if breakout_up and trend_analysis.get('trend_regime') in ['UPTREND', 'CHOP']:
                        trend_confirmation = True
                    elif breakout_down and trend_analysis.get('trend_regime') in ['DOWNTREND', 'CHOP']:
                        trend_confirmation = True
                    
                    # Calculate breakout strength
                    if breakout_up:
                        breakout_strength = (current_price - high_20) / high_20
                        breakout_type = "UP"
                    else:
                        breakout_strength = (low_20 - current_price) / low_20
                        breakout_type = "DOWN"
                    
                    # Only consider strong breakouts with confirmations
                    if breakout_strength > 0.002 and (cluster_confirmation or trend_confirmation):
                        breakout = {
                            'timestamp': hist.index[i],
                            'price': current_price,
                            'type': breakout_type,
                            'strength': breakout_strength,
                            'cluster_confirmation': cluster_confirmation,
                            'trend_confirmation': trend_confirmation,
                            'confidence': self._calculate_breakout_confidence(breakout_strength, cluster_confirmation, trend_confirmation, trend_analysis)
                        }
                        breakouts.append(breakout)
            
            return breakouts
            
        except Exception as e:
            logger.error(f"Error finding true breakouts: {e}")
            return []
    
    def _calculate_breakout_confidence(self, strength: float, cluster_conf: bool, trend_conf: bool, trend_analysis: Dict[str, Any]) -> float:
        """Calculate breakout confidence score"""
        try:
            confidence = 0.5  # Base confidence
            
            # Strength bonus
            confidence += min(0.3, strength * 50)
            
            # Cluster confirmation bonus
            if cluster_conf:
                confidence += 0.2
            
            # Trend confirmation bonus
            if trend_conf:
                confidence += 0.2
            
            # Trend strength bonus
            trend_strength = trend_analysis.get('trend_strength', 0)
            confidence += min(0.1, trend_strength * 0.1)
            
            return min(1.0, confidence)
            
        except Exception as e:
            logger.error(f"Error calculating breakout confidence: {e}")
            return 0.5
    
    def _generate_session_summary(self, hist: pd.DataFrame, trend_analysis: Dict[str, Any], flow_clusters: List[Dict[str, Any]], breakouts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate session summary"""
        try:
            session_start = hist.index[0]
            session_end = hist.index[-1]
            session_duration = (session_end - session_start).total_seconds() / 3600  # hours
            
            price_range = hist['High'].max() - hist['Low'].min()
            price_change = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
            
            total_volume = hist['Volume'].sum()
            avg_volume = hist['Volume'].mean()
            
            # Count breakouts by type
            up_breakouts = len([b for b in breakouts if b['type'] == 'UP'])
            down_breakouts = len([b for b in breakouts if b['type'] == 'DOWN'])
            
            # Count flow clusters by direction
            up_clusters = len([c for c in flow_clusters if c['direction'] == 'UP'])
            down_clusters = len([c for c in flow_clusters if c['direction'] == 'DOWN'])
            
            return {
                'session_start': session_start,
                'session_end': session_end,
                'session_duration_hours': session_duration,
                'price_range': price_range,
                'price_change_percent': price_change * 100,
                'total_volume': total_volume,
                'avg_volume': avg_volume,
                'trend_regime': trend_analysis.get('trend_regime', 'UNKNOWN'),
                'trend_strength': trend_analysis.get('trend_strength', 0),
                'volatility_regime': trend_analysis.get('volatility_regime', 'UNKNOWN'),
                'volume_regime': trend_analysis.get('volume_regime', 'UNKNOWN'),
                'total_breakouts': len(breakouts),
                'up_breakouts': up_breakouts,
                'down_breakouts': down_breakouts,
                'total_flow_clusters': len(flow_clusters),
                'up_clusters': up_clusters,
                'down_clusters': down_clusters,
                'breakout_success_rate': len([b for b in breakouts if b['confidence'] > 0.7]) / max(1, len(breakouts))
            }
            
        except Exception as e:
            logger.error(f"Error generating session summary: {e}")
            return {}

def analyze_todays_breakouts():
    """Analyze today's breakouts for major tickers"""
    print("🔥 TREND REGIME & FLOW CLUSTERING ANALYSIS")
    print("=" * 80)
    
    analyzer = TrendRegimeAnalyzer()
    tickers = ['SPY', 'QQQ', 'TSLA', 'AAPL', 'NVDA']
    
    all_results = {}
    
    for ticker in tickers:
        print(f"\n🔍 ANALYZING {ticker} SESSION:")
        
        try:
            analysis = analyzer.analyze_todays_session(ticker)
            if analysis:
                all_results[ticker] = analysis
                
                summary = analysis['summary']
                print(f"   Session Duration: {summary.get('session_duration_hours', 0):.1f} hours")
                print(f"   Price Change: {summary.get('price_change_percent', 0):.2f}%")
                print(f"   Trend Regime: {summary.get('trend_regime', 'UNKNOWN')}")
                print(f"   Trend Strength: {summary.get('trend_strength', 0):.2f}")
                print(f"   Volatility Regime: {summary.get('volatility_regime', 'UNKNOWN')}")
                print(f"   Volume Regime: {summary.get('volume_regime', 'UNKNOWN')}")
                print(f"   Total Breakouts: {summary.get('total_breakouts', 0)}")
                print(f"   Up Breakouts: {summary.get('up_breakouts', 0)}")
                print(f"   Down Breakouts: {summary.get('down_breakouts', 0)}")
                print(f"   Flow Clusters: {summary.get('total_flow_clusters', 0)}")
                print(f"   Breakout Success Rate: {summary.get('breakout_success_rate', 0):.2%}")
                
                # Show top breakouts
                breakouts = analysis['breakout_points']
                if breakouts:
                    print(f"   🚨 TOP BREAKOUTS:")
                    for i, breakout in enumerate(breakouts[:3]):
                        print(f"      {i+1}. {breakout['type']} @ ${breakout['price']:.2f}")
                        print(f"         Strength: {breakout['strength']:.3f}")
                        print(f"         Confidence: {breakout['confidence']:.2f}")
                        print(f"         Cluster Conf: {breakout['cluster_confirmation']}")
                        print(f"         Trend Conf: {breakout['trend_confirmation']}")
            else:
                print(f"   ❌ No analysis data available")
                
        except Exception as e:
            print(f"   ❌ Error analyzing {ticker}: {e}")
    
    # Generate overall insights
    print(f"\n🎯 OVERALL INSIGHTS:")
    
    total_breakouts = sum(r['summary'].get('total_breakouts', 0) for r in all_results.values())
    total_clusters = sum(r['summary'].get('total_flow_clusters', 0) for r in all_results.values())
    
    print(f"   Total Breakouts Detected: {total_breakouts}")
    print(f"   Total Flow Clusters: {total_clusters}")
    print(f"   Average Breakout Success Rate: {np.mean([r['summary'].get('breakout_success_rate', 0) for r in all_results.values()]):.2%}")
    
    # Identify best opportunities
    best_opportunities = []
    for ticker, analysis in all_results.items():
        breakouts = analysis['breakout_points']
        for breakout in breakouts:
            if breakout['confidence'] > 0.7:
                best_opportunities.append({
                    'ticker': ticker,
                    'type': breakout['type'],
                    'price': breakout['price'],
                    'confidence': breakout['confidence'],
                    'strength': breakout['strength']
                })
    
    if best_opportunities:
        print(f"\n🚀 BEST OPPORTUNITIES:")
        best_opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        for i, opp in enumerate(best_opportunities[:5]):
            print(f"   {i+1}. {opp['ticker']} {opp['type']} @ ${opp['price']:.2f}")
            print(f"      Confidence: {opp['confidence']:.2f}, Strength: {opp['strength']:.3f}")
    
    print(f"\n✅ TREND REGIME & FLOW CLUSTERING ANALYSIS COMPLETE!")
    print(f"🎯 READY TO CATCH THE RIPPERS!")

if __name__ == "__main__":
    analyze_todays_breakouts()

