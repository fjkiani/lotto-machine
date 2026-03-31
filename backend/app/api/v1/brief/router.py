"""
brief/router.py — OOM-SAFE endpoint for GET /brief/master.

MEMORY BUDGET: Render 512MB total, ~127MB baseline (Python + FastAPI + all imports).
Available: ~385MB for runtime data.

KEY INSIGHT: The old version ran GEX, COT, and FedWatch 2-3x each because
fetch_derivatives(), fetch_kill_chain(), and the old KillChainEngine all
created independent client instances. This alone consumed ~320MB runtime.

FIX: 3-wave architecture where Wave 1 fetches shared primitives (GEX, COT,
FedWatch), then Wave 2 builds derived layers (derivatives, kill_chain) from
that shared data with ZERO additional API calls.

Wave 1 (PRIMITIVES, 2 workers):  GEX + COT + FedWatch + Veto
Wave 2 (DERIVED, sync):          build_derivatives() + build_kill_chain()
                                 from shared Wave 1 data — no threads needed
Wave 3 (PARALLEL, 2 workers):    hidden_hands + macro + thresholds + nowcast
                                 + adp + gdp + jobless + pivots + squeeze

Expected peak: ~127MB + ~80MB (GEX) + ~50MB (brain) = ~257MB
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter

from .cache import get_cache, set_cache, _brief_lock
from .alert_engine import PreSignalAlertEngine
from .fetchers.core import (
    fetch_macro_regime, fetch_fedwatch, fetch_veto,
    fetch_nowcast, fetch_thresholds, fetch_hidden_hands,
    fetch_gex_shared, fetch_cot_shared,
    build_derivatives, build_kill_chain,
)
from .fetchers.signals import (
    fetch_adp_prediction, fetch_gdp_nowcast, fetch_jobless_claims,
    fetch_pivots, fetch_squeeze_context,
    fetch_darkpool_context, fetch_vol_regime, fetch_axlfi_walls, fetch_ta_consensus
)

logger        = logging.getLogger(__name__)
router        = APIRouter()
_alert_engine = PreSignalAlertEngine()

def _build_data_quality_flags(results: dict) -> dict:
    """Summarize degraded layers so consumers can separate signal vs data-quality risk."""
    degraded_layers = {}
    for key, value in results.items():
        if isinstance(value, dict) and value.get("error"):
            degraded_layers[key] = value.get("error")

    env_warnings = {}
    adp = results.get("adp_prediction", {})
    if isinstance(adp, dict):
        if adp.get("consensus_source") == "ner_pulse_baseline":
            env_warnings["adp_consensus_fallback"] = (
                "ADP consensus from 40K baseline — calendar/FF/TE page all failed"
            )
        elif adp.get("consensus") == 150000:
            env_warnings["adp_consensus_fallback"] = "legacy 150K consensus — investigate stale path"
    jobless = results.get("jobless_claims", {})
    if isinstance(jobless, dict) and jobless.get("error"):
        env_warnings["jobless_claims"] = jobless.get("error")
    hidden = results.get("hidden_hands", {})
    if isinstance(hidden, dict) and hidden.get("finnhub_signals") == []:
        env_warnings["finnhub_signals"] = "No Finnhub signals in payload"

    return {
        "integrity_status": "DEGRADED" if degraded_layers or env_warnings else "OK",
        "degraded_layers": degraded_layers,
        "warnings": env_warnings,
    }


async def _run_wave(wave: dict, loop, max_workers: int = 2) -> dict:
    """Run a wave of fetchers in a ThreadPoolExecutor. Executor is
    fully disposed (threads joined, memory freed) before return."""
    async def _run_one(key: str, fn, timeout_s: int):
        try:
            value = await asyncio.wait_for(loop.run_in_executor(executor, fn), timeout=timeout_s)
            return key, value
        except asyncio.TimeoutError:
            logger.warning(f"Layer {key} timed out after {timeout_s}s")
            return key, {'error': f'timeout after {timeout_s}s'}
        except Exception as e:
            logger.error(f"Layer {key} failed: {e}")
            return key, {'error': str(e)}

    executor = ThreadPoolExecutor(max_workers=max_workers)
    try:
        tasks = [_run_one(key, fn, timeout) for key, (fn, timeout) in wave.items()]
        pairs = await asyncio.gather(*tasks)
        return {k: v for k, v in pairs}
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


@router.get("/brief/master")
async def master_brief():
    """
    Unified intelligence brief — deduped 3-wave, 2-min TTL cache.

    Wave 1: GEX + COT + FedWatch + Veto (shared primitives)
    Wave 2: build_derivatives + build_kill_chain (from shared data, sync)
    Wave 3: hidden_hands + macro + thresholds + nowcast + ADP + GDP + jobless + pivots + squeeze
    """
    # ── Fast path: cache hit ──────────────────────────────────────────────────
    cached = get_cache()
    if cached is not None:
        return cached

    # ── Slow path: compute under mutex ───────────────────────────────────────
    async with _brief_lock:
        cached = get_cache()
        if cached is not None:
            return cached

        t0   = time.time()
        loop = asyncio.get_event_loop()
        results = {}

        # ── Wave 1: SHARED PRIMITIVES (heaviest: GEX downloads options chain) ─
        wave1 = {
            '_gex':             (fetch_gex_shared,   6),
            '_cot':             (fetch_cot_shared,   4),
            'fed_intelligence': (fetch_fedwatch,     4),
            'economic_veto':    (fetch_veto,         4),
        }
        w1 = await _run_wave(wave1, loop, max_workers=2)
        results['fed_intelligence'] = w1.get('fed_intelligence', {'error': 'timeout'})
        results['economic_veto']    = w1.get('economic_veto', {'error': 'timeout'})

        gex_shared = w1.get('_gex', {'error': 'timeout'})
        cot_shared = w1.get('_cot', {'error': 'timeout'})

        # ── Wave 2: DERIVED LAYERS (sync — zero API calls, just dict transforms) ─
        results['derivatives']      = build_derivatives(gex_shared, cot_shared)
        results['kill_chain_state'] = build_kill_chain(
            gex_shared, cot_shared,
            results['fed_intelligence'],
        )

        # ── Wave 3: REMAINING LAYERS (all independent, 2 workers) ─────────────
        wave3 = {
            'hidden_hands':     (fetch_hidden_hands,        8),
            'macro_regime':     (fetch_macro_regime,        6),
            'dynamic_thresholds': (fetch_thresholds,        6),
            'nowcast':          (fetch_nowcast,             5),
            'adp_prediction':   (fetch_adp_prediction,      5),
            'gdp_nowcast':      (fetch_gdp_nowcast,         5),
            'jobless_claims':   (fetch_jobless_claims,      5),
            'pivots':           (fetch_pivots,              5),
            'squeeze_context':  (fetch_squeeze_context,     5),
            'dark_pool':        (fetch_darkpool_context,    6),
            'vol_regime':       (fetch_vol_regime,          6),
            'axlfi_walls':      (fetch_axlfi_walls,         6),
            'ta_consensus':     (fetch_ta_consensus,        6),
        }
        results.update(await _run_wave(wave3, loop, max_workers=2))

        # ── Post-processing ──────────────────────────────────────────────────
        regime_mod = results.get('macro_regime', {}).get('modifier', {}).get('long_penalty', 0)
        veto_cap   = results.get('economic_veto', {}).get('confidence_cap', 65)
        kc         = results.get('kill_chain_state', {})
        kc['regime_modifier'] = regime_mod
        kc['confidence_cap']  = veto_cap
        kc['cap_reason'] = (
            f"{results.get('economic_veto', {}).get('next_event', '')} "
            f"{results.get('economic_veto', {}).get('hours_away', '')}h"
        )
        # Always ensure signals key is present (guards against fallback path)
        kc.setdefault('signals', [])
        results['kill_chain_state'] = kc

        try:
            results['alerts'] = _alert_engine.get_alerts(results)
        except Exception as e:
            logger.warning(f"Alert engine failed: {e}")
            results['alerts'] = []

        results['scan_time'] = round(time.time() - t0, 2)
        results['as_of']     = datetime.utcnow().isoformat()
        results['data_quality_flags'] = _build_data_quality_flags(results)

        set_cache(results)
        return results
