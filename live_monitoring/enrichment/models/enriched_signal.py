#!/usr/bin/env python3
"""
Enriched Signal Data Models
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Import base signal
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / 'core'))
from lottery_signals import LiveSignal, SignalAction, SignalType


class RiskEnvironment(Enum):
    """Market risk environment classification"""
    RISK_OFF = "RISK_OFF"        # Crypto down, equities down (bearish)
    RISK_ON = "RISK_ON"          # Crypto up, equities up (bullish)
    NEUTRAL = "NEUTRAL"          # Mixed signals
    DIVERGENCE = "DIVERGENCE"    # Crypto up, equities down (investigate)


@dataclass
class CryptoSentiment:
    """Crypto market sentiment from BTC/ETH"""
    btc_price: float
    btc_change_pct: float
    eth_price: float
    eth_change_pct: float
    correlation: float  # BTC-ETH correlation (-1 to 1)
    environment: RiskEnvironment
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class NarrativeAnalysis:
    """LLM-generated narrative analysis"""
    narrative: str  # 2-sentence summary
    catalysts: List[str]  # ["BTC breakdown", "Fed hawkish", ...]
    conviction: str  # HIGH/MEDIUM/LOW
    duration: str  # INTRADAY/MULTI_DAY/WEEK
    risk_environment: str  # RISK_OFF/RISK_ON/NEUTRAL
    confidence_boost: float  # 0.0 to 0.15


@dataclass
class UnusualOptionsActivity:
    """Unusual options flow detection"""
    unusual_puts: int  # Count of large put orders
    unusual_calls: int  # Count of large call orders
    put_volume: int
    call_volume: int
    pc_ratio: float  # Put/call ratio
    sentiment: str  # BEARISH_HEDGE/BULLISH_SPECULATION/NEUTRAL
    confidence_boost: float  # -0.15 to 0.15
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Catalyst:
    """Economic/news catalyst"""
    name: str  # "FOMC Minutes", "CPI Release"
    type: str  # "ECONOMIC", "EARNINGS", "GEOPOLITICAL"
    time: datetime
    impact: str  # HIGH/MEDIUM/LOW
    description: Optional[str] = None


@dataclass
class SentimentScore:
    """Alternative sentiment analysis"""
    source: str  # "crypto_twitter", "reddit", "stocktwits"
    sentiment_score: float  # -1.0 (extreme fear) to 1.0 (extreme greed)
    overall_tone: str  # EXTREME_FEAR/FEAR/NEUTRAL/GREED/EXTREME_GREED
    keywords: List[str]  # ["breakdown", "capitulation", etc.]
    mention_count: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EnrichedSignal(LiveSignal):
    """
    Enhanced signal with multi-factor enrichment
    
    Extends LiveSignal with:
    - Narrative analysis (LLM)
    - Alternative sentiment
    - Crypto correlation
    - Options flow
    - Economic catalysts
    """
    # Enrichment data
    crypto_sentiment: Optional[CryptoSentiment] = None
    narrative_analysis: Optional[NarrativeAnalysis] = None
    options_activity: Optional[UnusualOptionsActivity] = None
    catalysts: List[Catalyst] = field(default_factory=list)
    alt_sentiment: Optional[SentimentScore] = None
    
    # Enrichment metadata
    enrichment_modules_used: List[str] = field(default_factory=list)
    base_confidence: float = 0.0  # Original confidence before enrichment
    enrichment_boost: float = 0.0  # Total boost from all modules
    
    # Override from parent
    is_enriched: bool = True
    
    @classmethod
    def from_base_signal(cls, base_signal: LiveSignal) -> 'EnrichedSignal':
        """Convert base signal to enriched signal"""
        # Copy all fields from base signal
        return cls(
            symbol=base_signal.symbol,
            action=base_signal.action,
            timestamp=base_signal.timestamp,
            entry_price=base_signal.entry_price,
            target_price=base_signal.target_price,
            stop_price=base_signal.stop_price,
            confidence=base_signal.confidence,
            signal_type=base_signal.signal_type,
            rationale=base_signal.rationale,
            dp_level=base_signal.dp_level,
            dp_volume=base_signal.dp_volume,
            institutional_score=base_signal.institutional_score,
            supporting_factors=base_signal.supporting_factors.copy(),
            warnings=base_signal.warnings.copy(),
            is_master_signal=base_signal.is_master_signal,
            is_actionable=base_signal.is_actionable,
            position_size_pct=base_signal.position_size_pct,
            position_size_dollars=base_signal.position_size_dollars,
            risk_reward_ratio=base_signal.risk_reward_ratio,
            base_confidence=base_signal.confidence,  # Store original
        )
    
    def add_enrichment(self, module_name: str, confidence_boost: float, rationale_addition: str):
        """Add enrichment from a module"""
        self.enrichment_modules_used.append(module_name)
        self.enrichment_boost += confidence_boost
        self.confidence = min(self.base_confidence + self.enrichment_boost, 0.95)
        
        if rationale_addition:
            self.rationale += f" | {rationale_addition}"
        
        # Update position sizing based on new confidence
        if self.confidence >= 0.85:
            self.position_size_pct = 1.0  # Max conviction
        elif self.confidence >= 0.75:
            self.position_size_pct = 0.75
        else:
            self.position_size_pct = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        base_dict = {
            'symbol': self.symbol,
            'action': self.action.value if isinstance(self.action, SignalAction) else self.action,
            'signal_type': self.signal_type.value if isinstance(self.signal_type, SignalType) else self.signal_type,
            'timestamp': self.timestamp.isoformat(),
            'entry_price': self.entry_price,
            'stop_price': self.stop_price,
            'target_price': self.target_price,
            'base_confidence': self.base_confidence,
            'enriched_confidence': self.confidence,
            'enrichment_boost': self.enrichment_boost,
            'position_size_pct': self.position_size_pct,
            'risk_reward_ratio': self.risk_reward_ratio,
            'rationale': self.rationale,
            'enrichment_modules': self.enrichment_modules_used,
        }
        
        # Add enrichment data if present
        if self.crypto_sentiment:
            base_dict['crypto_btc_change'] = self.crypto_sentiment.btc_change_pct
            base_dict['crypto_environment'] = self.crypto_sentiment.environment.value
        
        if self.narrative_analysis:
            base_dict['narrative'] = self.narrative_analysis.narrative
            base_dict['catalysts'] = self.narrative_analysis.catalysts
        
        if self.options_activity:
            base_dict['options_pc_ratio'] = self.options_activity.pc_ratio
            base_dict['options_sentiment'] = self.options_activity.sentiment
        
        return base_dict


@dataclass
class EnrichmentConfig:
    """Configuration for enrichment pipeline"""
    # Module toggles
    use_narrative: bool = False  # LLM narrative agent (expensive)
    use_crypto: bool = True  # Crypto correlation (cheap, high value)
    use_sentiment: bool = False  # Alt sentiment (Twitter API required)
    use_options: bool = True  # Options flow (ChartExchange Tier 3)
    use_catalysts: bool = True  # Economic calendar (cheap)
    
    # API keys
    api_key: Optional[str] = None  # ChartExchange
    twitter_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Parameters
    crypto_lookback_minutes: int = 30
    options_lookback_minutes: int = 30
    sentiment_lookback_hours: int = 2
    
    # Thresholds
    crypto_correlation_threshold: float = 0.7  # Min correlation for confirmation
    options_unusual_size_threshold: int = 1000  # Min contracts for "unusual"
    
    # Position sizing
    max_position_size_pct: float = 1.0  # Max 1% for lottery signals

