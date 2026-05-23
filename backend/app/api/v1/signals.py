"""
📊 SIGNALS API ROUTER  (thin layer — all logic lives in backend.app.signals.*)

Sources, in priority order:
    1. LiveMonitor signal buffer   (real-time selloff/rally detections)
    2. AlertDB (alerts_history.db) (options flow, DP divergence, earnings, fed)
    3. Morning Brief fallback      (pre-market verdict — only when buffer empty)

Kill Chain is used ONLY as a confidence modifier and direction context.
It no longer emits its own hardcoded LONG signal.
"""

import json
import logging
import os
import sqlite3
import time
import threading
from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FuturesTimeout,
    wait,
    FIRST_COMPLETED,
)
from datetime import datetime, timedelta, time as dt_time, timezone
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.core.dependencies import get_monitor_bridge
from backend.app.integrations.unified_monitor_bridge import MonitorBridge
from backend.app.signals.models import DivergenceResponse, DivergenceSignal, SignalResponse
from backend.app.signals.kill_chain import compute_kill_chain
from backend.app.signals.canonical_state import (
    _confidence_is_master,
    load_latest_kill_chain_for_inject,
    load_recent_oracle_signals,
    oracle_signal_cache_bump,
)
from backend.app.signals.sources.alert_db_source import fetch_alert_db_signals
from backend.app.signals.sources.monitor_source import fetch_monitor_signals
from backend.app.signals.sources.morning_brief_source import fetch_morning_brief_signals
from backend.app.signals.sources.darkpool_source import fetch_darkpool_signals

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Response-level cache (prevents 3+ consumers from each triggering 13s chains)
_signals_cache = {}  # key → {"data": ..., "expires": timestamp}
_cache_lock = threading.Lock()
SIGNALS_CACHE_TTL = 300  # 5 minutes

ROOT = Path(__file__).resolve().parents[4]

SOURCE_TIMEOUT = 3  # fail fast; keep endpoint responsive under upstream slowness
KC_TIMEOUT = 12     # allow full compute (COT + brain); fallback to canonical SQLite if still slow
REGIME_TIMEOUT = 2
INJECT_ENRICH_TIMEOUT = 2  # TE calendar scrape (keep tight)
MACRO_INJECT_TIMEOUT = 10  # FRED + Cleveland nowcast — was timing out at 2s every cold inject
PARALLEL_SOURCES_BUDGET = 9.0  # wall-clock cap for monitor + AlertDB + dark pool together

# Kill-chain inject: MacroRegimeDetector pulls FRED + Cleveland Fed scrape — cache 5m per process
_MACRO_REGIME_INJECT_CACHE: dict = {"ts": 0.0, "data": None}
_MACRO_REGIME_INJECT_LOCK = threading.Lock()
_MACRO_REGIME_INJECT_TTL = 300.0

_ET = ZoneInfo("America/New_York")
_STALE_OUTSIDE_RTH_SEC = 3600  # Bug 11: AH / pre-market — flag aged intraday snapshots


def _parse_iso_to_utc(val: object) -> Optional[datetime]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _us_equities_rth_open(now_et: datetime) -> bool:
    """US equity regular session Mon–Fri 09:30–16:00 ET."""
    if now_et.weekday() >= 5:
        return False
    t = now_et.time()
    return dt_time(9, 30) <= t < dt_time(16, 0)


