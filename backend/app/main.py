"""
🔥 ALPHA TERMINAL - FastAPI Application

Main entry point for the backend API with Savage LLM Agent integration.
"""

import os
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from backend.app.api.v1 import agents, websocket, dp, health, market, killchain, signals, darkpool, gamma, options, squeeze, charts, agentx, calendar, enrichment, economic, pivots, cot, ta, axlfi, gate, intraday
from backend.app.core.dependencies import set_monitor_bridge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import and initialize monitor
try:
    from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
    MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("UnifiedAlphaMonitor not available - running without monitor")
    MONITOR_AVAILABLE = False
    UnifiedAlphaMonitor = None

# Create FastAPI app
app = FastAPI(
    title="Alpha Terminal API",
    description="Real-time institutional intelligence with Savage LLM Agents",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])
app.include_router(dp.router, prefix="/api/v1", tags=["dp"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(market.router, prefix="/api/v1", tags=["market"])
app.include_router(killchain.router, prefix="/api/v1", tags=["killchain"])
app.include_router(signals.router, prefix="/api/v1", tags=["signals"])
app.include_router(darkpool.router, prefix="/api/v1", tags=["darkpool"])
app.include_router(gamma.router, prefix="/api/v1", tags=["gamma"])
app.include_router(options.router, prefix="/api/v1", tags=["options"])
app.include_router(squeeze.router, prefix="/api/v1", tags=["squeeze"])
app.include_router(charts.router, prefix="/api/v1", tags=["charts"])
app.include_router(agentx.router, prefix="/api/v1", tags=["agentx"])
app.include_router(calendar.router, prefix="/api/v1", tags=["calendar"])
app.include_router(enrichment.router, prefix="/api/v1", tags=["enrichment"])
app.include_router(economic.router, prefix="/api/v1", tags=["economic"])
app.include_router(pivots.router, prefix="/api/v1", tags=["pivots"])
app.include_router(cot.router, prefix="/api/v1", tags=["cot"])
app.include_router(ta.router, prefix="/api/v1", tags=["ta"])
app.include_router(axlfi.router, prefix="/api/v1", tags=["axlfi"])
app.include_router(gate.router, prefix="/api/v1", tags=["gate"])
app.include_router(intraday.router, prefix="/api/v1", tags=["intraday"])


@app.get("/debug/supabase")
async def debug_supabase():
    """Diagnostic endpoint: check Supabase env vars, connectivity, and alert count."""
    import os
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    result = {
        "env_SUPABASE_URL": url[:30] + "..." if url else "MISSING",
        "env_SUPABASE_KEY": key[:8] + "..." if key else "MISSING",
        "is_available": False,
        "alert_count": None,
        "error": None,
    }
    try:
        from core.utils.supabase_storage import is_supabase_available, read_alerts
        result["is_available"] = is_supabase_available()
        if result["is_available"]:
            alerts = read_alerts(limit=5)
            result["alert_count"] = len(alerts)
            result["latest_5"] = [
                {"type": a.get("alert_type"), "sym": a.get("symbol"), "ts": a.get("timestamp", "")[:19]}
                for a in alerts
            ]
    except Exception as e:
        result["error"] = str(e)
    return result




# Global thread status tracking
_thread_status = {}
_pipe_instances = {}
_startup_errors = {}  # Captures init failures at startup for /startup-errors

def _run_pipe(name, instance, method_name, interval, first_capture_method=None):
    """Wrapper that tracks thread status and does immediate first capture."""
    import traceback as tb
    _thread_status[name] = {'status': 'starting', 'started': datetime.now().isoformat()}
    try:
        # Immediate first capture
        if first_capture_method:
            try:
                result = first_capture_method()
                _thread_status[name]['first_capture'] = 'ok'
                _thread_status[name]['first_result'] = str(result)[:200]
                logger.info(f"✅ {name}: first capture complete")
            except Exception as e:
                _thread_status[name]['first_capture'] = f'error: {e}'
                logger.error(f"⚠️ {name} first capture failed: {e}")
        # Start continuous loop
        _thread_status[name]['status'] = 'running'
        getattr(instance, method_name)(interval)
    except Exception as e:
        _thread_status[name]['status'] = f'crashed: {e}'
        _thread_status[name]['traceback'] = tb.format_exc()
        logger.error(f"💀 {name} thread crashed: {e}")


@app.on_event("startup")
async def startup():
    """Initialize monitor bridge + start background data capture threads."""
    import asyncio
    import threading

    if MONITOR_AVAILABLE:
        try:
            monitor = UnifiedAlphaMonitor()
            set_monitor_bridge(monitor)
            logger.info("✅ Monitor bridge initialized")

            # Start the monitor's main run loop as a daemon thread.
            _thread_status['monitor_run_loop'] = {'status': 'starting', 'started': datetime.now().isoformat()}
            def _monitor_run_wrapper():
                import traceback as _tb
                try:
                    _thread_status['monitor_run_loop']['status'] = 'running'
                    monitor.run()
                    _thread_status['monitor_run_loop']['status'] = 'exited'
                except Exception as _e:
                    _thread_status['monitor_run_loop']['status'] = f'crashed: {_e}'
                    _thread_status['monitor_run_loop']['traceback'] = _tb.format_exc()
                    _startup_errors['monitor_run_loop'] = str(_e)
                    logger.error(f"💀 monitor-run-loop crashed: {_e}")
            threading.Thread(target=_monitor_run_wrapper, daemon=True, name="monitor-run-loop").start()
            logger.info("✅ Monitor run loop thread launched")

            # 🔥 FIX #2: Start the Kill Chain triple-confluence logger.
            # This tracks COT divergence + GEX + DVR and fires on activation/deactivation.
            try:
                from live_monitoring.kill_chain_logger import start_kill_chain_logger_thread
                kc_thread, kc_logger_instance = start_kill_chain_logger_thread(check_interval_min=30)
                _pipe_instances['kill_chain_logger'] = kc_logger_instance
                _thread_status['kill_chain_logger'] = {
                    'status': 'running',
                    'started': datetime.now().isoformat(),
                }
                logger.info("✅ Kill Chain Logger thread launched")
            except Exception as kc_e:
                logger.error(f"⚠️ Kill Chain Logger failed to init: {kc_e}")
                _thread_status['kill_chain_logger'] = {'status': f'init_failed: {kc_e}'}

            # 🔥 FIX #3: Share the monitor's health registry with the health API.
            # health.py creates its own orphan CheckerHealthRegistry() — replace it with
            # the live one that the monitor's checkers actually write to.
            try:
                from backend.app.api.v1 import health as health_module
                health_module.health_registry = monitor.health_registry
                logger.info("✅ Health registry connected to monitor's live registry")
            except Exception as hr_e:
                logger.warning(f"⚠️ Could not connect health registry: {hr_e}")

            # 🔥 FIX #4: Start the paper trade scheduler (built but never started locally).
            # Watches TE calendar for CPI/Housing releases, runs SurpriseEngine,
            # pulls 30m Alpaca bars, logs to Discord. 476 lines — fully sandbagged.
            try:
                from live_monitoring.paper_trade_scheduler import start_scheduler_thread
                pt_thread, pt_scheduler = start_scheduler_thread()
                _pipe_instances['paper_trade_scheduler'] = pt_scheduler
                _thread_status['paper_trade_scheduler'] = {
                    'status': 'running',
                    'started': datetime.now().isoformat(),
                }
                logger.info("✅ Paper trade scheduler thread launched")
            except Exception as pt_e:
                logger.warning(f"⚠️ Paper trade scheduler failed to init: {pt_e}")
                _thread_status['paper_trade_scheduler'] = {'status': f'init_failed: {pt_e}'}

            # 🔥 FIX #5: Start the FRED economic release capture thread.
            # Polls FRED every 15 min for CPI, PCE, GDP, PPI, unemployment, etc.
            # Writes new releases to economic_intelligence.db + alerts_history.db.
            try:
                from live_monitoring.core.econ_release_capture import start_capture_thread
                econ_thread, _ = start_capture_thread(interval_minutes=15)
                _thread_status['econ_release_capture'] = {
                    'status': 'running',
                    'started': datetime.now().isoformat(),
                }
                logger.info("✅ Economic release capture thread launched (FRED → DB)")
            except Exception as econ_e:
                logger.warning(f"⚠️ Economic release capture failed to init: {econ_e}")
                _thread_status['econ_release_capture'] = {'status': f'init_failed: {econ_e}'}

        except Exception as e:
            import traceback as _tb
            _startup_errors['monitor_init'] = str(e)
            _startup_errors['monitor_init_traceback'] = _tb.format_exc()
            _thread_status['monitor_run_loop'] = {'status': f'init_failed: {e}'}
            _thread_status['kill_chain_logger'] = {'status': 'skipped (monitor init failed)'}
            _thread_status['paper_trade_scheduler'] = {'status': 'skipped (monitor init failed)'}
            _thread_status['econ_release_capture'] = {'status': 'skipped (monitor init failed)'}
            logger.error(f"Error initializing monitor: {e}", exc_info=True)
    else:
        logger.warning("⚠️ Running without monitor - agent endpoints will have limited functionality")

    # Background brain polling — keeps intelligence warm every 15 min
    asyncio.create_task(_brain_polling_loop())

    # Start DP snapshot recorder (5min)
    try:
        from live_monitoring.enrichment.apis.dp_snapshot_recorder import DPSnapshotRecorder
        dp = DPSnapshotRecorder(db_path='/tmp/dp_timeseries.db')
        _pipe_instances['dp_recorder'] = dp
        threading.Thread(
            target=_run_pipe,
            args=('dp_recorder', dp, 'run_continuous', 5, lambda: dp.capture_snapshot(symbols=['SPY'])),
            daemon=True
        ).start()
        logger.info("✅ DP snapshot recorder thread launched")
    except Exception as e:
        logger.error(f"⚠️ DP snapshot recorder failed to init: {e}")
        _thread_status['dp_recorder'] = {'status': f'init_failed: {e}'}

    # Start AXLFI signal differ (60min)
    try:
        from live_monitoring.enrichment.apis.axlfi_signal_differ import AXLFISignalDiffer
        sd = AXLFISignalDiffer()
        _pipe_instances['signal_differ'] = sd
        threading.Thread(
            target=_run_pipe,
            args=('signal_differ', sd, 'run_continuous', 60, sd.capture_and_diff),
            daemon=True
        ).start()
        logger.info("✅ AXLFI signal differ thread launched")
    except Exception as e:
        logger.error(f"⚠️ AXLFI signal differ failed to init: {e}")
        _thread_status['signal_differ'] = {'status': f'init_failed: {e}'}

    # Start volume spike detector (5min)
    try:
        from live_monitoring.enrichment.apis.volume_spike_detector import VolumeSpikeDetector
        vs = VolumeSpikeDetector(symbol='SPY')
        _pipe_instances['volume_spikes'] = vs
        threading.Thread(
            target=_run_pipe,
            args=('volume_spikes', vs, 'run_continuous', 5, vs.check_for_spikes),
            daemon=True
        ).start()
        logger.info("✅ Volume spike detector thread launched")
    except Exception as e:
        logger.error(f"⚠️ Volume spike detector failed to init: {e}")
        _thread_status['volume_spikes'] = {'status': f'init_failed: {e}'}

    # Start option wall tracker (30min)
    try:
        from live_monitoring.enrichment.apis.option_wall_tracker import OptionWallTracker
        ow = OptionWallTracker()
        _pipe_instances['option_walls'] = ow
        threading.Thread(
            target=_run_pipe,
            args=('option_walls', ow, 'run_continuous', 30, ow.capture_walls),
            daemon=True
        ).start()
        logger.info("✅ Option wall tracker thread launched")
    except Exception as e:
        logger.error(f"⚠️ Option wall tracker failed to init: {e}")
        _thread_status['option_walls'] = {'status': f'init_failed: {e}'}

    # Start pre-market scheduler (restart-resilient, catches up missed stages)
    try:
        from live_monitoring.premarket_scheduler import start_scheduler_thread
        pm_thread = start_scheduler_thread()
        _thread_status['premarket_scheduler'] = {
            'status': 'running',
            'started': datetime.now().isoformat(),
        }
        logger.info("✅ Pre-market scheduler thread launched (restart-resilient)")
    except Exception as pm_e:
        logger.warning(f"⚠️ Pre-market scheduler failed to init: {pm_e}")
        _thread_status['premarket_scheduler'] = {'status': f'init_failed: {pm_e}'}


async def _brain_polling_loop():
    """Continuous brain polling — agents run even with zero frontend traffic."""
    import asyncio
    await asyncio.sleep(10)  # Let startup finish first
    while True:
        try:
            from live_monitoring.core.brain_manager import BrainManager
            bm = BrainManager()
            report = bm.get_report(use_cache=False)
            boost = report.get("divergence_boost", 0) if report else "N/A"
            logger.info(f"🧠 Background brain poll complete — divergence_boost={boost}")
        except Exception as e:
            logger.error(f"Brain poll failed: {e}")
        await asyncio.sleep(900)  # 15 minutes


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "ALPHA TERMINAL API ONLINE",
        "version": "1.0.0",
        "savage_agents": "enabled",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "monitor_available": MONITOR_AVAILABLE,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/kill-chain")
async def kill_chain_signals():
    """Kill chain triple confluence signal log."""
    try:
        from live_monitoring.kill_chain_logger import get_kill_chain_signals
        signals = get_kill_chain_signals()
        latest = signals[-1] if signals else {}
        activations = [s for s in signals if s.get('type') == 'ACTIVATION']
        return {
            "total_checks": len(signals),
            "activations": len(activations),
            "current_state": latest,
            "history": signals[-50:],
        }
    except Exception as e:
        return {"error": str(e), "signals": []}


@app.get("/paper-trades")
async def paper_trades():
    """Paper trade log for economic surprise signals."""
    try:
        from live_monitoring.paper_trade_scheduler import get_paper_trades
        trades = get_paper_trades()
        clean = [t for t in trades if t.get('correct') is not None and not t.get('macro_filtered')]
        wins = sum(1 for t in clean if t['correct'])
        return {
            'total_trades': len(trades),
            'clean_trades': len(clean),
            'clean_accuracy': f'{wins}/{len(clean)}={wins/len(clean)*100:.0f}%' if clean else 'N/A',
            'trades': trades,
        }
    except Exception as e:
        return {"error": str(e), "trades": []}


@app.get("/dp-snapshots")
async def dp_snapshots():
    """Dark pool snapshot timeseries."""
    try:
        import sqlite3
        db_path = '/tmp/dp_timeseries.db'
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT timestamp, symbol, short_vol_pct, json_data FROM dp_snapshots ORDER BY id DESC LIMIT 20"
            ).fetchall()
            conn.close()
            import json as _json
            snapshots = [{"timestamp": r[0], "symbol": r[1], "short_vol_pct": r[2], "data": _json.loads(r[3])} for r in rows]
            return {"total": len(snapshots), "snapshots": snapshots}
        return {"total": 0, "snapshots": [], "note": "recorder not yet started"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/signal-diffs")
async def signal_diffs():
    """AXLFI signal regime changes."""
    try:
        inst = _pipe_instances.get('signal_differ')
        if inst:
            return inst.get_latest()
        from live_monitoring.enrichment.apis.axlfi_signal_differ import AXLFISignalDiffer
        return AXLFISignalDiffer().get_latest()
    except Exception as e:
        return {"error": str(e)}


@app.get("/volume-spikes")
async def volume_spikes():
    """SPY intraday volume spike events."""
    try:
        inst = _pipe_instances.get('volume_spikes')
        if inst:
            return inst.get_latest()
        from live_monitoring.enrichment.apis.volume_spike_detector import VolumeSpikeDetector
        return VolumeSpikeDetector().get_latest()
    except Exception as e:
        return {"error": str(e)}


@app.get("/option-walls")
async def option_walls():
    """SPY/QQQ/IWM option wall levels."""
    try:
        inst = _pipe_instances.get('option_walls')
        if inst:
            return inst.get_latest()
        from live_monitoring.enrichment.apis.option_wall_tracker import OptionWallTracker
        return OptionWallTracker().get_latest()
    except Exception as e:
        return {"error": str(e)}


@app.get("/startup-errors")
async def startup_errors():
    """Expose startup init errors — use this when thread-status shows missing/failed threads."""
    return {
        "errors": _startup_errors,
        "has_errors": len(_startup_errors) > 0,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/thread-status")
async def thread_status():
    """Diagnostic: status of all background data capture threads."""
    return {
        "threads": _thread_status,
        "instances": {k: type(v).__name__ for k, v in _pipe_instances.items()},

        "timestamp": datetime.now().isoformat(),
    }


@app.get("/signal-intel")
async def signal_intel():
    """Full tactical signal intelligence — answers all manager questions in one call."""
    try:
        from live_monitoring.enrichment.apis.signal_intel_engine import SignalIntelEngine
        engine = SignalIntelEngine()
        return engine.generate_report()
    except Exception as e:
        logger.error(f"Signal intel failed: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/morning-brief")
async def morning_brief():
    """Today's trader brief — zero-click, auto-generated by pre-market scheduler."""
    try:
        from live_monitoring.enrichment.apis.morning_brief_generator import MorningBriefGenerator
        return MorningBriefGenerator.get_latest()
    except Exception as e:
        logger.error(f"Morning brief failed: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/morning-brief/generate")
async def morning_brief_generate():
    """Force-generate today's brief (for testing / manual trigger)."""
    try:
        from live_monitoring.enrichment.apis.morning_brief_generator import MorningBriefGenerator
        gen = MorningBriefGenerator()
        return gen.generate(force=True)
    except Exception as e:
        logger.error(f"Morning brief generate failed: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/kill-shots-live")
async def kill_shots_live():
    """
    LIVE Kill Shots Divergence Score — Modular
    Orchestrates the 5 core scorers (Brain, COT, GEX, Fed/DP, Combined).
    """
    try:
        score = 0
        layers = {}
        reasons = []
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Import scorers
        from backend.app.signals.brain_scorer import BrainScorer
        from backend.app.signals.cot_scorer import CotScorer
        from backend.app.signals.gex_scorer import GexScorer
        from backend.app.signals.fed_dp_scorer import FedDpScorer
        from backend.app.signals.combined_scorer import CombinedScorer

        # Evaluate
        brain_res = BrainScorer().evaluate()
        cot_res = CotScorer().evaluate(symbol="ES")
        gex_res = GexScorer().evaluate(cot_boost=cot_res.boost)
        fed_dp_res = FedDpScorer().evaluate(brain_reasons=brain_res.reasons)
        combined_res = CombinedScorer().evaluate(gex_result=gex_res, cot_result=cot_res)

        # Aggregate Results
        for res in [brain_res, cot_res, gex_res, fed_dp_res, combined_res]:
            score += res.boost
            reasons.extend(res.reasons)
            
            # Map back to flat 'layers' dict for backward-compatibility
            # and to feed the existing SignalExplainer
            prefix = res.name.lower()
            layers[f"{prefix}_boost"] = res.boost
            layers[f"{prefix}_slug"] = res.slug
            layers[f"{prefix}_source_date"] = res.source_date
            layers[f"{prefix}_timestamp"] = res.timestamp
            
            # Merge raw data directly into layers
            for k, v in res.raw.items():
                layers[k] = v

        # ── VERDICT & ACTION PLAN ──────────────────────────────────────────
        action_plan = {
            "position": "NEUTRAL",
            "entry_trigger": "N/A",
            "invalidation": "N/A",
            "time_window": "Intraday"
        }

        if score > 7:
            verdict = "BOOST"
            action = "+15% confidence on all signals"
            action_plan["position"] = "1/3 LONG"
            action_plan["entry_trigger"] = "SPX clears +0.5% early AM"
            action_plan["invalidation"] = "SPY loses VWAP for >15min"
            action_plan["time_window"] = "1-3 Days"
        elif score >= 5:
            verdict = "NEUTRAL"
            action = "Signals pass through unchanged"
        elif score > 0:
            verdict = "SOFT_VETO"
            action = "Signals pass ONLY if no narrative divergence"
            action_plan["invalidation"] = "SPX pushes > +1.0%"
        else:
            verdict = "HARD_VETO"
            action = "All signals killed"

        # ── LLM EXPLANATIONS ─────────────────────────────────────────────
        explanations = {}
        try:
            from backend.app.signals.signal_explainer import SignalExplainer
            explainer = SignalExplainer()
            explanations = explainer.explain_all(layers)
        except Exception as e:
            logger.warning(f"LLM explanations skipped: {e}")

        # Map explanations directly into layers for Phase 3 Pillar UI mapping
        for key, text in explanations.items():
            layers[f"explanation_{key}"] = text

        return {
            'divergence_score': score,
            'verdict': verdict,
            'action': action,
            'action_plan': action_plan,
            'layers': layers,
            'reasons': reasons,
            'explanations': explanations, # Kept for backward compatibility
            'timestamp': now_iso,
        }
    except Exception as e:
        logger.error(f"Kill Shots Live Error: {e}")
        return {"error": str(e)}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

