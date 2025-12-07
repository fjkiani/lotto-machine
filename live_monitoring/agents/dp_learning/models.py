"""
🧠 DP Learning Engine - Data Models
===================================
Clean data contracts for dark pool learning.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class LevelType(Enum):
    SUPPORT = "SUPPORT"
    RESISTANCE = "RESISTANCE"


class Outcome(Enum):
    PENDING = "PENDING"      # Waiting for result
    BOUNCE = "BOUNCE"        # Price reversed at level
    BREAK = "BREAK"          # Price broke through level
    FADE = "FADE"            # Nothing happened, choppy
    UNKNOWN = "UNKNOWN"      # Couldn't determine


class ApproachDirection(Enum):
    FROM_ABOVE = "FROM_ABOVE"  # Price coming down to level
    FROM_BELOW = "FROM_BELOW"  # Price coming up to level


@dataclass
class DPInteraction:
    """
    A single interaction with a dark pool level.
    This is what we log when price touches a battleground.
    """
    # Identity
    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    symbol: str = ""
    
    # Level Info
    level_price: float = 0.0
    level_volume: int = 0
    level_type: LevelType = LevelType.RESISTANCE
    level_date: str = ""  # When the DP data is from
    
    # Approach Info
    approach_price: float = 0.0
    approach_direction: ApproachDirection = ApproachDirection.FROM_BELOW
    distance_pct: float = 0.0
    touch_count: int = 1  # 1st, 2nd, 3rd touch of this level
    
    # Market Context at Alert Time
    market_trend: str = "UNKNOWN"  # UP, DOWN, CHOP
    volume_vs_avg: float = 1.0     # 1.5x, 2x, etc.
    momentum_pct: float = 0.0      # Recent price change %
    vix_level: float = 0.0
    time_of_day: str = "UNKNOWN"   # MORNING, MIDDAY, AFTERNOON
    
    # Outcome (filled later)
    outcome: Outcome = Outcome.PENDING
    outcome_timestamp: Optional[datetime] = None
    max_move_pct: float = 0.0      # Max move after alert
    time_to_outcome_min: int = 0   # Minutes until outcome clear
    
    # Notes
    notes: str = ""


@dataclass
class DPOutcome:
    """
    The result of tracking an interaction over time.
    """
    interaction_id: int
    outcome: Outcome
    max_move_pct: float
    time_to_outcome_min: int
    price_at_5min: float = 0.0
    price_at_15min: float = 0.0
    price_at_30min: float = 0.0
    price_at_60min: float = 0.0


@dataclass
class DPPattern:
    """
    A learned pattern from historical interactions.
    """
    pattern_name: str           # e.g., "volume_1m_plus", "morning_resistance"
    total_samples: int = 0
    bounce_count: int = 0
    break_count: int = 0
    fade_count: int = 0
    
    @property
    def bounce_rate(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return self.bounce_count / self.total_samples
    
    @property
    def break_rate(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return self.break_count / self.total_samples
    
    @property
    def confidence(self) -> str:
        """Confidence level based on sample size."""
        if self.total_samples < 5:
            return "LOW"
        elif self.total_samples < 15:
            return "MEDIUM"
        else:
            return "HIGH"


@dataclass
class DPPrediction:
    """
    A prediction for a new interaction based on learned patterns.
    """
    symbol: str
    level_price: float
    predicted_outcome: Outcome
    bounce_probability: float
    break_probability: float
    confidence: str  # LOW, MEDIUM, HIGH
    supporting_patterns: List[str] = field(default_factory=list)
    expected_move_pct: float = 0.0
    suggested_action: str = ""  # "SHORT", "LONG", "WAIT"


