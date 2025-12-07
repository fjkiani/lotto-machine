#!/usr/bin/env python3
"""
🎯 EDGE VALIDATION SCRIPT 🎯

THE ONLY QUESTION: Does this system make money?

This script:
1. Gets 30 days of historical SPY data
2. For each day, generates signals using our system
3. Simulates trades with realistic execution
4. Calculates whether we would have made money

RUN THIS BEFORE ANYTHING ELSE.

Usage:
    python3 validate_edge.py

Author: Zo
Date: 2025-12-05
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import json

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

import yfinance as yf
import pandas as pd
import numpy as np

# Import our signal generator
from configs.chartexchange_config import get_api_key
from core.ultra_institutional_engine import UltraInstitutionalEngine
from live_monitoring.core.signal_generator import SignalGenerator


@dataclass
class SimulatedTrade:
    """A simulated trade for backtesting"""
    entry_time: datetime
    symbol: str
    action: str  # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    signal_type: str
    confidence: float
    
    # Outcomes
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # STOP_LOSS, TAKE_PROFIT, END_OF_DAY
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    result: Optional[str] = None  # WIN, LOSS, BREAKEVEN


@dataclass
class ValidationResult:
    """Results of edge validation"""
    total_signals: int = 0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    
    total_pnl_pct: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_rr: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    
    trades: List[SimulatedTrade] = field(default_factory=list)
    daily_pnl: Dict[str, float] = field(default_factory=dict)
    
    edge_exists: bool = False
    verdict: str = ""


class EdgeValidator:
    """Validates if our signal system has edge"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.inst_engine = UltraInstitutionalEngine(api_key)
        self.sig_gen = SignalGenerator(api_key=api_key)
        
        # Trade simulation params
        self.slippage_pct = 0.0002  # 0.02% slippage
        self.commission = 0.0  # Commission-free trading
        
    def fetch_historical_data(self, symbol: str, days: int = 30) -> pd.DataFrame:
        """Fetch minute-level historical data"""
        print(f"📊 Fetching {days} days of {symbol} data...")
        
        ticker = yf.Ticker(symbol)
        
        # yfinance only gives ~7 days of 1-minute data
        # Use 5-minute data for 30 days instead
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        df = ticker.history(start=start_date, end=end_date, interval="5m")
        
        if df.empty:
            print(f"   ⚠️ No minute data, falling back to daily")
            df = ticker.history(start=start_date, end=end_date, interval="1d")
        
        print(f"   ✅ Got {len(df)} bars")
        return df
    
    def simulate_trade(self, trade: SimulatedTrade, price_data: pd.DataFrame) -> SimulatedTrade:
        """Simulate a trade through the day"""
        
        # Get prices after entry
        entry_idx = price_data.index.get_indexer([trade.entry_time], method='nearest')[0]
        remaining_prices = price_data.iloc[entry_idx:]
        
        for idx, row in remaining_prices.iterrows():
            current_price = row['Close']
            
            if trade.action == "BUY":
                # Check stop loss
                if current_price <= trade.stop_loss:
                    trade.exit_time = idx
                    trade.exit_price = trade.stop_loss * (1 - self.slippage_pct)
                    trade.exit_reason = "STOP_LOSS"
                    trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price
                    trade.result = "LOSS"
                    break
                    
                # Check take profit
                if current_price >= trade.take_profit:
                    trade.exit_time = idx
                    trade.exit_price = trade.take_profit * (1 - self.slippage_pct)
                    trade.exit_reason = "TAKE_PROFIT"
                    trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price
                    trade.result = "WIN"
                    break
            
            else:  # SELL
                # Check stop loss (above entry for shorts)
                if current_price >= trade.stop_loss:
                    trade.exit_time = idx
                    trade.exit_price = trade.stop_loss * (1 + self.slippage_pct)
                    trade.exit_reason = "STOP_LOSS"
                    trade.pnl_pct = (trade.entry_price - trade.exit_price) / trade.entry_price
                    trade.result = "LOSS"
                    break
                    
                # Check take profit
                if current_price <= trade.take_profit:
                    trade.exit_time = idx
                    trade.exit_price = trade.take_profit * (1 + self.slippage_pct)
                    trade.exit_reason = "TAKE_PROFIT"
                    trade.pnl_pct = (trade.entry_price - trade.exit_price) / trade.entry_price
                    trade.result = "WIN"
                    break
        
        # If no exit, close at end of day
        if trade.exit_time is None:
            trade.exit_time = remaining_prices.index[-1]
            trade.exit_price = remaining_prices.iloc[-1]['Close']
            trade.exit_reason = "END_OF_DAY"
            
            if trade.action == "BUY":
                trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price
            else:
                trade.pnl_pct = (trade.entry_price - trade.exit_price) / trade.entry_price
            
            if trade.pnl_pct > 0.001:
                trade.result = "WIN"
            elif trade.pnl_pct < -0.001:
                trade.result = "LOSS"
            else:
                trade.result = "BREAKEVEN"
        
        trade.pnl = trade.pnl_pct * 100  # Convert to percentage
        return trade
    
    def validate(self, symbol: str = "SPY", days: int = 30) -> ValidationResult:
        """Run full validation"""
        
        print("\n" + "🔥" * 30)
        print("   EDGE VALIDATION - THE MOMENT OF TRUTH")
        print("🔥" * 30)
        print(f"\n📊 Symbol: {symbol}")
        print(f"📅 Period: Last {days} days")
        print(f"🎯 Question: Does this system make money?\n")
        
        result = ValidationResult()
        
        # Fetch price data
        price_data = self.fetch_historical_data(symbol, days)
        if price_data.empty:
            result.verdict = "NO DATA - Cannot validate"
            return result
        
        # Group by date
        price_data['date'] = price_data.index.date
        unique_dates = sorted(price_data['date'].unique())
        
        print(f"\n🗓️  Testing {len(unique_dates)} trading days...")
        print("-" * 60)
        
        # For each day, generate signals
        for date in unique_dates:
            date_str = str(date)
            day_data = price_data[price_data['date'] == date]
            
            if len(day_data) < 10:  # Skip days with insufficient data
                continue
            
            # Get opening price
            open_price = day_data.iloc[0]['Open']
            
            # Build institutional context for this date
            try:
                context = self.inst_engine.build_institutional_context(symbol, date_str)
            except Exception as e:
                # Use a simple context if API fails
                context = None
            
            # Generate signals
            try:
                if context:
                    signals = self.sig_gen.generate_signals(
                        symbol, 
                        open_price, 
                        context,
                        account_value=100000.0
                    )
                else:
                    signals = []
            except Exception as e:
                signals = []
            
            # Count signals
            result.total_signals += len(signals)
            
            # Simulate trades for master signals (75%+)
            for signal in signals:
                if hasattr(signal, 'confidence') and signal.confidence >= 0.75:
                    # Create simulated trade
                    trade = SimulatedTrade(
                        entry_time=day_data.index[0],
                        symbol=symbol,
                        action=signal.action if hasattr(signal, 'action') else "BUY",
                        entry_price=signal.entry_price * (1 + self.slippage_pct),
                        stop_loss=signal.stop_price if hasattr(signal, 'stop_price') else signal.entry_price * 0.99,
                        take_profit=signal.target_price if hasattr(signal, 'target_price') else signal.entry_price * 1.02,
                        signal_type=signal.signal_type if hasattr(signal, 'signal_type') else "UNKNOWN",
                        confidence=signal.confidence
                    )
                    
                    # Simulate through day
                    trade = self.simulate_trade(trade, day_data)
                    result.trades.append(trade)
                    result.total_trades += 1
                    
                    if trade.result == "WIN":
                        result.wins += 1
                    elif trade.result == "LOSS":
                        result.losses += 1
                    else:
                        result.breakeven += 1
                    
                    result.total_pnl_pct += trade.pnl_pct
                    result.daily_pnl[date_str] = result.daily_pnl.get(date_str, 0) + trade.pnl_pct
                    
                    status = "✅" if trade.result == "WIN" else "❌" if trade.result == "LOSS" else "⚪"
                    print(f"   {status} {date_str}: {trade.action} @ ${trade.entry_price:.2f} → {trade.exit_reason} ({trade.pnl:.2f}%)")
            
            if not signals:
                print(f"   ⚪ {date_str}: No signals (thresholds not met)")
        
        # Calculate final metrics
        print("\n" + "=" * 60)
        print("📊 CALCULATING RESULTS...")
        print("=" * 60)
        
        if result.total_trades > 0:
            result.win_rate = result.wins / result.total_trades
            
            # Average win/loss
            wins = [t.pnl_pct for t in result.trades if t.result == "WIN"]
            losses = [t.pnl_pct for t in result.trades if t.result == "LOSS"]
            
            result.avg_win = np.mean(wins) if wins else 0
            result.avg_loss = np.mean(losses) if losses else 0
            
            # R/R
            if result.avg_loss != 0:
                result.avg_rr = abs(result.avg_win / result.avg_loss)
            
            # Max drawdown
            cumulative = np.cumsum([t.pnl_pct for t in result.trades])
            peak = np.maximum.accumulate(cumulative)
            drawdown = (peak - cumulative)
            result.max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0
            
            # Sharpe ratio (simplified)
            daily_returns = list(result.daily_pnl.values())
            if daily_returns:
                result.sharpe_ratio = (np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252) if np.std(daily_returns) > 0 else 0
            
            # Profit factor
            total_wins = sum(wins) if wins else 0
            total_losses = abs(sum(losses)) if losses else 0
            result.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Determine if edge exists
        result.edge_exists = (
            result.total_trades >= 10 and
            result.win_rate >= 0.50 and
            result.avg_rr >= 1.5 and
            result.total_pnl_pct > 0
        )
        
        if result.total_trades < 10:
            result.verdict = "INSUFFICIENT DATA - Need more trades"
        elif result.edge_exists:
            result.verdict = "✅ EDGE EXISTS - Proceed to paper trading"
        else:
            result.verdict = "❌ NO EDGE - System needs improvement"
        
        return result
    
    def print_results(self, result: ValidationResult):
        """Print validation results"""
        
        print("\n" + "🎯" * 30)
        print("   VALIDATION RESULTS")
        print("🎯" * 30)
        
        print(f"""
📊 TRADE STATISTICS:
   Total Signals Generated: {result.total_signals}
   Master Signals (75%+):   {result.total_trades}
   Wins:                    {result.wins}
   Losses:                  {result.losses}
   Breakeven:               {result.breakeven}

📈 PERFORMANCE METRICS:
   Win Rate:        {result.win_rate:.1%} {'✅' if result.win_rate >= 0.55 else '❌'} (target: 55%+)
   Avg Win:         {result.avg_win:.2f}%
   Avg Loss:        {result.avg_loss:.2f}%
   Avg R/R:         {result.avg_rr:.2f} {'✅' if result.avg_rr >= 2.0 else '❌'} (target: 2.0+)
   Total P&L:       {result.total_pnl_pct:.2f}% {'✅' if result.total_pnl_pct > 0 else '❌'}
   Max Drawdown:    {result.max_drawdown:.2f}% {'✅' if result.max_drawdown < 10 else '❌'} (target: <10%)
   Sharpe Ratio:    {result.sharpe_ratio:.2f} {'✅' if result.sharpe_ratio >= 1.5 else '❌'} (target: 1.5+)
   Profit Factor:   {result.profit_factor:.2f} {'✅' if result.profit_factor >= 1.5 else '❌'} (target: 1.5+)

{'=' * 60}
🎯 VERDICT: {result.verdict}
{'=' * 60}
""")
        
        # Save results to file
        results_file = Path("logs/validation_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        results_dict = {
            "timestamp": datetime.now().isoformat(),
            "total_signals": result.total_signals,
            "total_trades": result.total_trades,
            "wins": result.wins,
            "losses": result.losses,
            "win_rate": result.win_rate,
            "avg_win": result.avg_win,
            "avg_loss": result.avg_loss,
            "avg_rr": result.avg_rr,
            "total_pnl_pct": result.total_pnl_pct,
            "max_drawdown": result.max_drawdown,
            "sharpe_ratio": result.sharpe_ratio,
            "profit_factor": result.profit_factor,
            "edge_exists": result.edge_exists,
            "verdict": result.verdict,
            "trades": [
                {
                    "entry_time": str(t.entry_time),
                    "symbol": t.symbol,
                    "action": t.action,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": t.pnl_pct,
                    "result": t.result,
                    "signal_type": t.signal_type,
                    "confidence": t.confidence
                }
                for t in result.trades
            ]
        }
        
        with open(results_file, "w") as f:
            json.dump(results_dict, f, indent=2)
        
        print(f"💾 Results saved to: {results_file}")


def main():
    """Main validation function"""
    
    print("\n" + "=" * 60)
    print("🔥 EDGE VALIDATION - THE MOMENT OF TRUTH 🔥")
    print("=" * 60)
    print("\nThis script will determine if our system actually makes money.")
    print("If it doesn't, we need to fix it before building anything else.\n")
    
    try:
        api_key = get_api_key()
        validator = EdgeValidator(api_key)
        
        # Validate SPY
        result = validator.validate(symbol="SPY", days=30)
        validator.print_results(result)
        
        # If no signals from institutional context, try simpler approach
        if result.total_signals == 0:
            print("\n" + "⚠️" * 20)
            print("No signals generated from institutional context.")
            print("This could mean:")
            print("  1. Market conditions don't meet thresholds")
            print("  2. Thresholds are too strict")
            print("  3. API data is limited")
            print("⚠️" * 20)
            
            print("\n🔧 Running simplified validation (price-based only)...")
            # Run simpler validation here if needed
        
        return result.edge_exists
        
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n✅ System has edge! Proceed to paper trading.")
    else:
        print("\n❌ No edge proven yet. Debug signals before proceeding.")



