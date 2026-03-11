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
    """Initialize monitor bridge + start background brain polling."""
    import asyncio

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

