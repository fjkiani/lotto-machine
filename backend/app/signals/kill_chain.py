"""
Kill Chain scorer — computes a multi-layer confluence score + market direction.

Direction is derived from actual data signals, NOT hardcoded.

Returned dict shape:
    {
        "score": int,           # 0-10+
        "verdict": str,         # BOOST | NEUTRAL | SOFT_VETO | HARD_VETO
        "direction": str,       # BULLISH | BEARISH | MIXED
        "confluence": str,      # TRIPLE | DOUBLE | SINGLE | WAITING
        "bearish_points": int,
        "bullish_points": int,
        "layer_1": dict,        # COT Divergence
        "layer_2": dict,        # GEX Regime
        "layer_3": dict,        # DVR / Short-Vol Ratio
        "position": dict,       # entry_price, current_pnl, activated_at
        "layers": dict,         # raw debug info
        "errors": bool,
    }
"""
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_kc_cache: Dict[str, Any] = {"data": None, "ts": 0}
_kc_lock = threading.Lock()
# 15-minute TTL — COT is weekly, GEX changes hourly. Reduce cold-start stampede risk.
_CACHE_TTL = 900

# ── Module-level client singletons — shared across ALL callers ────────────────
# (compute_kill_chain is called from /kill-chain, /signals/master, /killchain/scan)
# Creating a new COTClient or GEXCalculator per-call means N concurrent callers
# each trigger an independent CFTC download + yfinance options chain fetch = OOM.
_cot_client = None
_gex_client = None
_client_init_lock = threading.Lock()


def _get_cot_client():
    """Lazy singleton COTClient — one download shared across all callers."""
    global _cot_client
    if _cot_client is None:
        with _client_init_lock:
            if _cot_client is None:
                from live_monitoring.enrichment.apis.cot_client import COTClient
                _cot_client = COTClient(cache_ttl=3600)
    return _cot_client


def _get_gex_client():
    """Lazy singleton GEXCalculator — one options chain download shared across all callers."""
    global _gex_client
    if _gex_client is None:
        with _client_init_lock:
            if _gex_client is None:
                from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
                _gex_client = GEXCalculator(cache_ttl=300)
    return _gex_client


# 🔥 OOM FIX: BrainManager singleton — prevents fresh LLM/Tavily sessions per call
_brain_manager = None

def _get_brain_manager():
    """Lazy singleton BrainManager — one instance shared across compute_kill_chain() calls."""
    global _brain_manager
    if _brain_manager is None:
        with _client_init_lock:
            if _brain_manager is None:
                from live_monitoring.core.brain_manager import BrainManager
                _brain_manager = BrainManager()
    return _brain_manager

# ── State file path ───────────────────────────────────────────────────────────
_STATE_PATH = Path(__file__).resolve().parents[3] / "live_monitoring" / "data" / "kill_chain" / "kill_chain_state.json"


def _load_state() -> dict:
    """Load kill chain state from disk. Returns defaults if missing."""
    default = {
        "triple_active": False,
        "last_check": None,
        "spy_price": 0.0,
        "position": {
            "entry_price": 0.0,
            "activated_at": None,
            "current_pnl": 0.0,
        },
    }
    try:
        if _STATE_PATH.exists():
            with open(_STATE_PATH) as f:
                data = json.load(f)
            # Back-fill position block if state pre-dates this schema
            if "position" not in data:
                data["position"] = default["position"]
            return data
    except Exception as e:
        logger.warning(f"Could not load kill chain state: {e}")
    return default


def _save_state(state: dict) -> None:
    """Persist kill chain state to disk."""
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Could not save kill chain state: {e}")


