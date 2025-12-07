"""
📊 Data Contracts for Fed Officials Intelligence
=================================================
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum


class FedPosition(Enum):
    CHAIR = "Chair"
    VICE_CHAIR = "Vice Chair"
    GOVERNOR = "Governor"
    REGIONAL_PRESIDENT = "Regional President"
    VICE_CHAIR_SUPERVISION = "Vice Chair for Supervision"


@dataclass
class FedOfficial:
    """Fed official (learned from data, not hardcoded)."""
    name: str
    position: Optional[FedPosition] = None
    voting_member: bool = True
    
    # Learned attributes (from historical data)
    historical_sentiment: str = "NEUTRAL"  # Most common sentiment
    market_impact_score: float = 1.0  # Learned from actual price moves
    comment_frequency: int = 0  # How often they comment
    
    # Dynamic keywords (learned from mentions)
    detected_keywords: List[str] = field(default_factory=list)
    
    # Metadata
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


@dataclass
class FedComment:
    """A Fed official's comment (with learned sentiment)."""
    timestamp: datetime
    official_name: str
    headline: str
    content: str
    source: str
    url: Optional[str] = None
    
    # LLM-analyzed (not keyword-based!)
    sentiment: str = "NEUTRAL"  # HAWKISH, DOVISH, NEUTRAL
    sentiment_confidence: float = 0.0
    sentiment_reasoning: str = ""  # Why LLM thinks this
    
    # Market impact (learned from actual moves)
    predicted_market_impact: str = "UNKNOWN"  # BULLISH, BEARISH, NEUTRAL
    actual_market_impact: Optional[str] = None  # Filled in after price moves
    impact_accuracy: Optional[float] = None  # How accurate was prediction?
    
    # Metadata
    comment_hash: str = ""  # For deduplication


@dataclass
class QueryPerformance:
    """Track which queries work best."""
    query_template: str
    success_count: int = 0
    failure_count: int = 0
    avg_comments_found: float = 0.0
    last_used: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


@dataclass
class SentimentPattern:
    """Learned pattern: phrase → sentiment."""
    phrase: str
    sentiment: str  # HAWKISH, DOVISH, NEUTRAL
    confidence: float  # How often this phrase = this sentiment
    sample_count: int  # How many times we've seen this
    last_seen: Optional[datetime] = None


@dataclass
class MarketImpactPattern:
    """Learned: official + sentiment → actual market move."""
    official_name: str
    sentiment: str
    avg_spy_move_1hr: float  # Average SPY move 1 hour after comment
    avg_spy_move_4hr: float  # Average SPY move 4 hours after
    sample_count: int
    accuracy: float  # How often prediction matched reality


@dataclass
class FedCommentReport:
    """Report of Fed comments (with learned insights)."""
    timestamp: datetime = field(default_factory=datetime.now)
    comments: List[FedComment] = field(default_factory=list)
    
    # Learned insights
    overall_sentiment: str = "NEUTRAL"
    market_bias: str = "NEUTRAL"
    confidence: float = 0.0
    
    # Recommendations (data-driven)
    recommendation: str = ""
    suggested_positions: List[str] = field(default_factory=list)
    
    # Pattern insights
    detected_patterns: List[str] = field(default_factory=list)



