#!/usr/bin/env python3
"""
LIVE MONITOR - Main orchestrator
- Run monitoring loop
- Check signals every minute
- Route alerts
"""

import time
from datetime import datetime, time as dt_time
import logging
import sys
from pathlib import Path
from typing import List

# Add paths
sys.path.append(str(Path(__file__).parent.parent / 'core'))
sys.path.append(str(Path(__file__).parent.parent / 'config'))
sys.path.append(str(Path(__file__).parent.parent / 'alerting'))

from data_fetcher import DataFetcher
from signal_generator import SignalGenerator, LiveSignal
from alert_router import AlertRouter
from console_alerter import ConsoleAlerter
from csv_logger import CSVLogger
from slack_alerter import SlackAlerter
from volume_profile import VolumeProfileAnalyzer
from stock_screener import InstitutionalScreener
import monitoring_config

logger = logging.getLogger(__name__)

class LiveMonitor:
    """Main monitoring orchestrator"""
    
    def __init__(self, config=None):
        self.config = config or monitoring_config
        
        # Initialize components
        self.data_fetcher = DataFetcher(
            api_key=self.config.API.chartexchange_api_key,
            use_cache=self.config.MONITORING.use_local_cache,
            cache_dir="cache"
        )
        
        self.signal_generator = SignalGenerator(
            min_master_confidence=self.config.TRADING.min_master_confidence,
            min_high_confidence=self.config.TRADING.min_high_confidence,
            api_key=self.config.API.chartexchange_api_key,
            use_sentiment=self.config.MONITORING.use_sentiment
        )
        
        # Initialize enhanced modules
        self.volume_analyzer = VolumeProfileAnalyzer(
            api_key=self.config.API.chartexchange_api_key
        )
        self.screener = InstitutionalScreener(
            api_key=self.config.API.chartexchange_api_key
        )
        
        # Track discovered tickers
        self.discovered_tickers = set(self.config.TRADING.symbols)
        
        # Setup alerting
        self.alert_router = AlertRouter()
        
        if self.config.ALERTS.console_enabled:
            self.alert_router.add_alerter(ConsoleAlerter())
        
        if self.config.ALERTS.csv_enabled:
            self.alert_router.add_alerter(CSVLogger(self.config.ALERTS.csv_file))
        
        if self.config.ALERTS.slack_enabled and self.config.ALERTS.slack_webhook_url:
            self.alert_router.add_alerter(
                SlackAlerter(
                    webhook_url=self.config.ALERTS.slack_webhook_url,
                    channel=self.config.ALERTS.slack_channel,
                    username=self.config.ALERTS.slack_username
                )
            )
        
        self.running = False
        self.cycle_count = 0
        self.signal_count = 0
        
        logger.info("🚀 Live Monitor initialized")
    
    def is_market_hours(self) -> bool:
        """Check if currently in RTH"""
        now = datetime.now()
        current_time = now.time()
        
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = dt_time(
            self.config.MONITORING.market_open_hour,
            self.config.MONITORING.market_open_minute
        )
        market_close = dt_time(
            self.config.MONITORING.market_close_hour,
            self.config.MONITORING.market_close_minute
        )
        
        # Check if it's a weekday (Mon=0, Sun=6)
        is_weekday = now.weekday() < 5
        
        # Check if in market hours
        in_hours = market_open <= current_time < market_close
        
        return is_weekday and in_hours
    
    def discover_opportunities(self):
        """Run screener to find new tickers (called at start of day)"""
        try:
            logger.info("🔍 Running stock screener to discover opportunities...")
            high_flow = self.screener.screen_high_flow_tickers(
                min_price=20.0,
                min_volume=5_000_000,
                max_results=10
            )
            
            new_tickers = [r.symbol for r in high_flow if r.symbol not in self.discovered_tickers]
            
            if new_tickers:
                logger.info(f"✅ Discovered {len(new_tickers)} new tickers: {', '.join(new_tickers)}")
                self.discovered_tickers.update(new_tickers)
            else:
                logger.info("   No new tickers discovered")
                
        except Exception as e:
            logger.error(f"Error running screener: {e}")
    
    def check_symbols(self):
        """Check all symbols for signals"""
        # Check both configured symbols and discovered tickers
        all_symbols = list(self.discovered_tickers)
        
        for symbol in all_symbols:
            try:
                logger.info(f"\n📊 Checking {symbol}...")
                
                # Get current price
                price = self.data_fetcher.get_current_price(symbol)
                if not price:
                    logger.warning(f"Could not fetch price for {symbol}")
                    continue
                
                logger.info(f"   Current price: ${price:.2f}")
                
                # Check volume profile for timing (use yesterday's profile)
                from datetime import timedelta
                yesterday = datetime.now() - timedelta(days=1)
                profile = self.volume_analyzer.fetch_intraday_volume(symbol, yesterday)
                
                if profile:
                    should_trade, reason = self.volume_analyzer.should_trade_now(profile)
                    if not should_trade:
                        logger.info(f"   ⏸️  {reason} - skipping signal generation")
                        continue
                    else:
                        logger.info(f"   ✅ Volume profile: {reason}")
                
                # Get institutional context
                inst_context = self.data_fetcher.get_institutional_context(symbol)
                if not inst_context:
                    logger.warning(f"Could not fetch institutional context for {symbol}")
                    continue
                
                logger.info(f"   DP battlegrounds: {len(inst_context.dp_battlegrounds)}")
                logger.info(f"   Institutional buying: {inst_context.institutional_buying_pressure:.0%}")
                logger.info(f"   Squeeze potential: {inst_context.squeeze_potential:.0%}")
                logger.info(f"   Gamma pressure: {inst_context.gamma_pressure:.0%}")
                
                # Generate signals
                signals = self.signal_generator.generate_signals(
                    symbol, price, inst_context
                )
                
                # Send alerts
                for signal in signals:
                    self.alert_router.send_signal_alert(signal)
                    self.signal_count += 1
                
                if not signals:
                    logger.info(f"   No signals generated for {symbol}")
                
            except Exception as e:
                logger.error(f"Error checking {symbol}: {e}")
                self.alert_router.send_error(f"Error checking {symbol}: {e}")
    
    def run_once(self):
        """Run one monitoring cycle"""
        self.cycle_count += 1
        
        logger.info(f"\n{'='*80}")
        logger.info(f"CYCLE {self.cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")
        
        if not self.is_market_hours():
            logger.info("⏸️  Outside market hours - waiting...")
            return
        
        try:
            self.check_symbols()
        except Exception as e:
            logger.error(f"Error in monitoring cycle: {e}")
            self.alert_router.send_error(f"Monitoring cycle error: {e}")
    
    def run(self):
        """Run continuous monitoring loop"""
        self.running = True
        
        self.alert_router.send_info("🚀 Live monitoring started")
        
        # Run screener at start to discover opportunities
        if self.config.MONITORING.use_screener:
            self.discover_opportunities()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"LIVE MONITORING STARTED")
        logger.info(f"{'='*80}")
        logger.info(f"Symbols: {', '.join(sorted(self.discovered_tickers))}")
        logger.info(f"Check interval: {self.config.MONITORING.check_interval_seconds}s")
        logger.info(f"Market hours: {self.config.MONITORING.market_open_hour:02d}:{self.config.MONITORING.market_open_minute:02d} - {self.config.MONITORING.market_close_hour:02d}:{self.config.MONITORING.market_close_minute:02d}")
        logger.info(f"{'='*80}\n")
        
        try:
            while self.running:
                self.run_once()
                
                # Sleep until next check
                time.sleep(self.config.MONITORING.check_interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Monitoring stopped by user")
            self.stop()
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
            self.alert_router.send_error(f"Fatal error: {e}")
            self.stop()
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        
        logger.info(f"\n{'='*80}")
        logger.info(f"MONITORING SESSION SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total cycles: {self.cycle_count}")
        logger.info(f"Signals generated: {self.signal_count}")
        logger.info(f"{'='*80}\n")
        
        self.alert_router.send_info(
            f"🏁 Monitoring stopped - {self.cycle_count} cycles, {self.signal_count} signals"
        )