def compute_kill_chain() -> dict:
    """Compute the kill chain score with real directional bias.

    Caches for 15 minutes. Uses a threading lock to prevent cache stampedes —
    on a cold-start pod, concurrent requests would all independently download
    COT data and call BrainManager LLM simultaneously (OOM risk).
    """
    now = time.time()
    # Fast path — check outside lock first to avoid contention on warm cache
    if _kc_cache["data"] and (now - _kc_cache["ts"]) < _CACHE_TTL:
        return _kc_cache["data"]

    with _kc_lock:
        # Re-check after acquiring lock — another thread may have computed it
        now = time.time()
        if _kc_cache["data"] and (now - _kc_cache["ts"]) < _CACHE_TTL:
            return _kc_cache["data"]

        bullish_pts = 0
        bearish_pts = 0
        raw: Dict[str, Any] = {}
        signals: List[Dict[str, Any]] = []

        # ── Variables surfaced for structured layer output ────────────────────────
        es_specs: int = 0
        regime: str = ""
        total_gex: float = 0.0
        sv_pct: float = 50.0
        current_spot: float = 0.0

        # ── Brain Manager (insider / politician divergence — boosts score only) ───
        try:
            brain = _get_brain_manager().get_report(use_cache=True)  # 🔥 OOM FIX: singleton
            if brain:
                boost = brain.get("divergence_boost", 0)
                brain_direction = str(brain.get("direction", "NEUTRAL")).upper()
                raw["brain_boost"] = boost
                raw["brain_direction"] = brain_direction
                if "BEAR" in brain_direction:
                    bearish_pts += boost
                else:
                    bullish_pts += boost
        except Exception as exc:
            raw["brain_error"] = str(exc)

        # ── Layer 1 — COT Divergence ──────────────────────────────────────────────
        try:
            cot = _get_cot_client().get_divergence_signal("ES")
            if cot:
                es_specs = cot.get("specs_net", 0)
                comms = cot.get("comm_net", 0)
                divergent = cot.get("divergent", False)
                raw["cot_specs_net"] = es_specs
                raw["cot_comm_net"] = comms
                raw["cot_divergent"] = divergent

                if divergent and es_specs < -100_000 and comms > 50_000:
                    bullish_pts += 3
                    raw["cot_signal"] = "EXTREME_DIVERGENCE → BULLISH"
                    signals.append({
                        "id": f"cot-extreme-div-{datetime.utcnow().strftime('%Y-%m-%d')}",
                        "source": "COT",
                        "type": "BULLISH",
                        "strength": "HIGH",
                        "headline": f"Specs net short {es_specs:,} contracts",
                        "detail": "Major smart-money divergence setup. Retail is trapped short.",
                        "data": {"spec_net": es_specs, "comm_net": comms, "side": "SHORT"}
                    })
                elif divergent and es_specs < -50_000 and comms > 25_000:
                    bullish_pts += 1
                    raw["cot_signal"] = "MODERATE_DIVERGENCE → BULLISH"
                    signals.append({
                        "id": f"cot-mod-div-{datetime.utcnow().strftime('%Y-%m-%d')}",
                        "source": "COT",
                        "type": "BULLISH",
                        "strength": "MEDIUM",
                        "headline": f"Specs net short {es_specs:,} contracts",
                        "detail": "Mild divergence. Commercials buying into spec shorts.",
                        "data": {"spec_net": es_specs, "comm_net": comms, "side": "SHORT"}
                    })
                elif es_specs < -50_000 and not divergent:
                    bearish_pts += 1
                    raw["cot_signal"] = "SPEC_SHORTS_NO_DIVERGENCE → BEARISH"
                    signals.append({
                        "id": f"cot-spec-short-{datetime.utcnow().strftime('%Y-%m-%d')}",
                        "source": "COT",
                        "type": "BEARISH",
                        "strength": "MEDIUM",
                        "headline": f"Specs net short {es_specs:,} contracts",
                        "detail": "Spec trap loaded — squeeze fuel if market rallies, but currently bearish.",
                        "data": {"spec_net": es_specs, "side": "SHORT"}
                    })
                else:
                    raw["cot_signal"] = "NEUTRAL"
        except Exception as exc:
            raw["cot_error"] = str(exc)

        # ── Layer 2 — GEX Regime + Layer 3 DVR (Short-Vol) ───────────────────────
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

            gex_calc = _get_gex_client()
            gex_result = gex_calc.compute_gex("SPX")
            regime = gex_result.gamma_regime or ""
            total_gex = gex_result.total_gex
            current_spot = gex_result.spot_price or 0.0

            try:
                sg = StockgridClient()
                sv_pct = sg.get_short_volume_pct("SPY") or 50.0
            except Exception:
                pass

            raw["gex_regime"] = regime
            raw["gex_total"] = total_gex
            raw["sv_pct"] = sv_pct

            if "NEGATIVE" in regime and abs(total_gex) > 1e6:
                if sv_pct > 55:
                    bearish_pts += 2
                    raw["gex_signal"] = "NEG_GEX + HIGH_SV → BEARISH AMPLIFIER"
                    signals.append({
                        "id": f"gex-gravity-{datetime.utcnow().strftime('%Y-%m-%d')}",
                        "source": "GEX",
                        "type": "BEARISH",
                        "strength": "HIGH",
                        "headline": f"NEGATIVE gamma · spot ${current_spot:.2f}",
                        "detail": "Gravitational pull downwards. Dealers short options, amplifying moves.",
                        "data": {"spot": current_spot, "total_gex": round(total_gex/1e6, 2), "sv_pct": sv_pct}
                    })
                else:
                    bullish_pts += 1
                    raw["gex_signal"] = "NEG_GEX + NEUTRAL_SV → SNAP_BACK_RISK"
                    signals.append({
                        "id": f"gex-snapback-{datetime.utcnow().strftime('%Y-%m-%d')}",
                        "source": "GEX",
                        "type": "BULLISH",
                        "strength": "MEDIUM",
                        "headline": "NEGATIVE gamma but neutral short-vol",
                        "detail": "Snap-back risk is high. Market is compressed but not panicked.",
                        "data": {"spot": current_spot, "total_gex": round(total_gex/1e6, 2), "sv_pct": sv_pct}
                    })
            elif "POSITIVE" in regime:
                bullish_pts += 1
                raw["gex_signal"] = "POS_GEX → VOLATILITY SUPPRESSED (BULLISH BIAS)"
                signals.append({
                    "id": f"gex-suppression-{datetime.utcnow().strftime('%Y-%m-%d')}",
                    "source": "GEX",
                    "type": "BULLISH",
                    "strength": "LOW",
                    "headline": "POSITIVE gamma regime",
                    "detail": "Volatility suppressed. Dealers buying dips and selling rips.",
                    "data": {"spot": current_spot, "total_gex": round(total_gex/1e6, 2)}
                })
            else:
                raw["gex_signal"] = "NEUTRAL"
        except Exception as exc:
            raw["gex_error"] = str(exc)

        # ── Structured layer output ──────────────────────────────────────────────
        layer_1_triggered = es_specs < -50_000
        layer_2_triggered = "NEGATIVE" in regime
        layer_3_triggered = sv_pct > 55.0

        layer_1 = {
            "name": "COT Divergence",
            "triggered": layer_1_triggered,
            "value": es_specs,
            "unit": "Specs Net",
            "signal": "CROWDED_SHORT" if layer_1_triggered else "NEUTRAL",
        }
        layer_2 = {
            "name": "GEX Regime",
            "triggered": layer_2_triggered,
            "value": round(total_gex / 1e6, 3),
            "unit": "GEX $M",
            "signal": regime if regime else "NEUTRAL",
        }
        layer_3 = {
            "name": "DVR",
            "triggered": layer_3_triggered,
            "value": sv_pct,
            "unit": "Short Vol %",
            "signal": "PANIC_THRESHOLD" if layer_3_triggered else "WATCHING",
        }

        # ── Confluence label ─────────────────────────────────────────────────────
        triggered_count = sum([layer_1_triggered, layer_2_triggered, layer_3_triggered])
        if triggered_count == 3:
            confluence = "TRIPLE"
        elif triggered_count == 2:
            confluence = "DOUBLE"
        elif triggered_count == 1:
            confluence = "SINGLE"
        else:
            confluence = "WAITING"

        # ── Final score and verdict ───────────────────────────────────────────────
        total_score = bullish_pts + bearish_pts

        if bullish_pts > bearish_pts + 1:
            direction = "BULLISH"
        elif bearish_pts > bullish_pts + 1:
            direction = "BEARISH"
        else:
            direction = "MIXED"

        from .verdict_utils import compute_verdict
        verdict, _, _ = compute_verdict(total_score)

        # ── Position / P&L state ─────────────────────────────────────────────────
        state = _load_state()
        was_active = state.get("triple_active", False)
        is_now_active = triggered_count >= 2  # Armed on DOUBLE or TRIPLE

        newly_activated = is_now_active and not was_active
        deactivated = not is_now_active and was_active

        position = state.get("position", {"entry_price": 0.0, "activated_at": None, "current_pnl": 0.0})

        if newly_activated and position.get("entry_price", 0) == 0 and current_spot > 0:
            position["entry_price"] = round(current_spot, 2)
            position["activated_at"] = datetime.utcnow().isoformat()
            position["current_pnl"] = 0.0
            logger.info(f"⚔️ Kill chain ACTIVATED — entry ${position['entry_price']}")

        elif is_now_active and position.get("entry_price", 0) > 0 and current_spot > 0:
            ep = position["entry_price"]
            pnl = ((current_spot - ep) / ep) * 100
            position["current_pnl"] = round(pnl, 2)

        if deactivated:
            logger.info(f"🔓 Kill chain DEACTIVATED — final P&L: {position.get('current_pnl', 0):.2f}%")
            position = {"entry_price": 0.0, "activated_at": None, "current_pnl": 0.0}

        state["triple_active"] = is_now_active
        state["last_check"] = datetime.utcnow().isoformat()
        state["spy_price"] = round(current_spot, 2) if current_spot else state.get("spy_price", 0.0)
        state["position"] = position
        _save_state(state)

        # ── Final result ──────────────────────────────────────────────────────────
        result = {
            "score": total_score,
            "verdict": verdict,
            "direction": direction,
            "confluence": confluence,
            "triggered_count": triggered_count,
            "armed": is_now_active,
            "bullish_points": bullish_pts,
            "bearish_points": bearish_pts,
            "layer_1": layer_1,
            "layer_2": layer_2,
            "layer_3": layer_3,
            "position": position,
            "signals": signals,
            "layers": raw,
            "errors": any("error" in k for k in raw),
        }

        _kc_cache["data"] = result
        _kc_cache["ts"] = time.time()
        return result

