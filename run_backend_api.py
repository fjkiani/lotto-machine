#!/usr/bin/env python3
"""
Run the Alpha Terminal Backend API

Starts the FastAPI server with Savage LLM Agent endpoints.
Includes self-ping keep-alive for Render free tier.
"""

import os
import sys
import logging
import threading
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


def self_ping():
    """
    Keep-alive ping for Render free tier.
    Render spins down after 15 min of inactivity.
    We ping ourselves every 2 minutes to stay alive.
    """
    import requests
    
    service_url = os.getenv('RENDER_SERVICE_URL', '')
    port = int(os.getenv('PORT', 8000))
    
    # Try external URL first, fallback to localhost
    if service_url:
        ping_url = f"{service_url}/health"
    else:
        ping_url = f"http://localhost:{port}/health"
    
    logger.info(f"🏓 Self-ping thread started → {ping_url}")
    
    # Wait for server to start
    time.sleep(10)
    
    while True:
        try:
            resp = requests.get(ping_url, timeout=10)
            logger.debug(f"🏓 Self-ping: {resp.status_code}")
        except Exception as e:
            logger.warning(f"🏓 Self-ping failed: {e}")
        
        time.sleep(120)  # Every 2 minutes


def main():
    """Start the FastAPI server"""
    try:
        import uvicorn
        from backend.app.main import app
        
        port = int(os.getenv("PORT", 8000))
        host = os.getenv("HOST", "0.0.0.0")
        is_render = bool(os.getenv("RENDER"))
        
        logger.info("=" * 70)
        logger.info("🔥 ALPHA TERMINAL BACKEND API - STARTING")
        logger.info("=" * 70)
        logger.info(f"   Host: {host}")
        logger.info(f"   Port: {port}")
        logger.info(f"   Render: {is_render}")
        logger.info(f"   API Docs: http://{host}:{port}/docs")
        logger.info("=" * 70)
        
        # Start self-ping keep-alive (CRITICAL for Render free tier)
        if is_render:
            ping_thread = threading.Thread(target=self_ping, daemon=True, name="SelfPing")
            ping_thread.start()
            logger.info("   ✅ Self-ping keep-alive started (every 2 min)")
        
        # Start paper trade scheduler in background
        try:
            from live_monitoring.paper_trade_scheduler import start_scheduler_thread
            pt_thread, pt_scheduler = start_scheduler_thread()
            logger.info("   ✅ Paper trade scheduler thread started")
        except Exception as e:
            logger.warning(f"   ⚠️ Paper trade scheduler: {e}")
        
        # Start kill chain signal logger
        try:
            from live_monitoring.kill_chain_logger import start_kill_chain_logger_thread
            kc_thread, kc_logger = start_kill_chain_logger_thread(check_interval_min=30)
            logger.info("   ✅ Kill chain signal logger started (every 30 min)")
        except Exception as e:
            logger.warning(f"   ⚠️ Kill chain logger: {e}")
        
        logger.info("=" * 70)
        logger.info("🚀 ALL SYSTEMS GO!")
        logger.info("=" * 70)
        
        if is_render:
            # On Render: no reload (reload needs import string, not app object)
            uvicorn.run(
                app,
                host=host,
                port=port,
                log_level="info",
                reload=False,
            )
        else:
            # Local dev: use import string for reload support
            uvicorn.run(
                "backend.app.main:app",
                host=host,
                port=port,
                log_level="info",
                reload=True,
            )
    except ImportError as e:
        logger.error(f"❌ Missing dependencies: {e}")
        logger.error("   Install with: pip install fastapi uvicorn redis")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error starting server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
