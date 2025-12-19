"""
🌅 PRE-MARKET GAP DETECTOR SIMULATOR
Simulates pre-market gap signals and trades

Signals:
- GAP_UP_BREAKOUT: Gap up + price above pre-market high
- GAP_DOWN_BREAKDOWN: Gap down + price below pre-market low
- GAP_FILL: Gap filling back to previous close
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import yfinance as yf
import pandas as pd

# Add parent paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)
sys.path.insert(0, os.path.join(base_path, 'core', 'data'))
sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'strategies'))

from ..config.trading_params import TradingParams


@dataclass
class GapSignal:
    """Pre-market gap signal"""
    symbol: str
    timestamp: datetime
    signal_type: str  # GAP_UP_BREAKOUT, GAP_DOWN_BREAKDOWN, GAP_FILL
    gap_pct: float
    prev_close: float
    open_price: float
    entry_price: float
    stop_price: float
    target_price: float
    confidence: float
    dp_confluence: bool
    reasoning: str


class PreMarketGapBacktester:
    """
    Backtests pre-market gap strategy on historical data.
    
    Gap > 0.3% with DP confluence = high probability trade
    """
    
    def __init__(self, api_key: str = None, params: TradingParams = None):
        self.api_key = api_key or os.getenv('CHARTEXCHANGE_API_KEY')
        self.params = params or TradingParams()
        
    def detect_gap_signals(
        self,
        symbol: str,
        date: str,
        min_gap_pct: float = 0.3
    ) -> List[GapSignal]:
        """
        Detect gap signals for a given date.
        
        Args:
            symbol: Stock symbol
            date: Date to analyze (YYYY-MM-DD)
            min_gap_pct: Minimum gap size to trigger signal
            
        Returns:
            List of GapSignal objects
        """
        signals = []
        
        try:
            ticker = yf.Ticker(symbol)
            
            # Get 5 days of data to find previous close
            hist = ticker.history(period='5d', interval='1d')
            
            if hist.empty or len(hist) < 2:
                return signals
                
            target_date = datetime.strptime(date, '%Y-%m-%d').date()
            
            # Find the row for target date and previous day
            prev_close = None
            today_open = None
            
            for i in range(1, len(hist)):
                if hist.index[i].date() == target_date:
                    prev_close = float(hist['Close'].iloc[i-1])
                    today_open = float(hist['Open'].iloc[i])
                    break
            
            if prev_close is None or today_open is None:
                return signals
                
            # Calculate gap
            gap_pct = ((today_open - prev_close) / prev_close) * 100
            
            # Check if gap is significant
            if abs(gap_pct) < min_gap_pct:
                return signals
            
            # Get intraday data to determine signal type
            intraday = ticker.history(period='5d', interval='1m')
            if intraday.empty:
                return signals
                
            # Filter to target date
            intraday = intraday[intraday.index.date == target_date]
            
            if intraday.empty:
                return signals
            
            # Check DP confluence (if available)
            dp_confluence = False
            try:
                from ultimate_chartexchange_client import UltimateChartExchangeClient
                client = UltimateChartExchangeClient(api_key=self.api_key)
                yesterday = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                dp_data = client.get_dark_pool_levels(symbol, yesterday)
                
                if dp_data and 'levels' in dp_data:
                    for level in dp_data['levels'][:10]:
                        level_price = float(level.get('level', level.get('price', 0)))
                        if abs(today_open - level_price) / today_open < 0.01:  # Within 1%
                            dp_confluence = True
                            break
            except Exception:
                pass
            
            # First hour high/low
            first_hour = intraday.iloc[:30]  # First 30 minutes
            first_hour_high = float(first_hour['High'].max())
            first_hour_low = float(first_hour['Low'].min())
            current_price = float(intraday['Close'].iloc[-1])
            
            # Determine signal type
            if gap_pct > 0:
                if current_price > first_hour_high:
                    signal_type = "GAP_UP_BREAKOUT"
                    entry = first_hour_high
                    stop = first_hour_low
                    target = entry + (entry - stop) * 2  # 2:1 R/R
                    confidence = 0.65 + (0.15 if dp_confluence else 0)
                    reasoning = f"Gap up {gap_pct:.1f}%, broke above first hour high"
                elif current_price < prev_close:
                    signal_type = "GAP_FILL"
                    entry = prev_close * 0.998  # Just below prev close
                    stop = today_open * 1.01  # Above open
                    target = prev_close * 0.99  # 1% below fill level
                    confidence = 0.60 + (0.10 if dp_confluence else 0)
                    reasoning = f"Gap up {gap_pct:.1f}% filling back to previous close"
                else:
                    return signals  # No clear signal
            else:  # gap_pct < 0
                if current_price < first_hour_low:
                    signal_type = "GAP_DOWN_BREAKDOWN"
                    entry = first_hour_low
                    stop = first_hour_high
                    target = entry - (stop - entry) * 2  # 2:1 R/R
                    confidence = 0.65 + (0.15 if dp_confluence else 0)
                    reasoning = f"Gap down {gap_pct:.1f}%, broke below first hour low"
                elif current_price > prev_close:
                    signal_type = "GAP_FILL"
                    entry = prev_close * 1.002
                    stop = today_open * 0.99
                    target = prev_close * 1.01
                    confidence = 0.60 + (0.10 if dp_confluence else 0)
                    reasoning = f"Gap down {gap_pct:.1f}% filling back to previous close"
                else:
                    return signals
            
            signal = GapSignal(
                symbol=symbol,
                timestamp=datetime.strptime(date, '%Y-%m-%d'),
                signal_type=signal_type,
                gap_pct=gap_pct,
                prev_close=prev_close,
                open_price=today_open,
                entry_price=entry,
                stop_price=stop,
                target_price=target,
                confidence=confidence,
                dp_confluence=dp_confluence,
                reasoning=reasoning
            )
            signals.append(signal)
            
        except Exception as e:
            print(f"Error detecting gap signals: {e}")
        
        return signals
    
    def backtest_date(
        self,
        symbol: str,
        date: str
    ) -> Dict:
        """
        Backtest gap signals for a specific date.
        
        Returns:
            Dict with signals and simulated outcomes
        """
        signals = self.detect_gap_signals(symbol, date)
        
        results = {
            'date': date,
            'symbol': symbol,
            'signals': [],
            'wins': 0,
            'losses': 0
        }
        
        for signal in signals:
            # Simulate trade outcome
            try:
                ticker = yf.Ticker(symbol)
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                intraday = ticker.history(period='5d', interval='1m')
                intraday = intraday[intraday.index.date == target_date]
                
                if intraday.empty:
                    continue
                
                # Check if target or stop was hit
                outcome = 'NO_HIT'
                for _, row in intraday.iterrows():
                    if signal.signal_type in ['GAP_UP_BREAKOUT', 'GAP_FILL']:
                        if row['High'] >= signal.target_price:
                            outcome = 'WIN'
                            break
                        if row['Low'] <= signal.stop_price:
                            outcome = 'LOSS'
                            break
                    else:  # GAP_DOWN_BREAKDOWN
                        if row['Low'] <= signal.target_price:
                            outcome = 'WIN'
                            break
                        if row['High'] >= signal.stop_price:
                            outcome = 'LOSS'
                            break
                
                if outcome == 'WIN':
                    results['wins'] += 1
                elif outcome == 'LOSS':
                    results['losses'] += 1
                
                results['signals'].append({
                    'signal_type': signal.signal_type,
                    'gap_pct': signal.gap_pct,
                    'confidence': signal.confidence,
                    'dp_confluence': signal.dp_confluence,
                    'outcome': outcome
                })
                
            except Exception as e:
                print(f"Error simulating trade: {e}")
        
        return results
    
    def backtest_range(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Backtest gap signals over a date range.
        """
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        all_results = []
        current = start
        
        while current <= end:
            if current.weekday() < 5:  # Skip weekends
                date_str = current.strftime('%Y-%m-%d')
                result = self.backtest_date(symbol, date_str)
                all_results.append(result)
            current += timedelta(days=1)
        
        # Aggregate
        total_signals = sum(len(r['signals']) for r in all_results)
        total_wins = sum(r['wins'] for r in all_results)
        total_losses = sum(r['losses'] for r in all_results)
        
        win_rate = total_wins / (total_wins + total_losses) * 100 if (total_wins + total_losses) > 0 else 0
        
        return {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'total_signals': total_signals,
            'wins': total_wins,
            'losses': total_losses,
            'win_rate': win_rate,
            'daily_results': all_results
        }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 60)
    print("🌅 PRE-MARKET GAP BACKTEST")
    print("=" * 60)
    
    backtester = PreMarketGapBacktester()
    
    # Test today
    today = datetime.now().strftime('%Y-%m-%d')
    result = backtester.backtest_date('SPY', today)
    
    print(f"\n📊 Results for {today}:")
    print(f"   Signals: {len(result['signals'])}")
    print(f"   Wins: {result['wins']}")
    print(f"   Losses: {result['losses']}")
    
    for sig in result['signals']:
        print(f"\n   Signal: {sig['signal_type']}")
        print(f"   Gap: {sig['gap_pct']:.2f}%")
        print(f"   Confidence: {sig['confidence']:.0%}")
        print(f"   DP Confluence: {'✅' if sig['dp_confluence'] else '❌'}")
        print(f"   Outcome: {sig['outcome']}")