def _annotate_signals_staleness(signals: List[dict], now_utc: datetime) -> None:
    """Per-signal age; stale outside RTH when older than _STALE_OUTSIDE_RTH_SEC."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_et = now_utc.astimezone(_ET)
    outside_rth = not _us_equities_rth_open(now_et)
    for sig in signals:
        ev = _parse_iso_to_utc(sig.get("created_at")) or _parse_iso_to_utc(
            sig.get("timestamp")
        )
        if ev is None:
            sig["signal_age_seconds"] = None
            sig["stale"] = False
            continue
        age = max(0, int((now_utc - ev).total_seconds()))
        sig["signal_age_seconds"] = age
        sig["stale"] = bool(outside_rth and age > _STALE_OUTSIDE_RTH_SEC)


def _finalize_signals_payload(payload: dict) -> None:
    """Refresh staleness + session flags (call on cache hits too)."""
    now_utc = datetime.now(timezone.utc)
    sigs: List[dict] = payload.get("signals") or []
    _annotate_signals_staleness(sigs, now_utc)
    payload["us_market_rth"] = _us_equities_rth_open(now_utc.astimezone(_ET))
    payload["signal_stale_count"] = sum(1 for s in sigs if s.get("stale"))


def _safe_fetch(name: str, fn, timeout: int = SOURCE_TIMEOUT, default=None):
    """Run a source fetch with a timeout — never hang the pipeline."""
    if default is None:
        default = []
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fn)
        value = future.result(timeout=timeout)
        executor.shutdown(wait=False, cancel_futures=True)
        return value
    except FuturesTimeout:
        logger.warning(f"⏰ {name} timed out after {timeout}s — returning empty")
        executor.shutdown(wait=False, cancel_futures=True)
        return default
    except Exception as exc:
        logger.warning(f"❌ {name} failed: {exc} — returning empty")
        executor.shutdown(wait=False, cancel_futures=True)
        return default


def _safe_fetch_value(name: str, fn, *, timeout: int = SOURCE_TIMEOUT, default=None):
    """Like _safe_fetch but preserves arbitrary default (not forced to [])."""
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fn)
        value = future.result(timeout=timeout)
        executor.shutdown(wait=False, cancel_futures=True)
        return value
    except FuturesTimeout:
        logger.warning(f"⏰ {name} timed out after {timeout}s")
        executor.shutdown(wait=False, cancel_futures=True)
        return default
    except Exception as exc:
        logger.warning(f"❌ {name} failed: {exc}")
        executor.shutdown(wait=False, cancel_futures=True)
        return default


def _parallel_fetch_sources(
    monitor,
    symbol: Optional[str],
    signal_type: Optional[str],
    master_only: bool,
    regime_tier: int,
) -> List[dict]:
    """Run monitor, AlertDB, and dark-pool fetches concurrently (bounded wall time)."""
    executor = ThreadPoolExecutor(max_workers=3)

    def _mon():
        try:
            return fetch_monitor_signals(
                monitor=monitor,
                symbol=symbol,
                signal_type=signal_type,
                master_only=master_only,
            )
        except Exception as exc:
            logger.warning(f"MonitorBuffer parallel: {exc}")
            return []

    def _adb():
        try:
            return fetch_alert_db_signals(symbol=symbol, master_only=master_only)
        except Exception as exc:
            logger.warning(f"AlertDB parallel: {exc}")
            return []

    def _dp():
        try:
            return fetch_darkpool_signals(symbol=symbol or "SPY", regime_tier=regime_tier)
        except Exception as exc:
            logger.warning(f"DarkPoolTrend parallel: {exc}")
            return []

    future_to_name = {
        executor.submit(_mon): "MonitorBuffer",
        executor.submit(_adb): "AlertDB",
        executor.submit(_dp): "DarkPoolTrend",
    }
    pending = set(future_to_name.keys())
    merged: List[dict] = []
    deadline = time.time() + PARALLEL_SOURCES_BUDGET
    try:
        while pending and time.time() < deadline:
            wait_timeout = min(1.0, max(0.01, deadline - time.time()))
            done, pending = wait(pending, timeout=wait_timeout, return_when=FIRST_COMPLETED)
            for fut in done:
                name = future_to_name.get(fut, "?")
                try:
                    part = fut.result(timeout=0)
                    merged.extend(part or [])
                except Exception as exc:
                    logger.warning(f"{name} result error: {exc}")
        if pending:
            logger.warning(
                "⏰ Parallel sources: %d task(s) incomplete at budget — cancelling",
                len(pending),
            )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    return merged


# ── Helpers ───────────────────────────────────────────────────────────────────

def _inject_kill_chain(signals: List[dict], kc: dict) -> List[dict]:
    """Annotate each signal with kill chain verdict + optionally adjust confidence.

    Economic veto fires FIRST (pre-release risk):
      ≤0.5h → confidence=0 (BLOCKED)
      ≤2h   → cap at 35%
      ≤6h   → cap at 50%

    BOOST  → +15 confidence cap at 99
    HARD_VETO → -30 confidence floor at 20
    Direction mismatch → add a warning (don't silently flip direction)
    """
    if not signals:
        return signals

    verdict = kc.get("verdict", "NEUTRAL")
    score = kc.get("score", 0)
    kc_direction = kc.get("direction", "MIXED")

    # ── Economic veto — pre-release risk cap (time-boxed; TE scrape can be slow)
    econ_hours = None
    econ_event = "critical release"

    def _econ():
        from live_monitoring.enrichment.apis.te_calendar_scraper import TECalendarScraper
        return TECalendarScraper(cache_ttl=300).get_hours_until_next_critical()

    result = _safe_fetch_value(
        "EconCalendar", _econ, timeout=INJECT_ENRICH_TIMEOUT, default=None
    )
    if result is not None:
        econ_hours, econ_event = result[0], (result[1] or econ_event)

    def _macro():
        from live_monitoring.agents.economic.macro_regime_detector import MacroRegimeDetector

        now = time.monotonic()
        with _MACRO_REGIME_INJECT_LOCK:
            hit = _MACRO_REGIME_INJECT_CACHE["data"]
            ts = _MACRO_REGIME_INJECT_CACHE["ts"]
            if hit is not None and (now - ts) < _MACRO_REGIME_INJECT_TTL:
                return hit
        data = MacroRegimeDetector().get_regime()
        with _MACRO_REGIME_INJECT_LOCK:
            _MACRO_REGIME_INJECT_CACHE["data"] = data
            _MACRO_REGIME_INJECT_CACHE["ts"] = time.monotonic()
        return data

    _macro_regime_data = _safe_fetch_value(
        "MacroRegime", _macro, timeout=MACRO_INJECT_TIMEOUT, default=None
    )

    for sig in signals:
        sig_action = sig.get("action", "WATCH")
        sig["kill_chain_verdict"] = verdict
        sig["kill_chain_score"] = score
        sig["kill_chain_direction"] = kc_direction

        if "warnings" not in sig or not isinstance(sig["warnings"], list):
            sig["warnings"] = []

        # ── Economic veto (fires before Kill Chain) ───────────────────────
        if econ_hours is not None:
            if econ_hours <= 0.5:
                original_conf = sig["confidence"]
                sig["confidence"] = 0
                sig["warnings"].append(
                    f"🛑 ECONOMIC VETO BLOCKED: {econ_event} in {econ_hours:.1f}h "
                    f"(was {original_conf}%)"
                )
                continue  # skip Kill Chain adjustments — signal is dead
            elif econ_hours <= 2.0:
                original_conf = sig["confidence"]
                if original_conf > 35:
                    sig["confidence"] = 35
                    sig["warnings"].append(
                        f"⚠️ Economic risk cap 35%: {econ_event} in {econ_hours:.1f}h "
                        f"(was {original_conf}%)"
                    )
            elif econ_hours <= 6.0:
                original_conf = sig["confidence"]
                if original_conf > 50:
                    sig["confidence"] = 50
                    sig["warnings"].append(
                        f"⚠️ Economic risk cap 50%: {econ_event} in {econ_hours:.1f}h "
                        f"(was {original_conf}%)"
                    )
            elif econ_hours <= 24.0:
                original_conf = sig["confidence"]
                if original_conf > 55:
                    sig["confidence"] = 55
                    sig["warnings"].append(
                        f"⚠️ Economic awareness cap 55%: {econ_event} in {econ_hours:.1f}h "
                        f"(was {original_conf}%)"
                    )

        # ── Kill Chain adjustments ────────────────────────────────────────
        if verdict == "BOOST":
            sig["confidence"] = min(int(sig["confidence"] + 15), 99)
            sig["warnings"].append(f"Kill Chain BOOST (+15): {score}pts")
        elif verdict == "HARD_VETO":
            sig["confidence"] = min(max(int(sig["confidence"] - 30), 20), 30)
            sig["warnings"].append(f"Kill Chain HARD_VETO (cap 30%): {score}pts")
        elif verdict == "WAR_VETO":
            original_conf = sig["confidence"]
            if sig_action == "LONG":
                sig["action"] = "WATCH"
                sig["confidence"] = min(int(sig["confidence"]), 25)
                sig["warnings"].append(
                    f"Kill Chain WAR_VETO — LONG suppressed ({score}pts, was {original_conf}%)"
                )
            else:
                sig["confidence"] = min(int(sig["confidence"]), 65)
                sig["warnings"].append(f"Kill Chain WAR_VETO (cap 65%): {score}pts")
        elif verdict == "SOFT_VETO":
            original_conf = sig["confidence"]
            sig["confidence"] = min(int(sig["confidence"]), 65)
            if sig_action == "LONG":
                sig["action"] = "WATCH"
                sig["warnings"].append(
                    f"Kill Chain SOFT_VETO — LONG not actionable ({score}pts)"
                )
            if original_conf > 65:
                sig["warnings"].append(
                    f"Kill Chain SOFT_VETO (cap 65%): original {original_conf}% → {sig['confidence']}%"
                )
        elif verdict == "NEUTRAL":
            original_conf = sig["confidence"]
            sig["confidence"] = min(int(sig["confidence"]), 65)
            if original_conf > 65:
                sig["warnings"].append(
                    f"Kill Chain NEUTRAL (cap 65%): original {original_conf}% → {sig['confidence']}%")


        # Warn if signal direction disagrees with kill chain direction
        sig_action = sig.get("action", "WATCH")
        if kc_direction == "BEARISH" and sig_action == "LONG":
            sig["warnings"].append(f"⚠️ Kill Chain is BEARISH ({score}pts) — LONG signal is counter-trend")
        elif kc_direction == "BULLISH" and sig_action == "SHORT":
            sig["warnings"].append(f"⚠️ Kill Chain is BULLISH ({score}pts) — SHORT signal is counter-trend")

        # ── Macro regime modifier ─────────────────────────────────────────
        if _macro_regime_data:
            regime = _macro_regime_data.get("regime", "NEUTRAL")
            modifier = _macro_regime_data.get("modifier", {})
            penalty = 0
            if sig_action == "LONG":
                penalty = modifier.get("long_penalty", 0)
            elif sig_action == "SHORT":
                penalty = modifier.get("short_penalty", 0)

            if penalty != 0:
                original_conf = sig["confidence"]
                sig["confidence"] = max(int(sig["confidence"] + penalty), 0)
                warning_msg = modifier.get("warning", f"Macro regime: {regime}")
                sig["warnings"].append(
                    f"📊 {warning_msg} ({penalty:+d}%: {original_conf}% → {sig['confidence']}%)"
                )
            sig["macro_regime"] = regime

    return signals


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/signals")
def get_signals(
    master_only: bool = Query(False, description="Only return master signals (75%+ confidence)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge),
):
    """Aggregate signals from all live sources. No hardcoded signals."""
    try:
        # ── Cache check ───────────────────────────────────────────────
        cache_key = f"{symbol}:{signal_type}:{master_only}:{oracle_signal_cache_bump()}"
        with _cache_lock:
            entry = _signals_cache.get(cache_key)
            if entry and time.time() < entry["expires"]:
                logger.debug(f"signals cache HIT ({cache_key})")
                data = entry["data"]
                _finalize_signals_payload(data)
                return data

        all_signals: List[dict] = []

        # LAYER 0 — REGIME GATE (runs BEFORE any source; time-boxed)
        def _regime_gate():
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            return StockgridClient(cache_ttl=300).get_volatility_regime()

        regime = _safe_fetch_value(
            "RegimeGate",
            _regime_gate,
            timeout=REGIME_TIMEOUT,
            default={"current_regime": 1},
        )
        regime_tier = int((regime or {}).get("current_regime", 1))

        if regime_tier >= 4:
            veto_out = {
                "signals": [],
                "count": 0,
                "master_count": 0,
                "regime_tier": regime_tier,
                "regime_veto": True,
                "reason": "REGIME VETO: Tier 4 extreme volatility — all signals suppressed",
                "timestamp": datetime.utcnow().isoformat(),
            }
            _finalize_signals_payload(veto_out)
            return veto_out

        allowed_directions = ["LONG", "SHORT", "WATCH", "AVOID"]
        if regime_tier >= 3:
            allowed_directions = ["SHORT", "WATCH", "AVOID"]

        # Sources 1–3 in parallel (same total budget ≈ max of three, not sum)
        monitor = monitor_bridge.monitor if monitor_bridge else None
        all_signals += _parallel_fetch_sources(
            monitor, symbol, signal_type, master_only, regime_tier
        )

        # Source 4: Morning Brief fallback (only when the other sources are dry)
        if not all_signals:
            all_signals += _safe_fetch("MorningBrief", lambda: fetch_morning_brief_signals(symbol=symbol))

        # REGIME ENFORCEMENT — suppress disallowed directions
        for sig in all_signals:
            sig["regime_tier"] = regime_tier
            if sig.get("action") not in allowed_directions:
                original = sig["action"]
                sig["action"] = "WATCH"
                if "warnings" not in sig or not isinstance(sig["warnings"], list):
                    sig["warnings"] = []
                sig["warnings"].append(
                    f"⚠️ Tier {regime_tier} regime suppressed {original} → WATCH"
                )
            # Tier 3 confidence gate: LONGs require confidence >= 60
            if regime_tier >= 3 and sig.get("action") == "LONG" and sig.get("confidence", 0) < 60:
                sig["action"] = "WATCH"
                sig.setdefault("warnings", []).append(
                    f"⚠️ Tier {regime_tier}: LONG requires confidence ≥ 60, got {sig.get('confidence')}"
                )

        try:
            oracle_sigs = load_recent_oracle_signals(max_age_hours=4)
            if symbol:
                sym_u = symbol.strip().upper()
                oracle_sigs = [
                    o for o in oracle_sigs if o.get("symbol", "SPY").upper() == sym_u
                ]
            all_signals.extend(oracle_sigs)
        except Exception as exc:
            logger.warning("Oracle signal bridge failed: %s", exc)

        # Kill Chain: confidence modifier + direction annotation (no new signals)
        kc = _safe_fetch_value(
            "KillChain",
            lambda: compute_kill_chain(),
            timeout=KC_TIMEOUT,
            default=None,
        )
        if not kc:
            kc = load_latest_kill_chain_for_inject(max_age_sec=120.0)
            if kc:
                logger.warning("Kill chain live compute unavailable — using canonical SQLite snapshot")
        if kc:
            all_signals = _inject_kill_chain(all_signals, kc)
            if os.getenv("KILL_CHAIN_SCORE_DEBUG"):
                # Must match PRE_INJECT_SCORE from compute_kill_chain (same kc object) — Bug 4 seal
                logger.info(
                    "POST_INJECT_SCORE: %s %s",
                    kc.get("score"),
                    kc.get("verdict"),
                )
        else:
            logger.warning("Kill chain returned None/timed out — signals pass without KC modifier")

        # After KC inject (may cap confidence), re-derive master flags.
        # ORACLE: use Groq/raw scale via confidence_raw — not post-inject display confidence.
        for sig in all_signals:
            c_disp = sig.get("confidence")
            try:
                c_int = int(c_disp) if c_disp is not None else 0
            except (TypeError, ValueError):
                c_int = 0
            if str(sig.get("source") or "").upper() == "ORACLE":
                try:
                    raw_f = float(sig.get("confidence_raw", c_disp) or 0)
                except (TypeError, ValueError):
                    raw_f = 0.0
                sig["is_master"] = _confidence_is_master(raw_f)
            else:
                sig["is_master"] = bool(c_int >= 75)
            sig["is_primary"] = sig["is_master"]

        if master_only:
            all_signals = [s for s in all_signals if s.get("is_master")]

        all_signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        master_count = sum(1 for s in all_signals if s.get("is_master"))

        result = {
            "signals": all_signals,
            "count": len(all_signals),
            "master_count": master_count,
            "regime_tier": regime_tier,
            "timestamp": datetime.utcnow().isoformat(),
        }
        _finalize_signals_payload(result)

        # ── Cache store ───────────────────────────────────────────────
        with _cache_lock:
            _signals_cache[cache_key] = {
                "data": result,
                "expires": time.time() + SIGNALS_CACHE_TTL,
            }
            logger.debug(f"signals cache STORED ({cache_key})")

        return result

    except Exception as exc:
        logger.error(f"get_signals error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/signals/master")
def get_master_signals(
    symbol: Optional[str] = Query(None),
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge),
):
    """Only signals with confidence >= 75%."""
    return get_signals(master_only=True, symbol=symbol, monitor_bridge=monitor_bridge)


@router.get("/signals/divergence", response_model=DivergenceResponse)
async def get_divergence_signals(
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge),
):
    """DP confluence / options divergence signals from DPDivergenceChecker.

    Raises 503 if monitor not initialized. Never returns hardcoded data.
    """
    if not monitor_bridge or not monitor_bridge.monitor:
        raise HTTPException(status_code=503, detail="Monitor not initialized")

    monitor = monitor_bridge.monitor
    dp_div_checker = (
        getattr(monitor, "dp_divergence_checker", None)
        or getattr(monitor, "divergence_checker", None)
    )
    if not dp_div_checker:
        raise HTTPException(
            status_code=503,
            detail="DPDivergenceChecker not registered on monitor",
        )

    edge_stats: dict = {}
    try:
        edge_stats = dp_div_checker.get_dp_learning_stats()
    except Exception as exc:
        logger.warning(f"dp_learning stats unavailable: {exc}")

    try:
        raw_alerts = dp_div_checker.check()
    except Exception as exc:
        logger.error(f"DPDivergenceChecker.check() failed: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))

    signals = []
    for alert in (raw_alerts or []):
        try:
            embed = alert.embed or {}
            fields = {f["name"]: f["value"] for f in embed.get("fields", [])}

            entry_raw = fields.get("📊 Entry", "0").replace("$", "").strip()
            stop_raw = fields.get("🛑 Stop", "0.0%").replace("-", "").replace("%", "").strip()
            target_raw = fields.get("🎯 Target", "0.0%").replace("+", "").replace("%", "").strip()
            confidence_raw = fields.get("💪 Confidence", "0%").replace("%", "").strip()
            dp_bias_raw = fields.get("📈 DP Bias", "NEUTRAL").split(" ")[0]
            strength_raw = fields.get("📈 DP Bias", "0.0%").split("(")[-1].replace(")", "").replace("%", "").strip()
            signal_type_str = "DP_CONFLUENCE" if "CONFLUENCE" in embed.get("title", "") else "OPTIONS_DIVERGENCE"
            direction = "LONG" if "LONG" in embed.get("title", "") else "SHORT"

            signals.append(DivergenceSignal(
                symbol=alert.symbol or "UNKNOWN",
                signal_type=signal_type_str,
                direction=direction,
                confidence=float(confidence_raw) if confidence_raw else 0.0,
                entry_price=float(entry_raw) if entry_raw else 0.0,
                stop_pct=float(stop_raw) if stop_raw else 0.0,
                target_pct=float(target_raw) if target_raw else 0.0,
                reasoning=embed.get("description", ""),
                dp_bias=dp_bias_raw,
                dp_strength=float(strength_raw) / 100 if strength_raw else 0.0,
                has_divergence=signal_type_str == "OPTIONS_DIVERGENCE",
                options_bias=fields.get("📉 Options Bias"),
            ))
        except Exception as parse_err:
            logger.warning(f"Divergence alert parse error: {parse_err}")
            continue

    return DivergenceResponse(
        signals=signals,
        count=len(signals),
        dp_edge_stats=edge_stats,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/signals/history")
async def get_signal_history(
    limit: int = Query(100),
    alert_type: Optional[str] = Query(None),
):
    """Return today's raw alerts from alerts_history.db."""
    try:
        from backend.app.signals.sources.alert_db_source import _resolve_db_path
        alerts_path = _resolve_db_path()
        if not alerts_path:
            return {"alerts": [], "count": 0, "message": "alerts_history.db not found"}

        conn = sqlite3.connect(str(alerts_path))
        conn.row_factory = sqlite3.Row
        today = datetime.now().strftime("%Y-%m-%d")

        params = [f"{today}%"]
        type_filter = "AND alert_type = ?" if alert_type else ""
        if alert_type:
            params.append(alert_type)
        params.append(limit)

        rows = conn.execute(
            f"""SELECT rowid as id, *, MAX(timestamp) as latest_ts, COUNT(*) as dup_count
               FROM alerts
               WHERE timestamp LIKE ? {type_filter}
               GROUP BY alert_type, symbol, title
               ORDER BY latest_ts DESC
               LIMIT ?""",
            params,
        ).fetchall()

        type_counts = conn.execute(
            "SELECT alert_type, COUNT(*) as c FROM alerts WHERE timestamp LIKE ? GROUP BY alert_type ORDER BY c DESC",
            (f"{today}%",),
        ).fetchall()
        conn.close()

        return {
            "alerts": [dict(r) for r in rows],
            "count": len(rows),
            "type_breakdown": {t: c for t, c in type_counts},
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.error(f"signal history error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/signals/scorecard")
async def get_signal_scorecard():
    """P&L scorecard: tracks today's directional signals against current prices."""
    try:
        from backend.app.signals.sources.alert_db_source import _resolve_db_path
        alerts_path = _resolve_db_path()
        if not alerts_path:
            return {"entries": [], "count": 0, "message": "No alerts DB"}

        conn = sqlite3.connect(str(alerts_path))
        conn.row_factory = sqlite3.Row
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT rowid as id, * FROM alerts WHERE timestamp LIKE ? ORDER BY timestamp DESC",
            (f"{today}%",),
        ).fetchall()
        conn.close()

        from backend.app.signals.classifier import classify_alert

        symbol_signals = {}
        for row in rows:
            d = dict(row)
            at = d.get("alert_type", "")
            sym = d.get("symbol") or "SPY"
            action, _ = classify_alert(at, str(d.get("description", "")))
            if action in ("LONG", "SHORT") and sym not in symbol_signals:
                for s in sym.split(","):
                    s = s.strip()
                    if s and s not in symbol_signals:
                        symbol_signals[s] = {
                            "symbol": s,
                            "action": action,
                            "type": at,
                            "source": d.get("source", ""),
                            "timestamp": d.get("timestamp", ""),
                        }

        if not symbol_signals:
            return {"entries": [], "count": 0}

        symbols_list = list(symbol_signals.keys())
        try:
            tickers = yf.download(symbols_list, period="1d", interval="5m", progress=False, threads=True)
        except Exception as exc:
            return {"entries": [], "count": 0, "error": str(exc)}

        entries = []
        for sym, sig_info in symbol_signals.items():
            try:
                sym_data = tickers if len(symbols_list) == 1 else (
                    tickers.xs(sym, level=1, axis=1)
                    if sym in tickers.columns.get_level_values(1) else None
                )
                if sym_data is None or sym_data.empty:
                    continue

                today_data = sym_data[sym_data.index.strftime("%Y-%m-%d") == today]
                if today_data.empty:
                    today_data = sym_data

                try:
                    sp_data = today_data.between_time("12:15", "12:30")
                    sp = float(sp_data["Close"].iloc[0]) if not sp_data.empty else float(today_data["Open"].iloc[0])
                except Exception:
                    sp = float(today_data["Open"].iloc[0])

                cp = float(today_data["Close"].iloc[-1])
                pnl = ((cp - sp) / sp) * 100 * (-1 if sig_info["action"] == "SHORT" else 1)

                entries.append({
                    "symbol": sym,
                    "action": sig_info["action"],
                    "type": sig_info["type"],
                    "signal_price": round(sp, 2),
                    "current_price": round(cp, 2),
                    "high": round(float(today_data["High"].max()), 2),
                    "low": round(float(today_data["Low"].min()), 2),
                    "pnl_pct": round(pnl, 2),
                    "status": "WIN" if pnl > 0.1 else "LOSS" if pnl < -0.1 else "FLAT",
                    "timestamp": sig_info["timestamp"],
                    "source": sig_info["source"],
                })
            except Exception as exc:
                logger.warning(f"Scorecard error for {sym}: {exc}")

        entries.sort(key=lambda x: x["pnl_pct"], reverse=True)
        wins = sum(1 for e in entries if e["status"] == "WIN")
        losses = sum(1 for e in entries if e["status"] == "LOSS")

        return {
            "entries": entries,
            "count": len(entries),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
            "total_pnl": round(sum(e["pnl_pct"] for e in entries), 2),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.error(f"scorecard error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/signals/morning-brief")
async def morning_brief():
    """Raw morning brief data (not signal-shaped)."""
    try:
        from live_monitoring.core.morning_brief import generate_morning_brief
        return generate_morning_brief()
    except Exception as exc:
        logger.error(f"morning brief error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/signals/outcomes/check")
async def check_signal_outcomes():
    """Check active signals against current prices and update outcomes."""
    try:
        from live_monitoring.core.signal_outcome_tracker import check_outcomes
        return check_outcomes()
    except Exception as exc:
        logger.error(f"outcome check error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/signals/outcomes/scorecard")
async def get_outcome_scorecard():
    """P&L scorecard from outcome tracker DB."""
    try:
        from live_monitoring.core.signal_outcome_tracker import get_scorecard
        return get_scorecard()
    except Exception as exc:
        logger.error(f"outcome scorecard error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/signals/take-trade")
async def take_trade(signal_id: str = Query(...)):
    """Register a signal for outcome tracking."""
    try:
        from live_monitoring.core.signal_outcome_tracker import _get_conn
        conn = _get_conn()
        existing = conn.execute(
            "SELECT * FROM signal_outcomes WHERE signal_id = ?", (signal_id,)
        ).fetchone()
        conn.close()

        if existing:
            return {
                "status": "already_tracked",
                "signal_id": signal_id,
                "outcome": existing["outcome"],
            }
        return {"status": "registered", "signal_id": signal_id}
    except Exception as exc:
        logger.error(f"take-trade error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Kill Chain Specific Signal Feed ───────────────────────────────────────────

@router.get("/killchain/signals")
async def get_kill_chain_signals():
    """Return the structured Kill Chain signal feed from all scorers."""
    try:
        from backend.app.signals.kill_chain import compute_kill_chain
        kc = compute_kill_chain()
        if not kc or "error" in kc:
            return {"signals": [], "score": 0, "verdict": "NEUTRAL", "armed": False, "error": kc.get("error", "Unknown")}

        return {
            "signals": kc.get("signals", []),
            "score": kc.get("score", 0),
            "verdict": kc.get("verdict", "NEUTRAL"),
            "armed": kc.get("armed", False)
        }
    except Exception as exc:
        logger.error(f"killchain signals error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Economic Releases (unrelated to signals — kept here for router grouping) ──

@router.get("/economic-releases")
async def get_economic_releases(days: int = 30):
    """Economic releases from FRED capture DB."""
    try:
        db_path = ROOT / "data" / "economic_intelligence.db"
        if not db_path.exists():
            return {"releases": [], "message": "No economic intelligence DB found"}

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT * FROM economic_releases WHERE date >= ? ORDER BY date DESC",
            (cutoff,),
        ).fetchall()
        conn.close()
        return {"releases": [dict(r) for r in rows], "count": len(rows)}
    except Exception as exc:
        logger.error(f"economic releases error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/economic-releases/capture")
async def capture_economic_releases():
    """Trigger a FRED capture run."""
    try:
        from live_monitoring.core.econ_release_capture import capture_all_releases
        return capture_all_releases()
    except Exception as exc:
        logger.error(f"economic capture error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
