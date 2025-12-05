#!/usr/bin/env python3
"""
30-Day Backtest Validation Script
==================================
Tests the signal engine on 30 days of historical data to validate edge.

SUCCESS CRITERIA (from .cursor/rules/backtesting-validation-protocol.mdc):
- Win Rate: >55%
- Risk/Reward Ratio: >2.0
- Max Drawdown: <10%
- Sharpe Ratio: >1.5
- Profit Factor: >1.8

Author: Alpha's AI Hedge Fund
Date: 2025-10-18
"""

import sys
import os
import pickle
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import csv

# Add core paths
sys.path.append(os.path.join(os.path.dirname(__file__), 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'core/data'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'live_monitoring/core'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'live_monitoring/config'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'configs'))

try:
from ultra_institutional_engine import InstitutionalContext
except ImportError:
    InstitutionalContext = None
    logger.warning("UltraInstitutionalEngine not found - using dict for context")

from signal_generator import SignalGenerator, LiveSignal
from monitoring_config import TradingConfig, MonitoringConfig, AlertConfig, APIConfig
import chartexchange_config

# Initialize configs
trading_config = TradingConfig()
monitoring_conf = MonitoringConfig()
alert_config = AlertConfig()
api_config = APIConfig()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Represents a completed backtest trade"""
    timestamp: datetime
    symbol: str
    signal_type: str  # SQUEEZE, GAMMA_RAMP, BREAKOUT, BOUNCE
    action: str  # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_price: float
    exit_reason: str  # HIT_TARGET, HIT_STOP, END_OF_DAY
    pnl: float
    pnl_pct: float
    risk_reward_ratio: float
    confidence: float
    held_bars: int = 0


@dataclass
class BacktestResults:
    """Summary of backtest performance"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_rr: float = 0.0
    profit_factor: float = 0.0
    
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    
    sharpe_ratio: float = 0.0
    
    trades_by_type: Dict[str, int] = field(default_factory=dict)
    winrate_by_type: Dict[str, float] = field(default_factory=dict)
    
    all_trades: List[BacktestTrade] = field(default_factory=list)
    
    def calculate_metrics(self):
        """Calculate all performance metrics"""
        if self.total_trades == 0:
            return
        
        # Basic metrics
        self.win_rate = (self.winning_trades / self.total_trades) * 100
        
        # Average win/loss
        wins = [t.pnl for t in self.all_trades if t.pnl > 0]
        losses = [t.pnl for t in self.all_trades if t.pnl < 0]
        
        self.avg_win = sum(wins) / len(wins) if wins else 0
        self.avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        self.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Average R/R
        rr_ratios = [t.risk_reward_ratio for t in self.all_trades if t.risk_reward_ratio > 0]
        self.avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0
        
        # Max drawdown
        equity_curve = [0]
        for trade in self.all_trades:
            equity_curve.append(equity_curve[-1] + trade.pnl)
        
        peak = equity_curve[0]
        max_dd = 0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd
        
        self.max_drawdown = max_dd
        if peak > 0:
            self.max_drawdown_pct = (max_dd / peak) * 100
        
        # Sharpe ratio (simplified - daily returns)
        if len(self.all_trades) > 1:
            returns = [t.pnl_pct for t in self.all_trades]
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            self.sharpe_ratio = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        
        # By signal type
        for signal_type in ['SQUEEZE', 'GAMMA_RAMP', 'BREAKOUT', 'BOUNCE']:
            type_trades = [t for t in self.all_trades if t.signal_type == signal_type]
            self.trades_by_type[signal_type] = len(type_trades)
            if type_trades:
                type_wins = sum(1 for t in type_trades if t.pnl > 0)
                self.winrate_by_type[signal_type] = (type_wins / len(type_trades)) * 100


