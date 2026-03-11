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

from backend.app.api.v1 import agents, websocket, dp, health, market, killchain, signals, darkpool, gamma, options, squeeze, charts, agentx, calendar, enrichment, economic, pivots, cot, ta
from backend.app.core.dependencies import set_monitor_bridge

# Try to import and initialize monitor
try:
    from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
    MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("UnifiedAlphaMonitor not available - running without monitor")
    MONITOR_AVAILABLE = False
    UnifiedAlphaMonitor = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        except Exception as e:
            logger.error(f"Error initializing monitor: {e}", exc_info=True)
    else:
        logger.warning("⚠️ Running without monitor - agent endpoints will have limited functionality")

    # Background brain polling — keeps intelligence warm every 15 min
    asyncio.create_task(_brain_polling_loop())

    # Start DP snapshot recorder (5min during market hours)
    try:
        from live_monitoring.enrichment.apis.dp_snapshot_recorder import DPSnapshotRecorder
        dp_recorder = DPSnapshotRecorder(db_path='/tmp/dp_timeseries.db')
        threading.Thread(target=dp_recorder.run_continuous, args=(5,), daemon=True).start()
        logger.info("✅ DP snapshot recorder started (5min)")
    except Exception as e:
        logger.error(f"⚠️ DP snapshot recorder failed: {e}")

    # Start AXLFI signal differ (60min during market hours)
    try:
        from live_monitoring.enrichment.apis.axlfi_signal_differ import AXLFISignalDiffer
        threading.Thread(target=AXLFISignalDiffer().run_continuous, args=(60,), daemon=True).start()
        logger.info("✅ AXLFI signal differ started (60min)")
    except Exception as e:
        logger.error(f"⚠️ AXLFI signal differ failed: {e}")

    # Start volume spike detector (5min during market hours)
    try:
        from live_monitoring.enrichment.apis.volume_spike_detector import VolumeSpikeDetector
        threading.Thread(target=VolumeSpikeDetector(symbol='SPY').run_continuous, args=(5,), daemon=True).start()
        logger.info("✅ Volume spike detector started (5min)")
    except Exception as e:
        logger.error(f"⚠️ Volume spike detector failed: {e}")

    # Start option wall tracker (30min during market hours)
    try:
        from live_monitoring.enrichment.apis.option_wall_tracker import OptionWallTracker
        threading.Thread(target=OptionWallTracker().run_continuous, args=(30,), daemon=True).start()
        logger.info("✅ Option wall tracker started (30min)")
    except Exception as e:
        logger.error(f"⚠️ Option wall tracker failed: {e}")


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
        from live_monitoring.enrichment.apis.axlfi_signal_differ import AXLFISignalDiffer
        differ = AXLFISignalDiffer()
        return differ.get_latest()
    except Exception as e:
        return {"error": str(e)}


@app.get("/volume-spikes")
async def volume_spikes():
    """SPY intraday volume spike events."""
    try:
        from live_monitoring.enrichment.apis.volume_spike_detector import VolumeSpikeDetector
        detector = VolumeSpikeDetector()
        return detector.get_latest()
    except Exception as e:
        return {"error": str(e)}


@app.get("/option-walls")
async def option_walls():
    """SPY/QQQ/IWM option wall levels."""
    try:
        from live_monitoring.enrichment.apis.option_wall_tracker import OptionWallTracker
        tracker = OptionWallTracker()
        return tracker.get_latest()
    except Exception as e:
        return {"error": str(e)}


