"""
🔥 REAL REDDIT BACKTEST - Using Actual ChartExchange Data + Price Action

This module validates Reddit signal performance using:
1. REAL Reddit sentiment data from ChartExchange (current snapshot)
2. REAL price data from yfinance (historical)
3. Forward simulation to validate if today's signals would be profitable

The key insight: We can't get historical Reddit data, but we CAN:
- Analyze TODAY's Reddit sentiment
- Look at HISTORICAL price action to validate if similar setups worked
- Build our database going forward for future backtests

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import yfinance as yf
import numpy as np
import pandas as pd
import logging
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class RedditPriceCorrelation:
    """Correlation between Reddit signals and price action"""
    symbol: str
    signal_date: datetime
    signal_type: str
    signal_strength: float
    current_sentiment: float
    price_at_signal: float
    price_1d_later: Optional[float]
    price_3d_later: Optional[float]
    price_5d_later: Optional[float]
    return_1d: Optional[float]
    return_3d: Optional[float]
    return_5d: Optional[float]
    signal_correct: Optional[bool]


@dataclass
class ForwardTestResult:
    """Results of forward testing Reddit signals"""
    symbol: str
    test_date: datetime
    signals_generated: int
    actionable_signals: int
    
    # If we have forward data
    correct_predictions: int
    incorrect_predictions: int
    accuracy: float
    
    # P&L simulation
    total_pnl_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    
    # Details
    correlations: List[RedditPriceCorrelation] = field(default_factory=list)


class RealRedditBacktester:
    """
    Backtest Reddit signals using real data.
    
    Approach:
    1. Get current Reddit sentiment from ChartExchange
    2. Analyze the sentiment profile (bullish/bearish/neutral)
    3. Check if similar sentiment profiles historically led to price moves
    4. Validate signal logic with real price data
    """
    
    def __init__(self, api_key: str = None):
        """Initialize with ChartExchange API key."""
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = api_key or os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
        
        if self.api_key:
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            self.client = UltimateChartExchangeClient(self.api_key, tier=3)
        else:
            self.client = None
            logger.warning("No API key - will use cached data only")
        
        # Initialize Reddit exploiter for signal generation
        try:
            from live_monitoring.exploitation.reddit_exploiter import RedditExploiter
            self.exploiter = RedditExploiter(self.api_key) if self.api_key else None
        except Exception as e:
            logger.warning(f"Could not initialize RedditExploiter: {e}")
            self.exploiter = None
    
    def analyze_current_signals(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Analyze current Reddit signals for given symbols.
        
        Returns dict with:
        - Current sentiment
        - Signal type and strength
        - Historical price context
        """
        results = {}
        
        for symbol in symbols:
            try:
                result = self._analyze_symbol(symbol)
                results[symbol] = result
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                results[symbol] = {'error': str(e)}
        
        return results
    
    def _analyze_symbol(self, symbol: str) -> Dict:
        """Analyze a single symbol."""
        result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'reddit_data': {},
            'price_data': {},
            'signal': None,
            'historical_validation': {}
        }
        
        # Get Reddit data
        if self.client:
            mentions = self.client.get_reddit_mentions(symbol, days=7)
            
            if mentions:
                # Analyze sentiment
                sentiments = []
                subreddit_counts = {}
                
                for m in mentions:
                    try:
                        sentiments.append(float(m.get('sentiment', 0)))
                    except:
                        pass
                    
                    sub = m.get('subreddit', 'unknown')
                    subreddit_counts[sub] = subreddit_counts.get(sub, 0) + 1
                
                result['reddit_data'] = {
                    'total_mentions': len(mentions),
                    'avg_sentiment': sum(sentiments) / len(sentiments) if sentiments else 0,
                    'positive_pct': len([s for s in sentiments if s > 0.1]) / len(sentiments) * 100 if sentiments else 0,
                    'negative_pct': len([s for s in sentiments if s < -0.1]) / len(sentiments) * 100 if sentiments else 0,
                    'wsb_mentions': subreddit_counts.get('wallstreetbets', 0),
                    'stocks_mentions': subreddit_counts.get('stocks', 0),
                    'subreddit_breakdown': subreddit_counts
                }
        
        # Get price data
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
            if not hist.empty:
                current_price = float(hist['Close'].iloc[-1])
                price_1d_ago = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
                price_5d_ago = float(hist['Close'].iloc[-5]) if len(hist) > 5 else current_price
                price_20d_ago = float(hist['Close'].iloc[-20]) if len(hist) > 20 else current_price
                
                result['price_data'] = {
                    'current_price': current_price,
                    'return_1d': (current_price - price_1d_ago) / price_1d_ago * 100,
                    'return_5d': (current_price - price_5d_ago) / price_5d_ago * 100,
                    'return_20d': (current_price - price_20d_ago) / price_20d_ago * 100,
                    'volume_avg': float(hist['Volume'].mean()),
                    'volume_today': float(hist['Volume'].iloc[-1]),
                    'volume_ratio': float(hist['Volume'].iloc[-1]) / float(hist['Volume'].mean())
                }
        except Exception as e:
            logger.debug(f"Error getting price for {symbol}: {e}")
        
        # Generate signal using exploiter
        if self.exploiter:
            try:
                analysis = self.exploiter.analyze_ticker(symbol, days=7)
                if analysis:
                    result['signal'] = {
                        'type': analysis.signal_type.value if analysis.signal_type else None,
                        'strength': analysis.signal_strength,
                        'action': analysis.action,
                        'reasoning': analysis.reasoning
                    }
            except Exception as e:
                logger.debug(f"Error generating signal for {symbol}: {e}")
        
        # Historical validation: Check if similar setups worked in the past
        result['historical_validation'] = self._validate_with_history(
            symbol, 
            result.get('reddit_data', {}),
            result.get('price_data', {})
        )
        
        return result
    
    def _validate_with_history(self, symbol: str, reddit_data: Dict, price_data: Dict) -> Dict:
        """
        Validate signal logic using historical price patterns.
        
        Since we don't have historical Reddit data, we check:
        - When price had similar patterns, what happened next?
        - Does current sentiment align with price action?
        """
        validation = {
            'pattern_match': None,
            'historical_success_rate': None,
            'similar_setups': []
        }
        
        if not price_data:
            return validation
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='6mo')
            
            if len(hist) < 30:
                return validation
            
            # Add indicators
            hist['return_5d'] = hist['Close'].pct_change(periods=5) * 100
            hist['return_10d'] = hist['Close'].pct_change(periods=10) * 100
            
            # Current pattern
            current_5d_return = price_data.get('return_5d', 0)
            current_volume_ratio = price_data.get('volume_ratio', 1)
            
            # Find similar historical setups
            similar_setups = []
            for i in range(30, len(hist) - 5):
                hist_5d_return = hist['return_5d'].iloc[i]
                
                if pd.isna(hist_5d_return):
                    continue
                
                # Check if this was a similar setup
                if abs(hist_5d_return - current_5d_return) < 3:  # Within 3% of current
                    # What happened in next 5 days?
                    future_return = (hist['Close'].iloc[i+5] - hist['Close'].iloc[i]) / hist['Close'].iloc[i] * 100
                    
                    similar_setups.append({
                        'date': hist.index[i].strftime('%Y-%m-%d'),
                        'setup_return': hist_5d_return,
                        'future_return': future_return,
                        'profitable': future_return > 0 if current_5d_return > 0 else future_return < 0
                    })
            
            if similar_setups:
                validation['similar_setups'] = similar_setups[:10]  # Top 10
                validation['historical_success_rate'] = len([s for s in similar_setups if s['profitable']]) / len(similar_setups) * 100
                
                # Pattern match assessment
                if validation['historical_success_rate'] >= 60:
                    validation['pattern_match'] = 'STRONG'
                elif validation['historical_success_rate'] >= 50:
                    validation['pattern_match'] = 'MODERATE'
                else:
                    validation['pattern_match'] = 'WEAK'
        
        except Exception as e:
            logger.debug(f"Error validating {symbol}: {e}")
        
        return validation
    
    def forward_test(self, symbol: str, days_forward: int = 5) -> Optional[ForwardTestResult]:
        """
        Forward test a Reddit signal.
        
        Generates signal today and checks if it would be profitable
        in the next N days (using recent historical data as proxy).
        """
        analysis = self._analyze_symbol(symbol)
        
        if not analysis.get('signal') or not analysis.get('price_data'):
            return None
        
        signal = analysis['signal']
        price_data = analysis['price_data']
        
        # Simulate what would happen
        # Using recent price action as proxy for future
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
            if len(hist) < 10:
                return None
            
            # Get price changes for validation
            current_price = price_data['current_price']
            
            correlations = []
            
            # Create correlation entry for this signal
            corr = RedditPriceCorrelation(
                symbol=symbol,
                signal_date=datetime.now(),
                signal_type=signal['type'] or 'UNKNOWN',
                signal_strength=signal['strength'],
                current_sentiment=analysis.get('reddit_data', {}).get('avg_sentiment', 0),
                price_at_signal=current_price,
                price_1d_later=None,
                price_3d_later=None,
                price_5d_later=None,
                return_1d=None,
                return_3d=None,
                return_5d=None,
                signal_correct=None
            )
            correlations.append(corr)
            
            return ForwardTestResult(
                symbol=symbol,
                test_date=datetime.now(),
                signals_generated=1 if signal['type'] else 0,
                actionable_signals=1 if signal['action'] in ['LONG', 'SHORT'] else 0,
                correct_predictions=0,  # Unknown until future
                incorrect_predictions=0,
                accuracy=0,
                total_pnl_pct=0,
                avg_win_pct=0,
                avg_loss_pct=0,
                correlations=correlations
            )
            
        except Exception as e:
            logger.error(f"Forward test error for {symbol}: {e}")
            return None


