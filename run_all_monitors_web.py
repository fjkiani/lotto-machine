#!/usr/bin/env python3
"""
🎯 ALPHA INTELLIGENCE - WEB SERVICE VERSION (FREE TIER!)

Wraps run_all_monitors.py in a FastAPI web server so it stays awake on Render free tier.

Features:
- HTTP health check endpoint
- Background monitoring loop
- Self-pinging to prevent sleep (every 10 minutes)
- All monitors run in parallel

Usage:
    python3 run_all_monitors_web.py

Environment Variables:
    DISCORD_WEBHOOK_URL - Discord webhook (required)
    PERPLEXITY_API_KEY - For news/Trump intelligence
    CHARTEXCHANGE_API_KEY - For dark pool data
    FRED_API_KEY - For economic data
    PORT - Port for web server (Render sets automatically)
"""

import os
import sys
import time
import logging
import threading
import requests
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# Global monitor instance
monitor = None


def run_monitors():
    """Run the unified monitor in background thread."""
    global monitor
    
    try:
        from run_all_monitors import UnifiedAlphaMonitor
        
        logger.info("🚀 Starting Unified Alpha Monitor...")
        monitor = UnifiedAlphaMonitor()
        monitor.run()
        
    except Exception as e:
        logger.error(f"❌ Monitor error: {e}")
        import traceback
        logger.error(traceback.format_exc())


def self_ping():
    """
    Self-ping to keep Render free tier awake.
    
    Pings the health endpoint every 10 minutes to prevent sleep.
    """
    port = int(os.getenv('PORT', 8000))
    url = f"http://localhost:{port}/health"
    
    while True:
        try:
            time.sleep(600)  # Every 10 minutes
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.debug("✅ Self-ping successful (keeping service awake)")
            else:
                logger.warning(f"⚠️ Self-ping returned {response.status_code}")
        except Exception as e:
            logger.debug(f"Self-ping error: {e}")


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health checks and status."""
    
    def do_GET(self):
        global monitor
        
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            status = {
                "status": "running",
                "service": "alpha-intelligence-monitor",
                "timestamp": datetime.now().isoformat(),
                "monitor_running": monitor is not None and monitor.running if monitor else False,
            }
            
            # Add monitor stats if available
            if monitor:
                try:
                    status["fed_enabled"] = getattr(monitor, 'fed_enabled', False)
                    status["trump_enabled"] = getattr(monitor, 'trump_enabled', False)
                    status["econ_enabled"] = getattr(monitor, 'econ_enabled', False)
                    status["last_fed_check"] = str(monitor.last_fed_check) if monitor.last_fed_check else None
                    status["last_econ_check"] = str(monitor.last_econ_check) if monitor.last_econ_check else None
                except:
                    pass
            
            self.wfile.write(json.dumps(status, indent=2).encode())
            
        elif self.path == '/status':
            # Detailed status
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            status = {
                "service": "alpha-intelligence-monitor",
                "timestamp": datetime.now().isoformat(),
                "monitor": {
                    "running": monitor is not None and monitor.running if monitor else False,
                    "fed_enabled": getattr(monitor, 'fed_enabled', False) if monitor else False,
                    "trump_enabled": getattr(monitor, 'trump_enabled', False) if monitor else False,
                    "econ_enabled": getattr(monitor, 'econ_enabled', False) if monitor else False,
                },
                "environment": {
                    "discord_webhook": "✅" if os.getenv('DISCORD_WEBHOOK_URL') else "❌",
                    "perplexity_key": "✅" if os.getenv('PERPLEXITY_API_KEY') else "❌",
                    "chartexchange_key": "✅" if os.getenv('CHARTEXCHANGE_API_KEY') else "❌",
                    "fred_key": "✅" if os.getenv('FRED_API_KEY') else "❌",
                }
            }
            
            self.wfile.write(json.dumps(status, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass


def main():
    """Main entry point."""
    global monitor
    
    logger.info("=" * 70)
    logger.info("🌐 ALPHA INTELLIGENCE - WEB SERVICE STARTING")
    logger.info("=" * 70)
    
    # Check environment variables
    discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
    if not discord_webhook:
        logger.error("❌ DISCORD_WEBHOOK_URL not set!")
        logger.error("   Set it in Render dashboard: Environment → Add Environment Variable")
        sys.exit(1)
    
    logger.info("✅ Environment variables:")
    logger.info(f"   Discord: {'✅' if discord_webhook else '❌'}")
    logger.info(f"   Perplexity: {'✅' if os.getenv('PERPLEXITY_API_KEY') else '❌'}")
    logger.info(f"   ChartExchange: {'✅' if os.getenv('CHARTEXCHANGE_API_KEY') else '❌'}")
    logger.info(f"   FRED: {'✅' if os.getenv('FRED_API_KEY') else '❌'}")
    
    # Start monitor in background thread
    monitor_thread = threading.Thread(target=run_monitors, daemon=True)
    monitor_thread.start()
    logger.info("   ✅ Monitor thread started")
    
    # Start self-ping thread (keeps service awake on free tier)
    ping_thread = threading.Thread(target=self_ping, daemon=True)
    ping_thread.start()
    logger.info("   ✅ Self-ping thread started (pings every 10 min)")
    
    # Start HTTP server
    port = int(os.getenv('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    
    logger.info(f"   ✅ HTTP server on port {port}")
    logger.info(f"   Health: http://localhost:{port}/health")
    logger.info(f"   Status: http://localhost:{port}/status")
    logger.info("=" * 70)
    logger.info("🚀 ALL SYSTEMS RUNNING!")
    logger.info("=" * 70)
    
    try:
        # Run server (blocks)
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Shutting down...")
        if monitor:
            monitor.running = False
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

