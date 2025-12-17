"""
🔥 REDDIT MOMENTUM BACKTEST - REAL HISTORICAL VALIDATION

This module validates Reddit signals using REAL price data.
Since we don't have historical Reddit data, we simulate what signals 
WOULD have been generated based on price action criteria.

Key insight: We can validate the SIGNAL LOGIC by checking if the 
PRICE ACTION that would trigger our signals actually led to profitable trades.

For example:
- CONFIRMED_MOMENTUM triggers when: mega-cap + price up 5%+ in 7d + velocity surge
- We can backtest: "If we bought every time a mega-cap was up 5%+ in 7d, how did it perform?"

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import yfinance as yf
import pandas as pd
import numpy as np
import logging

from ..config.trading_params import TradingParams

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    """A momentum signal detected from price action"""
    symbol: str
    date: datetime
    signal_type: str  # CONFIRMED_MOMENTUM, BULLISH_DIV, VELOCITY_SURGE, etc.
    action: str  # LONG, SHORT, AVOID
    entry_price: float
    price_change_7d: float
    price_change_1d: float
    volume_ratio: float  # vs 20-day avg
    trigger_criteria: str


@dataclass 
class BacktestTrade:
    """A simulated trade from backtest"""
    symbol: str
    signal_type: str
    action: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime]
    exit_price: Optional[float]
    stop_price: float
    target_price: float
    pnl: Optional[float]
    pnl_pct: Optional[float]
    outcome: str  # WIN, LOSS, OPEN
    days_held: int
    max_favorable: float  # Maximum favorable excursion
    max_adverse: float  # Maximum adverse excursion


@dataclass
class BacktestResult:
    """Complete backtest results"""
    symbol: str
    start_date: datetime
    end_date: datetime
    
    # Signal counts
    total_signals: int
    long_signals: int
    short_signals: int
    avoid_signals: int
    
    # Trade stats
    trades_taken: int
    wins: int
    losses: int
    win_rate: float
    
    # P&L
    total_pnl_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    max_drawdown_pct: float
    
    # By signal type
    results_by_signal: Dict[str, Dict]
    
    # All trades
    trades: List[BacktestTrade] = field(default_factory=list)


class RedditMomentumBacktester:
    """
    Backtests momentum signals that mirror Reddit signal logic.
    
    Since we can't get historical Reddit sentiment, we validate the
    PRICE-BASED triggers that our signals use:
    
    1. CONFIRMED_MOMENTUM: Price up 5%+ in 7d (mega-caps only)
    2. BULLISH_DIVERGENCE: Price down but RSI oversold
    3. VELOCITY_SURGE: Volume spike 3x+ above average
    """
    
    # Mega-caps that get CONFIRMED_MOMENTUM treatment
    MEGA_CAPS = ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'AMD', 'NFLX']
    
    # Thresholds
    MOMENTUM_THRESHOLD_7D = 5.0  # 5% gain in 7 days
    MOMENTUM_THRESHOLD_1D = 2.0  # 2% gain in 1 day
    VOLUME_SURGE_THRESHOLD = 2.0  # 2x average volume
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    
    def __init__(self, params: Optional[TradingParams] = None):
        """Initialize backtester with trading parameters."""
        self.params = params or TradingParams()
        self.signals: List[MomentumSignal] = []
        self.trades: List[BacktestTrade] = []
    
    def backtest(self, 
                 symbol: str, 
                 start_date: datetime, 
                 end_date: datetime,
                 hold_days: int = 5) -> BacktestResult:
        """
        Run backtest for a symbol over a date range.
        
        Args:
            symbol: Ticker symbol
            start_date: Backtest start date
            end_date: Backtest end date
            hold_days: Days to hold position (default 5)
            
        Returns:
            BacktestResult with full metrics
        """
        logger.info(f"📊 Backtesting {symbol} from {start_date.date()} to {end_date.date()}")
        
        self.signals = []
        self.trades = []
        
        # Get historical data
        try:
            ticker = yf.Ticker(symbol)
            # Get extra data for lookback
            data_start = start_date - timedelta(days=30)
            hist = ticker.history(start=data_start.strftime('%Y-%m-%d'),
                                 end=end_date.strftime('%Y-%m-%d'))
            
            if hist.empty or len(hist) < 10:
                logger.warning(f"Insufficient data for {symbol}")
                return self._empty_result(symbol, start_date, end_date)
            
            # Add technical indicators
            hist = self._add_indicators(hist)
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return self._empty_result(symbol, start_date, end_date)
        
        # Detect signals
        is_mega_cap = symbol.upper() in self.MEGA_CAPS
        
        for i in range(20, len(hist)):
            current_date = hist.index[i].to_pydatetime()
            
            # Skip if before start date
            if current_date.date() < start_date.date():
                continue
            
            # Skip weekends
            if current_date.weekday() >= 5:
                continue
            
            signal = self._detect_signal(hist, i, symbol, is_mega_cap)
            
            if signal:
                self.signals.append(signal)
                
                # Simulate trade if actionable
                if signal.action in ["LONG", "SHORT"]:
                    trade = self._simulate_trade(hist, i, signal, hold_days)
                    if trade:
                        self.trades.append(trade)
        
        return self._calculate_results(symbol, start_date, end_date)
    
    def _add_indicators(self, hist: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to price data."""
        # Returns
        hist['return_1d'] = hist['Close'].pct_change() * 100
        hist['return_7d'] = hist['Close'].pct_change(periods=5) * 100  # 5 trading days
        hist['return_14d'] = hist['Close'].pct_change(periods=10) * 100
        
        # Volume
        hist['volume_avg_20d'] = hist['Volume'].rolling(20).mean()
        hist['volume_ratio'] = hist['Volume'] / hist['volume_avg_20d']
        
        # RSI (14-day)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['rsi'] = 100 - (100 / (1 + rs))
        
        # Volatility
        hist['volatility'] = hist['return_1d'].rolling(20).std()
        
        # ATR for stops
        hist['tr'] = np.maximum(
            hist['High'] - hist['Low'],
            np.maximum(
                abs(hist['High'] - hist['Close'].shift(1)),
                abs(hist['Low'] - hist['Close'].shift(1))
            )
        )
        hist['atr'] = hist['tr'].rolling(14).mean()
        
        return hist
    
    def _detect_signal(self, hist: pd.DataFrame, idx: int, symbol: str, 
                       is_mega_cap: bool) -> Optional[MomentumSignal]:
        """
        Detect signal based on price action criteria.
        
        Mirrors the Reddit signal logic but uses pure price action.
        """
        row = hist.iloc[idx]
        date = hist.index[idx].to_pydatetime()
        
        price = row['Close']
        return_7d = row['return_7d'] if not pd.isna(row['return_7d']) else 0
        return_1d = row['return_1d'] if not pd.isna(row['return_1d']) else 0
        volume_ratio = row['volume_ratio'] if not pd.isna(row['volume_ratio']) else 1.0
        rsi = row['rsi'] if not pd.isna(row['rsi']) else 50
        
        # SIGNAL 1: CONFIRMED_MOMENTUM (mega-caps only)
        # Price rallying + high volume = real momentum
        if is_mega_cap:
            if return_7d >= self.MOMENTUM_THRESHOLD_7D or return_1d >= self.MOMENTUM_THRESHOLD_1D:
                if volume_ratio >= 1.5:  # Higher volume confirming
                    return MomentumSignal(
                        symbol=symbol,
                        date=date,
                        signal_type="CONFIRMED_MOMENTUM",
                        action="LONG",
                        entry_price=price,
                        price_change_7d=return_7d,
                        price_change_1d=return_1d,
                        volume_ratio=volume_ratio,
                        trigger_criteria=f"7d: {return_7d:+.1f}%, 1d: {return_1d:+.1f}%, Vol: {volume_ratio:.1f}x"
                    )
        
        # SIGNAL 2: BULLISH_DIVERGENCE
        # Price down but oversold = accumulation opportunity
        if return_7d < -3 and rsi < self.RSI_OVERSOLD:
            return MomentumSignal(
                symbol=symbol,
                date=date,
                signal_type="BULLISH_DIVERGENCE",
                action="LONG",
                entry_price=price,
                price_change_7d=return_7d,
                price_change_1d=return_1d,
                volume_ratio=volume_ratio,
                trigger_criteria=f"7d: {return_7d:+.1f}%, RSI: {rsi:.0f} (oversold)"
            )
        
        # SIGNAL 3: BEARISH_DIVERGENCE
        # Price up but overbought = distribution warning
        if return_7d > 8 and rsi > self.RSI_OVERBOUGHT:
            return MomentumSignal(
                symbol=symbol,
                date=date,
                signal_type="BEARISH_DIVERGENCE",
                action="SHORT",
                entry_price=price,
                price_change_7d=return_7d,
                price_change_1d=return_1d,
                volume_ratio=volume_ratio,
                trigger_criteria=f"7d: {return_7d:+.1f}%, RSI: {rsi:.0f} (overbought)"
            )
        
        # SIGNAL 4: VELOCITY_SURGE (non mega-caps)
        # Volume spike without mega-cap status = potential pump, avoid
        if not is_mega_cap and volume_ratio >= self.VOLUME_SURGE_THRESHOLD:
            if return_7d < 5:  # If not confirmed by strong price move
                return MomentumSignal(
                    symbol=symbol,
                    date=date,
                    signal_type="VELOCITY_SURGE",
                    action="AVOID",
                    entry_price=price,
                    price_change_7d=return_7d,
                    price_change_1d=return_1d,
                    volume_ratio=volume_ratio,
                    trigger_criteria=f"Vol: {volume_ratio:.1f}x (surge), 7d: {return_7d:+.1f}%"
                )
        
        return None
    
    def _simulate_trade(self, hist: pd.DataFrame, entry_idx: int, 
                        signal: MomentumSignal, hold_days: int) -> Optional[BacktestTrade]:
        """Simulate a trade from a signal."""
        try:
            entry_row = hist.iloc[entry_idx]
            entry_price = signal.entry_price
            atr = entry_row['atr'] if not pd.isna(entry_row['atr']) else entry_price * 0.02
            
            # Calculate stop and target based on ATR
            if signal.action == "LONG":
                stop_price = entry_price - (1.5 * atr)
                target_price = entry_price + (3.0 * atr)  # 2:1 R/R
            else:  # SHORT
                stop_price = entry_price + (1.5 * atr)
                target_price = entry_price - (3.0 * atr)
            
            # Simulate trade outcome
            max_favorable = 0
            max_adverse = 0
            exit_price = None
            exit_date = None
            outcome = "OPEN"
            
            for i in range(1, min(hold_days + 1, len(hist) - entry_idx)):
                day_data = hist.iloc[entry_idx + i]
                high = day_data['High']
                low = day_data['Low']
                close = day_data['Close']
                check_date = hist.index[entry_idx + i].to_pydatetime()
                
                if signal.action == "LONG":
                    # Track MFE/MAE
                    max_favorable = max(max_favorable, (high - entry_price) / entry_price * 100)
                    max_adverse = max(max_adverse, (entry_price - low) / entry_price * 100)
                    
                    # Check stop
                    if low <= stop_price:
                        exit_price = stop_price
                        exit_date = check_date
                        outcome = "LOSS"
                        break
                    # Check target
                    if high >= target_price:
                        exit_price = target_price
                        exit_date = check_date
                        outcome = "WIN"
                        break
                else:  # SHORT
                    max_favorable = max(max_favorable, (entry_price - low) / entry_price * 100)
                    max_adverse = max(max_adverse, (high - entry_price) / entry_price * 100)
                    
                    if high >= stop_price:
                        exit_price = stop_price
                        exit_date = check_date
                        outcome = "LOSS"
                        break
                    if low <= target_price:
                        exit_price = target_price
                        exit_date = check_date
                        outcome = "WIN"
                        break
            
            # If no stop/target hit, exit at last close
            if exit_price is None:
                final_idx = min(entry_idx + hold_days, len(hist) - 1)
                exit_price = hist.iloc[final_idx]['Close']
                exit_date = hist.index[final_idx].to_pydatetime()
                
                if signal.action == "LONG":
                    outcome = "WIN" if exit_price > entry_price else "LOSS"
                else:
                    outcome = "WIN" if exit_price < entry_price else "LOSS"
            
            # Calculate P&L
            if signal.action == "LONG":
                pnl = exit_price - entry_price
            else:
                pnl = entry_price - exit_price
            
            pnl_pct = (pnl / entry_price) * 100
            days_held = (exit_date - signal.date).days if exit_date else 0
            
            return BacktestTrade(
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                action=signal.action,
                entry_date=signal.date,
                entry_price=entry_price,
                exit_date=exit_date,
                exit_price=exit_price,
                stop_price=stop_price,
                target_price=target_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                outcome=outcome,
                days_held=days_held,
                max_favorable=max_favorable,
                max_adverse=max_adverse
            )
            
        except Exception as e:
            logger.debug(f"Error simulating trade: {e}")
            return None
    
    def _calculate_results(self, symbol: str, start_date: datetime, 
                          end_date: datetime) -> BacktestResult:
        """Calculate backtest metrics."""
        
        # Signal counts
        long_signals = [s for s in self.signals if s.action == "LONG"]
        short_signals = [s for s in self.signals if s.action == "SHORT"]
        avoid_signals = [s for s in self.signals if s.action == "AVOID"]
        
        # Trade stats
        wins = [t for t in self.trades if t.outcome == "WIN"]
        losses = [t for t in self.trades if t.outcome == "LOSS"]
        
        trades_taken = len(self.trades)
        win_rate = (len(wins) / trades_taken * 100) if trades_taken > 0 else 0
        
        # P&L
        total_pnl = sum(t.pnl_pct for t in self.trades if t.pnl_pct)
        avg_win = np.mean([t.pnl_pct for t in wins if t.pnl_pct]) if wins else 0
        avg_loss = np.mean([abs(t.pnl_pct) for t in losses if t.pnl_pct]) if losses else 0
        
        # Profit factor
        gross_profit = sum(t.pnl_pct for t in wins if t.pnl_pct and t.pnl_pct > 0)
        gross_loss = abs(sum(t.pnl_pct for t in losses if t.pnl_pct and t.pnl_pct < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in sorted(self.trades, key=lambda x: x.entry_date):
            if t.pnl_pct:
                cumulative += t.pnl_pct
                peak = max(peak, cumulative)
                dd = peak - cumulative
                max_dd = max(max_dd, dd)
        
        # Results by signal type
        results_by_signal = {}
        for signal_type in set(t.signal_type for t in self.trades):
            type_trades = [t for t in self.trades if t.signal_type == signal_type]
            type_wins = [t for t in type_trades if t.outcome == "WIN"]
            results_by_signal[signal_type] = {
                'trades': len(type_trades),
                'wins': len(type_wins),
                'win_rate': len(type_wins) / len(type_trades) * 100 if type_trades else 0,
                'avg_pnl': np.mean([t.pnl_pct for t in type_trades if t.pnl_pct]) if type_trades else 0
            }
        
        return BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            total_signals=len(self.signals),
            long_signals=len(long_signals),
            short_signals=len(short_signals),
            avoid_signals=len(avoid_signals),
            trades_taken=trades_taken,
            wins=len(wins),
            losses=len(losses),
            win_rate=win_rate,
            total_pnl_pct=total_pnl,
            avg_win_pct=avg_win,
            avg_loss_pct=avg_loss,
            profit_factor=profit_factor,
            max_drawdown_pct=max_dd,
            results_by_signal=results_by_signal,
            trades=self.trades
        )
    
    def _empty_result(self, symbol: str, start_date: datetime, 
                     end_date: datetime) -> BacktestResult:
        """Return empty result for failed backtest."""
        return BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            total_signals=0,
            long_signals=0,
            short_signals=0,
            avoid_signals=0,
            trades_taken=0,
            wins=0,
            losses=0,
            win_rate=0,
            total_pnl_pct=0,
            avg_win_pct=0,
            avg_loss_pct=0,
            profit_factor=0,
            max_drawdown_pct=0,
            results_by_signal={},
            trades=[]
        )


