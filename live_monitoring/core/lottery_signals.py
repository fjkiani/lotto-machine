#!/usr/bin/env python3
"""
LOTTERY SIGNALS - Extended signal types for 0DTE options trading

This module defines:
- SignalType enum (regular + lottery types)
- LotterySignal dataclass (extends LiveSignal)
- SignalAction enum (BUY/SELL)

COMPONENT-BASED ARCHITECTURE:
- Clean separation of signal types
- Type-safe inheritance
- Easy to extend with new lottery types
"""

from dataclasses import dataclass, field
from typing import Optional, List, Union
from datetime import datetime
from enum import Enum


class SignalAction(Enum):
    """Trading action"""
    BUY = "BUY"
    SELL = "SELL"


class SignalType(Enum):
    """Signal types - regular and lottery"""
    # Regular signals
    REGULAR_BUY = "REGULAR_BUY"
    REGULAR_SELL = "REGULAR_SELL"
    SQUEEZE = "SQUEEZE"
    GAMMA_RAMP = "GAMMA_RAMP"
    BREAKOUT = "BREAKOUT"
    BOUNCE = "BOUNCE"
    BREAKDOWN = "BREAKDOWN"
    BEARISH_FLOW = "BEARISH_FLOW"
    SELLOFF = "SELLOFF"
    RALLY = "RALLY"  # Counterpart to selloff - rapid upward move
    
    # Lottery signals
    LOTTERY_0DTE_CALL = "LOTTERY_0DTE_CALL"
    LOTTERY_0DTE_PUT = "LOTTERY_0DTE_PUT"
    LOTTERY_LEVERAGED_ETF = "LOTTERY_LEVERAGED_ETF"
    LOTTERY_EVENT_STRADDLE = "LOTTERY_EVENT_STRADDLE"
    LOTTERY_VOLATILITY_EXPANSION = "LOTTERY_VOLATILITY_EXPANSION"
    
    @classmethod
    def is_lottery(cls, signal_type) -> bool:
        """Check if signal type is a lottery signal"""
        lottery_types = [
            cls.LOTTERY_0DTE_CALL,
            cls.LOTTERY_0DTE_PUT,
            cls.LOTTERY_LEVERAGED_ETF,
            cls.LOTTERY_EVENT_STRADDLE,
            cls.LOTTERY_VOLATILITY_EXPANSION,
        ]
        return signal_type in lottery_types
    
    @classmethod
    def is_regular(cls, signal_type) -> bool:
        """Check if signal type is a regular signal"""
        return not cls.is_lottery(signal_type)


@dataclass
class LiveSignal:
    """
    Base signal class for all trading signals
    
    Common fields shared by regular and lottery signals
    
    Note: All fields have defaults to allow inheritance with required fields
    """
    symbol: str = ""
    action: SignalAction = SignalAction.BUY
    timestamp: datetime = field(default_factory=datetime.now)
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_price: float = 0.0
    confidence: float = 0.0
    signal_type: SignalType = SignalType.REGULAR_BUY
    rationale: str = ""
    
    # Context (optional, for regular signals)
    dp_level: float = 0.0
    dp_volume: int = 0
    institutional_score: float = 0.0
    
    # Supporting info
    supporting_factors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # State
    is_master_signal: bool = False
    is_actionable: bool = True
    
    # Position sizing (calculated by RiskManager)
    position_size_pct: float = 0.0
    position_size_dollars: float = 0.0
    
    # Risk/Reward
    risk_reward_ratio: float = 0.0


@dataclass
class LotterySignal(LiveSignal):
    """
    Lottery-specific signal for 0DTE options trading
    
    Extends LiveSignal with lottery-specific fields
    
    Note: All fields have defaults to work with dataclass inheritance
    Required fields should be set explicitly when creating instances
    """
    # Options contract details (required but have defaults for inheritance)
    strike: float = 0.0
    expiry: str = ""  # e.g., "2025-11-20"
    option_type: str = "CALL"  # "CALL" or "PUT"
    delta: float = 0.0  # Target delta (0.05-0.10 for lottery)
    
    # Options Greeks
    gamma: float = 0.0
    iv: float = 0.0  # Implied volatility
    
    # Lottery-specific metrics
    iv_rank: float = 0.0  # Current IV percentile
    lottery_potential: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    
    # Event catalyst
    event_catalyst: Optional[str] = None  # e.g., "CPI_REPORT", "FOMC", "EARNINGS"
    
    # Options liquidity
    open_interest: int = 0
    volume: int = 0
    bid: float = 0.0
    ask: float = 0.0
    spread_pct: float = 0.0
    liquidity_score: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    
    # Profit-taking levels
    take_profit_levels: List[tuple] = field(default_factory=lambda: [
        (2.0, 0.30),   # 2x = sell 30%
        (5.0, 0.30),   # 5x = sell 30% more
        (10.0, 0.30),  # 10x = sell 30% more
        (20.0, 0.10),  # 20x = sell final 10%, let rest run
    ])
    
    def to_options_contract(self) -> str:
        """
        Convert to tradeable options contract symbol
        
        Format: SYMBOL + YYMMDD + C/P + Strike (5 digits)
        Example: SPY251120C656000
        """
        # Format expiry: YYMMDD
        expiry_parts = self.expiry.split('-')
        if len(expiry_parts) == 3:
            yy = expiry_parts[0][-2:]  # Last 2 digits of year
            mm = expiry_parts[1]
            dd = expiry_parts[2]
            expiry_str = f"{yy}{mm}{dd}"
        else:
            expiry_str = self.expiry.replace('-', '')[-6:]  # Fallback
        
        # Option type: C for CALL, P for PUT
        option_char = 'C' if self.option_type == 'CALL' else 'P'
        
        # Strike: 5 digits (e.g., 65600 for $656.00)
        strike_str = f"{int(self.strike * 1000):08d}"  # 8 digits with leading zeros
        
        return f"{self.symbol}{expiry_str}{option_char}{strike_str}"
    
    def get_premium(self) -> float:
        """Get mid price (premium)"""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.entry_price
    
    def is_liquid(self) -> bool:
        """Check if option is liquid enough to trade"""
        return (
            self.liquidity_score in ['HIGH', 'MEDIUM'] and
            self.open_interest >= 1000 and
            self.volume >= 100 and
            self.spread_pct < 0.20
        )

