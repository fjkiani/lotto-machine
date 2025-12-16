"""
🔥 SQUEEZE DETECTOR SIMULATOR
Simulates squeeze detector signals and trades
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import yfinance as yf
import pandas as pd

from ..simulation.trade_simulator import Trade
from ..config.trading_params import TradingParams


@dataclass
class SqueezeSignal:
    """Squeeze signal from detector"""
    symbol: str
    timestamp: datetime
    score: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward_ratio: float
    si_pct: float
    borrow_fee_pct: float
    ftd_spike_ratio: float
    dp_buying_pressure: float


class SqueezeDetectorSimulator:
    """
    Simulates squeeze detector on historical dates.
    
    Uses the actual SqueezeDetector but runs it as if it was a historical date.
    """
    
    def __init__(self, detector, params: Optional[TradingParams] = None):
        """
        Initialize with squeeze detector instance.
        
        Args:
            detector: SqueezeDetector instance
            params: Trading parameters (optional, uses defaults)
        """
        self.detector = detector
        self.params = params or TradingParams()
    
    def generate_signals(self, symbol: str, date: datetime) -> List[SqueezeSignal]:
        """
        Generate squeeze signals for a symbol on a specific date.
        
        Args:
            symbol: Stock ticker
            date: Date to test (as if it was that date)
        
        Returns:
            List of SqueezeSignal objects (usually 0 or 1)
        """
        signals = []
        
        try:
            # Get historical price for that date
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=date.strftime('%Y-%m-%d'), 
                                 end=(date + timedelta(days=1)).strftime('%Y-%m-%d'))
            
            if hist.empty:
                return signals
            
            current_price = float(hist['Close'].iloc[-1])
            
            # Task 2: Detect regime and pass to detector
            regime = self._detect_simple_regime(symbol, date)
            
            # Run squeeze detector with historical date and regime
            signal = self.detector.analyze(symbol, current_price=current_price, date=date, regime=regime)
            
            # Signal already passed detector threshold, no need to filter again
            if signal:
                squeeze_signal = SqueezeSignal(
                    symbol=signal.symbol,
                    timestamp=date.replace(hour=9, minute=30),  # Market open
                    score=signal.score,
                    entry_price=signal.entry_price,
                    stop_price=signal.stop_price,
                    target_price=signal.target_price,
                    risk_reward_ratio=signal.risk_reward_ratio,
                    si_pct=signal.short_interest_pct,
                    borrow_fee_pct=signal.borrow_fee_pct,
                    ftd_spike_ratio=signal.ftd_spike_ratio,
                    dp_buying_pressure=signal.dp_buying_pressure
                )
                signals.append(squeeze_signal)
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating squeeze signals for {symbol} on {date.date()}: {e}")
        
        return signals
    
    def _detect_simple_regime(self, symbol: str, date: datetime) -> str:
        """Simple regime detection based on 5-day price change BEFORE test date"""
        import yfinance as yf
        from datetime import timedelta
        
        ticker = yf.Ticker(symbol)
        
        # Calculate date range: 5 days BEFORE test date
        end_date = date.date()
        start_date = end_date - timedelta(days=6)  # 6 days to get 5 days of data
        
        hist = ticker.history(start=start_date.strftime('%Y-%m-%d'), 
                             end=end_date.strftime('%Y-%m-%d'))
        
        if len(hist) < 2:
            return 'UNKNOWN'
        
        change = (hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]
        
        if change > 0.03:
            return 'STRONG_UPTREND'
        elif change > 0.01:
            return 'UPTREND'
        elif change < -0.03:
            return 'STRONG_DOWNTREND'
        elif change < -0.01:
            return 'DOWNTREND'
        else:
            return 'CHOPPY'
    
    def simulate_trade(self, signal: SqueezeSignal, intraday_data: pd.DataFrame) -> Optional[Trade]:
        """
        Simulate a trade from a squeeze signal using intraday price data.
        
        Args:
            signal: SqueezeSignal object
            intraday_data: DataFrame with minute-by-minute prices
        
        Returns:
            Trade object with outcome
        """
        if intraday_data.empty:
            return None
        
        # Just use first bar as entry - simpler and more reliable
        entry_bar = intraday_data.iloc[0]
        entry_time = intraday_data.index[0]
        
        if entry_bar is None:
            return None
        
        # Use actual entry price from bar and recalculate stops/targets
        actual_entry = float(entry_bar['Open'])
        
        # Recalculate stop/target based on actual entry (using same R/R ratio)
        # Original R/R ratio from signal
        original_risk = signal.entry_price - signal.stop_price  # Risk per share
        original_reward = signal.target_price - signal.entry_price  # Reward per share
        
        # Scale to actual entry
        if original_risk > 0:
            risk_pct = original_risk / signal.entry_price
            reward_pct = original_reward / signal.entry_price
            
            stop_price = actual_entry * (1 - risk_pct)
            target_price = actual_entry * (1 + reward_pct)
        else:
            # Fallback to fixed percentages
            stop_price = actual_entry * 0.99  # 1% stop
            target_price = actual_entry * 1.02  # 2% target
        
        # Simulate trade through the day
        exit_price = None
        exit_time = None
        exit_reason = None
        
        for idx, row in intraday_data.iterrows():
            if idx <= entry_time:
                continue
            
            high = float(row['High'])
            low = float(row['Low'])
            close = float(row['Close'])
            
            # Check for stop or target hit
            if low <= stop_price:
                exit_price = stop_price
                exit_time = idx
                exit_reason = "HIT_STOP"
                break
            elif high >= target_price:
                exit_price = target_price
                exit_time = idx
                exit_reason = "HIT_TARGET"
                break
            
            # Check end of day (4:00 PM ET)
            if idx.hour >= 16:
                exit_price = close
                exit_time = idx
                exit_reason = "END_OF_DAY"
                break
        
        if exit_price is None:
            # No exit found, use last price
            exit_price = float(intraday_data['Close'].iloc[-1])
            exit_time = intraday_data.index[-1]
            exit_reason = "END_OF_DAY"
        
        # Calculate P&L (LONG trade)
        pnl = exit_price - actual_entry
        pnl_pct = (pnl / actual_entry) * 100
        
        # Determine outcome
        if exit_reason == "HIT_TARGET":
            outcome = "WIN"
        elif exit_reason == "HIT_STOP":
            outcome = "LOSS"
        else:
            # END_OF_DAY - check if profitable
            outcome = "WIN" if pnl > 0 else "LOSS"
        
        return Trade(
            entry_time=entry_time,
            symbol=signal.symbol,
            direction="LONG",  # Squeeze signals are always LONG
            entry_price=actual_entry,
            stop_loss=stop_price,
            take_profit=target_price,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            outcome=outcome,
            alert_confluence=signal.score,  # Use score as confluence
            max_move_observed=abs(pnl_pct)  # Actual move observed
        )
    
    def simulate(self, symbols: List[str], start_date: datetime, end_date: datetime) -> List[Trade]:
        """
        Simulate squeeze detector on multiple symbols over date range.
        
        Args:
            symbols: List of symbols to test
            start_date: Start date
            end_date: End date
        
        Returns:
            List of Trade objects
        """
        all_trades = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            for symbol in symbols:
                # Generate signals for this date
                signals = self.generate_signals(symbol, current_date)
                
                for signal in signals:
                    # Get intraday data for simulation
                    try:
                        ticker = yf.Ticker(symbol)
                        
                        # yfinance 1m data is only available for last 7 days with period
                        # For "today" simulation, just use period='1d'
                        days_ago = (datetime.now().date() - current_date.date()).days
                        
                        if days_ago == 0:
                            # Today - use period='1d' for 1-minute data
                            intraday = ticker.history(period='1d', interval='1m')
                        elif days_ago <= 7:
                            # Recent days - use period approach
                            intraday = ticker.history(period=f'{days_ago + 1}d', interval='1m')
                            # Filter to target date only
                            target_date = current_date.date()
                            intraday = intraday[intraday.index.date == target_date]
                        else:
                            # Older dates - use daily data (less accurate but available)
                            intraday = ticker.history(
                                start=current_date.strftime('%Y-%m-%d'),
                                end=(current_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                                interval='1d'
                            )
                        
                        if not intraday.empty:
                            trade = self.simulate_trade(signal, intraday)
                            if trade:
                                all_trades.append(trade)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.debug(f"Could not simulate trade for {symbol} on {current_date.date()}: {e}")
            
            current_date += timedelta(days=1)
        
        return all_trades

