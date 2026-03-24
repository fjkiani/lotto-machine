"""
brief/router.py — Thin FastAPI endpoint for GET /brief/master.

OOM-SAFE DESIGN (Render 512MB):
  - 2-wave sequential execution: CORE first (3 workers), then SIGNAL (3 workers)
  - No more than 3 threads alive at any moment (~250MB peak)
  - asyncio.Lock: only ONE compute runs at a time
  - squeeze_watchlist REMOVED (24 yfinance calls × 8 nested threads = OOM by itself)
  - Missing-module fetchers (pmi, umich, current_account) REMOVED — they timeout
    for 18s each accomplishing nothing, wasting thread slots
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
    fetch_derivatives, fetch_kill_chain,
)
from .fetchers.signals import (
    fetch_adp_prediction, fetch_gdp_nowcast, fetch_jobless_claims,
    fetch_pivots, fetch_squeeze_context,
)

logger        = logging.getLogger(__name__)
router        = APIRouter()
_alert_engine = PreSignalAlertEngine()

# ── Timeouts ─────────────────────────────────────────────────────────────────
TIMEOUT_CORE   = 25   # must-have layers
TIMEOUT_SIGNAL = 15   # nice-to-have (fail fast)

# ── Wave definitions ─────────────────────────────────────────────────────────
# Wave 1 (CORE): 8 fetchers, 3 workers at a time → ~200MB peak
WAVE_CORE = {
    'macro_regime':       (fetch_macro_regime,   TIMEOUT_CORE),
    'fed_intelligence':   (fetch_fedwatch,       TIMEOUT_CORE),
    'economic_veto':      (fetch_veto,           TIMEOUT_CORE),
    'nowcast':            (fetch_nowcast,         TIMEOUT_CORE),
    'dynamic_thresholds': (fetch_thresholds,     TIMEOUT_CORE),
    'hidden_hands':       (fetch_hidden_hands,   TIMEOUT_CORE),
    'derivatives':        (fetch_derivatives,    TIMEOUT_CORE),
    'kill_chain_state':   (fetch_kill_chain,     TIMEOUT_CORE),
}

# Wave 2 (SIGNAL): 5 fetchers, 3 workers — runs AFTER wave 1 finishes and frees memory
WAVE_SIGNAL = {
    'adp_prediction':   (fetch_adp_prediction,   TIMEOUT_SIGNAL),
    'gdp_nowcast':      (fetch_gdp_nowcast,      TIMEOUT_SIGNAL),
    'jobless_claims':   (fetch_jobless_claims,    TIMEOUT_SIGNAL),
    'pivots':           (fetch_pivots,            TIMEOUT_SIGNAL),
    'squeeze_context':  (fetch_squeeze_context,   TIMEOUT_SIGNAL),
}


async def _run_wave(wave: dict, loop, executor) -> dict:
    """Run a wave of fetchers with per-future timeouts. Returns results dict."""
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
            logger.error(f"Layer {key} executor failed: {e}")
            results[key] = {'error': str(e)}
    return results


@router.get("/brief/master")
async def master_brief():
    """
    Unified intelligence brief — 2-wave sequential execution, 2-min TTL cache.
    Wave 1: 8 CORE fetchers (3 workers)
    Wave 2: 5 SIGNAL fetchers (3 workers) — starts AFTER wave 1 frees memory
    asyncio.Lock: only ONE compute runs at a time.
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

        # Wave 1: CORE (heavy — macro, fed, derivatives, KC, hidden_hands)
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = await _run_wave(WAVE_CORE, loop, executor)
        # executor.__exit__ joins threads → memory freed before wave 2

        # Wave 2: SIGNAL (lighter — ADP, GDP, jobless, pivots, squeeze)
        with ThreadPoolExecutor(max_workers=3) as executor:
            signal_results = await _run_wave(WAVE_SIGNAL, loop, executor)
        results.update(signal_results)

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
