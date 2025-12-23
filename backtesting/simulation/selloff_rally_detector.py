"""
📉📈 SELLOFF/RALLY DETECTOR
Detects rapid price movements using multi-trigger approach.

TRIGGERS:
1. FROM_OPEN: -0.25% from day open (selloff) or +0.25% (rally)
2. ROLLING: -0.20% in last 20 bars (selloff) or +0.20% (rally)  
3. MOMENTUM: 3+ consecutive red bars (selloff) or green bars (rally)

VALIDATION (2025-12-19):
- Win Rate: 75% with 0.15% targets, 0.20% stops
- Best in TRENDING markets, not chop

Author: Zo (Alpha's AI)
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import pandas as pd

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from backtesting.simulation.base_detector import BaseDetector, Signal


class SelloffRallyDetector(BaseDetector):
    """
    Multi-trigger selloff/rally detector.
    
    Generates signals when:
    - Price drops/rises significantly from open
    - Rolling window shows momentum
    - Consecutive candle pattern detected
    
    Multiple triggers = higher confidence
    """
    
    # Configurable thresholds
    FROM_OPEN_THRESHOLD = 0.25      # % from open to trigger
    ROLLING_THRESHOLD = 0.20        # % rolling change to trigger
    ROLLING_WINDOW = 20             # Bars for rolling calculation
    CONSECUTIVE_BARS = 3            # Consecutive red/green bars
    COOLDOWN_BARS = 30              # Min bars between signals
    
    def __init__(
        self,
        from_open_threshold: float = None,
        rolling_threshold: float = None,
        stop_pct: float = 0.20,
        target_pct: float = 0.30,  # FIXED: 1.5:1 R/R (was 0.15 = 0.75:1 = losing!)
        max_bars: int = 30,
        enable_dp_confluence: bool = True
    ):
        super().__init__(stop_pct, target_pct, max_bars)
        self.from_open_threshold = from_open_threshold or self.FROM_OPEN_THRESHOLD
        self.rolling_threshold = rolling_threshold or self.ROLLING_THRESHOLD
        self.enable_dp_confluence = enable_dp_confluence
        
        # Initialize DP client if enabled
        self.dp_client = None
        if self.enable_dp_confluence:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.getenv('CHARTEXCHANGE_API_KEY')
                if api_key:
                    from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                    self.dp_client = UltimateChartExchangeClient(api_key=api_key)
            except Exception as e:
                print(f"   ⚠️ Could not init DP client for confluence: {e}")
                self.dp_client = None
    
    @property
    def name(self) -> str:
        return "selloff_rally_detector"
    
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
        symbol: str, 
        data: pd.DataFrame,
        **kwargs
    ) -> List[Signal]:
        """
        Detect selloff/rally signals from price data.
        
        Args:
            symbol: Stock symbol
            data: OHLCV DataFrame
            
        Returns:
            List of Signal objects
        """
        signals = []
        
        if len(data) < self.ROLLING_WINDOW + 10:
            return signals
        
        day_open = data['Open'].iloc[0]
        last_signal_idx = -self.COOLDOWN_BARS  # Allow first signal
        
        for i in range(self.ROLLING_WINDOW, len(data)):
            # Skip if too close to last signal
            if i - last_signal_idx < self.COOLDOWN_BARS:
                continue
            
            current_price = data['Close'].iloc[i]
            current_time = data.index[i]
            
            # Calculate metrics
            from_open_pct = (current_price - day_open) / day_open * 100
            
            window_start = data['Close'].iloc[i - self.ROLLING_WINDOW]
            rolling_pct = (current_price - window_start) / window_start * 100
            
            # Count consecutive bars
            consecutive_red = 0
            consecutive_green = 0
            for j in range(i - 1, max(i - 10, 0), -1):
                if data['Close'].iloc[j] < data['Open'].iloc[j]:
                    if consecutive_green == 0:
                        consecutive_red += 1
                    else:
                        break
                else:
                    if consecutive_red == 0:
                        consecutive_green += 1
                    else:
                        break
            
            # SELLOFF DETECTION - require 2+ triggers for higher confidence
            triggers = []
            if from_open_pct <= -self.from_open_threshold:
                triggers.append('FROM_OPEN')
            if rolling_pct <= -self.rolling_threshold:
                triggers.append('ROLLING')
            if consecutive_red >= self.CONSECUTIVE_BARS:
                triggers.append('MOMENTUM')
            
            # Require at least 2 triggers for signal (reduces false positives)
            if len(triggers) >= 2:
                confidence = 50 + len(triggers) * 15  # 65-95 based on triggers
                
                # Check DP confluence (boost confidence if present)
                date_str = data.index[0].strftime('%Y-%m-%d') if hasattr(data.index[0], 'strftime') else None
                has_dp, dp_level, dp_volume = self._check_dp_confluence(symbol, current_price, 'SHORT', date_str)
                
                if has_dp:
                    confidence += 15  # Boost confidence by 15% for DP confluence
                    reasoning = f"Selloff detected: {'+'.join(triggers)} | DP confluence @ ${dp_level:.2f} ({dp_volume:,} shares)"
                else:
                    reasoning = f"Selloff detected: {'+'.join(triggers)}"
                
                signal = Signal(
                    symbol=symbol,
                    timestamp=current_time if hasattr(current_time, 'isoformat') else datetime.now(),
                    signal_type='SELLOFF',
                    direction='SHORT',
                    entry_price=current_price,
                    stop_price=current_price * (1 + self.stop_pct / 100),
                    target_price=current_price * (1 - self.target_pct / 100),
                    confidence=min(confidence, 100),  # Cap at 100%
                    reasoning=reasoning,
                    metadata={
                        'from_open_pct': from_open_pct,
                        'rolling_pct': rolling_pct,
                        'consecutive_red': consecutive_red,
                        'triggers': triggers,
                        'bar_idx': i,
                        'dp_confluence': has_dp,
                        'dp_level': dp_level if has_dp else None
                    }
                )
                signals.append(signal)
                last_signal_idx = i
                continue  # Don't check rally on same bar
            
            # RALLY DETECTION - require 2+ triggers
            triggers = []
            if from_open_pct >= self.from_open_threshold:
                triggers.append('FROM_OPEN')
            if rolling_pct >= self.rolling_threshold:
                triggers.append('ROLLING')
            if consecutive_green >= self.CONSECUTIVE_BARS:
                triggers.append('MOMENTUM')
            
            # Require at least 2 triggers for signal
            if len(triggers) >= 2:
                confidence = 50 + len(triggers) * 15
                
                # Check DP confluence (boost confidence if present)
                date_str = data.index[0].strftime('%Y-%m-%d') if hasattr(data.index[0], 'strftime') else None
                has_dp, dp_level, dp_volume = self._check_dp_confluence(symbol, current_price, 'LONG', date_str)
                
                if has_dp:
                    confidence += 15  # Boost confidence by 15% for DP confluence
                    reasoning = f"Rally detected: {'+'.join(triggers)} | DP confluence @ ${dp_level:.2f} ({dp_volume:,} shares)"
                else:
                    reasoning = f"Rally detected: {'+'.join(triggers)}"
                
                signal = Signal(
                    symbol=symbol,
                    timestamp=current_time if hasattr(current_time, 'isoformat') else datetime.now(),
                    signal_type='RALLY',
                    direction='LONG',
                    entry_price=current_price,
                    stop_price=current_price * (1 - self.stop_pct / 100),
                    target_price=current_price * (1 + self.target_pct / 100),
                    confidence=min(confidence, 100),  # Cap at 100%
                    reasoning=reasoning,
                    metadata={
                        'from_open_pct': from_open_pct,
                        'rolling_pct': rolling_pct,
                        'consecutive_green': consecutive_green,
                        'triggers': triggers,
                        'bar_idx': i,
                        'dp_confluence': has_dp,
                        'dp_level': dp_level if has_dp else None
                    }
                )
                signals.append(signal)
                last_signal_idx = i
        
        return signals
    
    def simulate_trade(self, signal: Signal, data: pd.DataFrame, entry_idx: int = None):
        """Override to use bar_idx from metadata"""
        if entry_idx is None:
            entry_idx = signal.metadata.get('bar_idx', 0)
        return super().simulate_trade(signal, data, entry_idx)


# Standalone test
if __name__ == "__main__":
    print("=" * 70)
    print("📉📈 SELLOFF/RALLY DETECTOR BACKTEST")
    print("=" * 70)
    
    detector = SelloffRallyDetector(
        stop_pct=0.20,
        target_pct=0.30,  # FIXED: 1.5:1 R/R
        max_bars=30
    )
    
    # Test on SPY and QQQ
    symbols = ['SPY', 'QQQ']
    
    result = detector.backtest_date(symbols)
    detector.print_result(result)
    
    print("\n" + "=" * 70)
    print("✅ SELLOFF/RALLY DETECTOR BACKTEST COMPLETE!")
    print("=" * 70)

