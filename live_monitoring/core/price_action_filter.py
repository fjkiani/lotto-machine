#!/usr/bin/env python3
"""
PRICE ACTION FILTER - Real-Time Price Confirmation
==================================================
Confirms signals with actual price action:
- Waits for price to test DP level
- Confirms with volume spike + candlestick pattern
- Regime check (time of day + VIX + trend)
- Entry only if price < 0.5% from ideal entry

Author: Alpha's AI Hedge Fund
Date: 2025-01-XX
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime, time as dt_time
import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PriceActionConfirmation:
    """Price action confirmation result"""
    confirmed: bool
    reason: str
    current_price: float
    distance_from_entry_pct: float
    volume_spike: bool
    candlestick_pattern: str
    regime: str
    vix_level: float


class PriceActionFilter:
    """Filters signals based on real-time price action"""
    
    def __init__(self):
        self.vix_cache = None
        self.vix_cache_time = None
        logger.info("📊 Price Action Filter initialized")
    
    def confirm_signal(self, signal, lookback_minutes: int = 30) -> PriceActionConfirmation:
        """
        Confirm signal with real-time price action
        
        Args:
            signal: LiveSignal object
            lookback_minutes: Minutes of price history to analyze
        
        Returns:
            PriceActionConfirmation with confirmation status
        """
        try:
            # Get recent price data
            ticker = yf.Ticker(signal.symbol)
            hist = ticker.history(period='1d', interval='1m')
            
            if hist.empty or len(hist) < 5:
                return PriceActionConfirmation(
                    confirmed=False,
                    reason="Insufficient price data",
                    current_price=getattr(signal, "entry_price", 0.0),
                    distance_from_entry_pct=0.0,
                    volume_spike=False,
                    candlestick_pattern="UNKNOWN",
                    regime="UNKNOWN",
                    vix_level=0.0
                )
            
            current_price = float(hist['Close'].iloc[-1])
            distance_pct = abs(current_price - signal.entry_price) / signal.entry_price
            
            # Check 1: Price proximity (must be within 0.5% of ideal entry)
            if distance_pct > 0.005:
                return PriceActionConfirmation(
                    confirmed=False,
                    reason=f"Price {distance_pct:.2%} away from entry (max 0.5%)",
                    current_price=current_price,
                    distance_from_entry_pct=distance_pct,
                    volume_spike=False,
                    candlestick_pattern="UNKNOWN",
                    regime="UNKNOWN",
                    vix_level=0.0
                )
            
            # Check 2: Volume spike
            recent_volume = hist['Volume'].tail(lookback_minutes)
            avg_volume = recent_volume.mean()
            current_volume = recent_volume.iloc[-1]
            volume_spike = current_volume > (avg_volume * 1.5)
            
            # Check 3: Candlestick pattern
            recent_candles = hist.tail(5)
            # Normalize action to string ('BUY' / 'SELL')
            action_str = signal.action.value if hasattr(signal.action, "value") else str(signal.action)
            pattern = self._detect_candlestick_pattern(recent_candles, action_str)
            
            # Check 4: Regime
            regime = self._detect_regime(hist, signal.symbol)
            
            # Check 5: VIX level
            vix_level = self._get_vix_level()
            
            # Final confirmation
            if action_str == 'BUY':
                pattern_ok = pattern in ['BULLISH', 'STRONG_BULLISH']
            else:
                pattern_ok = pattern in ['BEARISH', 'STRONG_BEARISH']

            confirmed = (
                distance_pct <= 0.005 and
                volume_spike and
                pattern_ok
            )
            
            reason = "Confirmed" if confirmed else f"Failed: pattern={pattern}, volume_spike={volume_spike}"
            
            return PriceActionConfirmation(
                confirmed=confirmed,
                reason=reason,
                current_price=current_price,
                distance_from_entry_pct=distance_pct,
                volume_spike=volume_spike,
                candlestick_pattern=pattern,
                regime=regime,
                vix_level=vix_level
            )
            
        except Exception as e:
            logger.error(f"Error confirming price action: {e}")
            return PriceActionConfirmation(
                confirmed=False,
                reason=f"Error: {e}",
                current_price=getattr(signal, "entry_price", 0.0),
                distance_from_entry_pct=0.0,
                volume_spike=False,
                candlestick_pattern="ERROR",
                regime="ERROR",
                vix_level=0.0
            )
    
    def _detect_candlestick_pattern(self, candles: pd.DataFrame, action: str) -> str:
        """Detect candlestick pattern"""
        if len(candles) < 3:
            return "UNKNOWN"
        
        last = candles.iloc[-1]
        prev = candles.iloc[-2]
        
        body = abs(last['Close'] - last['Open'])
        range_size = last['High'] - last['Low']
        
        # Strong bullish
        if action == 'BUY':
            if last['Close'] > last['Open'] and body > range_size * 0.7:
                return "STRONG_BULLISH"
            elif last['Close'] > last['Open']:
                return "BULLISH"
            elif last['Close'] < last['Open']:
                return "BEARISH"
        
        # Strong bearish
        else:  # SELL
            if last['Close'] < last['Open'] and body > range_size * 0.7:
                return "STRONG_BEARISH"
            elif last['Close'] < last['Open']:
                return "BEARISH"
            elif last['Close'] > last['Open']:
                return "BULLISH"
        
        return "NEUTRAL"
    
    def _detect_regime(self, hist: pd.DataFrame, symbol: str) -> str:
        """Detect intraday regime"""
        if len(hist) < 20:
            return "UNKNOWN"
        
        now = datetime.now()
        current_time = now.time()
        
        # Time-based regime
        if dt_time(9, 30) <= current_time < dt_time(11, 0):
            time_regime = "MORNING_BREAKOUT"
        elif dt_time(11, 0) <= current_time < dt_time(14, 0):
            time_regime = "MIDDAY_CHOP"
        elif dt_time(14, 0) <= current_time < dt_time(16, 0):
            time_regime = "AFTERNOON_FADE"
        else:
            time_regime = "UNKNOWN"
        
        # Price trend
        recent_prices = hist['Close'].tail(20)
        trend = (recent_prices.iloc[-1] - recent_prices.iloc[0]) / recent_prices.iloc[0]
        
        if trend > 0.005:
            trend_regime = "UPTREND"
        elif trend < -0.005:
            trend_regime = "DOWNTREND"
        else:
            trend_regime = "CHOP"
        
        return f"{time_regime}_{trend_regime}"
    
    def _get_vix_level(self) -> float:
        """Get current VIX level (cached for 5 minutes)"""
        try:
            now = datetime.now()
            if self.vix_cache and self.vix_cache_time:
                if (now - self.vix_cache_time).total_seconds() < 300:  # 5 min cache
                    return self.vix_cache
            
            vix = yf.Ticker("^VIX")
            hist = vix.history(period='1d', interval='1m')
            if not hist.empty:
                vix_level = float(hist['Close'].iloc[-1])
                self.vix_cache = vix_level
                self.vix_cache_time = now
                return vix_level
        except Exception as e:
            logger.debug(f"Error fetching VIX: {e}")
        
        return 20.0  # Default neutral VIX

