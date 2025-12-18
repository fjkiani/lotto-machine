#!/usr/bin/env python3
"""
Run the Alpha Terminal Backend API

Starts the FastAPI server with Savage LLM Agent endpoints.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Start the FastAPI server"""
    try:
        import uvicorn
        from backend.app.main import app
        
        port = int(os.getenv("PORT", 8000))
        host = os.getenv("HOST", "0.0.0.0")
        
        logger.info("=" * 70)
        logger.info("🔥 ALPHA TERMINAL BACKEND API - STARTING")
        logger.info("=" * 70)
        logger.info(f"   Host: {host}")
        logger.info(f"   Port: {port}")
        logger.info(f"   API Docs: http://{host}:{port}/docs")
        logger.info("=" * 70)
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            reload=True  # Auto-reload on code changes
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

