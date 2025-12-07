"""
🔒 DP Monitor - Trade Calculator
=================================
Calculates entry, stop, target for DP trades.
"""

import logging
from typing import Optional

from .models import Battleground, TradeSetup, TradeDirection, LevelType

logger = logging.getLogger(__name__)


class TradeCalculator:
    """
    Calculates trade setups for dark pool levels.
    
    For SUPPORT levels:
    - Direction: LONG on bounce
    - Entry: At or slightly above the level
    - Stop: Below the level (0.15% minimum)
    - Target: 2:1 R/R ratio
    
    For RESISTANCE levels:
    - Direction: SHORT on bounce (fade)
    - Entry: At or slightly below the level
    - Stop: Above the level (0.15% minimum)
    - Target: 2:1 R/R ratio
    """
    
    # Default settings
    DEFAULT_STOP_PCT = 0.0015   # 0.15% stop distance
    DEFAULT_RR_RATIO = 2.0     # 2:1 reward/risk
    MIN_HOLD_TIME = 15         # 15 minutes minimum
    MAX_HOLD_TIME = 60         # 60 minutes maximum
    
    def __init__(
        self, 
        stop_pct: float = DEFAULT_STOP_PCT,
        rr_ratio: float = DEFAULT_RR_RATIO
    ):
        self.stop_pct = stop_pct
        self.rr_ratio = rr_ratio
    
    def calculate_setup(self, battleground: Battleground) -> TradeSetup:
        """
        Calculate trade setup for a battleground level.
        
        Args:
            battleground: The battleground with level_type set
            
        Returns:
            TradeSetup with entry, stop, target, direction
        """
        if battleground.level_type is None:
            logger.warning("Battleground has no level_type set")
            return self._default_setup(battleground)
        
        level_price = battleground.price
        
        if battleground.level_type == LevelType.SUPPORT:
            return self._calculate_support_trade(level_price)
        else:
            return self._calculate_resistance_trade(level_price)
    
    def _calculate_support_trade(self, level_price: float) -> TradeSetup:
        """
        Calculate LONG trade setup for support level.
        
        SUPPORT = Buy the bounce
        Entry: At the level (or slightly above for safer entry)
        Stop: Below the level
        Target: Above entry (2:1 R/R)
        """
        # Entry at level or 0.05% above for safer entry
        entry = level_price * 1.0005
        
        # Stop below the level
        stop = level_price * (1 - self.stop_pct)
        
        # Calculate risk
        risk = entry - stop
        
        # Target = entry + (risk * R/R ratio)
        target = entry + (risk * self.rr_ratio)
        
        return TradeSetup(
            direction=TradeDirection.LONG,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target=round(target, 2),
            risk_reward=self.rr_ratio,
            hold_time_min=self.MIN_HOLD_TIME,
            hold_time_max=self.MAX_HOLD_TIME,
        )
    
    def _calculate_resistance_trade(self, level_price: float) -> TradeSetup:
        """
        Calculate SHORT trade setup for resistance level.
        
        RESISTANCE = Fade the rally
        Entry: At the level (or slightly below for safer entry)
        Stop: Above the level
        Target: Below entry (2:1 R/R)
        """
        # Entry at level or 0.05% below for safer entry
        entry = level_price * 0.9995
        
        # Stop above the level
        stop = level_price * (1 + self.stop_pct)
        
        # Calculate risk
        risk = stop - entry
        
        # Target = entry - (risk * R/R ratio)
        target = entry - (risk * self.rr_ratio)
        
        return TradeSetup(
            direction=TradeDirection.SHORT,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target=round(target, 2),
            risk_reward=self.rr_ratio,
            hold_time_min=self.MIN_HOLD_TIME,
            hold_time_max=self.MAX_HOLD_TIME,
        )
    
    def _default_setup(self, battleground: Battleground) -> TradeSetup:
        """Return a default 'wait' setup when level type unknown."""
        return TradeSetup(
            direction=TradeDirection.WAIT,
            entry=battleground.price,
            stop=battleground.price * 0.998,
            target=battleground.price * 1.002,
            risk_reward=1.0,
            hold_time_min=self.MIN_HOLD_TIME,
            hold_time_max=self.MAX_HOLD_TIME,
        )
    
    def calculate_breakout_setup(
        self, 
        battleground: Battleground, 
        break_direction: str
    ) -> TradeSetup:
        """
        Calculate trade setup for a BREAKOUT (level broke).
        
        Args:
            battleground: The broken level
            break_direction: 'UP' or 'DOWN'
            
        Returns:
            TradeSetup for trading in direction of break
        """
        level_price = battleground.price
        
        if break_direction == 'UP':
            # Breakout above resistance - go LONG
            entry = level_price * 1.001  # Enter slightly above
            stop = level_price * 0.998   # Stop below the broken level
            risk = entry - stop
            target = entry + (risk * self.rr_ratio)
            direction = TradeDirection.LONG
        else:
            # Breakdown below support - go SHORT
            entry = level_price * 0.999  # Enter slightly below
            stop = level_price * 1.002   # Stop above the broken level
            risk = stop - entry
            target = entry - (risk * self.rr_ratio)
            direction = TradeDirection.SHORT
        
        return TradeSetup(
            direction=direction,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target=round(target, 2),
            risk_reward=self.rr_ratio,
            hold_time_min=30,   # Breakouts need more time
            hold_time_max=120,
        )



