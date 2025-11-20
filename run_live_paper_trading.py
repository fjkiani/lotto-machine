#!/usr/bin/env python3
"""
LIVE PAPER TRADING SYSTEM
=========================
Main entry point for live paper trading with Alpaca.

Combines:
- Real-time data fetching (institutional + technical)
- Signal generation (both strategies)
- Paper trade execution
- Position management
- Risk management
- Real-time alerts

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime
import time

# Add paths
sys.path.append(str(Path(__file__).parent / 'live_monitoring'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring/monitoring'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring/trading'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring/config'))

from live_monitor import LiveMonitor
from paper_trader import PaperTrader
from monitoring_config import trading_config, monitoring_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/live_paper_trading/trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LivePaperTradingSystem:
    """
    Orchestrates live paper trading
    """
    def __init__(self):
        """Initialize the live paper trading system"""
        logger.info("=" * 100)
        logger.info("🚀 ALPHA'S LIVE PAPER TRADING SYSTEM")
        logger.info("=" * 100)
        logger.info("")
        
        # Initialize paper trader
        logger.info("📊 Initializing Paper Trader...")
        self.trader = PaperTrader(
            max_position_size_pct=trading_config.max_position_size_pct
        )
        
        if not self.trader.is_connected():
            logger.error("❌ Paper trader not connected!")
            logger.error("   Please set up Alpaca API credentials")
            logger.error("   See: live_monitoring/trading/paper_trader.py for setup instructions")
            sys.exit(1)
        
        logger.info("")
        
        # Initialize live monitor
        logger.info("📡 Initializing Live Monitor...")
        self.monitor = LiveMonitor()
        logger.info("")
        
        logger.info("=" * 100)
        logger.info("✅ SYSTEM READY")
        logger.info("=" * 100)
        logger.info(f"Symbols: {', '.join(trading_config.symbols)}")
        logger.info(f"Max Position Size: {trading_config.max_position_size_pct:.1%}")
        logger.info(f"Max Daily Drawdown: {trading_config.max_daily_drawdown_pct:.1%}")
        logger.info(f"Signal Confidence Threshold: {trading_config.min_master_confidence:.0%}")
        logger.info("=" * 100)
        logger.info("")
    
    def run(self):
        """
        Main trading loop
        """
        try:
            logger.info("🔄 Starting live paper trading...")
            logger.info(f"⏰ Market Hours: {monitoring_config.rth_start_hour}:00 - {monitoring_config.rth_end_hour}:00 ET")
            logger.info("")
            
            while True:
                try:
                    # Check if market is open
                    if not self._is_market_hours():
                        logger.info("⏸️  Market closed - waiting...")
                        time.sleep(60)  # Check every minute
                        continue
                    
                    # Run monitoring cycle (fetches data, generates signals)
                    signals = self.monitor._monitor_once()
                    
                    # Execute master signals
                    if signals:
                        master_signals = [s for s in signals if s.is_master_signal]
                        
                        if master_signals:
                            logger.info(f"🎯 {len(master_signals)} MASTER SIGNAL(S) detected!")
                            
                            for signal in master_signals:
                                # Execute trade
                                trade = self.trader.execute_signal(signal)
                                
                                if trade:
                                    logger.info(f"   ✅ Trade executed: {signal.symbol}")
                        else:
                            logger.debug(f"   ⚪ {len(signals)} signal(s) but none meet master threshold")
                    
                    # Update existing positions (check stop loss / take profit)
                    self.trader.update_positions()
                    
                    # Print periodic summary
                    if datetime.now().minute % 15 == 0:  # Every 15 minutes
                        self._print_summary()
                    
                    # Wait before next cycle
                    time.sleep(monitoring_config.polling_interval_seconds)
                    
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"❌ Error in trading loop: {e}")
                    time.sleep(monitoring_config.polling_interval_seconds)
        
        except KeyboardInterrupt:
            logger.info("\n⏹️  Stopping paper trading system...")
            self._print_final_summary()
            logger.info("=" * 100)
            logger.info("✅ System stopped")
            logger.info("=" * 100)
    
    def _is_market_hours(self) -> bool:
        """Check if current time is within market hours"""
        now = datetime.now()
        # Simple check (can be enhanced with market calendar)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        hour = now.hour
        return monitoring_config.rth_start_hour <= hour < monitoring_config.rth_end_hour
    
    def _print_summary(self):
        """Print periodic summary"""
        summary = self.trader.get_summary()
        
        logger.info("")
        logger.info("=" * 100)
        logger.info(f"📊 TRADING SUMMARY - {datetime.now().strftime('%H:%M:%S')}")
        logger.info("=" * 100)
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info(f"Open Positions: {summary['open_positions']}")
        logger.info(f"Closed Trades: {summary['closed_trades']}")
        
        if summary['closed_trades'] > 0:
            logger.info(f"Wins: {summary['wins']} | Losses: {summary['losses']}")
            logger.info(f"Win Rate: {summary['win_rate']:.1f}%")
            logger.info(f"Total P&L: ${summary['total_pnl']:+.2f}")
            logger.info(f"Avg Win: ${summary['avg_win']:+.2f} | Avg Loss: ${summary['avg_loss']:+.2f}")
        
        logger.info("=" * 100)
        logger.info("")
    
    def _print_final_summary(self):
        """Print final summary on shutdown"""
        logger.info("")
        logger.info("=" * 100)
        logger.info("📊 FINAL TRADING SUMMARY")
        logger.info("=" * 100)
        
        summary = self.trader.get_summary()
        
        logger.info(f"Total Trades: {summary['total_trades']}")
        logger.info(f"Closed Trades: {summary['closed_trades']}")
        
        if summary['closed_trades'] > 0:
            logger.info(f"Wins: {summary['wins']} | Losses: {summary['losses']}")
            logger.info(f"Win Rate: {summary['win_rate']:.1f}%")
            logger.info(f"Total P&L: ${summary['total_pnl']:+.2f}")
            logger.info(f"Avg Win: ${summary['avg_win']:+.2f}")
            logger.info(f"Avg Loss: ${summary['avg_loss']:+.2f}")
            logger.info(f"Largest Win: ${summary['largest_win']:+.2f}")
            logger.info(f"Largest Loss: ${summary['largest_loss']:+.2f}")
        
        logger.info("")
        logger.info(f"📁 Logs saved to: logs/paper_trading/")
        logger.info("=" * 100)


def main():
    """Main entry point"""
    # Create logs directory
    Path("logs/live_paper_trading").mkdir(parents=True, exist_ok=True)
    
    # Initialize and run
    system = LivePaperTradingSystem()
    system.run()


if __name__ == "__main__":
    main()



