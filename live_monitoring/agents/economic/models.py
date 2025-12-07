"""
Economic Intelligence - Data Models

Clean, typed data contracts for the entire system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


class EventType(Enum):
    """Types of economic events we track."""
    NFP = "nonfarm_payrolls"
    UNEMPLOYMENT = "unemployment_rate"
    CPI = "cpi"
    CORE_CPI = "core_cpi"
    PPI = "ppi"
    CORE_PPI = "core_ppi"
    PCE = "pce"
    CORE_PCE = "core_pce"
    GDP = "gdp"
    RETAIL_SALES = "retail_sales"
    ISM_MANUFACTURING = "ism_manufacturing"
    ISM_SERVICES = "ism_services"
    JOBLESS_CLAIMS = "initial_jobless_claims"
    HOUSING_STARTS = "housing_starts"
    CONSUMER_CONFIDENCE = "consumer_confidence"
    FOMC_DECISION = "fomc_decision"
    FED_SPEECH = "fed_speech"


class ImpactDirection(Enum):
    """Direction of Fed policy impact."""
    DOVISH = "dovish"    # Weak data = more cuts likely
    HAWKISH = "hawkish"  # Strong data = fewer cuts likely
    NEUTRAL = "neutral"


class SignalStrength(Enum):
    """Strength of trading signal."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


@dataclass
class EconomicRelease:
    """
    A single economic data release.
    
    This is the core data unit - everything we need to learn from.
    """
    # Basic info
    date: str                    # YYYY-MM-DD
    time: str                    # HH:MM (EST)
    event_type: EventType
    event_name: str              # Human-readable name
    
    # Release data
    actual: float               # Actual value released
    forecast: float             # Consensus forecast
    previous: float             # Previous period value
    revision: Optional[float] = None  # Revision to previous
    
    # Calculated
    surprise_pct: float = 0.0   # (actual - forecast) / forecast * 100
    surprise_sigma: float = 0.0  # Standardized surprise (in σ)
    
    # Fed Watch impact (our target variable!)
    fed_watch_before: float = 50.0   # Cut % before release
    fed_watch_after_1hr: float = 50.0  # Cut % 1 hour after
    fed_watch_after_24hr: float = 50.0  # Cut % 24 hours after
    fed_watch_shift_1hr: float = 0.0  # Change in 1hr
    fed_watch_shift_24hr: float = 0.0  # Change in 24hr
    
    # Market reactions
    spy_change_1hr: float = 0.0  # SPY % change 1hr after
    spy_change_24hr: float = 0.0  # SPY % change 24hr after
    tlt_change_1hr: float = 0.0  # TLT (bonds) % change
    vix_change_1hr: float = 0.0  # VIX change
    volume_spike: float = 1.0    # Volume vs average
    
    # Dark Pool context (OUR EDGE!)
    dp_activity_before: float = 0.0   # DP % of volume before
    dp_activity_after: float = 0.0    # DP % of volume after
    dp_buy_ratio_before: float = 0.5  # Buy/sell ratio before
    dp_buy_ratio_after: float = 0.5   # Buy/sell ratio after
    dp_battleground_distance: float = 0.0  # Distance to nearest DP level
    
    # Context
    days_to_fomc: int = 30      # Days until next FOMC
    current_fed_rate: float = 4.5
    market_regime: str = "NORMAL"  # RISK_ON, RISK_OFF, NORMAL
    vix_level: float = 15.0
    
    # Metadata
    source: str = "manual"
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class LearnedPattern:
    """
    A learned correlation between an event type and Fed Watch movement.
    
    This is what we're trying to learn - how each event moves Fed Watch.
    """
    event_type: EventType
    
    # Core coefficients (what we learn)
    base_impact: float = 0.0         # Base Fed Watch shift per σ surprise
    surprise_scaling: float = 1.0    # How impact scales with surprise size
    fomc_proximity_boost: float = 0.0  # Extra impact near FOMC
    
    # Context multipliers
    high_vix_multiplier: float = 1.0   # Impact when VIX > 20
    dp_confirmation_boost: float = 0.0  # Boost when DP confirms direction
    
    # Model quality
    sample_count: int = 0
    r_squared: float = 0.0
    mean_absolute_error: float = 0.0
    
    # Tracking
    last_5_predictions: List[Dict] = field(default_factory=list)
    last_updated: str = ""
    
    def get_confidence(self) -> float:
        """Calculate confidence score based on model quality."""
        confidence = 0.3  # Base
        
        if self.sample_count >= 10:
            confidence += 0.1
        if self.sample_count >= 25:
            confidence += 0.1
        if self.sample_count >= 50:
            confidence += 0.1
        if self.r_squared >= 0.3:
            confidence += 0.1
        if self.r_squared >= 0.5:
            confidence += 0.15
        if self.mean_absolute_error < 3.0:
            confidence += 0.1
        
        return min(confidence, 0.95)


