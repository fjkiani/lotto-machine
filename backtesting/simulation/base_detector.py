"""
🎯 BASE DETECTOR - Abstract base class for all signal detectors

All detectors (options, selloff, news, gap, gamma, DP) inherit from this.
Provides consistent interface for:
- Signal generation
- Trade simulation
- Outcome validation
- Performance metrics

Author: Zo (Alpha's AI)
"""

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import yfinance as yf

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)


@dataclass
class Signal:
    """Universal signal format for all detectors"""
    symbol: str
    timestamp: datetime
    signal_type: str           # e.g., OPTIONS_BULLISH, SELLOFF, GAP_UP
    direction: str             # LONG or SHORT
    entry_price: float
    stop_price: float
    target_price: float
    confidence: float          # 0-100
    reasoning: str
    metadata: Dict = field(default_factory=dict)  # Detector-specific data


@dataclass
class TradeResult:
    """Trade outcome after simulation"""
    signal: Signal
    exit_price: float
    exit_time: Optional[datetime]
    pnl_pct: float
    outcome: str               # WIN, LOSS, TIMEOUT
    bars_held: int
    max_favorable: float       # Max favorable excursion
    max_adverse: float         # Max adverse excursion


@dataclass
class BacktestResult:
    """Complete backtest result for a detector"""
    detector_name: str
    date: str
    signals: List[Signal]
    trades: List[TradeResult]
    win_rate: float
    avg_pnl: float
    total_pnl: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    max_drawdown: float
    sharpe_ratio: float