@app.get("/kill-shots-live")
async def kill_shots_live():
    """LIVE Kill Shots Divergence Score — all layers, no InstitutionalContext needed."""
    try:
        score = 0
        layers = {}
        reasons = []

        # 2.7 Brain Conviction
        try:
            from live_monitoring.core.brain_manager import BrainManager
            bm = BrainManager()
            brain_report = bm.get_report(use_cache=True)
            if brain_report:
                boost = brain_report.get('divergence_boost', 0)
                score += boost
                layers['brain_boost'] = boost
                layers['brain_reasons'] = brain_report.get('reasons', [])
                for r in brain_report.get('reasons', []):
                    reasons.append(f"Brain: {r}")
        except Exception as e:
            layers['brain_error'] = str(e)

        # 2.8 COT Extreme Divergence
        try:
            from live_monitoring.enrichment.apis.cot_client import COTClient
            cot_client = COTClient(cache_ttl=3600)
            cot_div = cot_client.get_divergence_signal("ES")
            cot_add = 0
            if cot_div and cot_div.get("divergent"):
                specs = cot_div.get("specs_net", 0)
                comms = cot_div.get("comm_net", 0)
                if specs < -100_000 and comms > 50_000:
                    cot_add = 3
                    reasons.append(f"COT EXTREME: specs {specs:+,}, comms {comms:+,}")
                elif specs < -50_000 and comms > 25_000:
                    cot_add = 1
                    reasons.append(f"COT mild: specs {specs:+,}, comms {comms:+,}")
                layers['cot_specs_net'] = specs
                layers['cot_comm_net'] = comms
                layers['cot_date'] = cot_div.get('report_date')
            score += cot_add
            layers['cot_boost'] = cot_add
            layers['cot_divergent'] = cot_div.get('divergent', False) if cot_div else False
        except Exception as e:
            layers['cot_error'] = str(e)

        # 2.9 GEX Regime (VIX ratio proxy)
        gex_add = 0
        try:
            import yfinance as yf
            vix = yf.Ticker('^VIX').history(period='1d')['Close'].iloc[-1]
            vix3m = yf.Ticker('^VIX3M').history(period='1d')['Close'].iloc[-1]
            ratio = vix / vix3m
            layers['vix'] = round(float(vix), 2)
            layers['vix3m'] = round(float(vix3m), 2)
            layers['vix_ratio'] = round(float(ratio), 4)
            if ratio < 0.85:
                gex_add = 1
                layers['gex_regime'] = 'STRONG_POSITIVE'
                reasons.append(f"GEX strong positive (VIX ratio {ratio:.3f})")
            elif ratio < 1.0:
                layers['gex_regime'] = 'MILD_POSITIVE'
            elif ratio < 1.15:
                layers['gex_regime'] = 'MILD_NEGATIVE'
            else:
                layers['gex_regime'] = 'STRONG_NEGATIVE'
            score += gex_add
            layers['gex_boost'] = gex_add
        except Exception as e:
            layers['gex_error'] = str(e)

        # 2.10 Combined GEX + COT
        cot_extreme = layers.get('cot_boost', 0) >= 3
        gex_positive = layers.get('gex_regime', '') in ('STRONG_POSITIVE', 'MILD_POSITIVE')
        combined_add = 2 if (cot_extreme and gex_positive) else 0
        score += combined_add
        layers['combined_boost'] = combined_add
        if combined_add > 0:
            reasons.append(f"COMBINED: GEX+ ({layers.get('gex_regime')}) + COT Extreme → +2")

        # 2.5 Fed vs Dark Pool
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            sc = StockgridClient(cache_ttl=300)
            spy_detail = sc.get_ticker_detail('SPY')
            if spy_detail:
                sv_pct = spy_detail.short_volume_pct or 0
                layers['spy_short_vol_pct'] = round(sv_pct, 2)
                brain_tones = layers.get('brain_reasons', [])
                fed_hawkish = any('HAWKISH' in str(r).upper() for r in brain_tones)
                if fed_hawkish and sv_pct > 55:
                    score += 3
                    layers['fed_dp_divergence'] = True
                    reasons.append(f"Fed HAWKISH + SPY dark pool loading ({sv_pct:.1f}% SV)")
                else:
                    layers['fed_dp_divergence'] = False
        except Exception as e:
            layers['dp_error'] = str(e)

        # Verdict
        if score > 7:
            verdict = "BOOST"
            action = "+15% confidence on all signals"
        elif score >= 5:
            verdict = "NEUTRAL"
            action = "Signals pass through unchanged"
        elif score > 0:
            verdict = "SOFT_VETO"
            action = "Signals pass ONLY if no narrative divergence"
        else:
            verdict = "HARD_VETO"
            action = "All signals killed"

        return {
            'divergence_score': score,
            'verdict': verdict,
            'action': action,
            'layers': layers,
            'reasons': reasons,
            'timestamp': datetime.now().isoformat(),
        }
    except Exception as e:
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

