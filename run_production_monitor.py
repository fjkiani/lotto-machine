#!/usr/bin/env python3
"""
PRODUCTION SIGNAL MONITOR - Run continuously during market hours
=================================================================
- Monitors SPY/QQQ during RTH (9:30 AM - 4:00 PM ET)
- Sends signals to Discord
- Logs all signals and outcomes
- Tracks performance metrics
- Auto-restarts on errors

Usage:
    python3 run_production_monitor.py

Environment Variables:
    DISCORD_WEBHOOK_URL - Discord webhook URL (required)
    CHARTEXCHANGE_API_KEY - ChartExchange API key (required)
"""

import sys
import os
import logging
import time
import json
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import List, Dict
import traceback

# Add paths
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'core'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'monitoring'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'alerting'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'config'))
sys.path.append(str(Path(__file__).parent / 'configs'))

from configs.chartexchange_config import get_api_key
from data_fetcher import DataFetcher
from signal_generator import SignalGenerator, LiveSignal
from alert_router import AlertRouter
from console_alerter import ConsoleAlerter
from csv_logger import CSVLogger
from discord_alerter import DiscordAlerter
import monitoring_config
import yfinance as yf

# Setup logging
log_dir = Path("logs/production")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"monitor_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ProductionMonitor:
    """Production signal monitoring system"""
    
    def __init__(self):
        # Get API key from environment or config
        self.api_key = os.getenv('CHARTEXCHANGE_API_KEY') or get_api_key()
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        
        if not self.discord_webhook:
            logger.error("❌ DISCORD_WEBHOOK_URL environment variable not set!")
            logger.error("   Get webhook URL from Discord: Server Settings → Integrations → Webhooks")
            raise ValueError("DISCORD_WEBHOOK_URL required")
        
        # Initialize components
        self.data_fetcher = DataFetcher(
            api_key=self.api_key,
            use_cache=True,
            cache_dir="cache"
        )
        
        self.signal_generator = SignalGenerator(
            min_master_confidence=0.75,
            min_high_confidence=0.50,  # 50% threshold (validated!)
            api_key=self.api_key,
            use_sentiment=False,
            use_gamma=False,
            use_narrative=False
        )
        
        # Setup alerting
        self.alert_router = AlertRouter()
        self.alert_router.add_alerter(ConsoleAlerter())
        self.alert_router.add_alerter(CSVLogger(log_dir / "signals.csv"))
        self.alert_router.add_alerter(DiscordAlerter(self.discord_webhook))
        
        # Performance tracking
        self.signals_today: List[Dict] = []
        self.performance_file = log_dir / f"performance_{datetime.now().strftime('%Y%m%d')}.json"
        
        logger.info("🚀 Production Monitor initialized")
        logger.info(f"   Discord webhook: {'✅ Configured' if self.discord_webhook else '❌ Missing'}")
        logger.info(f"   Symbols: SPY, QQQ")
        logger.info(f"   Confidence threshold: 50%")
    
    def is_market_hours(self) -> bool:
        """Check if currently in RTH (9:30 AM - 4:00 PM ET)"""
        now = datetime.now()
        current_time = now.time()
        
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        
        is_weekday = now.weekday() < 5
        in_hours = market_open <= current_time < market_close
        
        return is_weekday and in_hours
    
    def check_symbol(self, symbol: str) -> List[LiveSignal]:
        """Check a symbol for signals"""
        try:
            logger.info(f"\n📊 Checking {symbol}...")
            
            # Get current price
            price = self.data_fetcher.get_current_price(symbol)
            if not price:
                logger.warning(f"   ⚠️  Could not fetch price for {symbol}")
                return []
            
            logger.info(f"   Current price: ${price:.2f}")
            
            # Get institutional context (yesterday's data - today's not available yet)
            inst_context = self.data_fetcher.get_institutional_context(symbol, use_yesterday=True)
            
            if not inst_context:
                logger.warning(f"   ⚠️  Could not fetch institutional context for {symbol}")
                return []
            
            logger.info(f"   DP battlegrounds: {len(inst_context.dp_battlegrounds)}")
            logger.info(f"   Buying pressure: {inst_context.institutional_buying_pressure:.0%}")
            logger.info(f"   Dark pool %: {inst_context.dark_pool_pct:.1f}%")
            
            # Get minute bars for momentum
            minute_bars = self.data_fetcher.get_minute_bars(symbol, lookback_minutes=30)
            
            # Generate signals
            signals = self.signal_generator.generate_signals(
                symbol, price, inst_context, minute_bars=minute_bars
            )
            
            if signals:
                logger.info(f"   ✅ Generated {len(signals)} signal(s)")
            else:
                logger.info(f"   No signals generated")
            
            return signals
            
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    def process_signal(self, signal: LiveSignal):
        """Process and send a signal"""
        try:
            # Log signal
            signal_data = {
                "timestamp": signal.timestamp.isoformat(),
                "symbol": signal.symbol,
                "signal_type": signal.signal_type.value,
                "action": signal.action.value,
                "entry_price": signal.entry_price,
                "stop_price": signal.stop_price,
                "target_price": signal.target_price,
                "confidence": signal.confidence,
                "rationale": signal.rationale,
                "is_master": signal.is_master_signal
            }
            
            self.signals_today.append(signal_data)
            
            # Send alert
            self.alert_router.send_signal_alert(signal)
            
            logger.info(f"   ✅ Signal sent: {signal.signal_type.value} @ ${signal.entry_price:.2f} ({signal.confidence:.0%} confidence)")
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            logger.debug(traceback.format_exc())
    
    def update_performance(self):
        """Update performance tracking"""
        try:
            # Load existing performance
            if self.performance_file.exists():
                with open(self.performance_file, 'r') as f:
                    perf = json.load(f)
            else:
                perf = {
                    "date": datetime.now().strftime('%Y-%m-%d'),
                    "signals": [],
                    "stats": {
                        "total_signals": 0,
                        "master_signals": 0,
                        "high_confidence": 0
                    }
                }
            
            # Update with today's signals
            perf["signals"] = self.signals_today
            perf["stats"]["total_signals"] = len(self.signals_today)
            perf["stats"]["master_signals"] = len([s for s in self.signals_today if s.get("is_master", False)])
            perf["stats"]["high_confidence"] = len([s for s in self.signals_today if s["confidence"] >= 0.60])
            
            # Save
            with open(self.performance_file, 'w') as f:
                json.dump(perf, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error updating performance: {e}")
    
    def send_daily_summary(self):
        """Send end-of-day summary to Discord"""
        try:
            if not self.signals_today:
                return
            
            total = len(self.signals_today)
            master = len([s for s in self.signals_today if s.get("is_master", False)])
            
            summary = f"📊 **Daily Summary - {datetime.now().strftime('%Y-%m-%d')}**\n\n"
            summary += f"Total Signals: {total}\n"
            summary += f"Master Signals (75%+): {master}\n"
            summary += f"High Confidence (60%+): {len([s for s in self.signals_today if s['confidence'] >= 0.60])}\n\n"
            
            summary += "**Signals Today:**\n"
            for sig in self.signals_today:
                icon = "🎯" if sig.get("is_master", False) else "📊"
                summary += f"{icon} {sig['symbol']} {sig['signal_type']} @ ${sig['entry_price']:.2f} ({sig['confidence']:.0%})\n"
            
            self.alert_router.send_info(summary)
            
        except Exception as e:
            logger.error(f"Error sending daily summary: {e}")
    
    def run(self):
        """Main monitoring loop"""
        logger.info("="*80)
        logger.info("🚀 PRODUCTION SIGNAL MONITOR STARTING")
        logger.info("="*80)
        
        symbols = ["SPY", "QQQ"]
        check_interval = 60  # Check every 60 seconds
        
        consecutive_errors = 0
        max_errors = 5
        
        while True:
            try:
                # Check if market is open
                if not self.is_market_hours():
                    # Market closed - wait until next market open
                    now = datetime.now()
                    if now.weekday() >= 5:  # Weekend
                        next_open = now + timedelta(days=(7 - now.weekday()))
                        next_open = next_open.replace(hour=9, minute=30, second=0, microsecond=0)
                    else:  # Weekday after hours
                        next_open = now + timedelta(days=1)
                        next_open = next_open.replace(hour=9, minute=30, second=0, microsecond=0)
                    
                    wait_seconds = (next_open - now).total_seconds()
                    logger.info(f"⏸️  Market closed. Next check: {next_open.strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info(f"   Waiting {wait_seconds/3600:.1f} hours...")
                    
                    # Send end-of-day summary if we had signals
                    if self.signals_today:
                        self.send_daily_summary()
                        self.update_performance()
                        self.signals_today = []  # Reset for next day
                    
                    time.sleep(min(wait_seconds, 3600))  # Sleep max 1 hour at a time
                    continue
                
                # Market is open - check symbols
                for symbol in symbols:
                    signals = self.check_symbol(symbol)
                    
                    for signal in signals:
                        self.process_signal(signal)
                
                # Update performance every 10 checks
                if len(self.signals_today) > 0 and len(self.signals_today) % 10 == 0:
                    self.update_performance()
                
                # Reset error counter on success
                consecutive_errors = 0
                
                # Wait before next check
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("\n⚠️  Shutting down gracefully...")
                if self.signals_today:
                    self.send_daily_summary()
                    self.update_performance()
                break
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"❌ Error in main loop: {e}")
                logger.debug(traceback.format_exc())
                
                if consecutive_errors >= max_errors:
                    logger.error(f"❌ Too many consecutive errors ({max_errors}). Shutting down.")
                    self.alert_router.send_error(f"Monitor crashed after {max_errors} errors: {e}")
                    break
                
                # Wait before retry
                time.sleep(30)


def main():
    """Main entry point"""
    try:
        monitor = ProductionMonitor()
        monitor.run()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

