"""
Data models for anomaly detection
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any

@dataclass
class MarketTick:
    """Single market data point"""
    timestamp: datetime
    ticker: str
    price: float
    volume: int
    trade_size: Optional[int] = None
    is_dark_pool: bool = False
    exchange: Optional[str] = None

@dataclass
class NewsEvent:
    """News/headline event"""
    timestamp: datetime
    ticker: Optional[str]
    headline: str
    source: str
    sentiment_score: Optional[float] = None

@dataclass
class OptionsFlow:
    """Options flow data"""
    timestamp: datetime
    ticker: str
    strike: float
    expiration: str
    contract_type: str  # 'call' or 'put'
    volume: int
    open_interest: int
    price: float
    is_sweep: bool = False

@dataclass
class AnomalyEvent:
    """Detected anomaly event"""
    timestamp: datetime
    ticker: str
    anomaly_type: str
    severity: float  # 0-1 scale
    details: Dict[str, Any]
    conviction_score: float = 0.0

@dataclass
class ClusterEvent:
    """Composite anomaly cluster"""
    timestamp: datetime
    ticker: str
    events: List[AnomalyEvent]
    cluster_score: float
    conviction_level: str  # 'low', 'medium', 'high', 'critical'
    details: Dict[str, Any]



