#!/usr/bin/env python3
"""
RISK MANAGER - Hard Risk Limits
================================
Enforces strict risk management rules:
- Position limits (max open, correlated, sector)
- Stop loss placement (exact distance from DP battlefield)
- Circuit breakers (daily drawdown limits)
- Position correlation tracking

Author: Alpha's AI Hedge Fund
Date: 2025-01-XX
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from datetime import datetime
import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position"""
    symbol: str
    entry_price: float
    stop_loss: float
    position_size_pct: float
    signal_type: str
    opened_at: datetime


@dataclass
class RiskLimits:
    """Hard risk limits"""
    max_position_size_pct: float = 0.02  # 2% per trade
    max_daily_drawdown_pct: float = 0.05  # 5% daily limit
    max_open_positions: int = 5  # Max simultaneous positions
    max_correlated_positions: int = 2  # Max correlated (e.g., SPY + QQQ)
    max_sector_exposure_pct: float = 0.40  # 40% max in one sector
    circuit_breaker_pnl_pct: float = -0.03  # -3% P&L = stop all trading
    stop_loss_buffer_atr_mult: float = 1.5  # Stop = DP edge + 1.5 * ATR
    min_stop_distance_pct: float = 0.005  # Minimum 0.5% from entry


class RiskManager:
    """Manages risk limits and position tracking"""
    
    def __init__(self, limits: RiskLimits = None, initial_capital: float = 100000.0):
        self.limits = limits or RiskLimits()
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.open_positions: List[Position] = []
        self.daily_pnl: float = 0.0
        self.daily_pnl_pct: float = 0.0
        self.circuit_breaker_triggered: bool = False
        
        # Track correlated symbols (SPY, QQQ, DIA are correlated)
        self.correlated_groups = [
            {'SPY', 'QQQ', 'DIA', 'IWM'},  # Major indices
            {'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN'},  # Tech
            {'NVDA', 'AMD', 'AVGO', 'TSM'},  # Semiconductors
        ]
        
        logger.info("🛡️  Risk Manager initialized")
        logger.info(f"   Initial capital: ${initial_capital:,.0f}")
        logger.info(f"   Max position: {self.limits.max_position_size_pct:.0%}")
        logger.info(f"   Max open: {self.limits.max_open_positions}")
        logger.info(f"   Max correlated: {self.limits.max_correlated_positions}")
        logger.info(f"   Circuit breaker: {self.limits.circuit_breaker_pnl_pct:.0%}")
    
    def get_current_account_value(self) -> float:
        """
        Calculate real-time account value
        
        Account value = initial capital + open positions value + daily P&L
        
        Returns:
            Current account value in dollars
        """
        # Calculate open positions value (simplified - assumes positions at entry price)
        # In production, you'd mark-to-market positions
        open_positions_value = sum(
            p.position_size_pct * self.initial_capital 
            for p in self.open_positions
        )
        
        # Account value = initial capital + P&L
        account_value = self.initial_capital + (self.daily_pnl_pct * self.initial_capital)
        
        return max(account_value, 0.0)  # Can't go negative
    
    def calculate_position_size(
        self, 
        signal,  # Union[LiveSignal, LotterySignal] - using Any for now to avoid import issues
        risk_pct: Optional[float] = None
    ) -> tuple[float, float]:
        """
        Calculate position size based on signal type and account value
        
        Regular signals: 2% risk
        Lottery signals: 0.5-1% risk (can lose 100%)
        
        Args:
            signal: LiveSignal or LotterySignal
            risk_pct: Optional override for risk percentage
        
        Returns:
            (position_size_pct, position_size_dollars)
        """
        account_value = self.get_current_account_value()
        
        # Determine if this is a lottery signal
        is_lottery = False
        try:
            # Check if signal has lottery-specific attributes
            if hasattr(signal, 'strike') and hasattr(signal, 'option_type'):
                is_lottery = True
            # Or check signal_type
            elif hasattr(signal, 'signal_type'):
                from lottery_signals import SignalType
                if SignalType.is_lottery(signal.signal_type):
                    is_lottery = True
        except:
            pass
        
        # Determine risk percentage
        if risk_pct is not None:
            # Use provided risk_pct
            pass
        elif is_lottery:
            # Lottery signals: smaller risk (0.5-1%)
            if signal.confidence > 0.85:
                risk_pct = 0.01  # 1% risk
            elif signal.confidence > 0.75:
                risk_pct = 0.005  # 0.5% risk
            else:
                risk_pct = 0.0  # Don't take <75% confidence on 0DTE
        else:
            # Regular signals: standard 2% risk
            risk_pct = self.limits.max_position_size_pct  # 0.02 (2%)
        
        if risk_pct <= 0:
            return 0.0, 0.0
        
        # Calculate max position value based on risk
        max_position_value = account_value * risk_pct
        
        # Calculate actual position size
        # Position size is the dollar amount we can risk, not the total position value
        # For lottery signals: position size = max risk (premium can go to zero)
        # For regular signals: position size = max risk / stop distance percentage
        
        if is_lottery:
            # For options, we risk the premium (can lose 100%)
            # Position size = max risk dollars (this is the premium we pay)
            premium = getattr(signal, 'entry_price', 0.0)
            if premium > 0:
                # How many contracts can we buy with max risk?
                max_contracts = int(max_position_value / premium)
                position_value = max_contracts * premium
                position_pct = (position_value / account_value) if account_value > 0 else 0.0
            else:
                position_pct = risk_pct  # Fallback
                position_value = max_position_value
        else:
            # Regular signals: position size based on stop distance
            # If stop is 1% away, we can risk 2% of account = 200% position size
            # But we cap at max_position_size_pct to avoid over-leveraging
            stop_distance_pct = abs(signal.entry_price - signal.stop_price) / signal.entry_price if signal.entry_price > 0 else 0.01
            
            if stop_distance_pct > 0:
                # Position size = risk_pct / stop_distance_pct
                # Example: 2% risk / 1% stop = 200% position (2x leverage)
                # But cap at max_position_size_pct to avoid over-leveraging
                calculated_pct = risk_pct / stop_distance_pct
                position_pct = min(calculated_pct, self.limits.max_position_size_pct)
                position_value = account_value * position_pct
            else:
                position_pct = risk_pct  # Fallback
                position_value = max_position_value
        
        return position_pct, position_value
    
    def can_open_position(self, symbol: str, position_size_pct: float) -> tuple[bool, str]:
        """
        Check if we can open a new position
        
        Returns:
            (can_open: bool, reason: str)
        """
        # Circuit breaker check
        if self.circuit_breaker_triggered:
            return False, "Circuit breaker triggered - trading halted"
        
        # Daily drawdown check
        if self.daily_pnl_pct <= self.limits.max_daily_drawdown_pct:
            return False, f"Daily drawdown limit reached: {self.daily_pnl_pct:.2%}"
        
        # Max open positions check
        if len(self.open_positions) >= self.limits.max_open_positions:
            return False, f"Max open positions reached: {len(self.open_positions)}/{self.limits.max_open_positions}"
        
        # Position size check
        if position_size_pct > self.limits.max_position_size_pct:
            return False, f"Position size {position_size_pct:.2%} exceeds limit {self.limits.max_position_size_pct:.2%}"
        
        # Correlated positions check
        correlated_count = self._count_correlated_positions(symbol)
        if correlated_count >= self.limits.max_correlated_positions:
            return False, f"Max correlated positions reached: {correlated_count}/{self.limits.max_correlated_positions}"
        
        # Sector exposure check
        sector_exposure = self._calculate_sector_exposure(symbol, position_size_pct)
        if sector_exposure > self.limits.max_sector_exposure_pct:
            return False, f"Sector exposure {sector_exposure:.2%} exceeds limit {self.limits.max_sector_exposure_pct:.2%}"
        
        return True, "OK"
    
    def calculate_stop_loss(self, entry_price: float, dp_battlefield_level: float, 
                           symbol: str, lookback_days: int = 14) -> float:
        """
        Calculate stop loss: DP battlefield edge + (1.5 * ATR)
        
        Args:
            entry_price: Entry price
            dp_battlefield_level: Nearest DP battleground level
            symbol: Ticker symbol
            lookback_days: Days for ATR calculation
        
        Returns:
            Stop loss price
        """
        try:
            # Calculate ATR
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f'{lookback_days}d', interval='1d')
            
            if hist.empty or len(hist) < 2:
                # Fallback: use 0.5% minimum
                atr = entry_price * 0.005
            else:
                # Calculate True Range
                high_low = hist['High'] - hist['Low']
                high_close = (hist['High'] - hist['Close'].shift()).abs()
                low_close = (hist['Low'] - hist['Close'].shift()).abs()
                
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr = tr.rolling(window=min(14, len(tr))).mean().iloc[-1]
            
            # Stop = DP battlefield edge + (1.5 * ATR)
            if entry_price > dp_battlefield_level:  # Above battlefield
                stop = dp_battlefield_level - (self.limits.stop_loss_buffer_atr_mult * atr)
            else:  # Below battlefield
                stop = dp_battlefield_level + (self.limits.stop_loss_buffer_atr_mult * atr)
            
            # Ensure minimum distance
            min_stop = entry_price * (1 - self.limits.min_stop_distance_pct) if entry_price > dp_battlefield_level else entry_price * (1 + self.limits.min_stop_distance_pct)
            
            if entry_price > dp_battlefield_level:
                stop = min(stop, min_stop)  # Stop can't be higher than entry - min distance
            else:
                stop = max(stop, min_stop)  # Stop can't be lower than entry + min distance
            
            return stop
            
        except Exception as e:
            logger.warning(f"Error calculating ATR for {symbol}: {e}")
            # Fallback: 0.5% from entry
            return entry_price * (1 - self.limits.min_stop_distance_pct) if entry_price > dp_battlefield_level else entry_price * (1 + self.limits.min_stop_distance_pct)
    
    def add_position(self, position: Position):
        """Add a new position"""
        self.open_positions.append(position)
        logger.info(f"📊 Position opened: {position.symbol} @ ${position.entry_price:.2f} ({position.position_size_pct:.1%})")
    
    def close_position(self, symbol: str, exit_price: float):
        """Close a position and update P&L"""
        position = next((p for p in self.open_positions if p.symbol == symbol), None)
        if position:
            self.open_positions.remove(position)
            
            # Calculate P&L
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
            pnl = pnl_pct * position.position_size_pct
            
            self.daily_pnl += pnl
            self.daily_pnl_pct += pnl_pct * position.position_size_pct
            
            logger.info(f"📊 Position closed: {symbol} @ ${exit_price:.2f} (P&L: {pnl_pct:+.2%})")
            
            # Check circuit breaker
            if self.daily_pnl_pct <= self.limits.circuit_breaker_pnl_pct:
                self.circuit_breaker_triggered = True
                logger.error(f"🚨 CIRCUIT BREAKER TRIGGERED: Daily P&L {self.daily_pnl_pct:.2%} <= {self.limits.circuit_breaker_pnl_pct:.2%}")
    
    def reset_daily(self):
        """Reset daily counters (call at start of trading day)"""
        self.daily_pnl = 0.0
        self.daily_pnl_pct = 0.0
        self.circuit_breaker_triggered = False
        logger.info("🔄 Daily risk counters reset")
    
    def _count_correlated_positions(self, symbol: str) -> int:
        """Count how many correlated positions are open"""
        for group in self.correlated_groups:
            if symbol in group:
                return sum(1 for p in self.open_positions if p.symbol in group)
        return 0
    
    def _calculate_sector_exposure(self, symbol: str, new_position_pct: float) -> float:
        """Calculate total sector exposure if we add this position"""
        # Simple sector mapping (can be enhanced)
        tech_symbols = {'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'AMZN', 'NVDA', 'AMD', 'AVGO', 'TSM'}
        
        if symbol in tech_symbols:
            existing_tech_exposure = sum(
                p.position_size_pct for p in self.open_positions 
                if p.symbol in tech_symbols
            )
            return existing_tech_exposure + new_position_pct
        
        return new_position_pct
    
    def get_risk_summary(self) -> Dict:
        """Get current risk summary"""
        return {
            'open_positions': len(self.open_positions),
            'max_positions': self.limits.max_open_positions,
            'daily_pnl_pct': self.daily_pnl_pct,
            'daily_drawdown_limit': self.limits.max_daily_drawdown_pct,
            'circuit_breaker_triggered': self.circuit_breaker_triggered,
            'positions': [
                {
                    'symbol': p.symbol,
                    'entry': p.entry_price,
                    'size_pct': p.position_size_pct
                }
                for p in self.open_positions
            ]
        }