class BacktestEngine:
    """
    Backtests the signal generation system on historical institutional data.
    """
    
    def __init__(self, data_dir: str = "data/historical/institutional_contexts", api_key: str = None):
        self.data_dir = Path(data_dir)
        self.api_key = api_key or chartexchange_config.CHARTEXCHANGE_API_KEY
        self.signal_gen = SignalGenerator(
            api_key=self.api_key,
            use_sentiment=False  # Disable sentiment for backtest (historical data)
        )
        self.results = BacktestResults()
        
    def load_historical_data(self, symbol: str, start_date: datetime, end_date: datetime) -> List[tuple]:
        """Load institutional contexts for a symbol within date range"""
        data = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            date_str = current_date.strftime("%Y-%m-%d")
            # New structure: SYMBOL_YYYY-MM-DD_context.pkl
            file_path = self.data_dir / f"{symbol}_{date_str}_context.pkl"
            
            if file_path.exists():
                try:
                    with open(file_path, 'rb') as f:
                        saved_data = pickle.load(f)
                        context = saved_data.get('context') if isinstance(saved_data, dict) else saved_data
                        if context:
                        data.append((current_date, context))
                        logger.debug(f"Loaded {symbol} {date_str}")
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {e}")
            
            current_date += timedelta(days=1)
        
        logger.info(f"📊 Loaded {len(data)} days of data for {symbol}")
        return data
    
    def get_historical_price(self, symbol: str, date: datetime) -> Optional[float]:
        """Get historical price for a date"""
        try:
            ticker = yf.Ticker(symbol)
            # Get data for the date
            hist = ticker.history(start=date, end=date + timedelta(days=1))
            if not hist.empty:
                return float(hist['Close'].iloc[0])
        except Exception as e:
            logger.debug(f"Error fetching price for {symbol} on {date.date()}: {e}")
        return None
    
    def get_intraday_prices(self, symbol: str, date: datetime) -> Optional[pd.DataFrame]:
        """Get intraday minute prices for a date"""
        try:
            ticker = yf.Ticker(symbol)
            # Get 1-minute data for the date
            start = date.strftime('%Y-%m-%d')
            end = (date + timedelta(days=1)).strftime('%Y-%m-%d')
            hist = ticker.history(start=start, end=end, interval='1m')
            return hist
        except Exception as e:
            logger.debug(f"Error fetching intraday prices for {symbol} on {date.date()}: {e}")
        return None
    
    def simulate_trade(self, signal: LiveSignal, timestamp: datetime, intraday_data: Optional[pd.DataFrame] = None) -> Optional[BacktestTrade]:
        """
        Simulate a trade based on a signal using actual price data.
        
        Args:
            signal: LiveSignal object
            timestamp: Entry timestamp
            intraday_data: DataFrame with minute-by-minute prices (optional)
        
        Returns:
            BacktestTrade with actual outcome
        """
        entry = signal.entry_price
        stop = signal.stop_loss
        target = signal.take_profit
        action = signal.action
        signal_type = signal.signal_type
        confidence = signal.confidence
        
        # Calculate risk and reward
        if action == "BUY":
            risk = entry - stop
            reward = target - entry
        else:  # SELL
            risk = stop - entry
            reward = entry - target
        
        if risk <= 0:
            logger.warning(f"Invalid risk calculation for {signal_type}: risk={risk}")
            return None
        
        rr_ratio = reward / risk if risk > 0 else 0
        
        # If we have intraday data, simulate using actual prices
        if intraday_data is not None and not intraday_data.empty:
            exit_price, exit_reason, held_bars = self._simulate_with_intraday(
                entry, stop, target, action, intraday_data
            )
        else:
            # Fallback: use historical daily price
            daily_price = self.get_historical_price(signal.symbol, timestamp)
            if daily_price:
                # Simple check: did price move toward target or stop?
                if action == "BUY":
                    if daily_price >= target:
            exit_price = target
            exit_reason = "HIT_TARGET"
                    elif daily_price <= stop:
                        exit_price = stop
                        exit_reason = "HIT_STOP"
        else:
                        # EOD - use closing price
                        exit_price = daily_price
                        exit_reason = "END_OF_DAY"
                else:  # SELL
                    if daily_price <= target:
                        exit_price = target
                        exit_reason = "HIT_TARGET"
                    elif daily_price >= stop:
            exit_price = stop
            exit_reason = "HIT_STOP"
                    else:
                        exit_price = daily_price
                        exit_reason = "END_OF_DAY"
                held_bars = 0
            else:
                # No price data - skip trade
                return None
        
        # Calculate P&L
        if action == "BUY":
            pnl = exit_price - entry
        else:  # SELL
            pnl = entry - exit_price
        
        pnl_pct = (pnl / entry) * 100
        
        trade = BacktestTrade(
            timestamp=timestamp,
            symbol=signal.symbol,
            signal_type=signal_type,
            action=action,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            exit_price=exit_price,
            exit_reason=exit_reason,
            pnl=pnl,
            pnl_pct=pnl_pct,
            risk_reward_ratio=rr_ratio,
            confidence=confidence,
            held_bars=held_bars
        )
        
        return trade
    
    def _simulate_with_intraday(self, entry: float, stop: float, target: float, 
                                action: str, intraday_data: pd.DataFrame) -> tuple:
        """Simulate trade using intraday minute data"""
        held_bars = 0
        
        for idx, row in intraday_data.iterrows():
            held_bars += 1
            high = row['High']
            low = row['Low']
            close = row['Close']
            
            if action == "BUY":
                # Check if stop or target hit
                if low <= stop:
                    return stop, "HIT_STOP", held_bars
                if high >= target:
                    return target, "HIT_TARGET", held_bars
            else:  # SELL
                if high >= stop:
                    return stop, "HIT_STOP", held_bars
                if low <= target:
                    return target, "HIT_TARGET", held_bars
        
        # EOD - use last close
        return close, "END_OF_DAY", held_bars
    
    def run_backtest(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """Run backtest for all symbols and date range"""
        logger.info("=" * 80)
        logger.info("🚀 STARTING 30-DAY BACKTEST VALIDATION")
        logger.info("=" * 80)
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
        logger.info("")
        
        all_signals = []
        
        # Load data for all symbols
        for symbol in symbols:
            logger.info(f"📈 Processing {symbol}...")
            historical_data = self.load_historical_data(symbol, start_date, end_date)
            
            # Generate signals for each day
            for timestamp, context in historical_data:
                try:
                    # Get actual historical price for this date
                    current_price = self.get_historical_price(symbol, timestamp)
                    if not current_price:
                        logger.debug(f"  ⏭️  Skipping {timestamp.date()} - no price data")
                        continue
                    
                    # Generate signals using production code
                    signal_objs = self.signal_gen.generate_signals(symbol, current_price, context)
                    
                    # Store signals with timestamp
                    for sig_obj in signal_objs:
                        all_signals.append((timestamp, sig_obj))
                        logger.debug(f"  Signal: {sig_obj.signal_type} @ ${sig_obj.entry_price:.2f} (conf: {sig_obj.confidence:.0%})")
                except Exception as e:
                    logger.error(f"Error generating signals for {symbol} on {timestamp.date()}: {e}")
            
            logger.info(f"  Generated {len([s for s in all_signals if s['symbol'] == symbol])} signals for {symbol}")
        
        logger.info("")
        logger.info(f"📊 Total Signals Generated: {len(all_signals)}")
        logger.info("")
        
        # Filter to master signals only (75%+ confidence)
        master_threshold = trading_config.min_master_confidence
        master_signals = [(ts, sig) for ts, sig in all_signals if sig.confidence >= master_threshold]
        logger.info(f"🎯 Master Signals (>={master_threshold:.0%} confidence): {len(master_signals)}")
        logger.info("")
        
        # Simulate trades
        logger.info("💰 Simulating Trades...")
        for timestamp, signal in master_signals:
            try:
                # Get intraday data for better simulation
                intraday_data = self.get_intraday_prices(signal.symbol, timestamp)
                
                trade = self.simulate_trade(signal, timestamp, intraday_data)
            if trade:
                self.results.all_trades.append(trade)
                
                if trade.pnl > 0:
                    self.results.winning_trades += 1
                elif trade.pnl < 0:
                    self.results.losing_trades += 1
                else:
                    self.results.breakeven_trades += 1
                
                self.results.total_pnl += trade.pnl
                self.results.total_pnl_pct += trade.pnl_pct
                self.results.total_trades += 1
                    
                    logger.debug(f"  Trade: {signal.signal_type} {signal.action} @ ${signal.entry_price:.2f} → ${trade.exit_price:.2f} ({trade.exit_reason}) P&L: ${trade.pnl:.2f}")
            except Exception as e:
                logger.error(f"Error simulating trade for {signal.symbol} on {timestamp.date()}: {e}")
        
        # Calculate final metrics
        self.results.calculate_metrics()
        
        # Export trade journal
        self.export_trade_journal()
        
        # Print results
        self.print_results()
        
        # Check pass/fail criteria
        self.check_pass_fail()
    
    def export_trade_journal(self, filename: str = "backtest_trade_journal.csv"):
        """Export all trades to CSV"""
        journal_file = Path("logs/backtest") / filename
        journal_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(journal_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp', 'Symbol', 'Signal Type', 'Action',
                'Entry Price', 'Stop Loss', 'Take Profit', 'Exit Price',
                'Exit Reason', 'P&L', 'P&L %', 'R/R Ratio', 'Confidence', 'Held Bars'
            ])
            
            for trade in self.results.all_trades:
                writer.writerow([
                    trade.timestamp.isoformat(),
                    trade.symbol,
                    trade.signal_type,
                    trade.action,
                    f"{trade.entry_price:.2f}",
                    f"{trade.stop_loss:.2f}",
                    f"{trade.take_profit:.2f}",
                    f"{trade.exit_price:.2f}",
                    trade.exit_reason,
                    f"{trade.pnl:.2f}",
                    f"{trade.pnl_pct:.2f}",
                    f"{trade.risk_reward_ratio:.2f}",
                    f"{trade.confidence:.2f}",
                    trade.held_bars
                ])
        
        logger.info(f"📄 Trade journal exported: {journal_file}")
    
    def check_pass_fail(self):
        """Check if backtest passes validation criteria"""
        r = self.results
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ VALIDATION CRITERIA CHECK")
        logger.info("=" * 80)
        
        criteria = {
            'Win Rate >55%': r.win_rate >= 55,
            'Avg R/R >2.0': r.avg_rr >= 2.0,
            'Max DD <10%': r.max_drawdown_pct < 10,
            'Sharpe >1.5': r.sharpe_ratio >= 1.5,
            'Profit Factor >1.8': r.profit_factor >= 1.8
        }
        
        passed = 0
        for criterion, result in criteria.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {criterion:25} : {status}")
            if result:
                passed += 1
        
        logger.info("")
        logger.info(f"  Overall: {passed}/{len(criteria)} criteria passed")
        
        if passed == len(criteria):
            logger.info("  🎉 BACKTEST VALIDATION PASSED - Strategy ready for paper trading!")
        else:
            logger.info("  ⚠️  BACKTEST VALIDATION FAILED - Tune thresholds before proceeding")
        
        logger.info("=" * 80)
    
    def print_results(self):
        """Print detailed backtest results"""
        r = self.results
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 BACKTEST RESULTS")
        logger.info("=" * 80)
        logger.info("")
        
        logger.info("TRADE SUMMARY:")
        logger.info(f"  Total Trades: {r.total_trades}")
        logger.info(f"  Winning Trades: {r.winning_trades}")
        logger.info(f"  Losing Trades: {r.losing_trades}")
        logger.info(f"  Breakeven Trades: {r.breakeven_trades}")
        logger.info("")
        
        logger.info("PERFORMANCE METRICS:")
        logger.info(f"  Win Rate: {r.win_rate:.1f}% {'✅' if r.win_rate >= 55 else '❌'} (target: >55%)")
        logger.info(f"  Avg Win: ${r.avg_win:.2f}")
        logger.info(f"  Avg Loss: ${r.avg_loss:.2f}")
        logger.info(f"  Avg R/R Ratio: {r.avg_rr:.2f} {'✅' if r.avg_rr >= 2.0 else '❌'} (target: >2.0)")
        logger.info(f"  Profit Factor: {r.profit_factor:.2f} {'✅' if r.profit_factor >= 1.8 else '❌'} (target: >1.8)")
        logger.info("")
        
        logger.info("RISK METRICS:")
        logger.info(f"  Max Drawdown: ${r.max_drawdown:.2f} ({r.max_drawdown_pct:.1f}%) {'✅' if r.max_drawdown_pct < 10 else '❌'} (target: <10%)")
        logger.info(f"  Sharpe Ratio: {r.sharpe_ratio:.2f} {'✅' if r.sharpe_ratio >= 1.5 else '❌'} (target: >1.5)")
        logger.info("")
        
        logger.info("P&L:")
        logger.info(f"  Total P&L: ${r.total_pnl:.2f}")
        logger.info(f"  Total P&L %: {r.total_pnl_pct:.1f}%")
        logger.info("")
        
        logger.info("BY SIGNAL TYPE:")
        for signal_type in ['SQUEEZE', 'GAMMA_RAMP', 'BREAKOUT', 'BOUNCE']:
            count = r.trades_by_type.get(signal_type, 0)
            winrate = r.winrate_by_type.get(signal_type, 0)
            logger.info(f"  {signal_type:12} : {count:3} trades, {winrate:5.1f}% WR")
        logger.info("")
        
        # Pass/Fail verdict
        criteria_met = (
            r.win_rate >= 55 and
            r.avg_rr >= 2.0 and
            r.max_drawdown_pct < 10 and
            r.sharpe_ratio >= 1.5 and
            r.profit_factor >= 1.8
        )
        
        logger.info("=" * 80)
        if criteria_met:
            logger.info("🎯 VERDICT: PASS - ALL CRITERIA MET! ✅")
            logger.info("✅ System has demonstrated EDGE. Proceed to paper trading.")
        else:
            logger.info("⚠️  VERDICT: NEEDS TUNING - Some criteria not met.")
            logger.info("📝 Review signal thresholds and filters before live deployment.")
        logger.info("=" * 80)
        logger.info("")
        
        # Sample trades
        if r.all_trades:
            logger.info("SAMPLE TRADES (First 10):")
            for i, trade in enumerate(r.all_trades[:10]):
                logger.info(f"  {i+1}. {trade.timestamp.date()} | {trade.symbol} | {trade.signal_type:12} | "
                           f"{trade.action} @ ${trade.entry_price:.2f} | "
                           f"{'WIN' if trade.pnl > 0 else 'LOSS':4} ${trade.pnl:+7.2f} ({trade.pnl_pct:+5.1f}%) | "
                           f"{trade.exit_reason}")
            logger.info("")


def main():
    """Main entry point"""
    # Calculate date range (last 30 days from today, but adjust to data availability)
    # Our data is from 9/19 to 10/17 based on populate script
    end_date = datetime(2025, 10, 17)
    start_date = datetime(2025, 9, 19)
    
    symbols = trading_config.symbols  # ['SPY', 'QQQ']
    
    engine = BacktestEngine()
    engine.run_backtest(symbols, start_date, end_date)
    
    logger.info("✅ Backtest complete!")


if __name__ == "__main__":
    main()
