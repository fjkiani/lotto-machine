"""
🚨 MOMENTUM DETECTOR

Detects rapid price moves (selloffs and rallies) regardless of battleground proximity.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


class MomentumDetector:
    """Detects real-time selloffs and rallies."""
    
    def __init__(self, signal_generator=None, institutional_engine=None):
        self.signal_generator = signal_generator
        self.institutional_engine = institutional_engine
    
    def check_selloffs(self, symbols: List[str]) -> List[dict]:
        """
        🚨 REAL-TIME SELLOFF DETECTION
        
        Detects rapid price drops with volume spikes (momentum-based).
        Threshold: -0.5% drop in 20 minutes with 1.5x volume spike
        """
        selloff_signals = []
        
        if not self.signal_generator:
            logger.debug("   ⚠️ SignalGenerator not available for selloff detection")
            return selloff_signals
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d', interval='1m')
                
                if hist.empty or len(hist) < 20:
                    continue
                
                # CRITICAL FIX: Pass FULL day data, not just last 30 minutes!
                # The selloff detection needs the day's open price, not just recent bars
                minute_bars = hist  # Use full day data
                current_price = float(minute_bars['Close'].iloc[-1])
                
                # Get institutional context
                inst_context = None
                if self.institutional_engine:
                    try:
                        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                        inst_context = self.institutional_engine.build_context(symbol, yesterday)
                    except Exception as e:
                        logger.debug(f"   ⚠️ Could not build institutional context for selloff: {e}")
                
                # Check for selloff
                selloff_signal = self.signal_generator._detect_realtime_selloff(
                    symbol=symbol,
                    current_price=current_price,
                    minute_bars=minute_bars,
                    context=inst_context
                )
                
                if selloff_signal:
                    selloff_signals.append({
                        'symbol': symbol,
                        'signal': selloff_signal,
                        'current_price': current_price
                    })
                    logger.warning(f"   🚨 SELLOFF DETECTED: {symbol} @ ${current_price:.2f}")
                    
            except Exception as e:
                logger.debug(f"   ⚠️ Selloff check error for {symbol}: {e}")
                continue
        
        return selloff_signals
    
    def check_rallies(self, symbols: List[str]) -> List[dict]:
        """
        🚀 REAL-TIME RALLY DETECTION (Counterpart to selloff)
        
        Detects rapid price rises with volume spikes (momentum-based).
        Threshold: +0.5% gain in 20 minutes with 1.5x volume spike
        """
        rally_signals = []
        
        if not self.signal_generator:
            logger.debug("   ⚠️ SignalGenerator not available for rally detection")
            return rally_signals
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d', interval='1m')
                
                if hist.empty or len(hist) < 20:
                    continue
                
                # CRITICAL FIX: Pass FULL day data, not just last 30 minutes!
                # The rally detection needs the day's open price, not just recent bars
                minute_bars = hist  # Use full day data
                current_price = float(minute_bars['Close'].iloc[-1])
                
                # Get institutional context
                inst_context = None
                if self.institutional_engine:
                    try:
                        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                        inst_context = self.institutional_engine.build_context(symbol, yesterday)
                    except Exception as e:
                        logger.debug(f"   ⚠️ Could not build institutional context for rally: {e}")
                
                # Check for rally
                rally_signal = self.signal_generator._detect_realtime_rally(
                    symbol=symbol,
                    current_price=current_price,
                    minute_bars=minute_bars,
                    context=inst_context
                )
                
                if rally_signal:
                    rally_signals.append({
                        'symbol': symbol,
                        'signal': rally_signal,
                        'current_price': current_price
                    })
                    logger.warning(f"   🚀 RALLY DETECTED: {symbol} @ ${current_price:.2f}")
                    
            except Exception as e:
                logger.debug(f"   ⚠️ Rally check error for {symbol}: {e}")
                continue
        
        return rally_signals

    def check_mean_reversion(self, symbols: List[str], threshold_pct: float = 0.75) -> List[dict]:
        """
        🔄 MEAN REVERSION DETECTION (backtested 65% WR at 0.75%, 71% at 1.0%)

        Fades rapid intraday moves: if SPY moves ≥threshold in 1 hour,
        bet on reversion. This REPLACES momentum continuation which
        proved sub-50% WR with negative P&L across all thresholds.

        Lookback: 4 x 15-min bars (1 hour).
        Direction: OPPOSITE of the move (fade).
        """
        signals = []

        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d', interval='15m')

                if hist.empty or len(hist) < 5:
                    continue

                # Last 4 bars = 1 hour lookback
                lookback = min(4, len(hist) - 1)
                start_price = float(hist['Open'].iloc[-lookback])
                current_price = float(hist['Close'].iloc[-1])
                move_pct = (current_price - start_price) / start_price * 100

                if abs(move_pct) < threshold_pct:
                    continue

                # FADE the move
                if move_pct > 0:
                    direction = "SHORT"
                    signal_type = "mean_reversion_fade_rally"
                else:
                    direction = "LONG"
                    signal_type = "mean_reversion_fade_selloff"

                # Volume confirmation (optional — edge exists without it)
                avg_vol = float(hist['Volume'].iloc[-lookback:].mean()) if 'Volume' in hist.columns else 0
                recent_vol = float(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0
                vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

                signals.append({
                    'symbol': symbol,
                    'direction': direction,
                    'signal_type': signal_type,
                    'move_pct': round(move_pct, 3),
                    'current_price': current_price,
                    'volume_ratio': round(vol_ratio, 2),
                    'threshold': threshold_pct,
                    'confidence': min(95, 60 + abs(move_pct) * 15),  # bigger move = more confidence
                })
                logger.warning(
                    f"   🔄 MEAN REVERSION: {symbol} {direction} | "
                    f"move={move_pct:+.2f}% in 1h | fade @ ${current_price:.2f}"
                )

            except Exception as e:
                logger.debug(f"   ⚠️ Mean reversion check error for {symbol}: {e}")
                continue

        return signals

