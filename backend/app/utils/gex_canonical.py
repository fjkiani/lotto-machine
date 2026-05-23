"""
Canonical GEX (gamma exposure) — single calculator path for the whole backend.

All modules that need GEX must use `compute_canonical_gex()` so `/api/v1/gamma/SPY`,
`compute_kill_chain()`, KillChainEngine, and DarkPoolTrend agree on the same number.

Policy: use **SPY** (and per-ETF symbol for QQQ/IWM) — not SPX as a stand-in for SPY.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

_calc_lock = threading.Lock()
_gex_calculator = None


def get_gex_calculator_singleton():
    """Shared GEXCalculator — same instance as `/api/v1/gamma` and Kill Chain."""
    global _gex_calculator
    if _gex_calculator is None:
        with _calc_lock:
            if _gex_calculator is None:
                from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator

                _gex_calculator = GEXCalculator(cache_ttl=300)
    return _gex_calculator


def compute_canonical_gex(symbol: str = "SPY"):
    """
    Run GEXCalculator.compute_gex once per shared singleton.
    Returns the raw result object (spot_price, total_gex, gamma_regime, gamma_walls, ...).
    """
    sym = (symbol or "SPY").upper()
    calc = get_gex_calculator_singleton()
    return calc.compute_gex(sym)


def canonical_gex_as_dict(symbol: str = "SPY") -> Dict[str, Any]:
    """Flat dict for JSON / signal payloads — matches /api/v1/gamma/{symbol} semantics."""
    r = compute_canonical_gex(symbol)
    top_wall = r.gamma_walls[0].strike if r.gamma_walls else None
    return {
        "symbol": symbol.upper(),
        "net_gex": r.total_gex,
        "total_gex": r.total_gex,
        "gamma_regime": r.gamma_regime,
        "gamma_flip": r.gamma_flip,
        "max_pain": r.max_pain,
        "spot_price": r.spot_price,
        "top_wall": top_wall,
    }


def canonical_gex_narrative(symbol: str = "SPY") -> str:
    calc = get_gex_calculator_singleton()
    return calc.get_narrative(symbol.upper())


def build_kill_chain_scan_gex_layer(symbol: str = "SPY") -> Dict[str, Any]:
    """
    GEX blob for 5-layer /killchain/scan — same numbers as GET /api/v1/gamma/{symbol}
    and compute_kill_chain layer_2 (fixes split-brain vs KillChainEngine narrative).
    """
    sym = (symbol or "SPY").upper()
    r = compute_canonical_gex(sym)
    return {
        "spot_price": r.spot_price,
        "total_gex": r.total_gex,
        "gamma_regime": r.gamma_regime,
        "gamma_flip": r.gamma_flip,
        "max_pain": r.max_pain,
        "gamma_walls": [
            {"strike": w.strike, "gex": w.gex, "signal": w.signal}
            for w in (r.gamma_walls or [])[:5]
        ],
        "negative_zones": [
            {"strike": z.strike, "gex": z.gex}
            for z in (r.negative_zones or [])[:3]
        ],
        "narrative": canonical_gex_narrative(sym),
        "gex_symbol": sym,
        "gex_source": "canonical_spy",
        "total_gex_raw": r.total_gex,
        "total_gex_millions": round(r.total_gex / 1e6, 3) if r.total_gex else 0.0,
    }
