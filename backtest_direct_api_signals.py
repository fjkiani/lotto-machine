#!/usr/bin/env python3
"""
🔍 BACKTEST DIRECT API SIGNALS
Tests what signals would have fired today and simulates their outcomes
"""

import os
from datetime import datetime, timedelta
import yfinance as yf
from backtesting.simulation.direct_api_test import DirectAPITester
from backtesting.simulation.trade_simulator import Trade, TradeSimulator
from backtesting.analysis.performance import PerformanceAnalyzer
from backtesting.config.trading_params import TradingParams
from backtesting.reports.generator import ReportGenerator

def simulate_trade_outcome(trade: Trade, symbol: str, signal_time: datetime) -> Trade:
    """Simulate trade outcome using actual price data"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Use yesterday's data (Dec 11) since we're using Dec 11 DP levels
        # This simulates what would have happened if system ran on Dec 11
        yesterday = (signal_time - timedelta(days=1)).strftime('%Y-%m-%d')
        hist = ticker.history(start=yesterday,
                             end=signal_time.strftime('%Y-%m-%d'),
                             interval='1m')
        
        if hist.empty:
            trade.outcome = "PENDING"
            trade.pnl_pct = 0.0
            return trade
        
        # Find entry time in data (handle timezone-aware timestamps)
        entry_idx = None
        signal_time_naive = signal_time.replace(tzinfo=None) if signal_time.tzinfo else signal_time
        
        for i, timestamp in enumerate(hist.index):
            ts_naive = timestamp.replace(tzinfo=None) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo else timestamp
            if ts_naive >= signal_time_naive:
                entry_idx = i
                break
        
        if entry_idx is None:
            trade.outcome = "PENDING"
            trade.pnl_pct = 0.0
            return trade
        
        # Simulate trade
        entry_price = trade.entry_price
        stop_loss = trade.stop_loss
        take_profit = trade.take_profit
        
        max_move = 0.0
        exit_price = None
        exit_idx = None
        
        # Check next 60 minutes (1 hour max hold)
        for i in range(entry_idx, min(entry_idx + 60, len(hist))):
            high = hist['High'].iloc[i]
            low = hist['Low'].iloc[i]
            close = hist['Close'].iloc[i]
            
            if trade.direction == "LONG":
                # Check stop loss
                if low <= stop_loss:
                    exit_price = stop_loss
                    exit_idx = i
                    trade.outcome = "LOSS"
                    break
                
                # Check take profit
                if high >= take_profit:
                    exit_price = take_profit
                    exit_idx = i
                    trade.outcome = "WIN"
                    break
                
                # Track max move
                move_pct = ((close - entry_price) / entry_price) * 100
                max_move = max(max_move, move_pct)
            
            else:  # SHORT
                # Check stop loss
                if high >= stop_loss:
                    exit_price = stop_loss
                    exit_idx = i
                    trade.outcome = "LOSS"
                    break
                
                # Check take profit
                if low <= take_profit:
                    exit_price = take_profit
                    exit_idx = i
                    trade.outcome = "WIN"
                    break
                
                # Track max move
                move_pct = ((entry_price - close) / entry_price) * 100
                max_move = max(max_move, move_pct)
        
        # If no exit, use end of hour price
        if exit_price is None:
            exit_price = hist['Close'].iloc[min(entry_idx + 60, len(hist) - 1)]
            exit_idx = min(entry_idx + 60, len(hist) - 1)
            
            if trade.direction == "LONG":
                move_pct = ((exit_price - entry_price) / entry_price) * 100
            else:
                move_pct = ((entry_price - exit_price) / entry_price) * 100
            
            if move_pct > 0:
                trade.outcome = "WIN"
            elif move_pct < 0:
                trade.outcome = "LOSS"
            else:
                trade.outcome = "PENDING"
        
        # Calculate P&L
        if trade.direction == "LONG":
            trade.pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        else:
            trade.pnl_pct = ((entry_price - exit_price) / entry_price) * 100
        
        trade.exit_price = exit_price
        trade.exit_time = hist.index[exit_idx] if exit_idx else None
        trade.max_move_observed = max_move
        
    except Exception as e:
        print(f"⚠️  Error simulating {symbol}: {e}")
        trade.outcome = "PENDING"
        trade.pnl_pct = 0.0
    
    return trade

def main():
    print("=" * 80)
    print("🔍 BACKTESTING DIRECT API SIGNALS - TODAY")
    print("=" * 80)
    print()
    
    # Initialize tester
    tester = DirectAPITester()
    
    # Get signals
    signals = tester.test_today(['SPY', 'QQQ'])
    
    if not signals:
        print("❌ No signals generated")
        return
    
    print(f"\n📊 Simulating {len(signals)} signals...")
    print("=" * 80)
    
    # Convert to trades
    trades = []
    params = TradingParams()
    
    for signal in signals:
        trade = Trade(
            entry_time=signal.timestamp,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=signal.entry or signal.price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            exit_time=None,
            exit_price=None,
            pnl_pct=0.0,
            outcome="PENDING",
            alert_confluence=signal.confidence,
            max_move_observed=0.0
        )
        
        # Simulate outcome
        trade = simulate_trade_outcome(trade, signal.symbol, signal.timestamp)
        trades.append(trade)
    
    # Analyze
    analyzer = PerformanceAnalyzer()
    metrics = analyzer.analyze(trades)
    
    # Report
    print("\n📊 BACKTEST RESULTS:")
    print("-" * 80)
    print(f"  Total Trades: {metrics.total_trades}")
    print(f"  Wins: {metrics.winning_trades}")
    print(f"  Losses: {metrics.losing_trades}")
    print(f"  Win Rate: {metrics.win_rate:.1f}%")
    print(f"  Total P&L: {metrics.total_pnl:.2f}%")
    print(f"  Avg P&L per Trade: {metrics.avg_pnl_per_trade:.2f}%")
    print(f"  Profit Factor: {metrics.profit_factor:.2f}")
    print()
    
    print("📈 TRADE BREAKDOWN:")
    print("-" * 80)
    for i, trade in enumerate(trades, 1):
        outcome_icon = "✅" if trade.outcome == "WIN" else "❌" if trade.outcome == "LOSS" else "⏳"
        exit_str = f"${trade.exit_price:.2f}" if trade.exit_price else "N/A"
        print(f"  {i:2d}. {outcome_icon} {trade.symbol} {trade.direction:<6} @ ${trade.entry_price:.2f} | "
              f"Exit: {exit_str} | "
              f"P&L: {trade.pnl_pct:+.2f}% | {trade.outcome}")
    
    print("\n" + "=" * 80)
    print("💡 These are signals that WOULD have fired if system was running today")
    print("=" * 80)
    
    # Create simple report
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append(f"BACKTEST RESULTS: {datetime.now().strftime('%Y-%m-%d')}")
    report_lines.append("=" * 80)
    report_lines.append("")
    report_lines.append(f"Total Trades: {metrics.total_trades}")
    report_lines.append(f"Win Rate: {metrics.win_rate:.1f}%")
    report_lines.append(f"Total P&L: {metrics.total_pnl:.2f}%")
    report_lines.append("")
    report_lines.append("Trades:")
    for i, trade in enumerate(trades, 1):
        outcome_icon = "✅" if trade.outcome == "WIN" else "❌" if trade.outcome == "LOSS" else "⏳"
        exit_str = f"${trade.exit_price:.2f}" if trade.exit_price else "N/A"
        report_lines.append(f"  {i}. {outcome_icon} {trade.symbol} {trade.direction} @ ${trade.entry_price:.2f} | "
                           f"Exit: {exit_str} | P&L: {trade.pnl_pct:+.2f}%")
    report = "\n".join(report_lines)
    
    output_file = f"backtesting/reports/direct_api_backtest_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"\n💾 Report saved to: {output_file}")

if __name__ == '__main__':
    main()

