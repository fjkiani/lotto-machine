"""
Signal Pydantic models — shared across router and sources.
"""
from typing import List, Optional
from pydantic import BaseModel


class SignalResponse(BaseModel):
    """Single actionable signal."""
    id: str
    symbol: str
    type: str
    action: str               # LONG | SHORT | WATCH | AVOID
    confidence: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    reasoning: List[str]
    warnings: List[str]
    timestamp: str
    source: str
    is_master: bool
    position_size_pct: Optional[float] = None
    position_size_dollars: Optional[float] = None
    technical_context: Optional[dict] = None
    kill_chain_verdict: Optional[str] = None
    kill_chain_score: Optional[int] = None


class DivergenceSignal(BaseModel):
    """DP Divergence or Confluence signal."""
    symbol: str
    signal_type: str          # DP_CONFLUENCE or OPTIONS_DIVERGENCE
    direction: str            # LONG or SHORT
    confidence: float
    entry_price: float
    stop_pct: float
    target_pct: float
    reasoning: str
    dp_bias: str
    dp_strength: float
    has_divergence: bool
    options_bias: Optional[str] = None


class DivergenceResponse(BaseModel):
    """Response for /signals/divergence."""
    signals: List[DivergenceSignal]
    count: int
    dp_edge_stats: dict
    timestamp: str
