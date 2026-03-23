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

        # ── Variables surfaced for structured layer output ────────────────────────
        es_specs: int = 0
        regime: str = ""
        total_gex: float = 0.0
        sv_pct: float = 50.0
        current_spot: float = 0.0

        # ── Brain Manager (insider / politician divergence — boosts score only) ───
        try:
            from live_monitoring.core.brain_manager import BrainManager
            brain = BrainManager().get_report(use_cache=True)
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
            from live_monitoring.enrichment.apis.cot_client import COTClient
            cot = COTClient(cache_ttl=3600).get_divergence_signal("ES")
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
                elif divergent and es_specs < -50_000 and comms > 25_000:
                    bullish_pts += 1
                    raw["cot_signal"] = "MODERATE_DIVERGENCE → BULLISH"
                elif es_specs < -50_000 and not divergent:
                    bearish_pts += 1
                    raw["cot_signal"] = "SPEC_SHORTS_NO_DIVERGENCE → BEARISH"
                else:
                    raw["cot_signal"] = "NEUTRAL"
        except Exception as exc:
            raw["cot_error"] = str(exc)

        # ── Layer 2 — GEX Regime + Layer 3 DVR (Short-Vol) ───────────────────────
        try:
            from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

            gex_calc = GEXCalculator(cache_ttl=300)
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
                else:
                    bullish_pts += 1
                    raw["gex_signal"] = "NEG_GEX + NEUTRAL_SV → SNAP_BACK_RISK"
            elif "POSITIVE" in regime:
                bullish_pts += 1
                raw["gex_signal"] = "POS_GEX → VOLATILITY SUPPRESSED (BULLISH BIAS)"
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
            "layers": raw,
            "errors": any("error" in k for k in raw),
        }

        _kc_cache["data"] = result
        _kc_cache["ts"] = time.time()
        return result

