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
from typing import Dict, Any, Optional, List

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
    """Load kill chain state from Supabase (primary) or disk (fallback)."""
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
    # Try Supabase first
    try:
        import os as _os
        _url = _os.getenv("SUPABASE_URL")
        _key = _os.getenv("SUPABASE_KEY") or _os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if _url and _key:
            from supabase import create_client as _create_client
            _sb = _create_client(_url, _key)
            _res = _sb.table("kill_chain_state").select("state").eq("id", 1).execute()
            if _res.data:
                _state = _res.data[0].get("state", default)
                if "position" not in _state:
                    _state["position"] = default["position"]
                return _state
    except Exception as e:
        logger.warning(f"Supabase state load failed, using disk: {e}")
    # Disk fallback
    try:
        if _STATE_PATH.exists():
            with open(_STATE_PATH) as f:
                data = json.load(f)
            if "position" not in data:
                data["position"] = default["position"]
            return data
    except Exception as e:
        logger.warning(f"Could not load kill chain state: {e}")
    return default


def _save_state(state: dict) -> None:
    """Persist kill chain state to disk + Supabase."""
    # Disk (always attempt — fast, local)
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE_PATH, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.warning(f"Disk state save failed: {e}")
    # Supabase upsert (best-effort — don't crash if unavailable)
    try:
        import os as _os
        _url = _os.getenv("SUPABASE_URL")
        _key = _os.getenv("SUPABASE_KEY") or _os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if _url and _key:
            from supabase import create_client as _create_client
            _sb = _create_client(_url, _key)
            _sb.table("kill_chain_state").upsert(
                {"id": 1, "state": state, "updated_at": datetime.utcnow().isoformat()}
            ).execute()
    except Exception as e:
        logger.warning(f"Supabase state save failed: {e}")


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

        # ── Politician Cluster Boost ─────────────────────────────────────────────
        try:
            if brain:
                _pol_cluster = brain.get("politician_cluster", 0)
                _pol_buys = brain.get("politician_buys", 0)
                _pol_details = brain.get("politician_details", [])
                _pol_tickers = [
                    d.get("ticker") for d in _pol_details
                    if d.get("type") == "buy" and not d.get("is_routine")
                ]
                raw["politician_cluster"] = _pol_cluster
                raw["politician_tickers"] = _pol_tickers
                if _pol_cluster >= 3 and _pol_buys > 0:
                    bullish_pts += 2
                    raw["politician_signal"] = f"CLUSTER_BUY: {_pol_cluster} politicians buying"
                elif _pol_cluster >= 2 and _pol_buys > 0:
                    bullish_pts += 1
                    raw["politician_signal"] = f"DUAL_BUY: {_pol_cluster} politicians buying"
                else:
                    raw["politician_signal"] = "NONE"
        except Exception as _exc:
            raw["politician_error"] = str(_exc)

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
            # Use SPY consistently across the stack so kill-chain, /gamma/SPY,
            # and /brief/master share the same notional base and magnitude.
            gex_result = gex_calc.compute_gex("SPY")
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
                        "data": {
                            "symbol": "SPY",
                            "spot": current_spot,
                            "total_gex_millions": round(total_gex / 1e6, 2),
                            "total_gex_raw": total_gex,
                            "sv_pct": sv_pct
                        }
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
                        "data": {
                            "symbol": "SPY",
                            "spot": current_spot,
                            "total_gex_millions": round(total_gex / 1e6, 2),
                            "total_gex_raw": total_gex,
                            "sv_pct": sv_pct
                        }
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
                    "data": {
                        "symbol": "SPY",
                        "spot": current_spot,
                        "total_gex_millions": round(total_gex / 1e6, 2),
                        "total_gex_raw": total_gex
                    }
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
            "raw_value": total_gex,
            "symbol": "SPY",
            "signal": regime if regime else "NEUTRAL",
        }
        layer_3 = {
            "name": "DVR",
            "triggered": layer_3_triggered,
            "value": sv_pct,
            "unit": "Short Vol %",
            "signal": "PANIC_THRESHOLD" if layer_3_triggered else "WATCHING",
        }

        # ── Layer 4 — AXLFI Wall Position ───────────────────────────────────────
        axlfi_wall_triggered = False
        axlfi_wall_signal = "NEUTRAL"
        _pts_above_call = None
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient as _SGClient
            _sg = _SGClient(cache_ttl=300)
            _walls = _sg.get_option_walls_today("SPY")
            if _walls and current_spot > 0:
                _call_wall = getattr(_walls, 'call_wall', None) or 0
                _put_wall = getattr(_walls, 'put_wall', None) or 0
                raw["axlfi_call_wall"] = _call_wall
                raw["axlfi_put_wall"] = _put_wall
                raw["axlfi_spot"] = current_spot
                _pts_above_call = round(current_spot - _call_wall, 2) if _call_wall else None
                raw["pts_above_call_wall"] = _pts_above_call

                if _call_wall > 0 and abs(current_spot - _call_wall) / _call_wall < 0.005:
                    # AT call wall = resistance zone (bearish)
                    bearish_pts += 2
                    axlfi_wall_triggered = True
                    axlfi_wall_signal = "AT_CALL_WALL"
                    raw["axlfi_signal"] = "AT_CALL_WALL"
                elif _call_wall > 0 and current_spot > _call_wall:
                    # ABOVE call wall = breakout, squeeze fuel (bullish)
                    bullish_pts += 1
                    axlfi_wall_triggered = True
                    axlfi_wall_signal = "ABOVE_CALL_WALL"
                    raw["axlfi_signal"] = "ABOVE_CALL_WALL"
                elif _put_wall > 0 and abs(current_spot - _put_wall) / _put_wall < 0.005:
                    # AT put wall = support zone (bullish)
                    bullish_pts += 2
                    axlfi_wall_triggered = True
                    axlfi_wall_signal = "AT_PUT_WALL"
                    raw["axlfi_signal"] = "AT_PUT_WALL"
                elif _put_wall > 0 and current_spot < _put_wall:
                    # BELOW put wall = breakdown (bearish)
                    bearish_pts += 1
                    axlfi_wall_triggered = True
                    axlfi_wall_signal = "BELOW_PUT_WALL"
                    raw["axlfi_signal"] = "BELOW_PUT_WALL"
                else:
                    axlfi_wall_signal = "BETWEEN_WALLS"
                    raw["axlfi_signal"] = "BETWEEN_WALLS"
        except Exception as _exc:
            raw["axlfi_error"] = str(_exc)

        layer_4 = {
            "name": "AXLFI Wall Position",
            "triggered": axlfi_wall_triggered,
            "value": current_spot,
            "unit": "SPY Price",
            "signal": axlfi_wall_signal,
            "pts_above_call_wall": _pts_above_call,
        }

        # ── Layer 5 — QQQ Reshort Spike ─────────────────────────────────────────
        qqq_reshort_triggered = False
        qqq_sv_delta = None
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient as _SGClient5
            from concurrent.futures import ThreadPoolExecutor as _TPE5, TimeoutError as _TE5
            _sg5 = _SGClient5(cache_ttl=300)
            with _TPE5(max_workers=1) as _pool5:
                _qqq_fut5 = _pool5.submit(_sg5.get_ticker_detail_raw, "QQQ")
                try:
                    _qqq_raw5 = _qqq_fut5.result(timeout=6)
                    if _qqq_raw5:
                        _sv_table5 = _qqq_raw5.get("individual_short_volume_table", {})
                        _sv_items5 = _sv_table5.get("data", []) if isinstance(_sv_table5, dict) else _sv_table5
                        if _sv_items5 and len(_sv_items5) >= 2:
                            _sv_sorted5 = sorted(_sv_items5, key=lambda x: x.get("date", "") if isinstance(x, dict) else "")
                            def _sv_val5(row):
                                v = float(row.get("short_volume_pct", row.get("short_volume%", row.get("short_volume_percent", 0))) or 0)
                                return v if v > 1.0 else v * 100.0
                            _qqq_latest5 = round(_sv_val5(_sv_sorted5[-1]), 1)
                            _qqq_prev5 = round(_sv_val5(_sv_sorted5[-2]), 1)
                            qqq_sv_delta = round(_qqq_latest5 - _qqq_prev5, 1)
                            raw["qqq_sv_delta"] = qqq_sv_delta
                            raw["qqq_sv_latest"] = _qqq_latest5
                            # Reshort spike: QQQ SV up >10pp AND SPY above call wall
                            if qqq_sv_delta > 10 and axlfi_wall_signal in ("ABOVE_CALL_WALL", "AT_CALL_WALL"):
                                qqq_reshort_triggered = True
                                bullish_pts += 2  # squeeze fuel
                                raw["qqq_reshort_spike"] = True
                                raw["qqq_reshort_note"] = f"QQQ SV +{qqq_sv_delta}pp in 1d while SPY above call wall = squeeze fuel"
                except _TE5:
                    raw["qqq_sv_error"] = "timeout"
        except Exception as _qqq_exc5:
            raw["qqq_sv_error"] = str(_qqq_exc5)

        layer_5 = {
            "name": "QQQ Reshort Spike",
            "triggered": qqq_reshort_triggered,
            "value": qqq_sv_delta,
            "unit": "QQQ SV 1d delta (pp)",
            "signal": f"RESHORT_SPIKE +{qqq_sv_delta}pp" if qqq_reshort_triggered else "NEUTRAL",
        }

        # ── Fed Event Veto ───────────────────────────────────────────────────────
        fed_veto_active = False
        fed_veto_event = None
        try:
            from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper as _TECal
            _te = _TECal(cache_ttl=300)
            _veto_result = _te.get_hours_until_next_critical()
            if _veto_result is not None:
                _hours_away, _event_name = _veto_result
                if _hours_away is not None and _hours_away <= 4:
                    fed_veto_active = True
                    fed_veto_event = _event_name
                    raw["fed_veto"] = f"CRITICAL EVENT IN {_hours_away:.1f}h: {_event_name}"
                else:
                    raw["fed_veto_hours"] = round(_hours_away, 1) if _hours_away else None
                    raw["fed_veto_next"] = _event_name
        except Exception as _exc:
            raw["fed_veto_error"] = str(_exc)

        # ── Confluence label ─────────────────────────────────────────────────────
        layer_4_triggered = axlfi_wall_triggered
        layer_5_triggered = qqq_reshort_triggered
        triggered_count = sum([layer_1_triggered, layer_2_triggered, layer_3_triggered, layer_4_triggered, layer_5_triggered])
        if fed_veto_active:
            confluence = "VETO"
        elif triggered_count >= 5:
            confluence = "QUINT"
        elif triggered_count == 4:
            confluence = "QUAD"
        elif triggered_count == 3:
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
            "fed_veto_active": fed_veto_active,
            "fed_veto_event": fed_veto_event,
            "bullish_points": bullish_pts,
            "bearish_points": bearish_pts,
            "layer_1": layer_1,
            "layer_2": layer_2,
            "layer_3": layer_3,
            "layer_4": layer_4,
            "layer_5": layer_5,
            "position": position,
            "signals": signals,
            "layers": raw,
            "errors": any("error" in k for k in raw),
        }

        _kc_cache["data"] = result
        _kc_cache["ts"] = time.time()
        return result

