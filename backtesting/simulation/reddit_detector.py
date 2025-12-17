"""
📱 REDDIT SIGNAL SIMULATOR - Task 5.10
Backtest Reddit-based trading signals historically.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import yfinance as yf
import pandas as pd
import logging

from ..simulation.trade_simulator import Trade
from ..config.trading_params import TradingParams

logger = logging.getLogger(__name__)


@dataclass
class RedditBacktestResult:
    """Backtest results for Reddit signals"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    trades_by_signal_type: Dict[str, int]
    win_rate_by_signal_type: Dict[str, float]
    best_signal_type: str
    worst_signal_type: str


@dataclass
class RedditBacktestTrade:
    """Single backtest trade"""
    symbol: str
    entry_date: datetime
    exit_date: Optional[datetime]
    signal_type: str
    action: str
    entry_price: float
    exit_price: Optional[float]
    stop_price: float
    target_price: float
    pnl: Optional[float]
    pnl_pct: Optional[float]
    win: Optional[bool]
    days_held: Optional[int]


class RedditSignalSimulator:
    """
    Backtest Reddit-based trading signals - Task 5.10.
    
    Simulates Reddit signals on historical data to validate edge.
    """
    
    def __init__(self, exploiter, params: Optional[TradingParams] = None):
        """
        Initialize Reddit signal simulator.
        
        Args:
            exploiter: RedditExploiter instance
            params: Trading parameters (optional, uses defaults)
        """
        self.exploiter = exploiter
        self.params = params or TradingParams()
        self.trades: List[RedditBacktestTrade] = []
    
    def simulate(self, symbols: List[str], days: int = 30) -> RedditBacktestResult:
        """
        Backtest Reddit signals - Task 5.10.
        
        For each day:
        1. Get Reddit sentiment at market open
        2. Generate signal
        3. If actionable, simulate trade
        4. Track P&L
        
        Args:
            symbols: List of ticker symbols to backtest
            days: Number of days to backtest
        
        Returns:
            RedditBacktestResult with metrics
        """
        logger.info(f"📱 Starting Reddit signal backtest for {len(symbols)} symbols over {days} days...")
        
        self.trades = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Market hours check (simplified - assume 9:30 AM ET)
            market_open = current_date.replace(hour=9, minute=30)
            
            for symbol in symbols:
                try:
                    # Generate signal for this date
                    analysis = self._get_historical_signal(symbol, market_open)
                    
                    if not analysis or not analysis.signal_type:
                        continue
                    
                    # Only trade actionable signals (LONG/SHORT, not AVOID/WATCH)
                    if analysis.action not in ["LONG", "SHORT"]:
                        continue
                    
                    # Check if signal strength meets threshold
                    if analysis.signal_strength < 60:
                        continue
                    
                    # Simulate trade
                    trade = self._simulate_trade(symbol, analysis, market_open)
                    if trade:
                        self.trades.append(trade)
                
                except Exception as e:
                    logger.debug(f"Error simulating {symbol} on {current_date.date()}: {e}")
                    continue
            
            current_date += timedelta(days=1)
        
        # Calculate metrics
        return self._calculate_metrics()
    
    def _get_historical_signal(self, symbol: str, date: datetime):
        """
        Get Reddit signal for a historical date.
        
        Note: This is a simplified version. In production, you'd need
        historical Reddit data. For now, we use current data as proxy.
        """
        try:
            # Use exploiter to analyze (will use current data)
            # In production, this would fetch historical Reddit data
            analysis = self.exploiter.analyze_ticker(symbol, days=3)
            return analysis
        except Exception as e:
            logger.debug(f"Error getting signal for {symbol}: {e}")
            return None
    
    def _simulate_trade(self, symbol: str, analysis, entry_date: datetime) -> Optional[RedditBacktestTrade]:
        """
        Simulate a trade from a Reddit signal.
        
        Args:
            symbol: Ticker symbol
            analysis: RedditTickerAnalysis
            entry_date: Entry date/time
        
        Returns:
            RedditBacktestTrade or None
        """
        try:
            # Get price data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=entry_date.strftime('%Y-%m-%d'),
                                 end=(entry_date + timedelta(days=10)).strftime('%Y-%m-%d'))
            
            if hist.empty:
                return None
            
            entry_price = float(hist['Close'].iloc[0])
            
            # Calculate stop and target
            if analysis.action == "LONG":
                stop_price = entry_price * (1 - self.params.stop_loss_pct)
                target_price = entry_price * (1 + self.params.take_profit_pct)
            else:  # SHORT
                stop_price = entry_price * (1 + self.params.stop_loss_pct)
                target_price = entry_price * (1 - self.params.take_profit_pct)
            
            # Simulate exit (check if stop or target hit)
            exit_date = None
            exit_price = None
            win = None
            
            for i in range(1, min(len(hist), 10)):  # Check up to 10 days
                day_data = hist.iloc[i]
                high = float(day_data['High'])
                low = float(day_data['Low'])
                close = float(day_data['Close'])
                check_date = day_data.name.to_pydatetime()
                
                if analysis.action == "LONG":
                    # Check if stop hit first
                    if low <= stop_price:
                        exit_date = check_date
                        exit_price = stop_price
                        win = False
                        break
                    # Check if target hit
                    elif high >= target_price:
                        exit_date = check_date
                        exit_price = target_price
                        win = True
                        break
                else:  # SHORT
                    # Check if stop hit first
                    if high >= stop_price:
                        exit_date = check_date
                        exit_price = stop_price
                        win = False
                        break
                    # Check if target hit
                    elif low <= target_price:
                        exit_date = check_date
                        exit_price = target_price
                        win = True
                        break
            
            # If no exit, use final price
            if exit_date is None:
                exit_date = hist.index[-1].to_pydatetime()
                exit_price = float(hist['Close'].iloc[-1])
                # Determine win/loss
                if analysis.action == "LONG":
                    win = exit_price > entry_price
                else:
                    win = exit_price < entry_price
            
            # Calculate P&L
            if analysis.action == "LONG":
                pnl = exit_price - entry_price
            else:
                pnl = entry_price - exit_price
            
            pnl_pct = (pnl / entry_price) * 100
            days_held = (exit_date - entry_date).days
            
            return RedditBacktestTrade(
                symbol=symbol,
                entry_date=entry_date,
                exit_date=exit_date,
                signal_type=analysis.signal_type.value if analysis.signal_type else "UNKNOWN",
                action=analysis.action,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_price=stop_price,
                target_price=target_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                win=win,
                days_held=days_held
            )
        
        except Exception as e:
            logger.debug(f"Error simulating trade for {symbol}: {e}")
            return None
    
    def _calculate_metrics(self) -> RedditBacktestResult:
        """Calculate backtest metrics"""
        if not self.trades:
            return RedditBacktestResult(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                trades_by_signal_type={},
                win_rate_by_signal_type={},
                best_signal_type="NONE",
                worst_signal_type="NONE"
            )
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.win]
        losing_trades = [t for t in self.trades if not t.win]
        
        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0.0
        
        total_pnl = sum(t.pnl for t in self.trades if t.pnl is not None)
        avg_win = sum(t.pnl for t in winning_trades if t.pnl) / len(winning_trades) if winning_trades else 0.0
        avg_loss = abs(sum(t.pnl for t in losing_trades if t.pnl)) / len(losing_trades) if losing_trades else 0.0
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades if t.pnl and t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in losing_trades if t.pnl and t.pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        # Max drawdown
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0.0
        
        for trade in sorted(self.trades, key=lambda x: x.entry_date):
            if trade.pnl:
                cumulative_pnl += trade.pnl
                peak = max(peak, cumulative_pnl)
                drawdown = peak - cumulative_pnl
                max_drawdown = max(max_drawdown, drawdown)
        
        # Sharpe ratio (simplified)
        returns = [t.pnl_pct for t in self.trades if t.pnl_pct is not None]
        if len(returns) > 1:
            import numpy as np
            sharpe_ratio = np.mean(returns) / np.std(returns) * (252 ** 0.5) if np.std(returns) > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        # Metrics by signal type
        trades_by_signal_type = {}
        wins_by_signal_type = {}
        
        for trade in self.trades:
            signal_type = trade.signal_type
            trades_by_signal_type[signal_type] = trades_by_signal_type.get(signal_type, 0) + 1
            if trade.win:
                wins_by_signal_type[signal_type] = wins_by_signal_type.get(signal_type, 0) + 1
        
        win_rate_by_signal_type = {
            sig_type: (wins_by_signal_type.get(sig_type, 0) / count * 100)
            for sig_type, count in trades_by_signal_type.items()
        }
        
        # Best/worst signal types
        if win_rate_by_signal_type:
            best_signal_type = max(win_rate_by_signal_type.items(), key=lambda x: x[1])[0]
            worst_signal_type = min(win_rate_by_signal_type.items(), key=lambda x: x[1])[0]
        else:
            best_signal_type = "NONE"
            worst_signal_type = "NONE"
        
        return RedditBacktestResult(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            trades_by_signal_type=trades_by_signal_type,
            win_rate_by_signal_type=win_rate_by_signal_type,
            best_signal_type=best_signal_type,
            worst_signal_type=worst_signal_type
        )
    
    def export_trade_journal(self, filename: str = "reddit_backtest_trades.csv"):
        """Export trade journal to CSV"""
        import csv
        
        if not self.trades:
            logger.warning("No trades to export")
            return
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Symbol', 'Entry Date', 'Exit Date', 'Signal Type', 'Action',
                'Entry Price', 'Exit Price', 'Stop Price', 'Target Price',
                'P&L', 'P&L %', 'Win', 'Days Held'
            ])
            
            for trade in self.trades:
                writer.writerow([
                    trade.symbol,
                    trade.entry_date.strftime('%Y-%m-%d %H:%M:%S'),
                    trade.exit_date.strftime('%Y-%m-%d %H:%M:%S') if trade.exit_date else '',
                    trade.signal_type,
                    trade.action,
                    f"{trade.entry_price:.2f}",
                    f"{trade.exit_price:.2f}" if trade.exit_price else '',
                    f"{trade.stop_price:.2f}",
                    f"{trade.target_price:.2f}",
                    f"{trade.pnl:.2f}" if trade.pnl else '',
                    f"{trade.pnl_pct:.2f}" if trade.pnl_pct else '',
                    'WIN' if trade.win else 'LOSS',
                    trade.days_held if trade.days_held else ''
                ])
        
        logger.info(f"✅ Trade journal exported to {filename}")

