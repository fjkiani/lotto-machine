#!/usr/bin/env python3
"""
🎯 ALPHA INTELLIGENCE - MODULAR PIPELINE

New modular version of run_all_monitors.py

Usage:
    python3 run_pipeline.py

This uses the new modular architecture:
- live_monitoring/pipeline/components/ - Individual capabilities
- live_monitoring/pipeline/config.py - Centralized configuration
- Clean separation of concerns
- Testable components
"""

import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

from live_monitoring.pipeline.orchestrator import PipelineOrchestrator
from live_monitoring.pipeline.config import PipelineConfig


def main():
    """Main entry point"""
    try:
        # Create config (can be customized)
        config = PipelineConfig()
        
        # Adjust thresholds if needed
        # config.dp.min_volume = 50_000  # Lower threshold
        # config.synthesis.min_confluence = 0.40  # Lower confluence
        
        # Create and run orchestrator
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.run()
        
    except KeyboardInterrupt:
        logger.info("⏹️  Stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())


