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

from backend.app.api.v1 import agents, websocket
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


@app.on_event("startup")
async def startup():
    """Initialize monitor bridge on startup"""
    if MONITOR_AVAILABLE:
        try:
            # Initialize monitor (it may already be running)
            # In production, we might want to connect to an existing instance
            monitor = UnifiedAlphaMonitor()
            
            # Set in bridge
            set_monitor_bridge(monitor)
            
            logger.info("✅ Monitor bridge initialized")
        except Exception as e:
            logger.error(f"Error initializing monitor: {e}", exc_info=True)
    else:
        logger.warning("⚠️ Running without monitor - agent endpoints will have limited functionality")


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

