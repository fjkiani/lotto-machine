#!/usr/bin/env python3
"""
LOTTO MACHINE - Unified Market Exploitation System
==================================================
Single entry point that exploits ALL market opportunities:
- Discovers tickers via stock screener
- Optimizes timing via volume profile
- Filters with contrarian sentiment
- Generates signals with all enhancements
- Executes trades (paper or live)

This is the "one-button" system that does everything.

Usage:
    python3 run_lotto_machine.py [--paper] [--symbols SPY QQQ] [--enable-screener]

Author: Alpha's AI Hedge Fund
Date: 2025-01-XX
"""

import sys
import logging
import time
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import List, Set
import argparse

# Add paths
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'core'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'monitoring'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'alerting'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'config'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'trading'))
sys.path.append(str(Path(__file__).parent / 'configs'))

from volume_profile import VolumeProfileAnalyzer
from stock_screener import InstitutionalScreener
from data_fetcher import DataFetcher
from signal_generator import SignalGenerator
from risk_manager import RiskManager, RiskLimits
from price_action_filter import PriceActionFilter
from alert_router import AlertRouter
from console_alerter import ConsoleAlerter
from csv_logger import CSVLogger
from slack_alerter import SlackAlerter
import monitoring_config

# Try to import paper trader
try:
    from paper_trader import PaperTrader
    PAPER_TRADING_AVAILABLE = True
