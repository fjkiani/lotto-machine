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


def _gex_from_axlfi_walls(symbol: str = "SPY"):
    """
    Build a GEXResult-compatible object from AXLFI /options/walls (dark-pool API).
    Used when CBOE is unavailable — walls are the linked institutional gamma source.
    """
    from live_monitoring.enrichment.apis.gex_calculator import GEXResult, GammaWall
    from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

    sg = StockgridClient(cache_ttl=300)
    walls_payload = sg.get_option_walls(symbol)
    today = sg.get_option_walls_today(symbol)
    if not walls_payload or not today:
        return None

    spot = float(walls_payload.get("spot") or 0)
    raw = walls_payload.get("_raw") or {}
    nearest = None
    for exp in raw.get("expiries") or []:
        if isinstance(exp, dict) and exp.get("walls"):
            nearest = exp
            break
    balance = 0.0
    call_total = 0.0
    put_total = 0.0
    if nearest:
        w = nearest.get("walls") or {}
        balance = float(w.get("balance_pct") or 0)
        call_total = float(w.get("call_total") or 0)
        put_total = float(w.get("put_total") or 0)

    # Map AXLFI balance to a signed notional proxy (millions → absolute scale)
    total_gex = balance * 1_000_000  # positive = call-heavy / dealer long-ish
    regime = "POSITIVE" if balance >= 0 else "NEGATIVE"

    gamma_walls = []
    for strike, label in (
        (today.call_wall, "RESISTANCE"),
        (today.call_wall_2, "RESISTANCE"),
        (today.call_wall_3, "RESISTANCE"),
    ):
        if strike:
            gamma_walls.append(GammaWall(strike=float(strike), gex=abs(call_total) * 1e6, signal=label))

    negative_zones = []
    for strike, label in (
        (today.put_wall, "SUPPORT"),
        (today.put_wall_2, "SUPPORT"),
        (today.put_wall_3, "SUPPORT"),
    ):
        if strike:
            negative_zones.append(
                GammaWall(strike=float(strike), gex=-abs(put_total) * 1e6, signal=label)
            )

    return GEXResult(
        ticker=symbol.upper(),
        spot_price=spot,
        total_gex=total_gex,
        gamma_regime=regime,
        gamma_flip=float(today.poc or 0) or None,
        max_pain=float(today.poc or 0),
        gamma_walls=gamma_walls,
        negative_zones=negative_zones,
        total_contracts=0,
        total_calls=int(call_total * 1000) if call_total else 0,
        total_puts=int(put_total * 1000) if put_total else 0,
        timestamp=str(walls_payload.get("as_of_date") or ""),
        source="axlfi_option_walls",
    )


def compute_canonical_gex(symbol: str = "SPY"):
    """
    Prefer CBOE calculator; fall back to AXLFI option walls (dark-pool API)
    when CBOE returns empty/errors. Walls are the linked gamma source.
    """
    sym = (symbol or "SPY").upper()
    try:
        calc = get_gex_calculator_singleton()
        result = calc.compute_gex(sym)
        if result and getattr(result, "spot_price", 0):
            return result
    except Exception:
        pass

    axlfi = _gex_from_axlfi_walls(sym)
    if axlfi and axlfi.spot_price:
        return axlfi

    # Last resort: empty CBOE-shaped result (callers already handle spot==0)
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
