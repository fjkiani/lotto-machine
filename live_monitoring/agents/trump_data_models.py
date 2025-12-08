#!/usr/bin/env python3
"""
TRUMP DATA MODELS
=================
Data structures for the Trump intelligence system.
Everything is measured, not guessed.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import json
import hashlib


class StatementSource(Enum):
    """Where the statement came from"""
    TRUTH_SOCIAL = "truth_social"
    NEWS = "news"
    TWITTER = "twitter"
    SPEECH = "speech"
    INTERVIEW = "interview"
    PRESS_RELEASE = "press_release"
    UNKNOWN = "unknown"


@dataclass
class TrumpStatement:
    """
    A single Trump statement with extracted features and market reaction.
    This is our core data unit - everything else builds on this.
    """
    # Identity
    id: str
    timestamp: datetime
    source: StatementSource
    raw_text: str
    url: Optional[str] = None
    
    # Extracted features (populated by NLP/LLM)
    entities: List[str] = field(default_factory=list)  # Apple, China, Powell
    topics: List[str] = field(default_factory=list)    # tariff, fed, trade
    sentiment: float = 0.0  # -1 (negative) to +1 (positive)
    intensity: float = 0.0  # 0 (mild) to 1 (extreme)
    urgency: float = 0.0    # 0 (no action implied) to 1 (immediate)
    
    # Embedding for similarity matching (computed later)
    embedding: Optional[List[float]] = None
    
    # Market reaction - MEASURED not guessed
    # These get filled in AFTER the statement
    spy_price_at_statement: Optional[float] = None
    spy_change_1min: Optional[float] = None   # % change
    spy_change_5min: Optional[float] = None
    spy_change_15min: Optional[float] = None
    spy_change_1hr: Optional[float] = None
    spy_change_1day: Optional[float] = None
    
    vix_at_statement: Optional[float] = None
    vix_change_1hr: Optional[float] = None
    
    # Per-symbol impact (for entities mentioned)
    symbol_impacts: Dict[str, float] = field(default_factory=dict)
    
    # Was this during market hours?
    is_market_hours: bool = False
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    market_data_collected: bool = False
    
    @staticmethod
    def generate_id(text: str, timestamp: datetime) -> str:
        """Generate unique ID from text and timestamp"""
        content = f"{text[:100]}{timestamp.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source.value,
            'raw_text': self.raw_text,
            'url': self.url,
            'entities': self.entities,
            'topics': self.topics,
            'sentiment': self.sentiment,
            'intensity': self.intensity,
            'urgency': self.urgency,
            'spy_price_at_statement': self.spy_price_at_statement,
            'spy_change_1min': self.spy_change_1min,
            'spy_change_5min': self.spy_change_5min,
            'spy_change_15min': self.spy_change_15min,
            'spy_change_1hr': self.spy_change_1hr,
            'spy_change_1day': self.spy_change_1day,
            'vix_at_statement': self.vix_at_statement,
            'vix_change_1hr': self.vix_change_1hr,
            'symbol_impacts': self.symbol_impacts,
            'is_market_hours': self.is_market_hours,
            'market_data_collected': self.market_data_collected,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrumpStatement':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            source=StatementSource(data.get('source', 'unknown')),
            raw_text=data['raw_text'],
            url=data.get('url'),
            entities=data.get('entities', []),
            topics=data.get('topics', []),
            sentiment=data.get('sentiment', 0.0),
            intensity=data.get('intensity', 0.0),
            urgency=data.get('urgency', 0.0),
            spy_price_at_statement=data.get('spy_price_at_statement'),
            spy_change_1min=data.get('spy_change_1min'),
            spy_change_5min=data.get('spy_change_5min'),
            spy_change_15min=data.get('spy_change_15min'),
            spy_change_1hr=data.get('spy_change_1hr'),
            spy_change_1day=data.get('spy_change_1day'),
            vix_at_statement=data.get('vix_at_statement'),
            vix_change_1hr=data.get('vix_change_1hr'),
            symbol_impacts=data.get('symbol_impacts', {}),
            is_market_hours=data.get('is_market_hours', False),
            market_data_collected=data.get('market_data_collected', False),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        )


@dataclass
class TopicCorrelation:
    """
    Learned correlation between a topic and market reaction.
    Updated continuously as we collect more data.
    """
    topic: str
    statement_count: int = 0
    
    # Aggregated market impact stats
    avg_spy_change_1hr: float = 0.0
    std_spy_change_1hr: float = 0.0
    median_spy_change_1hr: float = 0.0
    
    # Direction accuracy
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    
    # Win rate if we traded on it
    predicted_direction_accuracy: float = 0.0
    
    # By market session
    premarket_avg_impact: float = 0.0
    rth_avg_impact: float = 0.0
    afterhours_avg_impact: float = 0.0
    
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'topic': self.topic,
            'statement_count': self.statement_count,
            'avg_spy_change_1hr': self.avg_spy_change_1hr,
            'std_spy_change_1hr': self.std_spy_change_1hr,
            'median_spy_change_1hr': self.median_spy_change_1hr,
            'bullish_count': self.bullish_count,
            'bearish_count': self.bearish_count,
            'neutral_count': self.neutral_count,
            'predicted_direction_accuracy': self.predicted_direction_accuracy,
            'premarket_avg_impact': self.premarket_avg_impact,
            'rth_avg_impact': self.rth_avg_impact,
            'afterhours_avg_impact': self.afterhours_avg_impact,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class Prediction:
    """
    A prediction made by the system.
    We track ALL predictions to measure accuracy.
    """
    id: str
    statement_id: str
    timestamp: datetime
    
    # What we predicted
    predicted_direction: str  # "UP", "DOWN", "NEUTRAL"
    predicted_magnitude: float  # Expected % move
    confidence: float  # 0-1
    reasoning: str
    
    # What actually happened (filled later)
    actual_direction: Optional[str] = None
    actual_magnitude: Optional[float] = None
    
    # Accuracy assessment
    was_direction_correct: Optional[bool] = None
    magnitude_error: Optional[float] = None
    
    # If we traded
    position_taken: bool = False
    position_size: float = 0.0
    profit_loss: Optional[float] = None
    
    # Which agents contributed
    contributing_agents: List[str] = field(default_factory=list)
    similar_statements_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'statement_id': self.statement_id,
            'timestamp': self.timestamp.isoformat(),
            'predicted_direction': self.predicted_direction,
            'predicted_magnitude': self.predicted_magnitude,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'actual_direction': self.actual_direction,
            'actual_magnitude': self.actual_magnitude,
            'was_direction_correct': self.was_direction_correct,
            'magnitude_error': self.magnitude_error,
            'position_taken': self.position_taken,
            'position_size': self.position_size,
            'profit_loss': self.profit_loss,
            'contributing_agents': self.contributing_agents,
            'similar_statements_used': self.similar_statements_used
        }


@dataclass
class AgentAccuracy:
    """
    Tracks accuracy of a specific agent over time.
    Used to weight agent outputs.
    """
    agent_name: str
    total_predictions: int = 0
    correct_predictions: int = 0
    
    # Rolling accuracy (last N predictions)
    rolling_window: int = 50
    rolling_correct: int = 0
    rolling_total: int = 0
    
    # By topic
    topic_accuracy: Dict[str, float] = field(default_factory=dict)
    
    # By confidence level
    high_confidence_accuracy: float = 0.0  # conf > 0.7
    medium_confidence_accuracy: float = 0.0  # 0.4 < conf <= 0.7
    low_confidence_accuracy: float = 0.0  # conf <= 0.4
    
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def overall_accuracy(self) -> float:
        if self.total_predictions == 0:
            return 0.5  # Prior assumption
        return self.correct_predictions / self.total_predictions
    
    @property
    def rolling_accuracy(self) -> float:
        if self.rolling_total == 0:
            return 0.5
        return self.rolling_correct / self.rolling_total


@dataclass
class SimilarStatement:
    """Result from similarity search"""
    statement: TrumpStatement
    similarity_score: float  # 0-1
    market_reaction: float  # SPY % change


@dataclass 
class TrumpSignal:
    """
    Final signal output from the system.
    Data-driven, not hardcoded.
    """
    timestamp: datetime
    statement: TrumpStatement
    
    # Prediction
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    magnitude: float  # Expected % move
    confidence: float  # 0-1, based on historical accuracy
    
    # Supporting data
    similar_statements: List[SimilarStatement]
    topic_correlation: Optional[TopicCorrelation]
    
    # Agent consensus
    agent_votes: Dict[str, str]  # agent_name -> direction
    agent_confidences: Dict[str, float]
    
    # Action
    should_trade: bool
    suggested_symbols: List[str]
    suggested_position_size: float  # % of portfolio
    stop_loss_pct: float
    target_pct: float
    
    # Reasoning (human readable)
    reasoning: str
    data_points_used: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'statement_id': self.statement.id,
            'direction': self.direction,
            'magnitude': self.magnitude,
            'confidence': self.confidence,
            'similar_statements_count': len(self.similar_statements),
            'agent_votes': self.agent_votes,
            'agent_confidences': self.agent_confidences,
            'should_trade': self.should_trade,
            'suggested_symbols': self.suggested_symbols,
            'suggested_position_size': self.suggested_position_size,
            'stop_loss_pct': self.stop_loss_pct,
            'target_pct': self.target_pct,
            'reasoning': self.reasoning,
            'data_points_used': self.data_points_used
        }




