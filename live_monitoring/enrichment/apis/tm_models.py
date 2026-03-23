"""
tm_models.py — Trap Matrix Data Models
========================================

Single source of truth for all Trap Matrix dataclasses.
No business logic. No imports beyond stdlib.

Imported by:
  tm_layer_fetcher.py  → builds these
  tm_trap_classifier.py → reads these
  tm_state_differ.py   → diffs these
  trap_matrix_orchestrator.py → assembles these
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List


# ─── Trap Zone ───────────────────────────────────────────────────────────────

@dataclass
class TrapZone:
    """A classified trap zone with conviction score (1-5)."""
    trap_type: str       # BULL_TRAP | BEAR_TRAP_COIL | CEILING_TRAP | LIQUIDITY_TRAP | DEATH_CROSS_TRAP | WAR_HEADLINE
    price_min: float
    price_max: float
    conviction: int      # 1-5
    narrative: str       # One-line institutional narrative
    data_point: str      # Key supporting stat (e.g. "COT: -168K Short")
    supporting_sources: List[str] = field(default_factory=list)
    emoji: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.trap_type,
            "price_min": round(self.price_min, 2),
            "price_max": round(self.price_max, 2),
            "conviction": self.conviction,
            "narrative": self.narrative,
            "data_point": self.data_point,
            "supporting_sources": self.supporting_sources,
            "emoji": self.emoji,
        }


# ─── Staleness ───────────────────────────────────────────────────────────────

@dataclass
class StalenessInfo:
    """Per-source data freshness tracking."""
    source: str
    age_seconds: float
    stale: bool
    last_updated: str

    def to_dict(self) -> dict:
        age_str = (
            f"{self.age_seconds / 60:.0f}min" if self.age_seconds < 3600
            else f"{self.age_seconds / 3600:.1f}h"
        )
        return {
            "age": age_str,
            "stale": self.stale,
            "last_updated": self.last_updated,
        }


# ─── Market State ─────────────────────────────────────────────────────────────

@dataclass
class MarketState:
    """
    Unified market state — the orchestrator's output artifact.

    Built by tm_layer_fetcher.py (data),
    enriched by tm_trap_classifier.py (traps + alert),
    diffed by tm_state_differ.py (rebuild decision).
    """
    symbol: str
    current_price: float = 0.0
    timestamp: str = ""

    # ── Levels ──
    dp_levels: list = field(default_factory=list)
    dp_position_dollars: float = 0.0  # Total DP position from Stockgrid (e.g. 35_007_000_000)
    gex_walls: list = field(default_factory=list)
    gamma_flip: Optional[float] = None
    max_pain: Optional[float] = None
    pivots: dict = field(default_factory=dict)
    moving_averages: dict = field(default_factory=dict)
    vwap: Optional[float] = None

    # ── Traps ──
    traps: List[TrapZone] = field(default_factory=list)

    # ── Context ──
    cot_net_spec: Optional[int] = None
    cot_signal: str = ""
    gamma_regime: str = "UNKNOWN"
    vix: Optional[float] = None
    vix_regime: str = "UNKNOWN"
    death_cross: bool = False
    alert_level: str = "GREEN"

    # ── Meta ──
    staleness: Dict[str, StalenessInfo] = field(default_factory=dict)
    rebuild_reason: str = ""
    version: int = 0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "current_price": round(self.current_price, 2),
            "timestamp": self.timestamp,
            "levels": {
                "dp_levels": self.dp_levels,
                "gex_walls": self.gex_walls,
                "gamma_flip": round(self.gamma_flip, 2) if self.gamma_flip else None,
                "max_pain": round(self.max_pain, 2) if self.max_pain else None,
                "pivots": self.pivots,
                "moving_averages": self.moving_averages,
                "vwap": round(self.vwap, 2) if self.vwap else None,
            },
            "traps": [t.to_dict() for t in self.traps],
            "context": {
                "cot_net_spec": self.cot_net_spec,
                "cot_signal": self.cot_signal,
                "gamma_regime": self.gamma_regime,
                "vix": round(self.vix, 2) if self.vix else None,
                "vix_regime": self.vix_regime,
                "death_cross": self.death_cross,
                "alert_level": self.alert_level,
            },
            "staleness": {k: v.to_dict() for k, v in self.staleness.items()},
            "rebuild_reason": self.rebuild_reason,
            "version": self.version,
        }
