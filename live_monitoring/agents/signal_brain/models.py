"""
🧠 Signal Brain - Data Models
=============================
Data contracts for signal synthesis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict


class ZoneRank(Enum):
    """Zone importance based on volume."""
    PRIMARY = "PRIMARY"      # 2M+ shares
    SECONDARY = "SECONDARY"  # 1M+ shares
    TERTIARY = "TERTIARY"    # 500K+ shares


class Bias(Enum):
    """Market bias."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class TimeOfDay(Enum):
    """Trading session."""
    PREMARKET = "PREMARKET"
    OPEN = "OPEN"            # 9:30-10:00 - High volatility
    MORNING = "MORNING"      # 10:00-11:30
    MIDDAY = "MIDDAY"        # 11:30-14:00 - Choppy
    AFTERNOON = "AFTERNOON"  # 14:00-15:00
    POWER_HOUR = "POWER_HOUR"  # 15:00-16:00 - Institutional
    AFTER_HOURS = "AFTER_HOURS"


class CrossAssetSignal(Enum):
    """Cross-asset correlation."""
    CONFIRMS = "CONFIRMS"    # Both same direction
    DIVERGENT = "DIVERGENT"  # Different directions
    NEUTRAL = "NEUTRAL"      # One has no signal


@dataclass
class SupportZone:
    """A clustered support/resistance zone."""
    symbol: str
    center_price: float
    min_price: float
    max_price: float
    combined_volume: int
    level_count: int
    levels: List[float]
    rank: ZoneRank
    zone_type: str  # SUPPORT or RESISTANCE
    distance_pct: float = 0.0
    
    @property
    def volume_str(self) -> str:
        """Human-readable volume."""
        if self.combined_volume >= 1_000_000:
            return f"{self.combined_volume/1_000_000:.1f}M"
        return f"{self.combined_volume/1000:.0f}K"
    
    @property
    def range_str(self) -> str:
        """Zone range as string."""
        if self.min_price == self.max_price:
            return f"${self.center_price:.2f}"
        return f"${self.min_price:.2f}-{self.max_price:.2f}"


@dataclass
class MarketContext:
    """Full market context for synthesis."""
    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)
    time_of_day: TimeOfDay = TimeOfDay.MIDDAY
    minutes_to_close: int = 0
    
    # Price context (SPY)
    spy_price: float = 0.0
    spy_change_pct: float = 0.0
    spy_trend_1h: Bias = Bias.NEUTRAL
    spy_trend_1d: Bias = Bias.NEUTRAL
    
    # QQQ context
    qqq_price: float = 0.0
    qqq_change_pct: float = 0.0
    
    # Volatility
    vix_level: float = 0.0
    vix_trend: str = "STABLE"  # RISING/FALLING/STABLE
    
    # Macro
    fed_sentiment: str = "NEUTRAL"  # HAWKISH/DOVISH/NEUTRAL
    trump_risk: str = "LOW"  # HIGH/MEDIUM/LOW
    
    # Volume
    volume_vs_avg: float = 1.0  # 1.5 = 50% above average


@dataclass
class SignalState:
    """State for a single symbol."""
    symbol: str
    current_price: float
    
    # Zones
    support_zones: List[SupportZone] = field(default_factory=list)
    resistance_zones: List[SupportZone] = field(default_factory=list)
    nearest_support: Optional[SupportZone] = None
    nearest_resistance: Optional[SupportZone] = None
    
    # Calculated
    bias: Bias = Bias.NEUTRAL
    at_support: bool = False
    at_resistance: bool = False


@dataclass
class ConfluenceScore:
    """Confluence analysis result."""
    score: float  # 0-100
    bias: Bias
    
    # Component scores
    dp_score: float = 0.0
    cross_asset_score: float = 0.0
    macro_score: float = 0.0
    timing_score: float = 0.0
    
    # Flags
    conflicts: List[str] = field(default_factory=list)
    confirmations: List[str] = field(default_factory=list)
    
    @property
    def strength(self) -> str:
        """Strength label."""
        if self.score >= 80:
            return "STRONG"
        elif self.score >= 60:
            return "MEDIUM"
        elif self.score >= 40:
            return "WEAK"
        return "VERY WEAK"


@dataclass
class TradeRecommendation:
    """ONE clear trade recommendation."""
    action: str  # LONG/SHORT/WAIT
    symbol: str
    
    # Entry details
    entry_price: float
    stop_price: float
    target_price: float
    
    # Sizing
    size: str  # FULL/HALF/QUARTER/NONE
    risk_reward: float
    
    # Reasoning
    primary_reason: str
    why_this_level: str
    
    # Risks
    risks: List[str] = field(default_factory=list)
    
    # Timing
    wait_for: Optional[str] = None  # e.g., "Wait for price to test $684.40"


@dataclass
class SynthesisResult:
    """The final unified synthesis output."""
    timestamp: datetime
    
    # Symbols analyzed
    symbols: List[str]
    
    # Context
    context: MarketContext
    
    # Per-symbol states
    states: Dict[str, SignalState] = field(default_factory=dict)
    
    # Cross-asset
    cross_asset: CrossAssetSignal = CrossAssetSignal.NEUTRAL
    cross_asset_detail: str = ""
    
    # Confluence
    confluence: ConfluenceScore = field(default_factory=lambda: ConfluenceScore(0, Bias.NEUTRAL))
    
    # THE recommendation
    recommendation: Optional[TradeRecommendation] = None
    
    # Narrative
    thinking: str = ""  # The reasoning
    
    def to_discord_embed(self) -> dict:
        """Convert to Discord embed format."""
        # Implemented in synthesizer.py
        pass

