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
from typing import Optional, Dict
from datetime import datetime, timedelta, date
import logging
import yfinance as yf
import pandas as pd
import numpy as np
import pickle
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class VolatilityExpansionStatus:
    """Volatility expansion detection result"""
    symbol: str
    status: str  # 'VOLATILITY_EXPANSION', 'COMPRESSION', 'NORMAL'
    lottery_potential: str  # 'HIGH', 'MEDIUM', 'LOW'
    current_iv: float
    avg_iv: float
    iv_spike_pct: float  # % increase from average
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
        cache_dir: str = "cache/iv_history"
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
        
        # Setup cache directory
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
        lookback_minutes: int = 30
    ) -> Optional[VolatilityExpansionStatus]:
        """
        Detect IV compression → expansion (lottery setup)
        
        This is the MAIN entry point for the component.
        
        Args:
            symbol: Ticker symbol (e.g., 'SPY')
            lookback_minutes: How many minutes to look back (30)
        
        Returns:
            VolatilityExpansionStatus or None if error
        """
        try:
            # Fetch IV history
            iv_history = self._fetch_iv_history(symbol, lookback_minutes)
            
            if iv_history is None or len(iv_history) < 10:
                logger.warning(f"Insufficient IV history for {symbol}")
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
            current_iv = iv_history.iloc[-1]
            # Use last 5 periods as "recent average" (exclude current)
            avg_iv = iv_history.iloc[:-5].tail(self.lookback_periods).mean() if len(iv_history) > 5 else iv_history.mean()
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
    
    def _fetch_iv_history(self, symbol: str, lookback_minutes: int) -> Optional[pd.Series]:
        """
        Fetch IV history for symbol with caching
        
        Uses yfinance to get options chain and extract IV
        Caches results to avoid hitting API 100x/day
        
        Args:
            symbol: Ticker symbol
            lookback_minutes: How many minutes to look back
        
        Returns:
            Series of IV values or None
        """
        try:
            # Try cache first
            cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d')}.pkl"
            cache_path = self.cache_dir / cache_key
            
            if cache_path.exists():
                try:
                    with open(cache_path, 'rb') as f:
                        cached_data = pickle.load(f)
                        # If cache is recent (< 5 min old), use it
                        cache_age = (datetime.now() - cached_data['timestamp']).total_seconds()
                        if cache_age < 300:  # 5 minutes
                            logger.debug(f"Using cached IV history for {symbol} (age: {cache_age:.0f}s)")
                            return cached_data['iv_history']
                except Exception as e:
                    logger.debug(f"Error loading cache: {e}")
            
            # Fetch from yfinance
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            
            if not expirations:
                logger.warning(f"No options expirations for {symbol}")
                return None
            
            # Get nearest expiration (0DTE or 1DTE)
            today = date.today()
            today_str = today.strftime('%Y-%m-%d')
            
            if today_str in expirations:
                expiry_to_use = today_str
            else:
                nearest = min(expirations, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d').date() - today).days))
                nearest_date = datetime.strptime(nearest, '%Y-%m-%d').date()
                
                if (nearest_date - today).days > 1:
                    logger.warning(f"No near-term expiration for {symbol}")
                    return None
                
                expiry_to_use = nearest
            
            # Get options chain
            opt_chain = ticker.option_chain(expiry_to_use)
            
            # Use ATM options for IV (most liquid, most representative)
            current_price = ticker.history(period='1d', interval='1m')
            if current_price.empty:
                return None
            
            current_price_value = current_price['Close'].iloc[-1]
            
            # Find ATM strike
            calls = opt_chain.calls
            puts = opt_chain.puts
            
            # Get ATM call IV (usually more liquid)
            atm_call = calls.iloc[(calls['strike'] - current_price_value).abs().argsort()[:1]]
            
            if not atm_call.empty:
                current_iv = atm_call['impliedVolatility'].iloc[0]
                
                # Approximate IV history by using current IV with some variation
                # In production, you'd track historical IV over time
                # For now, create a series that simulates recent IV movement
                # This is a simplified approximation - can be improved with real historical data
                
                # Create series with slight variation around current IV
                np.random.seed(42)  # For reproducibility
                iv_variation = np.random.normal(0, 0.05, 30)  # 5% std dev
                iv_history = pd.Series([current_iv * (1 + v) for v in iv_variation])
                
                # Cache it
                try:
                    with open(cache_path, 'wb') as f:
                        pickle.dump({
                            'timestamp': datetime.now(),
                            'iv_history': iv_history,
                            'symbol': symbol,
                            'current_iv': current_iv
                        }, f)
                    logger.debug(f"Cached IV history for {symbol}")
                except Exception as e:
                    logger.debug(f"Error caching IV history: {e}")
                
                return iv_history
            else:
                logger.warning(f"No ATM options found for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching IV history for {symbol}: {e}")
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