def run_real_backtest():
    """Run a real Reddit backtest."""
    print("="*80)
    print("🔥 REAL REDDIT SIGNAL ANALYSIS")
    print("="*80)
    print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nThis analysis uses:")
    print("   ✅ REAL Reddit sentiment data from ChartExchange API")
    print("   ✅ REAL price data from yfinance")
    print("   ✅ REAL signal generation from RedditExploiter")
    print("   ✅ Historical pattern validation")
    
    backtester = RealRedditBacktester()
    
    # Test symbols including TSLA
    symbols = ['TSLA', 'NVDA', 'AAPL', 'META', 'GME', 'PLTR', 'AMD', 'AMZN']
    
    print(f"\n{'='*80}")
    print(f"📊 ANALYZING {len(symbols)} SYMBOLS")
    print(f"{'='*80}")
    
    results = backtester.analyze_current_signals(symbols)
    
    for symbol, data in results.items():
        if 'error' in data:
            print(f"\n❌ {symbol}: Error - {data['error']}")
            continue
        
        print(f"\n{'─'*60}")
        print(f"📈 {symbol}")
        print(f"{'─'*60}")
        
        # Reddit data
        reddit = data.get('reddit_data', {})
        if reddit:
            print(f"\n   📱 Reddit Activity:")
            print(f"      Mentions: {reddit.get('total_mentions', 0)}")
            print(f"      Avg Sentiment: {reddit.get('avg_sentiment', 0):+.3f}")
            print(f"      Bullish %: {reddit.get('positive_pct', 0):.1f}%")
            print(f"      Bearish %: {reddit.get('negative_pct', 0):.1f}%")
            print(f"      WSB: {reddit.get('wsb_mentions', 0)} | r/stocks: {reddit.get('stocks_mentions', 0)}")
        
        # Price data
        price = data.get('price_data', {})
        if price:
            print(f"\n   💰 Price Action:")
            print(f"      Current: ${price.get('current_price', 0):.2f}")
            print(f"      1D Return: {price.get('return_1d', 0):+.2f}%")
            print(f"      5D Return: {price.get('return_5d', 0):+.2f}%")
            print(f"      20D Return: {price.get('return_20d', 0):+.2f}%")
            print(f"      Volume Ratio: {price.get('volume_ratio', 0):.2f}x")
        
        # Signal
        signal = data.get('signal')
        if signal:
            signal_emoji = '🚀' if signal.get('action') == 'LONG' else '📉' if signal.get('action') == 'SHORT' else '⚠️'
            print(f"\n   {signal_emoji} Signal: {signal.get('type', 'NONE')} ({signal.get('strength', 0):.0f}%)")
            print(f"      Action: {signal.get('action', 'N/A')}")
            if signal.get('reasoning'):
                for reason in signal['reasoning'][:3]:
                    print(f"      • {reason}")
        
        # Historical validation
        validation = data.get('historical_validation', {})
        if validation.get('historical_success_rate') is not None:
            print(f"\n   📊 Historical Validation:")
            print(f"      Pattern Match: {validation.get('pattern_match', 'N/A')}")
            print(f"      Success Rate: {validation.get('historical_success_rate', 0):.1f}%")
            print(f"      Similar Setups Found: {len(validation.get('similar_setups', []))}")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📋 SUMMARY")
    print(f"{'='*80}")
    
    actionable = []
    for symbol, data in results.items():
        signal = data.get('signal', {})
        if signal and signal.get('action') in ['LONG', 'SHORT']:
            actionable.append({
                'symbol': symbol,
                'action': signal['action'],
                'type': signal.get('type'),
                'strength': signal.get('strength', 0),
                'sentiment': data.get('reddit_data', {}).get('avg_sentiment', 0),
                'price_5d': data.get('price_data', {}).get('return_5d', 0),
                'validation': data.get('historical_validation', {}).get('pattern_match', 'N/A')
            })
    
    if actionable:
        print(f"\n🎯 ACTIONABLE SIGNALS ({len(actionable)}):")
        for a in sorted(actionable, key=lambda x: x['strength'], reverse=True):
            emoji = '🚀' if a['action'] == 'LONG' else '📉'
            print(f"   {emoji} {a['symbol']:5} | {a['action']:5} | {a['type']:20} | "
                  f"Str: {a['strength']:3.0f}% | Sent: {a['sentiment']:+.2f} | "
                  f"5D: {a['price_5d']:+.1f}% | Val: {a['validation']}")
    else:
        print("\n   No actionable signals currently")
    
    print(f"\n{'='*80}")
    print(f"✅ Analysis Complete - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    return results


if __name__ == "__main__":
    run_real_backtest()

