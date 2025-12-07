"""
🔒 DP Monitor - Data Models
===========================
Data contracts for dark pool monitoring.
"""

from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import Optional


class AlertPriority(Enum):
    """Priority level based on volume significance."""
    CRITICAL = "CRITICAL"  # 2M+ shares, price AT level
    HIGH = "HIGH"          # 1M+ shares, or price very close
    MEDIUM = "MEDIUM"      # 500K+ shares, approaching
    LOW = "LOW"            # <500K shares


class AlertType(Enum):
    """Type of proximity alert."""
    AT_LEVEL = "AT_LEVEL"       # Within 0.1%
    APPROACHING = "APPROACHING"  # Within 0.3%
    NEAR = "NEAR"               # Within 0.5%


class LevelType(Enum):
    """Support or Resistance based on price position."""
    SUPPORT = "SUPPORT"       # Level below price
    RESISTANCE = "RESISTANCE"  # Level above price


class TradeDirection(Enum):
    """Suggested trade direction."""
    LONG = "LONG"
    SHORT = "SHORT"
    WAIT = "WAIT"  # Wait for confirmation


@dataclass
class Battleground:
    """A dark pool battleground level."""
    symbol: str
    price: float
    volume: int
    date: str  # Date the DP activity occurred
    
    # Calculated fields
    level_type: Optional[LevelType] = None
    distance_pct: Optional[float] = None
    current_price: Optional[float] = None
    
    @property
    def volume_tier(self) -> str:
        """Volume significance tier."""
        if self.volume >= 2_000_000:
            return "MAJOR"
        elif self.volume >= 1_000_000:
            return "STRONG"
        elif self.volume >= 500_000:
            return "MODERATE"
        else:
            return "MINOR"
    
    @property
    def confidence(self) -> float:
        """Confidence score based on volume."""
        if self.volume >= 2_000_000:
            return 0.90
        elif self.volume >= 1_000_000:
            return 0.75
        elif self.volume >= 500_000:
            return 0.60
        else:
            return 0.50


@dataclass
class TradeSetup:
    """Trade setup with entry, stop, target."""
    direction: TradeDirection
    entry: float
    stop: float
    target: float
    risk_reward: float
    hold_time_min: int  # Minimum hold time in minutes
    hold_time_max: int  # Maximum hold time in minutes
    
    @property
    def risk_pct(self) -> float:
        """Risk percentage from entry to stop."""
        return abs(self.entry - self.stop) / self.entry * 100
    
    @property
    def reward_pct(self) -> float:
        """Reward percentage from entry to target."""
        return abs(self.target - self.entry) / self.entry * 100


@dataclass
class DPAlert:
    """A dark pool alert with all context."""
    # Core info
    symbol: str
    battleground: Battleground
    alert_type: AlertType
    priority: AlertPriority
    timestamp: datetime
    
    # Trade setup
    trade_setup: Optional[TradeSetup] = None
    
    # AI prediction
    ai_prediction: Optional[float] = None  # Probability of bounce
    ai_confidence: Optional[str] = None    # HIGH/MEDIUM/LOW
    ai_patterns: Optional[list] = None     # Patterns detected
    
    # State
    already_alerted: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            'symbol': self.symbol,
            'level_price': self.battleground.price,
            'level_volume': self.battleground.volume,
            'level_type': self.battleground.level_type.value if self.battleground.level_type else None,
            'current_price': self.battleground.current_price,
            'distance_pct': self.battleground.distance_pct,
            'alert_type': self.alert_type.value,
            'priority': self.priority.value,
            'trade_direction': self.trade_setup.direction.value if self.trade_setup else None,
            'entry': self.trade_setup.entry if self.trade_setup else None,
            'stop': self.trade_setup.stop if self.trade_setup else None,
            'target': self.trade_setup.target if self.trade_setup else None,
            'ai_prediction': self.ai_prediction,
            'timestamp': self.timestamp.isoformat(),
        }