class BaseDetector(ABC):
    """
    Abstract base class for all signal detectors.
    
    Subclasses must implement:
    - name: Detector name
    - detect_signals(): Generate signals from market data
    """
    
    # Default trading params - subclasses can override
    DEFAULT_STOP_PCT = 0.20      # 0.20% stop loss
    DEFAULT_TARGET_PCT = 0.30   # 0.30% take profit (1.5:1 R/R minimum)
    DEFAULT_MAX_BARS = 30       # Max bars to hold
    
    def __init__(
        self,
        stop_pct: float = None,
        target_pct: float = None,
        max_bars: int = None
    ):
        self.stop_pct = stop_pct or self.DEFAULT_STOP_PCT
        self.target_pct = target_pct or self.DEFAULT_TARGET_PCT
        self.max_bars = max_bars or self.DEFAULT_MAX_BARS
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Detector name for logging/reports"""
        pass
    
    @abstractmethod
    def detect_signals(
        self, 
        symbol: str, 
        data: pd.DataFrame,
        **kwargs
    ) -> List[Signal]:
        """
        Detect signals from market data.
        
        Args:
            symbol: Stock symbol
            data: OHLCV DataFrame with datetime index
            **kwargs: Detector-specific parameters
            
        Returns:
            List of Signal objects
        """
        pass
    
    def get_intraday_data(
        self, 
        symbol: str, 
        period: str = "1d", 
        interval: str = "1m"
    ) -> pd.DataFrame:
        """
        Fetch intraday data from yfinance.
        
        Args:
            symbol: Stock symbol
            period: Data period (1d, 5d, etc.)
            interval: Bar interval (1m, 5m, etc.)
            
        Returns:
            OHLCV DataFrame
        """
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            return data
        except Exception as e:
            print(f"   ⚠️ Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def simulate_trade(
        self, 
        signal: Signal, 
        data: pd.DataFrame,
        entry_idx: int
    ) -> TradeResult:
        """
        Simulate a trade from a signal.
        
        Args:
            signal: Signal to trade
            data: Price data
            entry_idx: Index of entry bar
            
        Returns:
            TradeResult with outcome
        """
        if entry_idx >= len(data) - 1:
            return TradeResult(
                signal=signal,
                exit_price=signal.entry_price,
                exit_time=None,
                pnl_pct=0,
                outcome='NO_DATA',
                bars_held=0,
                max_favorable=0,
                max_adverse=0
            )
        
        max_favorable = 0
        max_adverse = 0
        
        for i in range(entry_idx + 1, min(entry_idx + self.max_bars + 1, len(data))):
            high = data['High'].iloc[i]
            low = data['Low'].iloc[i]
            
            if signal.direction == 'LONG':
                # Track excursions
                curr_favorable = (high - signal.entry_price) / signal.entry_price * 100
                curr_adverse = (signal.entry_price - low) / signal.entry_price * 100
                max_favorable = max(max_favorable, curr_favorable)
                max_adverse = max(max_adverse, curr_adverse)
                
                # Check target
                if high >= signal.target_price:
                    return TradeResult(
                        signal=signal,
                        exit_price=signal.target_price,
                        exit_time=data.index[i] if hasattr(data.index[i], 'isoformat') else None,
                        pnl_pct=self.target_pct,
                        outcome='WIN',
                        bars_held=i - entry_idx,
                        max_favorable=max_favorable,
                        max_adverse=max_adverse
                    )
                
                # Check stop
                if low <= signal.stop_price:
                    return TradeResult(
                        signal=signal,
                        exit_price=signal.stop_price,
                        exit_time=data.index[i] if hasattr(data.index[i], 'isoformat') else None,
                        pnl_pct=-self.stop_pct,
                        outcome='LOSS',
                        bars_held=i - entry_idx,
                        max_favorable=max_favorable,
                        max_adverse=max_adverse
                    )
            
            else:  # SHORT
                curr_favorable = (signal.entry_price - low) / signal.entry_price * 100
                curr_adverse = (high - signal.entry_price) / signal.entry_price * 100
                max_favorable = max(max_favorable, curr_favorable)
                max_adverse = max(max_adverse, curr_adverse)
                
                if low <= signal.target_price:
                    return TradeResult(
                        signal=signal,
                        exit_price=signal.target_price,
                        exit_time=data.index[i] if hasattr(data.index[i], 'isoformat') else None,
                        pnl_pct=self.target_pct,
                        outcome='WIN',
                        bars_held=i - entry_idx,
                        max_favorable=max_favorable,
                        max_adverse=max_adverse
                    )
                
                if high >= signal.stop_price:
                    return TradeResult(
                        signal=signal,
                        exit_price=signal.stop_price,
                        exit_time=data.index[i] if hasattr(data.index[i], 'isoformat') else None,
                        pnl_pct=-self.stop_pct,
                        outcome='LOSS',
                        bars_held=i - entry_idx,
                        max_favorable=max_favorable,
                        max_adverse=max_adverse
                    )
        
        # Timeout - close at last price
        last_price = data['Close'].iloc[min(entry_idx + self.max_bars, len(data) - 1)]
        if signal.direction == 'LONG':
            pnl = (last_price - signal.entry_price) / signal.entry_price * 100
        else:
            pnl = (signal.entry_price - last_price) / signal.entry_price * 100
        
        return TradeResult(
            signal=signal,
            exit_price=last_price,
            exit_time=None,
            pnl_pct=pnl,
            outcome='WIN' if pnl > 0 else 'LOSS',
            bars_held=self.max_bars,
            max_favorable=max_favorable,
            max_adverse=max_adverse
        )
    
    def backtest_date(
        self, 
        symbols: List[str],
        date: str = None,
        **kwargs
    ) -> BacktestResult:
        """
        Run backtest for a specific date.
        
        Args:
            symbols: List of symbols to test
            date: Date string (YYYY-MM-DD), defaults to today
            **kwargs: Passed to detect_signals
            
        Returns:
            BacktestResult with all metrics
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        all_signals = []
        all_trades = []
        
        for symbol in symbols:
            # Get data
            data = self.get_intraday_data(symbol, period="1d", interval="1m")
            if data.empty:
                continue
            
            # Detect signals
            signals = self.detect_signals(symbol, data, **kwargs)
            all_signals.extend(signals)
            
            # Simulate trades
            for signal in signals:
                # Find entry bar index
                entry_idx = None
                for i, idx in enumerate(data.index):
                    if hasattr(idx, 'timestamp'):
                        if idx >= signal.timestamp:
                            entry_idx = i
                            break
                    else:
                        entry_idx = 0  # Default to start
                
                if entry_idx is None:
                    continue
                
                trade = self.simulate_trade(signal, data, entry_idx)
                all_trades.append(trade)
        
        return self._calculate_metrics(date, all_signals, all_trades)
    
    def backtest_range(
        self,
        symbols: List[str],
        days: int = 5,
        **kwargs
    ) -> List[BacktestResult]:
        """
        Run backtest over multiple days.
        
        Args:
            symbols: List of symbols
            days: Number of days to backtest
            **kwargs: Passed to detect_signals
            
        Returns:
            List of BacktestResult, one per day
        """
        results = []
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            
            # Get multi-day data
            all_signals = []
            all_trades = []
            
            for symbol in symbols:
                data = self.get_intraday_data(symbol, period=f"{days+1}d", interval="5m")
                if data.empty:
                    continue
                
                # Filter to specific date
                date_data = data[data.index.date.astype(str) == date]
                if date_data.empty:
                    continue
                
                signals = self.detect_signals(symbol, date_data, **kwargs)
                all_signals.extend(signals)
                
                for signal in signals:
                    entry_idx = 0  # Start of day
                    trade = self.simulate_trade(signal, date_data, entry_idx)
                    all_trades.append(trade)
            
            result = self._calculate_metrics(date, all_signals, all_trades)
            results.append(result)
        
        return results
    
    def _calculate_metrics(
        self, 
        date: str,
        signals: List[Signal],
        trades: List[TradeResult]
    ) -> BacktestResult:
        """Calculate performance metrics from trades"""
        
        if not trades:
            return BacktestResult(
                detector_name=self.name,
                date=date,
                signals=signals,
                trades=trades,
                win_rate=0,
                avg_pnl=0,
                total_pnl=0,
                profit_factor=0,
                avg_win=0,
                avg_loss=0,
                max_drawdown=0,
                sharpe_ratio=0
            )
        
        wins = [t for t in trades if t.outcome == 'WIN']
        losses = [t for t in trades if t.outcome == 'LOSS']
        
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        
        pnls = [t.pnl_pct for t in trades]
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        total_pnl = sum(pnls)
        
        avg_win = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        
        gross_profit = sum(t.pnl_pct for t in wins)
        gross_loss = abs(sum(t.pnl_pct for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Max drawdown
        cumulative = 0
        peak = 0
        max_dd = 0
        for t in trades:
            cumulative += t.pnl_pct
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)
        
        # Sharpe (simplified - assumes 0 risk-free rate)
        if len(pnls) > 1:
            import numpy as np
            sharpe = np.mean(pnls) / np.std(pnls) if np.std(pnls) > 0 else 0
        else:
            sharpe = 0
        
        return BacktestResult(
            detector_name=self.name,
            date=date,
            signals=signals,
            trades=trades,
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            total_pnl=total_pnl,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe
        )
    
    def print_result(self, result: BacktestResult):
        """Print formatted backtest result"""
        print(f"\n{'='*60}")
        print(f"📊 {self.name.upper()} BACKTEST - {result.date}")
        print(f"{'='*60}")
        print(f"   Signals: {len(result.signals)}")
        print(f"   Trades: {len(result.trades)}")
        print(f"   Win Rate: {result.win_rate:.1f}%")
        print(f"   Avg P&L: {result.avg_pnl:+.2f}%")
        print(f"   Total P&L: {result.total_pnl:+.2f}%")
        print(f"   Profit Factor: {result.profit_factor:.2f}")
        print(f"   Avg Win: {result.avg_win:+.2f}%")
        print(f"   Avg Loss: {result.avg_loss:+.2f}%")
        print(f"   Max Drawdown: {result.max_drawdown:.2f}%")
        print(f"   Sharpe Ratio: {result.sharpe_ratio:.2f}")
        
        if result.trades:
            print(f"\n   📈 TRADES:")
            for t in result.trades[:10]:  # First 10
                emoji = "✅" if t.outcome == 'WIN' else "❌"
                print(f"   {emoji} {t.signal.symbol} {t.signal.direction} @ ${t.signal.entry_price:.2f} -> {t.outcome} ({t.pnl_pct:+.2f}%)")

