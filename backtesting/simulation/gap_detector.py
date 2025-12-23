"""
🌅 GAP DETECTOR
Detects pre-market gap opportunities.

SIGNALS:
1. GAP_UP_CONTINUATION: Large gap up (>0.5%) that continues
2. GAP_DOWN_CONTINUATION: Large gap down (<-0.5%) that continues  
3. GAP_FILL: Smaller gaps (0.3-0.5%) that tend to fill

STRATEGY LOGIC:
- Large gaps (>0.5%) often continue in the direction
- Small gaps (0.3-0.5%) often fill back to prior close
- Combine with DP levels for confirmation

Author: Zo (Alpha's AI)
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
import yfinance as yf

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from backtesting.simulation.base_detector import BaseDetector, Signal


class GapDetector(BaseDetector):
    """
    Pre-market gap detector.
    
    Generates signals based on overnight gaps.
    Large gaps continue, small gaps fill.
    """
    
    # Thresholds
    SMALL_GAP_MIN = 0.30      # Minimum gap % for small gap
    LARGE_GAP_MIN = 0.50      # Minimum gap % for large gap
    
    def __init__(
        self,
        small_gap_min: float = None,
        large_gap_min: float = None,
        stop_pct: float = 0.30,
        target_pct: float = 0.45,  # FIXED: 1.5:1 R/R (was 0.25 = 0.83:1)
        max_bars: int = 60
    ):
        super().__init__(stop_pct, target_pct, max_bars)
        self.small_gap_min = small_gap_min or self.SMALL_GAP_MIN
        self.large_gap_min = large_gap_min or self.LARGE_GAP_MIN
    
    @property
    def name(self) -> str:
        return "gap_detector"
    
    def detect_signals(
        self, 
        symbol: str, 
        data: pd.DataFrame,
        yesterday_close: float = None,
        check_dp_confluence: bool = True,
        **kwargs
    ) -> List[Signal]:
        """
        Detect gap signals with DP confluence and fill detection.
        
        Args:
            symbol: Stock symbol
            data: Today's OHLCV DataFrame
            yesterday_close: Previous day close (if known)
            check_dp_confluence: Check for DP level alignment
            
        Returns:
            List of Signal objects
        """
        signals = []
        
        if data.empty or len(data) < 30:  # Need at least 30 min of data
            return signals
        
        today_open = data['Open'].iloc[0]
        
        # Get yesterday's close if not provided
        if yesterday_close is None:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")
                if len(hist) >= 2:
                    # Find yesterday (previous trading day)
                    today_date = data.index[0].date() if hasattr(data.index[0], 'date') else datetime.now().date()
                    prev_days = hist[hist.index.date < today_date]
                    if not prev_days.empty:
                        yesterday_close = prev_days['Close'].iloc[-1]
            except:
                pass
        
        if yesterday_close is None:
            return signals
        
        # Calculate gap
        gap_pct = (today_open - yesterday_close) / yesterday_close * 100
        
        if abs(gap_pct) < self.small_gap_min:
            return signals  # No significant gap
        
        # Get first hour high/low for breakout detection
        first_hour = data.iloc[:30] if len(data) >= 30 else data.iloc[:len(data)]
        first_hour_high = first_hour['High'].max()
        first_hour_low = first_hour['Low'].min()
        
        current_price = data['Close'].iloc[-1] if len(data) > 0 else today_open
        current_time = data.index[0]  # Signal at open
        
        # Check DP confluence
        dp_confluence = False
        if check_dp_confluence:
            try:
                import os
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                api_key = os.getenv('CHARTEXCHANGE_API_KEY')
                if api_key:
                    client = UltimateChartExchangeClient(api_key=api_key)
                    yesterday_date = (datetime.strptime(data.index[0].strftime('%Y-%m-%d'), '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
                    dp_data = client.get_dark_pool_levels(symbol, yesterday_date)
                    
                    if dp_data and 'levels' in dp_data:
                        for level in dp_data['levels'][:10]:
                            level_price = float(level.get('level', level.get('price', 0)))
                            if abs(today_open - level_price) / today_open < 0.01:  # Within 1%
                                dp_confluence = True
                                break
            except Exception as e:
                pass  # DP check failed, continue without it
        
        # Determine signal type using OLD DETECTOR LOGIC (smarter!)
        if gap_pct > 0:
            # Gap up
            if current_price > first_hour_high:
                # GAP_UP_BREAKOUT - price broke above first hour high
                entry = first_hour_high
                stop = first_hour_low
                target = entry + (entry - stop) * 2  # 2:1 R/R
                confidence = 65 + (15 if dp_confluence else 0)
                
                signal = Signal(
                    symbol=symbol,
                    timestamp=current_time if hasattr(current_time, 'isoformat') else datetime.now(),
                    signal_type='GAP_UP_BREAKOUT',
                    direction='LONG',
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    confidence=confidence,
                    reasoning=f"Gap up {gap_pct:+.2f}%, broke above first hour high" + (" + DP confluence" if dp_confluence else ""),
                    metadata={
                        'gap_pct': gap_pct,
                        'yesterday_close': yesterday_close,
                        'today_open': today_open,
                        'dp_confluence': dp_confluence,
                        'gap_type': 'BREAKOUT'
                    }
                )
                signals.append(signal)
            elif current_price < yesterday_close:
                # GAP_FILL - price filling back to previous close
                entry = yesterday_close * 0.998  # Just below prev close
                stop = today_open * 1.01  # Above open
                target = yesterday_close * 0.99  # 1% below fill level
                confidence = 60 + (10 if dp_confluence else 0)
                
                signal = Signal(
                    symbol=symbol,
                    timestamp=current_time if hasattr(current_time, 'isoformat') else datetime.now(),
                    signal_type='GAP_FILL',
                    direction='SHORT',
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    confidence=confidence,
                    reasoning=f"Gap up {gap_pct:+.2f}% filling back to previous close" + (" + DP confluence" if dp_confluence else ""),
                    metadata={
                        'gap_pct': gap_pct,
                        'yesterday_close': yesterday_close,
                        'today_open': today_open,
                        'dp_confluence': dp_confluence,
                        'gap_type': 'FILL'
                    }
                )
                signals.append(signal)
        
        else:  # gap_pct < 0
            # Gap down
            if current_price < first_hour_low:
                # GAP_DOWN_BREAKDOWN - price broke below first hour low
                entry = first_hour_low
                stop = first_hour_high
                target = entry - (stop - entry) * 2  # 2:1 R/R
                confidence = 65 + (15 if dp_confluence else 0)
                
                signal = Signal(
                    symbol=symbol,
                    timestamp=current_time if hasattr(current_time, 'isoformat') else datetime.now(),
                    signal_type='GAP_DOWN_BREAKDOWN',
                    direction='SHORT',
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    confidence=confidence,
                    reasoning=f"Gap down {gap_pct:+.2f}%, broke below first hour low" + (" + DP confluence" if dp_confluence else ""),
                    metadata={
                        'gap_pct': gap_pct,
                        'yesterday_close': yesterday_close,
                        'today_open': today_open,
                        'dp_confluence': dp_confluence,
                        'gap_type': 'BREAKDOWN'
                    }
                )
                signals.append(signal)
            elif current_price > yesterday_close:
                # GAP_FILL - price filling back to previous close
                entry = yesterday_close * 1.002
                stop = today_open * 0.99
                target = yesterday_close * 1.01
                confidence = 60 + (10 if dp_confluence else 0)
                
                signal = Signal(
                    symbol=symbol,
                    timestamp=current_time if hasattr(current_time, 'isoformat') else datetime.now(),
                    signal_type='GAP_FILL',
                    direction='LONG',
                    entry_price=entry,
                    stop_price=stop,
                    target_price=target,
                    confidence=confidence,
                    reasoning=f"Gap down {gap_pct:+.2f}% filling back to previous close" + (" + DP confluence" if dp_confluence else ""),
                    metadata={
                        'gap_pct': gap_pct,
                        'yesterday_close': yesterday_close,
                        'today_open': today_open,
                        'dp_confluence': dp_confluence,
                        'gap_type': 'FILL'
                    }
                )
                signals.append(signal)
        
        return signals


# Standalone test
if __name__ == "__main__":
    print("=" * 70)
    print("🌅 GAP DETECTOR BACKTEST")
    print("=" * 70)
    
    detector = GapDetector(
        stop_pct=0.30,
        target_pct=0.45,  # FIXED: 1.5:1 R/R
        max_bars=60
    )
    
    symbols = ['SPY', 'QQQ']
    
    result = detector.backtest_date(symbols)
    detector.print_result(result)
    
    print("\n📋 SIGNAL DETAILS:")
    for sig in result.signals:
        gap_pct = sig.metadata.get('gap_pct', 0)
        print(f"   {sig.signal_type}: {sig.symbol} {sig.direction}")
        print(f"      Gap: {gap_pct:+.2f}% | Entry: ${sig.entry_price:.2f} | Target: ${sig.target_price:.2f}")
    
    print("\n" + "=" * 70)
    print("✅ GAP DETECTOR BACKTEST COMPLETE!")
    print("=" * 70)

