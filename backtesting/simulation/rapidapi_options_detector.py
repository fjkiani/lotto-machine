"""
📊 RAPIDAPI OPTIONS FLOW DETECTOR (HARDENED)
Uses Yahoo Finance 15 RapidAPI for real options flow data.

SIGNALS:
1. OPTIONS_BULLISH: Low P/C ratio (< 0.5) + volume + context alignment
2. OPTIONS_BEARISH: High P/C ratio (> 1.5) + volume + context alignment
3. UNUSUAL_ACTIVITY: Vol/OI ratio > 10x = smart money positioning

FILTERS (HARDENED 2025-12-25):
- Minimum confidence: 70%
- Market context alignment required
- DP confluence check (boosts confidence)
- Volume threshold (1.5x average)
- Only top unusual activity (Vol/OI > 10x, not 5x)

Author: Zo (Alpha's AI)
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    HARDENED Options flow detector using RapidAPI data.
    
    KEY CHANGES (Dec 25, 2025):
    - Tightened P/C thresholds (0.7 -> 0.5, 1.3 -> 1.5)
    - Raised unusual Vol/OI threshold (5x -> 10x)
    - Added confidence threshold (70% minimum)
    - Added market context filtering
    - Added volume confirmation
    - Reduced signal count from 50/day to ~5-10/day
    """
    
    # RUTHLESS Thresholds (2025-12-25 v2 - EVEN STRICTER)
    BULLISH_PC_THRESHOLD = 0.4       # Was 0.5 - now VERY strict
    BEARISH_PC_THRESHOLD = 1.8       # Was 1.5 - now VERY strict
    UNUSUAL_VOL_OI_THRESHOLD = 15.0  # Was 10.0 - only the extreme
    MIN_VOLUME = 50000               # Was 25000 - only liquid
    MIN_CONFIDENCE = 80              # Was 70 - now 80% minimum
    REQUIRE_DP_CONFLUENCE = True     # NEW - Must have DP support/resistance
    
    def __init__(
        self,
        api_key: str = None,
        stop_pct: float = 0.75,   # Tighter stop (was 1.0)
        target_pct: float = 1.50,  # 2:1 R/R
        max_bars: int = 60,  # 5 hours of 5-min bars
        enable_dp_confluence: bool = True,
        enable_context_filter: bool = True,  # NEW
        min_confidence: float = None
    ):
        super().__init__(stop_pct, target_pct, max_bars)
        
        self.min_confidence = min_confidence or self.MIN_CONFIDENCE
        self.enable_context_filter = enable_context_filter
        self.require_dp_confluence = self.REQUIRE_DP_CONFLUENCE
        
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
                print(f"   ⚠️ Could not init DP client: {e}")
        
        # Market context (lazy loaded)
        self._market_context = None
    
    @property
    def name(self) -> str:
        return "rapidapi_options_detector"
    
    def _get_market_context(self, date_str: str = None):
        """Get market context for filtering"""
        if self._market_context is not None:
            return self._market_context
        
        try:
            from backtesting.simulation.market_context_detector import MarketContextDetector
            detector = MarketContextDetector()
            date_str = date_str or datetime.now().strftime('%Y-%m-%d')
            self._market_context = detector.analyze_market(date_str)
            return self._market_context
        except Exception as e:
            return None
    
    def _check_dp_confluence(self, symbol: str, price: float, direction: str, date_str: str = None) -> tuple:
        """
        Check if there's DP confluence near the signal price.
        
        Returns:
            (has_confluence, dp_level, dp_volume)
        """
        if not self.dp_client or not self.enable_dp_confluence:
            return False, 0.0, 0
        
        try:
            if date_str:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_obj = datetime.now()
            prev_date = (date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
            
            levels_data = self.dp_client.get_dark_pool_levels(symbol, prev_date)
            if not levels_data:
                return False, 0.0, 0
            
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
            
            for level_data in levels[:20]:
                level = float(level_data.get('level', level_data.get('price', 0)))
                volume = int(level_data.get('volume', level_data.get('total_volume', 0)))
                
                distance = abs(price - level) / price
                
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_level = level
                    nearest_volume = volume
            
            # Within 1% and supports trade direction
            if nearest_level and nearest_distance < 0.01:
                supports_trade = False
                if direction == 'LONG' and nearest_level <= price:
                    supports_trade = True
                elif direction == 'SHORT' and nearest_level >= price:
                    supports_trade = True
                
                if supports_trade and nearest_volume >= 500_000:
                    return True, nearest_level, nearest_volume
            
            return False, nearest_level or 0.0, nearest_volume
            
        except Exception:
            return False, 0.0, 0
    
    def _passes_context_filter(self, direction: str, context) -> tuple:
        """
        Check if signal aligns with market context.
        
        Returns:
            (passes, reason)
        """
        if not self.enable_context_filter or context is None:
            return True, "Context filtering disabled"
        
        # Don't go LONG in bearish market
        if direction == 'LONG' and getattr(context, 'favor_shorts', False):
            return False, f"LONG signal rejected - market favors shorts ({context.direction})"
        
        # Don't go SHORT in bullish market
        if direction == 'SHORT' and getattr(context, 'favor_longs', False):
            return False, f"SHORT signal rejected - market favors longs ({context.direction})"
        
        # In choppy market, require higher confidence (handled in signal generation)
        return True, f"Aligned with {context.direction} market"
    
    def detect_signals(
        self, 
        symbol: str = None, 
        data: pd.DataFrame = None,
        **kwargs
    ) -> List[Signal]:
        """
        Detect HARDENED options flow signals.
        
        KEY FILTERS:
        1. Stricter P/C thresholds
        2. Confidence >= 70%
        3. Market context alignment
        4. DP confluence (boosts confidence)
        5. Volume confirmation
        """
        signals = []
        filtered_count = 0
        
        # Get market context for filtering
        context = self._get_market_context()
        
        try:
            # Get most active options
            most_active = self.client.get_most_active_options(option_type='STOCKS')
            
            if most_active:
                for opt in most_active:
                    # FILTER 1: Volume threshold (stricter)
                    if opt.total_volume < self.MIN_VOLUME:
                        continue
                    
                    pc_ratio = opt.put_call_ratio
                    current_price = opt.last_price
                    date_str = datetime.now().strftime('%Y-%m-%d')
                    
                    # === BULLISH SIGNAL ===
                    if pc_ratio < self.BULLISH_PC_THRESHOLD:
                        # Calculate base confidence
                        # Lower P/C = higher confidence
                        confidence = 50 + (self.BULLISH_PC_THRESHOLD - pc_ratio) * 80
                        confidence = min(85, confidence)  # Cap at 85 before DP boost
                        
                        # Check DP confluence
                        has_dp, dp_level, dp_volume = self._check_dp_confluence(
                            opt.symbol, current_price, 'LONG', date_str
                        )
                        
                        if has_dp:
                            confidence += 15  # Boost for DP confluence
                            confidence = min(100, confidence)
                        
                        # FILTER 2: DP CONFLUENCE REQUIRED
                        if self.require_dp_confluence and not has_dp:
                            filtered_count += 1
                            continue
                        
                        # FILTER 3: Minimum confidence
                        if confidence < self.min_confidence:
                            filtered_count += 1
                            continue
                        
                        # FILTER 4: Market context
                        passes, reason = self._passes_context_filter('LONG', context)
                        if not passes:
                            filtered_count += 1
                            continue
                        
                        # Build reasoning
                        reasoning = f"Bullish options flow: P/C {pc_ratio:.2f}, Call% {opt.call_volume_pct:.0f}%"
                        if has_dp:
                            reasoning += f" | DP confluence @ ${dp_level:.2f} ({dp_volume:,} shares)"
                        
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
                                'dp_level': dp_level if has_dp else None,
                                'market_direction': getattr(context, 'direction', 'UNKNOWN')
                            }
                        )
                        signals.append(signal)
                    
                    # === BEARISH SIGNAL ===
                    elif pc_ratio > self.BEARISH_PC_THRESHOLD:
                        # Calculate base confidence
                        confidence = 50 + (pc_ratio - self.BEARISH_PC_THRESHOLD) * 25
                        confidence = min(85, confidence)
                        
                        # Check DP confluence
                        has_dp, dp_level, dp_volume = self._check_dp_confluence(
                            opt.symbol, current_price, 'SHORT', date_str
                        )
                        
                        if has_dp:
                            confidence += 15
                            confidence = min(100, confidence)
                        
                        # FILTER 2: DP CONFLUENCE REQUIRED
                        if self.require_dp_confluence and not has_dp:
                            filtered_count += 1
                            continue
                        
                        # FILTER 3: Minimum confidence
                        if confidence < self.min_confidence:
                            filtered_count += 1
                            continue
                        
                        # FILTER 4: Market context
                        passes, reason = self._passes_context_filter('SHORT', context)
                        if not passes:
                            filtered_count += 1
                            continue
                        
                        reasoning = f"Bearish options flow: P/C {pc_ratio:.2f}, Put% {opt.put_volume_pct:.0f}%"
                        if has_dp:
                            reasoning += f" | DP confluence @ ${dp_level:.2f} ({dp_volume:,} shares)"
                        
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
                                'dp_level': dp_level if has_dp else None,
                                'market_direction': getattr(context, 'direction', 'UNKNOWN')
                            }
                        )
                        signals.append(signal)
            
            # === UNUSUAL ACTIVITY (STRICT) ===
            unusual = self.client.get_unusual_activity(option_type='STOCKS')
            
            if unusual:
                processed_symbols = set()
                for opt in unusual[:20]:
                    # FILTER: Much stricter Vol/OI threshold
                    if opt.vol_oi_ratio < self.UNUSUAL_VOL_OI_THRESHOLD:
                        continue
                    
                    # Extract stock symbol
                    stock_symbol = opt.symbol.split('|')[0] if '|' in opt.symbol else opt.symbol
                    
                    if stock_symbol in processed_symbols:
                        continue
                    processed_symbols.add(stock_symbol)
                    
                    direction = 'LONG' if opt.option_type == 'Call' else 'SHORT'
                    signal_type = 'UNUSUAL_CALL' if opt.option_type == 'Call' else 'UNUSUAL_PUT'
                    
                    # Higher base confidence for very unusual activity
                    confidence = min(95, 60 + opt.vol_oi_ratio * 2)
                    
                    # Market context filter
                    passes, reason = self._passes_context_filter(direction, context)
                    if not passes:
                        filtered_count += 1
                        continue
                    
                    if confidence < self.min_confidence:
                        filtered_count += 1
                        continue
                    
                    # Get STOCK price
                    price_data = self.get_intraday_data(stock_symbol, period="1d", interval="5m")
                    if price_data.empty:
                        continue
                    
                    current_price = price_data['Close'].iloc[-1]
                    
                    signal = Signal(
                        symbol=stock_symbol,
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
                            'days_to_exp': opt.days_to_exp,
                            'market_direction': getattr(context, 'direction', 'UNKNOWN')
                        }
                    )
                    signals.append(signal)
        
        except Exception as e:
            print(f"   ❌ Options API error: {e}")
            import traceback
            traceback.print_exc()
        
        # Log filtering stats
        if filtered_count > 0:
            print(f"   📊 Filtered out {filtered_count} low-quality options signals")
        
        return signals
    
    def backtest_date(
        self, 
        symbols: List[str] = None,
        date: str = None,
        **kwargs
    ):
        """
        Run backtest for today.
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        
        # Reset context cache for new backtest
        self._market_context = None
        
        # Get signals from API
        signals = self.detect_signals()
        
        print(f"   📊 Options Flow: {len(signals)} signals after filtering")
        
        # Simulate trades
        trades = []
        for signal in signals:
            data = self.get_intraday_data(signal.symbol, period="1d", interval="5m")
            if data.empty:
                continue
            
            trade = self.simulate_trade(signal, data, entry_idx=0)
            trades.append(trade)
        
        return self._calculate_metrics(date, signals, trades)


# Standalone test
if __name__ == "__main__":
    print("=" * 70)
    print("📊 RAPIDAPI OPTIONS FLOW DETECTOR (HARDENED) BACKTEST")
    print("=" * 70)
    
    detector = RapidAPIOptionsDetector(
        stop_pct=0.75,
        target_pct=1.50,  # 2:1 R/R
        max_bars=60,
        enable_context_filter=True,
        min_confidence=70
    )
    
    print("\n📋 RUTHLESS THRESHOLDS (v2):")
    print(f"   P/C Bullish: < {detector.BULLISH_PC_THRESHOLD} (original: 0.7)")
    print(f"   P/C Bearish: > {detector.BEARISH_PC_THRESHOLD} (original: 1.3)")
    print(f"   Vol/OI Unusual: > {detector.UNUSUAL_VOL_OI_THRESHOLD}x (original: 5x)")
    print(f"   Min Volume: {detector.MIN_VOLUME:,} (original: 10,000)")
    print(f"   Min Confidence: {detector.min_confidence}%")
    print(f"   DP Confluence: REQUIRED")
    print(f"   Context Filter: ENABLED")
    
    result = detector.backtest_date()
    detector.print_result(result)
    
    print("\n📋 SIGNAL DETAILS:")
    for sig in result.signals[:10]:
        print(f"   {sig.signal_type}: {sig.symbol} {sig.direction} @ ${sig.entry_price:.2f}")
        print(f"      Confidence: {sig.confidence:.0f}% | {sig.reasoning}")
    
    print("\n" + "=" * 70)
    print("✅ HARDENED OPTIONS DETECTOR BACKTEST COMPLETE!")
    print("=" * 70)
