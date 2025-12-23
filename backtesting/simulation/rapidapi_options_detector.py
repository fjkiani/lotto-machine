"""
📊 RAPIDAPI OPTIONS FLOW DETECTOR
Uses Yahoo Finance 15 RapidAPI for real options flow data.

SIGNALS:
1. OPTIONS_BULLISH: Low P/C ratio (< 0.7) = bullish accumulation
2. OPTIONS_BEARISH: High P/C ratio (> 1.3) = bearish hedging
3. UNUSUAL_ACTIVITY: Vol/OI ratio > 5x = smart money positioning

DATA SOURCE: 
- /api/v1/markets/options/most-active (WORKING)
- /api/v1/markets/options/unusual-options-activity (WORKING)

Author: Zo (Alpha's AI)
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict
import pandas as pd

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from dotenv import load_dotenv
load_dotenv()

from backtesting.simulation.base_detector import BaseDetector, Signal


class RapidAPIOptionsDetector(BaseDetector):
    """
    Options flow detector using RapidAPI data.
    
    Generates signals based on:
    - Put/Call ratio extremes
    - Unusual volume/OI activity
    - Options accumulation patterns
    """
    
    # Thresholds
    BULLISH_PC_THRESHOLD = 0.7      # P/C below this = bullish
    BEARISH_PC_THRESHOLD = 1.3      # P/C above this = bearish
    UNUSUAL_VOL_OI_THRESHOLD = 5.0  # Vol/OI ratio for unusual
    MIN_VOLUME = 10000              # Minimum options volume
    
    def __init__(
        self,
        api_key: str = None,
        stop_pct: float = 1.00,  # 1% stop for options signals
        target_pct: float = 1.50,  # FIXED: 1.5:1 R/R (was 0.75 = 0.75:1 = losing!)
        max_bars: int = 78,  # Full day of 5-min bars
        enable_dp_confluence: bool = True
    ):
        super().__init__(stop_pct, target_pct, max_bars)
        
        # Initialize RapidAPI client
        from core.data.rapidapi_options_client import RapidAPIOptionsClient
        self.client = RapidAPIOptionsClient(api_key=api_key)
        
        # Initialize DP client for confluence checking
        self.enable_dp_confluence = enable_dp_confluence
        self.dp_client = None
        if self.enable_dp_confluence:
            try:
                chartexchange_key = os.getenv('CHARTEXCHANGE_API_KEY')
                if chartexchange_key:
                    from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                    self.dp_client = UltimateChartExchangeClient(api_key=chartexchange_key)
            except Exception as e:
                print(f"   ⚠️ Could not init DP client for confluence: {e}")
                self.dp_client = None
    
    @property
    def name(self) -> str:
        return "rapidapi_options_detector"
    
    def _check_dp_confluence(self, symbol: str, price: float, direction: str, date_str: str = None) -> tuple[bool, float, int]:
        """
        Check if there's DP confluence near the signal price.
        
        Returns:
            (has_confluence, dp_level, dp_volume)
        """
        if not self.dp_client or not self.enable_dp_confluence:
            return False, 0.0, 0
        
        try:
            # Use previous day for T+1 data
            from datetime import datetime, timedelta
            if date_str:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_obj = datetime.now()
            prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
            
            levels_data = self.dp_client.get_dark_pool_levels(symbol, prev_date)
            if not levels_data:
                return False, 0.0, 0
            
            # Extract levels
            levels = []
            if isinstance(levels_data, dict) and 'levels' in levels_data:
                levels = levels_data['levels']
            elif isinstance(levels_data, list):
                levels = levels_data
            
            if not levels:
                return False, 0.0, 0
            
            # Find nearest DP level
            nearest_level = None
            nearest_distance = float('inf')
            nearest_volume = 0
            
            for level_data in levels[:20]:  # Top 20 levels
                level = float(level_data.get('level', level_data.get('price', 0)))
                volume = int(level_data.get('volume', level_data.get('total_volume', 0)))
                
                distance = abs(price - level) / price
                
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_level = level
                    nearest_volume = volume
            
            # Check if DP level supports the trade direction
            if nearest_level and nearest_distance < 0.01:  # Within 1%
                supports_trade = False
                if direction == 'LONG' and nearest_level <= price:
                    supports_trade = True  # DP support below
                elif direction == 'SHORT' and nearest_level >= price:
                    supports_trade = True  # DP resistance above
                
                if supports_trade and nearest_volume >= 500_000:  # At least 500k shares
                    return True, nearest_level, nearest_volume
            
            return False, nearest_level or 0.0, nearest_volume
            
        except Exception as e:
            # Fail silently - DP check is optional
            return False, 0.0, 0
    
    def detect_signals(
        self, 
        symbol: str = None, 
        data: pd.DataFrame = None,
        **kwargs
    ) -> List[Signal]:
        """
        Detect options flow signals.
        
        Note: This detector uses API data, not price data.
        Symbol parameter is optional - will scan all active stocks.
        
        Returns:
            List of Signal objects
        """
        signals = []
        
        try:
            # Get most active options
            most_active = self.client.get_most_active_options(option_type='STOCKS')
            
            if most_active:
                for opt in most_active:
                    if opt.total_volume < self.MIN_VOLUME:
                        continue
                    
                    pc_ratio = opt.put_call_ratio
                    
                    # Bullish signal
                    if pc_ratio < self.BULLISH_PC_THRESHOLD:
                        confidence = min(90, 50 + (self.BULLISH_PC_THRESHOLD - pc_ratio) * 100)
                        
                        # Get current price from data or fetch
                        current_price = opt.last_price
                        
                        # Check DP confluence (boost confidence if present)
                        date_str = datetime.now().strftime('%Y-%m-%d')
                        has_dp, dp_level, dp_volume = self._check_dp_confluence(opt.symbol, current_price, 'LONG', date_str)
                        
                        if has_dp:
                            confidence += 15  # Boost confidence by 15% for DP confluence
                            confidence = min(confidence, 100)  # Cap at 100%
                            reasoning = f"Bullish options flow: P/C {pc_ratio:.2f}, Call% {opt.call_volume_pct:.0f}% | DP confluence @ ${dp_level:.2f} ({dp_volume:,} shares)"
                        else:
                            reasoning = f"Bullish options flow: P/C {pc_ratio:.2f}, Call% {opt.call_volume_pct:.0f}%"
                        
                        signal = Signal(
                            symbol=opt.symbol,
                            timestamp=datetime.now(),
                            signal_type='OPTIONS_BULLISH',
                            direction='LONG',
                            entry_price=current_price,
                            stop_price=current_price * (1 - self.stop_pct / 100),
                            target_price=current_price * (1 + self.target_pct / 100),
                            confidence=confidence,
                            reasoning=reasoning,
                            metadata={
                                'pc_ratio': pc_ratio,
                                'call_pct': opt.call_volume_pct,
                                'put_pct': opt.put_volume_pct,
                                'total_volume': opt.total_volume,
                                'iv_rank': opt.iv_rank_1y,
                                'dp_confluence': has_dp,
                                'dp_level': dp_level if has_dp else None
                            }
                        )
                        signals.append(signal)
                    
                    # Bearish signal
                    elif pc_ratio > self.BEARISH_PC_THRESHOLD:
                        confidence = min(90, 50 + (pc_ratio - self.BEARISH_PC_THRESHOLD) * 30)
                        
                        current_price = opt.last_price
                        
                        # Check DP confluence (boost confidence if present)
                        date_str = datetime.now().strftime('%Y-%m-%d')
                        has_dp, dp_level, dp_volume = self._check_dp_confluence(opt.symbol, current_price, 'SHORT', date_str)
                        
                        if has_dp:
                            confidence += 15  # Boost confidence by 15% for DP confluence
                            confidence = min(confidence, 100)  # Cap at 100%
                            reasoning = f"Bearish options flow: P/C {pc_ratio:.2f}, Put% {opt.put_volume_pct:.0f}% | DP confluence @ ${dp_level:.2f} ({dp_volume:,} shares)"
                        else:
                            reasoning = f"Bearish options flow: P/C {pc_ratio:.2f}, Put% {opt.put_volume_pct:.0f}%"
                        
                        signal = Signal(
                            symbol=opt.symbol,
                            timestamp=datetime.now(),
                            signal_type='OPTIONS_BEARISH',
                            direction='SHORT',
                            entry_price=current_price,
                            stop_price=current_price * (1 + self.stop_pct / 100),
                            target_price=current_price * (1 - self.target_pct / 100),
                            confidence=confidence,
                            reasoning=reasoning,
                            metadata={
                                'pc_ratio': pc_ratio,
                                'call_pct': opt.call_volume_pct,
                                'put_pct': opt.put_volume_pct,
                                'total_volume': opt.total_volume,
                                'iv_rank': opt.iv_rank_1y,
                                'dp_confluence': has_dp,
                                'dp_level': dp_level if has_dp else None
                            }
                        )
                        signals.append(signal)
            
            # Get unusual activity
            unusual = self.client.get_unusual_activity(option_type='STOCKS')
            
            if unusual:
                processed_symbols = set()  # Avoid duplicate symbols
                for opt in unusual[:20]:  # Top 20 unusual
                    if opt.vol_oi_ratio >= self.UNUSUAL_VOL_OI_THRESHOLD:
                        # Extract stock symbol from options symbol (e.g., "AAPL|20251219|200.00C" -> "AAPL")
                        stock_symbol = opt.symbol.split('|')[0] if '|' in opt.symbol else opt.symbol
                        
                        if stock_symbol in processed_symbols:
                            continue
                        processed_symbols.add(stock_symbol)
                        
                        direction = 'LONG' if opt.option_type == 'Call' else 'SHORT'
                        signal_type = 'UNUSUAL_CALL' if opt.option_type == 'Call' else 'UNUSUAL_PUT'
                        
                        confidence = min(95, 60 + opt.vol_oi_ratio * 3)
                        
                        # Get STOCK price (not option price)
                        price_data = self.get_intraday_data(stock_symbol, period="1d", interval="5m")
                        if price_data.empty:
                            continue
                        
                        current_price = price_data['Close'].iloc[-1]
                        
                        signal = Signal(
                            symbol=stock_symbol,  # Use stock symbol
                            timestamp=datetime.now(),
                            signal_type=signal_type,
                            direction=direction,
                            entry_price=current_price,
                            stop_price=current_price * (1 - self.stop_pct / 100) if direction == 'LONG' else current_price * (1 + self.stop_pct / 100),
                            target_price=current_price * (1 + self.target_pct / 100) if direction == 'LONG' else current_price * (1 - self.target_pct / 100),
                            confidence=confidence,
                            reasoning=f"Unusual {opt.option_type}: ${opt.strike} exp {opt.expiration}, Vol/OI {opt.vol_oi_ratio:.1f}x",
                            metadata={
                                'strike': opt.strike,
                                'expiration': opt.expiration,
                                'vol_oi_ratio': opt.vol_oi_ratio,
                                'volume': opt.volume,
                                'open_interest': opt.open_interest,
                                'days_to_exp': opt.days_to_exp
                            }
                        )
                        signals.append(signal)
        
        except Exception as e:
            print(f"   ❌ Options API error: {e}")
            import traceback
            traceback.print_exc()
        
        return signals
    
    def backtest_date(
        self, 
        symbols: List[str] = None,
        date: str = None,
        **kwargs
    ):
        """
        Run backtest for today.
        
        Note: Options detector scans all active stocks, not just specific symbols.
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        
        # Get signals from API
        signals = self.detect_signals()
        
        # Simulate trades using intraday price data
        trades = []
        for signal in signals:
            data = self.get_intraday_data(signal.symbol, period="1d", interval="5m")
            if data.empty:
                continue
            
            # Assume entry at signal time (now) - use current bar
            entry_idx = len(data) - 1 if len(data) > 0 else 0
            
            # For today's backtest, we check from open
            trade = self.simulate_trade(signal, data, entry_idx=0)
            trades.append(trade)
        
        return self._calculate_metrics(date, signals, trades)


# Standalone test
if __name__ == "__main__":
    print("=" * 70)
    print("📊 RAPIDAPI OPTIONS FLOW DETECTOR BACKTEST")
    print("=" * 70)
    
    detector = RapidAPIOptionsDetector(
        stop_pct=0.50,
        target_pct=0.75,  # FIXED: 1.5:1 R/R
        max_bars=60
    )
    
    result = detector.backtest_date()
    detector.print_result(result)
    
    print("\n📋 SIGNAL DETAILS:")
    for sig in result.signals[:10]:
        print(f"   {sig.signal_type}: {sig.symbol} {sig.direction} @ ${sig.entry_price:.2f}")
        print(f"      Confidence: {sig.confidence:.0f}% | {sig.reasoning}")
    
    print("\n" + "=" * 70)
    print("✅ RAPIDAPI OPTIONS DETECTOR BACKTEST COMPLETE!")
    print("=" * 70)

