#!/usr/bin/env python3
"""
VOLATILITY EXPANSION DETECTOR - Modular IV Compression → Expansion Component

This module detects:
- IV compression (calm before storm)
- IV expansion (volatility spike starting)
- Lottery potential (HIGH/MEDIUM/LOW)

COMPONENT-BASED ARCHITECTURE:
- Pure logic, no side effects
- Takes symbol + lookback → returns expansion status
- Can be easily tested, improved, or replaced
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import logging

import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VolatilityExpansionStatus:
    """
    Volatility expansion detection result.

    NOTE: Field names are IV-oriented for backwards compatibility, but in this
    implementation they are computed from REALIZED INTRADAY VOLATILITY
    (1-minute returns) instead of options IV to avoid rate limits.
    """
    symbol: str
    status: str  # 'VOLATILITY_EXPANSION', 'COMPRESSION', 'NORMAL'
    lottery_potential: str  # 'HIGH', 'MEDIUM', 'LOW'
    current_iv: float       # actually: current realized volatility
    avg_iv: float           # actually: average realized volatility
    iv_spike_pct: float     # % increase from average realized vol
    bb_width: float
    bb_width_ratio: float  # Current width / 20-period average
    compression_detected: bool
    expansion_detected: bool
    timestamp: datetime
    reason: str


class VolatilityExpansionDetector:
    """
    Modular volatility expansion detector component
    
    Detects IV compression → expansion transitions (lottery setups)
    
    This is a PURE component - no state, no side effects.
    Takes inputs → returns outputs.
    Easy to test, improve, or replace.
    """
    
    def __init__(
        self,
        compression_threshold: float = 0.5,
        expansion_threshold: float = 1.2,
        high_expansion_threshold: float = 1.5,
        lookback_periods: int = 20,
        cache_dir: str = "cache/iv_history",
    ):
        """
        Initialize volatility expansion detector with caching
        
        Args:
            compression_threshold: BB width < this * average = compression (0.5 = 50%)
            expansion_threshold: Current IV > this * average = expansion (1.2 = 20% spike)
            high_expansion_threshold: Current IV > this * average = HIGH lottery (1.5 = 50% spike)
            lookback_periods: Periods for moving average (20)
            cache_dir: Directory for IV history cache
        """
        self.compression_threshold = compression_threshold
        self.expansion_threshold = expansion_threshold
        self.high_expansion_threshold = high_expansion_threshold
        self.lookback_periods = lookback_periods

        # Cache dir kept for backwards compatibility (not used in realized-vol mode)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info("📊 Volatility Expansion Detector initialized")
        logger.info(f"   Compression threshold: {compression_threshold:.0%}")
        logger.info(f"   Expansion threshold: {expansion_threshold:.0%}")
        logger.info(f"   High expansion threshold: {high_expansion_threshold:.0%}")
        logger.info(f"   Cache directory: {cache_dir}")
    
    def detect_expansion(
        self,
        symbol: str,
        minute_bars: pd.DataFrame,
        lookback_minutes: int = 30,
    ) -> Optional[VolatilityExpansionStatus]:
        """
        Detect volatility compression → expansion (lottery setup)
        
        This is the MAIN entry point for the component.
        
        Args:
            symbol: Ticker symbol (e.g., 'SPY')
            minute_bars: DataFrame with recent 1-minute bars (Open, High, Low, Close, Volume)
            lookback_minutes: How many minutes to look back (30)
        
        Returns:
            VolatilityExpansionStatus or None if error
        """
        try:
            # Use realized volatility from minute bars instead of options IV
            if minute_bars is None or len(minute_bars) < self.lookback_periods + 5:
                logger.warning(f"Insufficient minute bars for realized volatility for {symbol}")
                return None

            # Use last N minutes window
            window = minute_bars.tail(lookback_minutes)

            # Compute 1-minute log returns
            closes = window["Close"].astype(float)
            returns = np.log(closes).diff().dropna()
            if returns.empty:
                logger.warning(f"No returns for realized volatility for {symbol}")
                return None

            # Realized vol proxy: rolling std of returns
            iv_history = returns.rolling(window=5, min_periods=5).std().dropna()

            if iv_history is None or len(iv_history) < self.lookback_periods:
                logger.warning(f"Insufficient realized vol history for {symbol}")
                return None

            # Calculate Bollinger Band width (volatility measure)
            bb_width = self._calculate_bb_width(iv_history)
            
            if bb_width is None or len(bb_width) < self.lookback_periods:
                logger.warning(f"Insufficient data for BB width calculation")
                return None
            
            # Check for compression
            current_bb_width = bb_width.iloc[-1]
            avg_bb_width = bb_width.rolling(self.lookback_periods).mean().iloc[-1]
            bb_width_ratio = current_bb_width / avg_bb_width if avg_bb_width > 0 else 1.0
            compression_detected = bb_width_ratio < self.compression_threshold
            
            # Check for expansion
            current_iv = float(iv_history.iloc[-1])
            # Use last 5 periods as "recent average" (exclude current)
            if len(iv_history) > 5:
                avg_iv = float(iv_history.iloc[:-5].tail(self.lookback_periods).mean())
            else:
                avg_iv = float(iv_history.mean())
            iv_spike_pct = ((current_iv / avg_iv) - 1.0) * 100 if avg_iv > 0 else 0.0
            expansion_detected = current_iv > (avg_iv * self.expansion_threshold)
            
            # Determine status
            if compression_detected and expansion_detected:
                status = 'VOLATILITY_EXPANSION'
                # Determine lottery potential
                if current_iv > (avg_iv * self.high_expansion_threshold):
                    lottery_potential = 'HIGH'
                    reason = f"IV spike {iv_spike_pct:.1f}% (HIGH expansion from compression)"
                else:
                    lottery_potential = 'MEDIUM'
                    reason = f"IV spike {iv_spike_pct:.1f}% (MEDIUM expansion from compression)"
            elif compression_detected:
                status = 'COMPRESSION'
                lottery_potential = 'MEDIUM'
                reason = f"IV compression detected (BB width {bb_width_ratio:.0%} of average)"
            else:
                status = 'NORMAL'
                lottery_potential = 'LOW'
                reason = f"Normal volatility (IV: {current_iv:.0%}, BB width: {bb_width_ratio:.0%})"
            
            return VolatilityExpansionStatus(
                symbol=symbol,
                status=status,
                lottery_potential=lottery_potential,
                current_iv=current_iv,
                avg_iv=avg_iv,
                iv_spike_pct=iv_spike_pct,
                bb_width=current_bb_width,
                bb_width_ratio=bb_width_ratio,
                compression_detected=compression_detected,
                expansion_detected=expansion_detected,
                timestamp=datetime.now(),
                reason=reason
            )
            
        except Exception as e:
            logger.error(f"Error detecting volatility expansion for {symbol}: {e}")
            return None
    
    def _calculate_bb_width(self, iv_history: pd.Series) -> Optional[pd.Series]:
        """
        Calculate Bollinger Band width from IV history
        
        BB width = (Upper Band - Lower Band) / Middle Band
        
        Args:
            iv_history: Series of IV values
        
        Returns:
            Series of BB widths or None
        """
        try:
            if len(iv_history) < self.lookback_periods:
                return None
            
            # Calculate moving average
            ma = iv_history.rolling(self.lookback_periods).mean()
            
            # Calculate standard deviation
            std = iv_history.rolling(self.lookback_periods).std()
            
            # Bollinger Bands
            upper_band = ma + (2 * std)
            lower_band = ma - (2 * std)
            
            # BB Width = (Upper - Lower) / Middle
            bb_width = (upper_band - lower_band) / ma
            
            return bb_width
            
        except Exception as e:
            logger.error(f"Error calculating BB width: {e}")
            return None