except ImportError:
    PAPER_TRADING_AVAILABLE = False
    logger.warning("Paper trading not available - alerts only")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LottoMachine:
    """
    Unified market exploitation system
    Combines all capabilities into one powerful machine
    """
    
    def __init__(self, config=None, paper_trading: bool = False):
        self.config = config or monitoring_config
        self.paper_trading = paper_trading and PAPER_TRADING_AVAILABLE
        
        # Initialize all components
        api_key = self.config.API.chartexchange_api_key
        
        self.data_fetcher = DataFetcher(
            api_key=api_key,
            use_cache=self.config.MONITORING.use_local_cache,
            cache_dir="cache"
        )
        
        self.signal_generator = SignalGenerator(
            min_master_confidence=self.config.TRADING.min_master_confidence,
            min_high_confidence=self.config.TRADING.min_high_confidence,
            api_key=api_key,
            use_sentiment=self.config.MONITORING.use_sentiment,
            use_gamma=True  # Enable gamma tracking
        )
        
        self.volume_analyzer = VolumeProfileAnalyzer(api_key=api_key)
        self.screener = InstitutionalScreener(api_key=api_key)
        
        # Initialize risk manager
        risk_limits = RiskLimits(
            max_position_size_pct=self.config.TRADING.max_position_size_pct,
            max_daily_drawdown_pct=self.config.TRADING.max_daily_drawdown_pct,
            max_open_positions=5,
            max_correlated_positions=2,
            max_sector_exposure_pct=0.40,
            circuit_breaker_pnl_pct=-0.03
        )
        self.risk_manager = RiskManager(limits=risk_limits)
        
        # Initialize price action filter
        self.price_action_filter = PriceActionFilter()
        
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
        
        # Setup trading (if enabled)
        if self.paper_trading:
            try:
                self.trader = PaperTrader()
                logger.info("💰 Paper trading enabled")
            except Exception as e:
                logger.error(f"Failed to initialize paper trader: {e}")
                self.paper_trading = False
        
        # Track discovered tickers
        self.monitored_symbols: Set[str] = set(self.config.TRADING.symbols)
        self.volume_profiles = {}  # Cache volume profiles
        
        self.running = False
        self.cycle_count = 0
        self.signal_count = 0
        self.trade_count = 0
        
        logger.info("🎰 Lotto Machine initialized")
        logger.info(f"   Monitored symbols: {', '.join(sorted(self.monitored_symbols))}")
        logger.info(f"   Paper trading: {'enabled' if self.paper_trading else 'disabled'}")
        logger.info(f"   Screener: {'enabled' if self.config.MONITORING.use_screener else 'disabled'}")
        logger.info(f"   Volume profile: {'enabled' if self.config.MONITORING.use_volume_profile else 'disabled'}")
        logger.info(f"   Sentiment: {'enabled' if self.config.MONITORING.use_sentiment else 'disabled'}")
        logger.info(f"   Gamma tracking: enabled")
    
    def morning_setup(self):
        """Run pre-market setup (screener, volume profiles)"""
        logger.info("\n" + "="*80)
        logger.info("🌅 MORNING SETUP")
        logger.info("="*80)
        
        # Run screener to discover opportunities
        if self.config.MONITORING.use_screener:
            logger.info("🔍 Running stock screener...")
            try:
                high_flow = self.screener.screen_high_flow_tickers(
                    min_price=20.0,
                    min_volume=5_000_000,
                    max_results=10
                )
                
                new_tickers = [r.symbol for r in high_flow if r.symbol not in self.monitored_symbols]
                
                if new_tickers:
                    logger.info(f"✅ Discovered {len(new_tickers)} new tickers: {', '.join(new_tickers)}")
                    self.monitored_symbols.update(new_tickers)
                else:
                    logger.info("   No new tickers discovered")
            except Exception as e:
                logger.error(f"Error running screener: {e}")
        
        # Load volume profiles for all monitored symbols
        if self.config.MONITORING.use_volume_profile:
            logger.info("📊 Loading volume profiles...")
            yesterday = datetime.now() - timedelta(days=1)
            
            for symbol in self.monitored_symbols:
                try:
                    profile = self.volume_analyzer.fetch_intraday_volume(symbol, yesterday)
                    if profile:
                        self.volume_profiles[symbol] = profile
                        logger.info(f"   ✅ {symbol}: Peak institutional time: {profile.peak_institutional_time}")
                        
                        # Calculate order flow imbalance
                        order_flow = self.volume_analyzer.calculate_order_flow_imbalance(
                            symbol, yesterday.strftime('%Y-%m-%d')
                        )
                        if order_flow:
                            logger.info(f"      Order flow: {order_flow.bias} (ratio: {order_flow.imbalance_ratio:.2f})")
                            logger.info(f"      Buy: {order_flow.buy_volume:,} | Sell: {order_flow.sell_volume:,} | Net: {order_flow.net_imbalance:+,}")
                    
                    # Get current price for gamma analysis
                    try:
                        import yfinance as yf
                        ticker = yf.Ticker(symbol)
                        price = float(ticker.history(period='1d')['Close'].iloc[-1])
                        
                        # Calculate gamma exposure
                        if self.signal_generator.gamma_tracker:
                            gamma_data = self.signal_generator.gamma_tracker.calculate_gamma_exposure(symbol, price)
                            if gamma_data:
                                logger.info(f"      Gamma regime: {gamma_data.current_regime}")
                                if gamma_data.gamma_flip_level:
                                    logger.info(f"      Gamma flip: ${gamma_data.gamma_flip_level:.2f}")
                    except Exception as e:
                        logger.debug(f"Could not calculate gamma for {symbol}: {e}")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️  Failed to load profile for {symbol}: {e}")
        
        logger.info(f"\n📈 Monitoring {len(self.monitored_symbols)} tickers:")
        logger.info(f"   {', '.join(sorted(self.monitored_symbols))}")
        logger.info("="*80 + "\n")
    
    def is_market_hours(self) -> bool:
        """Check if currently in RTH"""
        now = datetime.now()
        current_time = now.time()
        
        market_open = dt_time(
            self.config.MONITORING.market_open_hour,
            self.config.MONITORING.market_open_minute
        )
        market_close = dt_time(
            self.config.MONITORING.market_close_hour,
            self.config.MONITORING.market_close_minute
        )
        
        is_weekday = now.weekday() < 5
        in_hours = market_open <= current_time < market_close
        
        return is_weekday and in_hours
    
    def check_symbol(self, symbol: str):
        """Check a single symbol for signals"""
        try:
            logger.info(f"\n📊 Checking {symbol}...")
            
            # Get current price
            price = self.data_fetcher.get_current_price(symbol)
            if not price:
                logger.warning(f"   ⚠️  Could not fetch price for {symbol}")
                return
            
            logger.info(f"   Current price: ${price:.2f}")
            
            # Check volume profile timing
            if self.config.MONITORING.use_volume_profile and symbol in self.volume_profiles:
                profile = self.volume_profiles[symbol]
                should_trade, reason = self.volume_analyzer.should_trade_now(profile)
                if not should_trade:
                    logger.info(f"   ⏸️  {reason} - skipping signal generation")
                    return
                else:
                    logger.info(f"   ✅ Volume profile: {reason}")
            
            # Get institutional context
            inst_context = self.data_fetcher.get_institutional_context(symbol)
            if not inst_context:
                logger.warning(f"   ⚠️  Could not fetch institutional context for {symbol}")
                return
            
            logger.info(f"   DP battlegrounds: {len(inst_context.dp_battlegrounds)}")
            logger.info(f"   Institutional buying: {inst_context.institutional_buying_pressure:.0%}")
            logger.info(f"   Squeeze potential: {inst_context.squeeze_potential:.0%}")
            logger.info(f"   Gamma pressure: {inst_context.gamma_pressure:.0%}")
            
            # Get minute bars for real-time momentum detection
            minute_bars = self.data_fetcher.get_minute_bars(symbol, lookback_minutes=30)
            
            # Generate signals (now includes real-time selloff detection)
            signals = self.signal_generator.generate_signals(symbol, price, inst_context, minute_bars=minute_bars)
            
            # Process signals
            for signal in signals:
                # Check risk limits
                can_open, risk_reason = self.risk_manager.can_open_position(
                    signal.symbol, signal.position_size_pct
                )
                if not can_open:
                    logger.info(f"   ⛔ Risk check failed: {risk_reason}")
                    continue
                
                # Confirm with price action
                confirmation = self.price_action_filter.confirm_signal(signal)
                if not confirmation.confirmed:
                    logger.info(f"   ⛔ Price action not confirmed: {confirmation.reason}")
                    continue
                
                # Update stop loss using risk manager (ATR-based)
                if signal.signal_type in ['BOUNCE', 'BREAKOUT']:
                    signal.stop_loss = self.risk_manager.calculate_stop_loss(
                        signal.entry_price,
                        signal.dp_level,
                        signal.symbol
                    )
                
                # Send alert
                self.alert_router.send_signal_alert(signal)
                self.signal_count += 1
                
                # Execute trade if paper trading enabled
                if self.paper_trading and signal.is_master_signal:
                    try:
                        self._execute_trade(signal)
                    except Exception as e:
                        logger.error(f"Error executing trade: {e}")
            
            if not signals:
                logger.info(f"   No signals generated for {symbol}")
            
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")
            self.alert_router.send_error(f"Error checking {symbol}: {e}")
    
    def _execute_trade(self, signal):
        """Execute a trade via paper trader with slippage/commission model"""
        try:
            logger.info(f"💰 Executing trade: {signal.action} {signal.symbol} @ ${signal.entry_price:.2f}")
            
            # Calculate position size (2% of account)
            account_value = self.trader.get_account_value()
            position_value = account_value * signal.position_size_pct
            shares = int(position_value / signal.entry_price)
            
            if shares < 1:
                logger.warning("   Position size too small, skipping")
                return
            
            # Apply slippage model (0.05-0.10 per share for options, 0.01-0.02 for stocks)
            # For stocks, assume $0.01-0.02 slippage
            slippage_per_share = 0.015  # $0.015 average slippage
            slippage_cost = shares * slippage_per_share
            
            # Commission (Alpaca: $0 per stock trade, but model for options)
            # For stocks: $0, for options: $0.65 per contract
            commission = 0.0  # Stocks are commission-free on Alpaca
            
            # Adjust entry price for slippage
            if signal.action == 'BUY':
                adjusted_entry = signal.entry_price + slippage_per_share
            else:
                adjusted_entry = signal.entry_price - slippage_per_share
            
            logger.info(f"   📊 Execution costs: Slippage ${slippage_cost:.2f}, Commission ${commission:.2f}")
            logger.info(f"   📊 Adjusted entry: ${adjusted_entry:.2f} (slippage: ${slippage_per_share:.3f}/share)")
            
            # Submit order with adjusted price
            order = self.trader.submit_order(
                symbol=signal.symbol,
                side=signal.action.lower(),
                qty=shares,
                order_type='limit',
                limit_price=adjusted_entry,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit
            )
            
            if order:
                self.trade_count += 1
                # Track position in risk manager
                from risk_manager import Position
                position = Position(
                    symbol=signal.symbol,
                    entry_price=adjusted_entry,
                    stop_loss=signal.stop_loss,
                    position_size_pct=signal.position_size_pct,
                    signal_type=signal.signal_type,
                    opened_at=datetime.now()
                )
                self.risk_manager.add_position(position)
                logger.info(f"   ✅ Order submitted: {order.get('id', 'N/A')}")
            else:
                logger.warning("   ⚠️  Order submission failed")
                
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
    
    def run_cycle(self):
        """Run one monitoring cycle"""
        self.cycle_count += 1
        
        logger.info(f"\n{'='*80}")
        logger.info(f"CYCLE {self.cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*80}")
        
        if not self.is_market_hours():
            logger.info("⏸️  Outside market hours - waiting...")
            return
        
        # Check all monitored symbols
        for symbol in sorted(self.monitored_symbols):
            self.check_symbol(symbol)
    
    def end_of_day(self):
        """Generate end-of-day report"""
        risk_summary = self.risk_manager.get_risk_summary()
        
        logger.info("\n" + "="*80)
        logger.info("🌆 END OF DAY REPORT")
        logger.info("="*80)
        logger.info(f"Total cycles: {self.cycle_count}")
        logger.info(f"Signals generated: {self.signal_count}")
        logger.info(f"Trades executed: {self.trade_count}")
        logger.info(f"Open positions: {risk_summary['open_positions']}/{risk_summary['max_positions']}")
        logger.info(f"Daily P&L: {risk_summary['daily_pnl_pct']:+.2%}")
        logger.info(f"Circuit breaker: {'TRIGGERED' if risk_summary['circuit_breaker_triggered'] else 'OK'}")
        
        if self.paper_trading:
            try:
                account_value = self.trader.get_account_value()
                logger.info(f"Account value: ${account_value:.2f}")
            except:
                pass
        
        logger.info("="*80 + "\n")
    
    def run(self):
        """Run continuous monitoring loop"""
        self.running = True
        
        # Reset daily risk counters
        self.risk_manager.reset_daily()
        
        # Morning setup
        self.morning_setup()
        
        self.alert_router.send_info("🎰 Lotto Machine started")
        
        logger.info(f"\n{'='*80}")
        logger.info("🎰 LOTTO MACHINE RUNNING")
        logger.info(f"{'='*80}")
        logger.info(f"Symbols: {', '.join(sorted(self.monitored_symbols))}")
        logger.info(f"Check interval: {self.config.MONITORING.check_interval_seconds}s")
        logger.info(f"Market hours: {self.config.MONITORING.market_open_hour:02d}:{self.config.MONITORING.market_open_minute:02d} - {self.config.MONITORING.market_close_hour:02d}:{self.config.MONITORING.market_close_minute:02d}")
        logger.info(f"{'='*80}\n")
        
        try:
            while self.running:
                self.run_cycle()
                
                # Check if market closed
                if not self.is_market_hours() and self.cycle_count > 0:
                    self.end_of_day()
                    logger.info("⏸️  Market closed - stopping")
                    break
                
                # Sleep until next check
                time.sleep(self.config.MONITORING.check_interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Lotto Machine stopped by user")
            self.end_of_day()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.alert_router.send_error(f"Fatal error: {e}")
            self.end_of_day()
    
    def stop(self):
        """Stop the machine"""
        self.running = False
        self.end_of_day()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Lotto Machine - Unified Market Exploitation System')
    parser.add_argument('--paper', action='store_true', help='Enable paper trading')
    parser.add_argument('--symbols', nargs='+', help='Additional symbols to monitor')
    parser.add_argument('--enable-screener', action='store_true', help='Force enable screener')
    parser.add_argument('--disable-screener', action='store_true', help='Disable screener')
    parser.add_argument('--disable-volume-profile', action='store_true', help='Disable volume profile')
    parser.add_argument('--disable-sentiment', action='store_true', help='Disable sentiment filtering')
    
    args = parser.parse_args()
    
    # Update config based on args
    if args.enable_screener:
        monitoring_config.MONITORING.use_screener = True
    if args.disable_screener:
        monitoring_config.MONITORING.use_screener = False
    if args.disable_volume_profile:
        monitoring_config.MONITORING.use_volume_profile = False
    if args.disable_sentiment:
        monitoring_config.MONITORING.use_sentiment = False
    
    # Add additional symbols
    if args.symbols:
        monitoring_config.TRADING.symbols.extend(args.symbols)
    
    # Initialize and run
    machine = LottoMachine(paper_trading=args.paper)
    
    try:
        machine.run()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Stopped by user")
        machine.stop()
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

