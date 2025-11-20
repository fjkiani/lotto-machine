#!/usr/bin/env python3
"""
LIVE SIGNAL MONITOR - Main Entry Point

Usage:
    python3 run_live_monitor.py

Features:
- Real-time monitoring during RTH
- Multi-channel alerts (console, CSV, Slack)
- Modular, production-grade architecture
"""

import sys
import logging
from pathlib import Path

# Add live_monitoring to path
sys.path.append(str(Path(__file__).parent / 'live_monitoring'))

from monitoring.live_monitor import LiveMonitor
from config import monitoring_config

def setup_logging():
    """Setup logging configuration"""
    log_dir = Path(monitoring_config.MONITORING.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"monitor_{Path(__file__).stem}.log"
    
    logging.basicConfig(
        level=monitoring_config.MONITORING.log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def print_banner():
    """Print startup banner"""
    print("\n" + "="*80)
    print("🚀 LIVE SIGNAL MONITORING SYSTEM")
    print("="*80)
    print(f"Version: 1.0.0")
    print(f"Symbols: {', '.join(monitoring_config.TRADING.symbols)}")
    print(f"Position Size: {monitoring_config.TRADING.max_position_size_pct:.1%}")
    print(f"Daily DD Limit: {monitoring_config.TRADING.max_daily_drawdown_pct:.1%}")
    print(f"Master Threshold: {monitoring_config.TRADING.min_master_confidence:.0%}")
    print("="*80)
    print("\n📊 MONITORING STATUS:")
    print(f"  ✅ Console alerts: {monitoring_config.ALERTS.console_enabled}")
    print(f"  ✅ CSV logging: {monitoring_config.ALERTS.csv_enabled}")
    print(f"  {'✅' if monitoring_config.ALERTS.slack_enabled else '❌'} Slack alerts: {monitoring_config.ALERTS.slack_enabled}")
    print(f"\n💾 Logs: {monitoring_config.MONITORING.log_dir}/")
    print(f"📈 Signals CSV: {monitoring_config.ALERTS.csv_file}")
    print("\n" + "="*80)
    print("⏳ Starting monitoring loop...")
    print("   Press Ctrl+C to stop")
    print("="*80 + "\n")

def main():
    """Main entry point"""
    logger = setup_logging()
    
    try:
        print_banner()
        
        # Initialize monitor
        monitor = LiveMonitor(config=monitoring_config)
        
        # Run!
        monitor.run()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())



