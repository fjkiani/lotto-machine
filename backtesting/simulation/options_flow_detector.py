"""
📊 OPTIONS FLOW DETECTOR SIMULATOR
Simulates options flow signals and trades

Signals:
- CALL_ACCUMULATION: Unusual call buying
- PUT_ACCUMULATION: Unusual put buying
- PC_RATIO_EXTREME: Put/Call ratio at extremes
- MAX_PAIN_MAGNET: Price approaching max pain
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

from ..config.trading_params import TradingParams


@dataclass
class OptionsFlowSignal:
    """Options flow signal"""
    symbol: str
    timestamp: datetime
    signal_type: str  # CALL_ACCUMULATION, PUT_ACCUMULATION, etc.
    put_call_ratio: float
    max_pain: float
    current_price: float
    max_pain_distance_pct: float
    total_call_volume: int
    total_put_volume: int
    entry_price: float
    stop_price: float
    target_price: float
    confidence: float
    reasoning: str


class OptionsFlowBacktester:
    """
    Backtests options flow strategy on historical data.
    
    Uses yfinance options chain data for analysis.
    Note: Real-time sweeps require premium API.
    """
    
    def __init__(self, params: TradingParams = None):
        self.params = params or TradingParams()
        
    def get_options_metrics(self, symbol: str) -> Optional[Dict]:
        """
        Get options metrics from yfinance.
        
        Returns:
            Dict with P/C ratio, max pain, volumes
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Get options expirations
            expirations = ticker.options
            if not expirations:
                return None
            
            # Use nearest expiration
            nearest_exp = expirations[0]
            
            # Get option chain
            chain = ticker.option_chain(nearest_exp)
            calls = chain.calls
            puts = chain.puts
            
            if calls.empty or puts.empty:
                return None
            
            # Calculate metrics
            total_call_volume = int(calls['volume'].sum())
            total_put_volume = int(puts['volume'].sum())
            total_call_oi = int(calls['openInterest'].sum())
            total_put_oi = int(puts['openInterest'].sum())
            
            # Put/Call ratio
            pc_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 1.0
            
            # Max pain calculation
            current_price = float(ticker.history(period='1d')['Close'].iloc[-1])
            
            strikes = sorted(set(calls['strike'].tolist() + puts['strike'].tolist()))
            
            max_pain_strike = current_price
            min_pain_value = float('inf')
            
            for strike in strikes:
                # Calculate total pain for each strike
                call_pain = 0
                put_pain = 0
                
                # Pain for calls (if price > strike, call holders profit)
                call_row = calls[calls['strike'] == strike]
                if not call_row.empty:
                    call_oi = int(call_row['openInterest'].iloc[0])
                    if current_price > strike:
                        call_pain = (current_price - strike) * call_oi * 100
                
                # Pain for puts (if price < strike, put holders profit)
                put_row = puts[puts['strike'] == strike]
                if not put_row.empty:
                    put_oi = int(put_row['openInterest'].iloc[0])
                    if current_price < strike:
                        put_pain = (strike - current_price) * put_oi * 100
                
                total_pain = call_pain + put_pain
                if total_pain < min_pain_value:
                    min_pain_value = total_pain
                    max_pain_strike = strike
            
            return {
                'expiration': nearest_exp,
                'current_price': current_price,
                'put_call_ratio': pc_ratio,
                'max_pain': max_pain_strike,
                'max_pain_distance_pct': ((current_price - max_pain_strike) / current_price) * 100,
                'total_call_volume': total_call_volume,
                'total_put_volume': total_put_volume,
                'total_call_oi': total_call_oi,
                'total_put_oi': total_put_oi
            }
            
        except Exception as e:
            print(f"Error getting options metrics: {e}")
            return None
    
    def detect_signals(self, symbol: str, date: str = None) -> List[OptionsFlowSignal]:
        """
        Detect options flow signals.
        
        Args:
            symbol: Stock symbol
            date: Date (for logging, uses current data)
            
        Returns:
            List of OptionsFlowSignal objects
        """
        signals = []
        
        metrics = self.get_options_metrics(symbol)
        if not metrics:
            return signals
        
        current_price = metrics['current_price']
        pc_ratio = metrics['put_call_ratio']
        max_pain = metrics['max_pain']
        max_pain_dist = metrics['max_pain_distance_pct']
        
        timestamp = datetime.strptime(date, '%Y-%m-%d') if date else datetime.now()
        
        # Signal 1: Extreme Put/Call Ratio
        if pc_ratio < 0.5:  # Very bullish
            signal = OptionsFlowSignal(
                symbol=symbol,
                timestamp=timestamp,
                signal_type="CALL_ACCUMULATION",
                put_call_ratio=pc_ratio,
                max_pain=max_pain,
                current_price=current_price,
                max_pain_distance_pct=max_pain_dist,
                total_call_volume=metrics['total_call_volume'],
                total_put_volume=metrics['total_put_volume'],
                entry_price=current_price,
                stop_price=current_price * 0.99,
                target_price=current_price * 1.02,
                confidence=0.65,
                reasoning=f"Low P/C ratio ({pc_ratio:.2f}) indicates call accumulation"
            )
            signals.append(signal)
            
        elif pc_ratio > 1.5:  # Very bearish
            signal = OptionsFlowSignal(
                symbol=symbol,
                timestamp=timestamp,
                signal_type="PUT_ACCUMULATION",
                put_call_ratio=pc_ratio,
                max_pain=max_pain,
                current_price=current_price,
                max_pain_distance_pct=max_pain_dist,
                total_call_volume=metrics['total_call_volume'],
                total_put_volume=metrics['total_put_volume'],
                entry_price=current_price,
                stop_price=current_price * 1.01,
                target_price=current_price * 0.98,
                confidence=0.65,
                reasoning=f"High P/C ratio ({pc_ratio:.2f}) indicates put accumulation"
            )
            signals.append(signal)
        
        # Signal 2: Max Pain Magnet
        if abs(max_pain_dist) > 1.0 and abs(max_pain_dist) < 3.0:
            # Price is 1-3% away from max pain - expect convergence
            direction = "UP" if max_pain > current_price else "DOWN"
            
            if direction == "UP":
                target = max_pain * 0.998
                stop = current_price * 0.99
            else:
                target = max_pain * 1.002
                stop = current_price * 1.01
            
            signal = OptionsFlowSignal(
                symbol=symbol,
                timestamp=timestamp,
                signal_type="MAX_PAIN_MAGNET",
                put_call_ratio=pc_ratio,
                max_pain=max_pain,
                current_price=current_price,
                max_pain_distance_pct=max_pain_dist,
                total_call_volume=metrics['total_call_volume'],
                total_put_volume=metrics['total_put_volume'],
                entry_price=current_price,
                stop_price=stop,
                target_price=target,
                confidence=0.60,
                reasoning=f"Price {abs(max_pain_dist):.1f}% from max pain ${max_pain:.2f}, expect convergence"
            )
            signals.append(signal)
        
        return signals
    
    def backtest_date(self, symbol: str, date: str) -> Dict:
        """
        Backtest options flow signals for a specific date.
        """
        signals = self.detect_signals(symbol, date)
        
        results = {
            'date': date,
            'symbol': symbol,
            'signals': [],
            'wins': 0,
            'losses': 0
        }
        
        for signal in signals:
            # Simulate trade outcome (simplified)
            try:
                ticker = yf.Ticker(symbol)
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
                
                hist = ticker.history(period='5d', interval='1m')
                hist = hist[hist.index.date == target_date]
                
                if hist.empty:
                    continue
                
                # Check if target or stop was hit
                outcome = 'NO_HIT'
                is_long = signal.signal_type in ['CALL_ACCUMULATION', 'MAX_PAIN_MAGNET'] and signal.target_price > signal.entry_price
                
                for _, row in hist.iterrows():
                    if is_long:
                        if row['High'] >= signal.target_price:
                            outcome = 'WIN'
                            break
                        if row['Low'] <= signal.stop_price:
                            outcome = 'LOSS'
                            break
                    else:
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
                    'pc_ratio': signal.put_call_ratio,
                    'max_pain': signal.max_pain,
                    'confidence': signal.confidence,
                    'outcome': outcome
                })
                
            except Exception as e:
                print(f"Error simulating trade: {e}")
        
        return results
    
    def backtest_range(self, symbol: str, days: int = 30) -> Dict:
        """
        Backtest options flow over last N days.
        
        Note: yfinance options data is current, not historical.
        This provides current snapshot analysis.
        """
        # For options, we can only analyze current data
        # Historical options data requires premium sources
        
        today = datetime.now().strftime('%Y-%m-%d')
        result = self.backtest_date(symbol, today)
        
        return {
            'symbol': symbol,
            'analysis_date': today,
            'note': 'Options data is current snapshot only (historical requires premium API)',
            'signals': result['signals'],
            'wins': result['wins'],
            'losses': result['losses']
        }


if __name__ == "__main__":
    print("=" * 60)
    print("📊 OPTIONS FLOW BACKTEST")
    print("=" * 60)
    
    backtester = OptionsFlowBacktester()
    
    for symbol in ['SPY', 'QQQ']:
        print(f"\n📈 {symbol}:")
        
        metrics = backtester.get_options_metrics(symbol)
        if metrics:
            print(f"   P/C Ratio: {metrics['put_call_ratio']:.2f}")
            print(f"   Max Pain: ${metrics['max_pain']:.2f}")
            print(f"   Distance: {metrics['max_pain_distance_pct']:.1f}%")
            print(f"   Call Volume: {metrics['total_call_volume']:,}")
            print(f"   Put Volume: {metrics['total_put_volume']:,}")
        
        today = datetime.now().strftime('%Y-%m-%d')
        signals = backtester.detect_signals(symbol, today)
        
        if signals:
            print(f"\n   ✅ {len(signals)} signals detected:")
            for sig in signals:
                print(f"      {sig.signal_type}: {sig.reasoning}")
        else:
            print(f"\n   ⚪ No signals detected")

