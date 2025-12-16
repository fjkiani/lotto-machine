"""
🎲 GAMMA DETECTOR SIMULATOR
Simulates gamma tracker signals and trades
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
import yfinance as yf
import pandas as pd

from ..simulation.trade_simulator import Trade
from ..config.trading_params import TradingParams


@dataclass
class GammaBacktestSignal:
    """Gamma signal from detector for backtesting"""
    symbol: str
    timestamp: datetime
    direction: str  # UP, DOWN
    score: float
    put_call_ratio: float
    max_pain: float
    max_pain_distance_pct: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward_ratio: float
    expiration: str


class GammaDetectorSimulator:
    """
    Simulates gamma tracker on historical dates.
    
    Uses the actual GammaTracker but runs it as if it was a historical date.
    """
    
    def __init__(self, detector, params: Optional[TradingParams] = None):
        """
        Initialize with gamma tracker instance.
        
        Args:
            detector: GammaTracker instance
            params: Trading parameters (optional, uses defaults)
        """
        self.detector = detector
        self.params = params or TradingParams()
    
    def generate_signals(self, symbol: str, date: datetime) -> List[GammaBacktestSignal]:
        """
        Generate gamma signals for a symbol on a specific date.
        
        ⚠️ LIMITATION: yfinance options data is only available for CURRENT expirations.
        For historical dates, we use TODAY's options data as a proxy (not ideal but best available).
        This means backtesting gamma signals is most accurate for recent dates.
        
        Args:
            symbol: Stock ticker
            date: Date to test (as if it was that date)
        
        Returns:
            List of GammaBacktestSignal objects (usually 0 or 1)
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
            
            # Get current options expirations (yfinance doesn't provide historical options)
            expirations = ticker.options
            if not expirations:
                return signals
            
            # Detect regime for filtering (Task 7)
            regime = self._detect_simple_regime(symbol, date)
            
            # Try multiple expirations, starting from index 3 (skip 0-2 as they often have 0 OI)
            # Check up to index 10 to find one with valid OI
            for exp_idx in range(3, min(11, len(expirations))):
                try:
                    signal = self.detector.analyze(symbol, current_price=current_price, expiration_idx=exp_idx, regime=regime)
                    
                    if signal:
                        backtest_signal = GammaBacktestSignal(
                            symbol=signal.symbol,
                            timestamp=date.replace(hour=9, minute=30),  # Market open
                            direction=signal.direction,
                            score=signal.score,
                            put_call_ratio=signal.put_call_ratio,
                            max_pain=signal.max_pain,
                            max_pain_distance_pct=signal.max_pain_distance_pct,
                            entry_price=signal.entry_price,
                            stop_price=signal.stop_price,
                            target_price=signal.target_price,
                            risk_reward_ratio=signal.risk_reward_ratio,
                            expiration=signal.expiration
                        )
                        signals.append(backtest_signal)
                        break  # One signal per symbol per day
                except (IndexError, AttributeError, ValueError) as e:
                    # Skip if expiration doesn't exist, has no OI, or other error
                    continue
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating gamma signals for {symbol} on {date.date()}: {e}")
        
        return signals
    
    def simulate_trade(self, signal: GammaBacktestSignal, intraday_data: pd.DataFrame) -> Optional[Trade]:
        """
        Simulate a trade from a gamma signal using intraday price data.
        
        Args:
            signal: GammaBacktestSignal object
            intraday_data: DataFrame with minute-by-minute prices
            
        Returns:
            Trade object with outcome
        """
        if intraday_data.empty:
            return None
        
        # Use first bar as entry
        entry_bar = intraday_data.iloc[0]
        entry_time = intraday_data.index[0]
        
        if entry_bar is None:
            return None
        
        # Use actual entry price from bar
        actual_entry = float(entry_bar['Open'])
        
        # Recalculate stop/target based on actual entry (using same R/R ratio)
        original_risk = abs(signal.entry_price - signal.stop_price)
        original_reward = abs(signal.target_price - signal.entry_price)
        
        # Scale to actual entry
        if original_risk > 0:
            risk_pct = original_risk / signal.entry_price
            reward_pct = original_reward / signal.entry_price
            
            if signal.direction == 'UP':
                # LONG trade
                stop_price = actual_entry * (1 - risk_pct)
                target_price = actual_entry * (1 + reward_pct)
                direction = 'LONG'
            else:
                # SHORT trade
                stop_price = actual_entry * (1 + risk_pct)
                target_price = actual_entry * (1 - reward_pct)
                direction = 'SHORT'
        else:
            # Fallback
            if signal.direction == 'UP':
                stop_price = actual_entry * 0.995  # 0.5% stop
                target_price = actual_entry * 1.02  # 2% target
                direction = 'LONG'
            else:
                stop_price = actual_entry * 1.005  # 0.5% stop
                target_price = actual_entry * 0.98  # 2% target
                direction = 'SHORT'
        
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
            if direction == 'LONG':
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
            else:  # SHORT
                if high >= stop_price:
                    exit_price = stop_price
                    exit_time = idx
                    exit_reason = "HIT_STOP"
                    break
                elif low <= target_price:
                    exit_price = target_price
                    exit_time = idx
                    exit_reason = "HIT_TARGET"
                    break
        
        # If no exit, use end of day close
        if exit_price is None:
            exit_price = float(intraday_data.iloc[-1]['Close'])
            exit_time = intraday_data.index[-1]
            exit_reason = "END_OF_DAY"
        
        # Calculate P&L
        if direction == 'LONG':
            pnl_pct = ((exit_price - actual_entry) / actual_entry) * 100
        else:
            pnl_pct = ((actual_entry - exit_price) / actual_entry) * 100
        
        # Determine outcome
        if exit_reason == "HIT_TARGET":
            outcome = "WIN"
        elif exit_reason == "HIT_STOP":
            outcome = "LOSS"
        else:
            # End of day - check if profitable
            outcome = "WIN" if pnl_pct > 0 else "LOSS"
        
        return Trade(
            entry_time=entry_time,
            symbol=signal.symbol,
            direction=direction,
            entry_price=actual_entry,
            stop_loss=stop_price,
            take_profit=target_price,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            outcome=outcome,
            alert_confluence=signal.score,  # Use score as confluence
            max_move_observed=abs(pnl_pct)
        )
    
    def simulate(self, symbols: List[str], start_date: datetime, end_date: datetime) -> List[Trade]:
        """
        Simulate gamma tracker on multiple symbols over date range.
        
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