def run_tsla_rally_backtest():
    """Run backtest specifically for TSLA rally period."""
    backtester = RedditMomentumBacktester()
    
    # TSLA rally period: Nov 21 2025 (low $391) to Dec 17 2025 (high ~$490)
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 12, 17)
    
    print("="*80)
    print("🔥 TSLA RALLY BACKTEST - CONFIRMED MOMENTUM STRATEGY")
    print("="*80)
    print(f"\nPeriod: {start_date.date()} to {end_date.date()}")
    print(f"Strategy: Buy when TSLA up 5%+ in 7 days with volume confirmation")
    
    result = backtester.backtest('TSLA', start_date, end_date, hold_days=5)
    
    print(f"\n📊 RESULTS:")
    print("-"*60)
    print(f"   Total Signals: {result.total_signals}")
    print(f"   LONG Signals: {result.long_signals}")
    print(f"   AVOID Signals: {result.avoid_signals}")
    print(f"\n   Trades Taken: {result.trades_taken}")
    print(f"   Wins: {result.wins}")
    print(f"   Losses: {result.losses}")
    print(f"   Win Rate: {result.win_rate:.1f}%")
    print(f"\n   Total P&L: {result.total_pnl_pct:+.1f}%")
    print(f"   Avg Win: {result.avg_win_pct:+.1f}%")
    print(f"   Avg Loss: {result.avg_loss_pct:.1f}%")
    print(f"   Profit Factor: {result.profit_factor:.2f}")
    print(f"   Max Drawdown: {result.max_drawdown_pct:.1f}%")
    
    if result.results_by_signal:
        print(f"\n📈 BY SIGNAL TYPE:")
        for sig_type, stats in result.results_by_signal.items():
            print(f"   {sig_type}: {stats['trades']} trades, {stats['win_rate']:.0f}% win rate, {stats['avg_pnl']:+.1f}% avg")
    
    if result.trades:
        print(f"\n📋 TRADE LOG:")
        print("-"*100)
        for trade in result.trades:
            print(f"   {trade.entry_date.strftime('%Y-%m-%d')} | {trade.signal_type:20} | "
                  f"{trade.action:5} @ ${trade.entry_price:.2f} → ${trade.exit_price:.2f} | "
                  f"{trade.pnl_pct:+.1f}% | {trade.outcome}")
    
    return result


if __name__ == "__main__":
    run_tsla_rally_backtest()

