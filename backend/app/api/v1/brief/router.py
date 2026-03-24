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
)

logger        = logging.getLogger(__name__)
router        = APIRouter()
_alert_engine = PreSignalAlertEngine()


async def _run_wave(wave: dict, loop, max_workers: int = 2) -> dict:
    """Run a wave of fetchers in a ThreadPoolExecutor. Executor is
    fully disposed (threads joined, memory freed) before return."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            key: (loop.run_in_executor(executor, fn), timeout)
            for key, (fn, timeout) in wave.items()
        }
        results = {}
        for key, (future, timeout_s) in futures.items():
            try:
                results[key] = await asyncio.wait_for(future, timeout=timeout_s)
            except asyncio.TimeoutError:
                logger.warning(f"Layer {key} timed out after {timeout_s}s")
                results[key] = {'error': f'timeout after {timeout_s}s'}
            except Exception as e:
                logger.error(f"Layer {key} failed: {e}")
                results[key] = {'error': str(e)}
    return results


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
            '_gex':             (fetch_gex_shared,  25),
            '_cot':             (fetch_cot_shared,  15),
            'fed_intelligence': (fetch_fedwatch,    20),
            'economic_veto':    (fetch_veto,        15),
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
            'hidden_hands':     (fetch_hidden_hands,      25),
            'macro_regime':     (fetch_macro_regime,       15),
            'dynamic_thresholds': (fetch_thresholds,       15),
            'nowcast':          (fetch_nowcast,             10),
            'adp_prediction':   (fetch_adp_prediction,     10),
            'gdp_nowcast':      (fetch_gdp_nowcast,        10),
            'jobless_claims':   (fetch_jobless_claims,     10),
            'pivots':           (fetch_pivots,             10),
            'squeeze_context':  (fetch_squeeze_context,    10),
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
        results['kill_chain_state'] = kc

        try:
            results['alerts'] = _alert_engine.get_alerts(results)
        except Exception as e:
            logger.warning(f"Alert engine failed: {e}")
            results['alerts'] = []

        results['scan_time'] = round(time.time() - t0, 2)
        results['as_of']     = datetime.utcnow().isoformat()

        set_cache(results)
        return results
