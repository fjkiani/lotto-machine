"""
Data models for Narrative Brain system
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class AlertType(Enum):
    PRE_MARKET = "pre_market"
    INTRA_DAY = "intra_day"
    EVENT_TRIGGERED = "event_triggered"
    END_OF_DAY = "end_of_day"


class NarrativePriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class NarrativeContext:
    """Context for narrative continuity across sessions"""
    timestamp: datetime
    market_regime: str  # BULLISH/BEARISH/NEUTRAL
    key_levels: Dict[str, float]  # SPY: 685.50, QQQ: 620.25
    sentiment: Dict[str, str]  # fed: HAWKISH, trump: BULLISH
    recent_events: List[str]  # Last 24h economic events
    narrative_themes: List[str]  # Current market themes
    last_update: datetime


@dataclass
class NarrativeUpdate:
    """A potential narrative update to send"""
    alert_type: AlertType
    priority: NarrativePriority
    title: str
    content: str
    context_references: List[str]  # Previous analyses to reference
    intelligence_sources: List[str]  # DP, Fed, Trump, etc.
    market_impact: str  # Expected move/significance
    timestamp: datetime


@dataclass
class IntelligenceSnapshot:
    """Snapshot of all intelligence sources at a moment"""
    timestamp: datetime
    dp_context: Dict[str, Any]
    fed_context: Dict[str, Any]
    trump_context: Dict[str, Any]
    economic_context: Dict[str, Any]
    market_regime: str
    confluence_score: float


@dataclass
class NarrativeMemoryEntry:
    """Entry in narrative memory for continuity"""
    timestamp: datetime
    alert_type: str
    content: str
    intelligence_sources: List[str]
    market_impact: str
    context_hash: str  # For deduplication




