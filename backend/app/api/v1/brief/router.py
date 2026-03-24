"""
brief/router.py — Thin FastAPI endpoint for GET /brief/master.

Orchestrates 18 parallel fetchers via ThreadPoolExecutor + asyncio.wait_for.
asyncio.Lock ensures only ONE heavy compute runs at a time — concurrent
requests wait for in-flight compute then serve from cache (prevents double
OOM on Render's 512MB instance).

Max workers: 6 → ~360MB peak on cold start (down from 10/18).
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import APIRouter

from .cache import lazy, get_cache, set_cache, _brief_lock   # noqa: F401
from .alert_engine import PreSignalAlertEngine
from .fetchers import (
    fetch_macro_regime, fetch_fedwatch, fetch_veto,
    fetch_nowcast, fetch_thresholds, fetch_hidden_hands,
    fetch_derivatives, fetch_kill_chain,
    fetch_adp_prediction, fetch_gdp_nowcast, fetch_jobless_claims,
    fetch_pmi, fetch_current_account, fetch_umich_sentiment,
    fetch_umich_expectations, fetch_pivots,
    fetch_squeeze_context, fetch_squeeze_watchlist,
)

logger       = logging.getLogger(__name__)
router       = APIRouter()
_alert_engine = PreSignalAlertEngine()

# ── Tiered timeouts (seconds) ────────────────────────────────────────────────
TIMEOUT_CORE     = 30   # regime, fed, KC, derivatives — must succeed
TIMEOUT_SIGNAL   = 25   # ADP, GDP, jobless, hidden_hands
TIMEOUT_ENRICHED = 8    # pivots, pmi, umich, current_account — nice-to-have


@router.get("/brief/master")
async def master_brief():
    """
    Unified intelligence brief — 18 parallel layers, 2-min TTL cache.
    asyncio.Lock: only ONE compute runs at a time — concurrents wait for cache.
    """
    # ── Fast path: cache hit ──────────────────────────────────────────────────
    cached = get_cache()
    if cached is not None:
        return cached

    # ── Slow path: compute under mutex ───────────────────────────────────────
    async with _brief_lock:
        cached = get_cache()          # re-check inside lock
        if cached is not None:
            return cached

        t0 = time.time()
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor(max_workers=6) as executor:
            raw_futures = {
                'macro_regime':       (loop.run_in_executor(executor, fetch_macro_regime),     TIMEOUT_CORE),
                'fed_intelligence':   (loop.run_in_executor(executor, fetch_fedwatch),        TIMEOUT_CORE),
                'economic_veto':      (loop.run_in_executor(executor, fetch_veto),            TIMEOUT_CORE),
                'nowcast':            (loop.run_in_executor(executor, fetch_nowcast),         TIMEOUT_SIGNAL),
                'dynamic_thresholds': (loop.run_in_executor(executor, fetch_thresholds),     TIMEOUT_SIGNAL),
                'hidden_hands':       (loop.run_in_executor(executor, fetch_hidden_hands),   TIMEOUT_SIGNAL),
                'derivatives':        (loop.run_in_executor(executor, fetch_derivatives),    TIMEOUT_CORE),
                'pivots':             (loop.run_in_executor(executor, fetch_pivots),          TIMEOUT_ENRICHED),
                'kill_chain_state':   (loop.run_in_executor(executor, fetch_kill_chain),     TIMEOUT_CORE),
                'adp_prediction':     (loop.run_in_executor(executor, fetch_adp_prediction), TIMEOUT_SIGNAL),
                'gdp_nowcast':        (loop.run_in_executor(executor, fetch_gdp_nowcast),    TIMEOUT_SIGNAL),
                'jobless_claims':     (loop.run_in_executor(executor, fetch_jobless_claims), TIMEOUT_SIGNAL),
                'pmi':                (loop.run_in_executor(executor, fetch_pmi),             TIMEOUT_ENRICHED),
                'current_account':    (loop.run_in_executor(executor, fetch_current_account), TIMEOUT_ENRICHED),
                'umich_sentiment':    (loop.run_in_executor(executor, fetch_umich_sentiment), TIMEOUT_ENRICHED),
                'umich_expectations': (loop.run_in_executor(executor, fetch_umich_expectations), TIMEOUT_ENRICHED),
                'squeeze_context':    (loop.run_in_executor(executor, fetch_squeeze_context),    TIMEOUT_ENRICHED),
                'squeeze_watchlist':  (loop.run_in_executor(executor, fetch_squeeze_watchlist),  TIMEOUT_ENRICHED),
            }

            results: dict = {}
            for key, (future, timeout_s) in raw_futures.items():
                try:
                    results[key] = await asyncio.wait_for(future, timeout=timeout_s)
                except asyncio.TimeoutError:
                    logger.warning(f"Layer {key} timed out after {timeout_s}s")
                    results[key] = {'error': f'timeout after {timeout_s}s'}
                except Exception as e:
                    logger.error(f"Layer {key} executor failed: {e}")
                    results[key] = {'error': str(e)}

        # ── Post-processing (sequential — depends on prior results) ──────────
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