@dataclass
class DarkPoolContext:
    """
    Dark Pool signals around an economic release.
    
    This is OUR EDGE - institutions position before data!
    """
    symbol: str = "SPY"
    timestamp: str = ""
    
    # Volume analysis
    total_dp_volume: int = 0
    dp_pct_of_total: float = 0.0
    volume_vs_average: float = 1.0
    
    # Flow analysis
    buy_volume: int = 0
    sell_volume: int = 0
    buy_ratio: float = 0.5  # >0.55 = bullish, <0.45 = bearish
    
    # Battleground proximity
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0
    current_price: float = 0.0
    support_distance_pct: float = 0.0
    resistance_distance_pct: float = 0.0
    
    # Institutional positioning signals
    large_prints_count: int = 0  # Prints > $1M
    avg_print_size: float = 0.0
    block_trade_ratio: float = 0.0  # % of volume in blocks
    
    def get_signal(self) -> ImpactDirection:
        """Interpret DP data as directional signal."""
        if self.buy_ratio > 0.58:
            return ImpactDirection.DOVISH  # Institutions buying = expect good news
        elif self.buy_ratio < 0.42:
            return ImpactDirection.HAWKISH  # Institutions selling = expect bad news
        return ImpactDirection.NEUTRAL


@dataclass
class Prediction:
    """
    A Fed Watch movement prediction.
    """
    event_type: EventType
    event_name: str
    
    # Input
    surprise_sigma: float
    current_fed_watch: float
    
    # Prediction
    predicted_shift: float
    predicted_fed_watch: float
    confidence: float
    
    # Direction
    direction: ImpactDirection
    
    # Context used
    dp_signal: Optional[ImpactDirection] = None
    dp_confirmation: bool = False
    days_to_fomc: int = 30
    vix_level: float = 15.0
    
    # Rationale
    rationale: str = ""
    
    # Metadata
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Scenario:
    """
    A pre-event scenario (weak/inline/strong).
    """
    name: str  # "weak", "inline", "strong"
    description: str
    
    # Assumed surprise
    assumed_surprise_sigma: float
    
    # Predicted outcomes
    predicted_fed_watch_shift: float
    predicted_fed_watch: float
    predicted_spy_move: float
    predicted_tlt_move: float
    
    # Trade recommendation
    trade_action: str  # "BUY SPY/TLT", "SELL", "HOLD"
    trade_symbols: List[str] = field(default_factory=list)
    
    confidence: float = 0.5


@dataclass
class PreEventAlert:
    """
    Alert generated BEFORE an economic release.
    """
    event_type: EventType
    event_name: str
    event_date: str
    event_time: str
    
    # Timing
    hours_until: float
    
    # Current state
    current_fed_watch: float
    
    # Scenarios
    weak_scenario: Scenario
    inline_scenario: Scenario
    strong_scenario: Scenario
    
    # Max potential move
    max_swing: float
    
    # DP context (if available)
    dp_context: Optional[DarkPoolContext] = None
    dp_positioning_signal: Optional[ImpactDirection] = None
    
    # Recommendation
    recommended_positioning: str = ""
    confidence: float = 0.5
    
    # Metadata
    generated_at: str = ""
    
    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()


@dataclass 
class TrainingData:
    """
    Complete training dataset for the learning engine.
    """
    releases: List[EconomicRelease]
    
    # Stats
    total_count: int = 0
    by_event_type: Dict[str, int] = field(default_factory=dict)
    date_range: str = ""
    
    # Quality
    completeness_score: float = 0.0  # % of fields populated
    
    def __post_init__(self):
        self.total_count = len(self.releases)
        
        # Count by type
        for r in self.releases:
            key = r.event_type.value if isinstance(r.event_type, EventType) else str(r.event_type)
            self.by_event_type[key] = self.by_event_type.get(key, 0) + 1
        
        # Date range
        if self.releases:
            dates = sorted([r.date for r in self.releases])
            self.date_range = f"{dates[0]} to {dates[-1]}"


