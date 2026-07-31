"""
Canonical market regime — SINGLE SOURCE OF TRUTH.

One function, one computation, one answer. Every regime consumer — kill-shots-live,
auto-snapshot, training labels, the UI via the API payload — reads from here.

Replaces the split-brain:
  - main.py::_compute_regime (missing-key 0.0 default → manufactured CHOPPY on +1.51% day)
  - confluence_gate._get_market_regime (wall-based, correct inputs, but unreachable by API)
  - RegimeDetector.detect (yfinance 5m bars, disabled in API_LIGHT_MODE)

Authoritative detector: wall-based (the only one with correct inputs today).
  Inputs: spy_price, call_wall, put_wall, thesis_valid, bearish_breakdown_building.
  Optional enrichment: spy_change_pct (real, fetched — NEVER defaulted), vix, rsi.

Hard rules:
  - spy_change_pct is NEVER defaulted to 0.0. If it cannot be fetched, the
    change-based branches are SKIPPED, not fed a fake zero.
  - No silent UNKNOWN. Every return path carries a reason string.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── In-process cache (60s TTL) — regime is per-timestamp, not per-request ──
_CACHE_LOCK = threading.Lock()
_CACHE: dict = {"regime": None, "reason": None, "inputs": None, "ts": 0.0}
_CACHE_TTL_S = 60.0


def compute_regime(
    spy_price: Optional[float] = None,
    call_wall: Optional[float] = None,
    put_wall: Optional[float] = None,
    thesis_valid: bool = True,
    bearish_breakdown_building: bool = False,
    spy_change_pct: Optional[float] = None,
    vix: Optional[float] = None,
    rsi: Optional[float] = None,
    kc_verdict: str = "",
) -> dict:
    """
    THE regime function. Returns {"regime": str, "reason": str, "inputs": dict}.

    Priority order (wall-based detector — the only one reading correct inputs):
      1. BREAKDOWN — bearish_breakdown_building active
      2. WAR_VETO / hard macro veto → STRONG_DOWNTREND
      3. TREND_EXTENDED — spy >= call_wall
      4. CHOPPY — spy between walls with tight spread (< 12)
      5. Change-based trend (ONLY if spy_change_pct is a REAL value, never defaulted)
      6. BULLISH — default when thesis valid and none of the above
      7. UNKNOWN — no usable price from any source
    """
    inputs = {
        "spy_price": spy_price, "call_wall": call_wall, "put_wall": put_wall,
        "thesis_valid": thesis_valid, "bearish_breakdown_building": bearish_breakdown_building,
        "spy_change_pct": spy_change_pct, "vix": vix, "rsi": rsi, "kc_verdict": kc_verdict,
    }

    # 1. BREAKDOWN takes priority — wall already broken
    if bearish_breakdown_building:
        return {"regime": "BREAKDOWN", "reason": "bearish_breakdown_building active", "inputs": inputs}

    # 2. Hard macro veto
    if kc_verdict == "WAR_VETO":
        return {"regime": "STRONG_DOWNTREND", "reason": "WAR_VETO kill chain verdict", "inputs": inputs}

    if not thesis_valid:
        return {"regime": "UNKNOWN", "reason": "thesis_valid=False — cannot evaluate", "inputs": inputs}

    # 3-4. Wall-based detection (requires price + both walls)
    if spy_price and spy_price > 0 and call_wall and call_wall > 0 and put_wall and put_wall > 0:
        wall_spread = call_wall - put_wall
        if spy_price >= call_wall:
            return {"regime": "TREND_EXTENDED",
                    "reason": f"spy {spy_price:.2f} >= call_wall {call_wall:.2f}",
                    "inputs": inputs}
        if spy_price > put_wall and wall_spread < 12:
            return {"regime": "CHOPPY",
                    "reason": f"spy {spy_price:.2f} between walls {put_wall:.2f}/{call_wall:.2f}, spread {wall_spread:.2f} < 12",
                    "inputs": inputs}

    # 5. Change-based trend — ONLY with a REAL spy_change_pct (never defaulted to 0.0)
    if spy_change_pct is not None:
        chg = float(spy_change_pct)
        v = float(vix) if vix is not None else None
        r = float(rsi) if rsi is not None else None
        if v is not None and v > 28 and chg < -0.8:
            return {"regime": "STRONG_DOWNTREND", "reason": f"vix {v} > 28 and spy {chg:+.2f}% < -0.8%", "inputs": inputs}
        if v is not None and v > 22 and chg < -0.4:
            return {"regime": "DOWNTREND", "reason": f"vix {v} > 22 and spy {chg:+.2f}% < -0.4%", "inputs": inputs}
        if chg < -0.3 or (r is not None and r < 38):
            return {"regime": "DOWNTREND", "reason": f"spy {chg:+.2f}% < -0.3% or rsi {r} < 38", "inputs": inputs}
        if chg > 0.6 and r is not None and r > 62:
            return {"regime": "STRONG_UPTREND", "reason": f"spy {chg:+.2f}% > 0.6% and rsi {r} > 62", "inputs": inputs}
        if chg > 0.25 or (r is not None and r > 55):
            return {"regime": "UPTREND", "reason": f"spy {chg:+.2f}% > 0.25% or rsi {r} > 55", "inputs": inputs}
        # Genuine small move with real data
        if abs(chg) < 0.15:
            return {"regime": "CHOPPY", "reason": f"REAL small move spy {chg:+.2f}% (measured, not defaulted)", "inputs": inputs}

    # 6. No walls, no change data — but we have a price and valid thesis
    if spy_price and spy_price > 0:
        return {"regime": "BULLISH",
                "reason": "thesis valid, no wall positioning, no change data — default",
                "inputs": inputs}

    # 7. Nothing usable
    return {"regime": "UNKNOWN", "reason": "no usable price from any source", "inputs": inputs}


def get_regime(
    layers: Optional[dict] = None,
    kill_chain_result: Optional[dict] = None,
    force_refresh: bool = False,
) -> dict:
    """
    Cached accessor. Builds inputs from a kill-shots-style layers dict,
    calls compute_regime, caches for 60s.

    spy_change_pct: fetched from layers if present; if absent, fetched live
    from yfinance (2d daily closes). NEVER defaulted to 0.0 — if the fetch
    fails, it stays None and change-based branches are skipped.
    """
    now = time.time()
    with _CACHE_LOCK:
        if not force_refresh and _CACHE["regime"] and (now - _CACHE["ts"]) < _CACHE_TTL_S:
            return {"regime": _CACHE["regime"], "reason": _CACHE["reason"], "inputs": _CACHE["inputs"]}

    layers = layers or {}
    kc = kill_chain_result or {}

    spy_price = layers.get("axlfi_spot") or layers.get("gex_spot_price") or layers.get("spy_price")
    call_wall = layers.get("axlfi_call_wall")
    put_wall = layers.get("axlfi_put_wall")
    vix = layers.get("vix") or layers.get("vix_level")
    rsi = layers.get("rsi_14") or layers.get("tech_rsi")
    kc_verdict = kc.get("verdict", "")

    # spy_change_pct: real value from layers, or fetch. NEVER default to 0.0.
    spy_change_pct = layers.get("spy_change_pct") or layers.get("tech_spy_change")
    if spy_change_pct is None:
        spy_change_pct = _fetch_spy_change_pct()

    result = compute_regime(
        spy_price=spy_price, call_wall=call_wall, put_wall=put_wall,
        thesis_valid=True,  # kill-shots layers don't carry thesis state; guardian owns that
        spy_change_pct=spy_change_pct, vix=vix, rsi=rsi, kc_verdict=kc_verdict,
    )

    with _CACHE_LOCK:
        _CACHE.update({"regime": result["regime"], "reason": result["reason"],
                       "inputs": result["inputs"], "ts": now})
    return result


def _fetch_spy_change_pct() -> Optional[float]:
    """
    Fetch real SPY daily change from yfinance (2d daily closes).
    Returns None on any failure — NEVER 0.0. A missing value must skip
    change-based branches, not manufacture a fake flat day.
    """
    try:
        import yfinance as yf
        hist = yf.Ticker("SPY").history(period="2d", interval="1d")
        if len(hist) >= 2:
            chg = (hist["Close"].iloc[-1] - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2] * 100
            return round(float(chg), 4)
        return None
    except Exception as e:
        logger.warning(f"⚠️ regime_state: spy_change_pct fetch failed (staying None): {e}")
        return None


def invalidate_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.update({"regime": None, "reason": None, "inputs": None, "ts": 0.0})
