#!/usr/bin/env python3
"""
🔍 DIRECT API SIGNAL TEST
Bypasses deployment and tests what signals would fire TODAY

Usage:
    python3 test_direct_api_signals.py
"""

import os
from datetime import datetime
from backtesting.simulation.direct_api_test import DirectAPITester
from backtesting.simulation.trade_simulator import TradeSimulator
from backtesting.analysis.performance import PerformanceAnalyzer
from backtesting.config.trading_params import TradingParams
from backtesting.reports.generator import ReportGenerator

def main():
    print("=" * 80)
    print("🔍 DIRECT API SIGNAL TEST - TODAY")
    print("=" * 80)
    print()
    
    # Initialize tester
    tester = DirectAPITester()
    
    # Test today's APIs
    signals = tester.test_today(['SPY', 'QQQ'])
    
    if not signals:
        print("\n❌ No signals generated")
        print("   → Check API keys, data availability, or thresholds")
        return
    
    print("\n" + "=" * 80)
    print(f"📊 GENERATED {len(signals)} SIGNALS")
    print("=" * 80)
    
    # Convert to trade format for backtesting
    from backtesting.simulation.trade_simulator import Trade
    from datetime import datetime
    
    trades = []
    params = TradingParams()
    trade_sim = TradeSimulator(params)
    
    for signal in signals:
        # Simulate trade (match Trade dataclass fields)
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
        
        trades.append(trade)
    
    # Analyze
    analyzer = PerformanceAnalyzer()
    metrics = analyzer.analyze(trades)
    
    # Report
    print("\n📊 SIGNAL SUMMARY:")
    print("-" * 80)
    print(f"  Total Signals: {len(signals)}")
    print(f"  SPY Signals: {len([s for s in signals if s.symbol == 'SPY'])}")
    print(f"  QQQ Signals: {len([s for s in signals if s.symbol == 'QQQ'])}")
    print(f"  Avg Confidence: {sum(s.confidence for s in signals) / len(signals):.1f}%")
    print()
    
    print("🎯 TOP SIGNALS:")
    print("-" * 80)
    sorted_signals = sorted(signals, key=lambda x: x.confidence, reverse=True)
    for i, signal in enumerate(sorted_signals[:10], 1):
        entry_str = f"${signal.entry:.2f}" if signal.entry else f"${signal.price:.2f}"
        stop_str = f"${signal.stop_loss:.2f}" if signal.stop_loss else "N/A"
        target_str = f"${signal.take_profit:.2f}" if signal.take_profit else "N/A"
        
        print(f"  {i:2d}. {signal.symbol} {signal.direction:<6} @ {entry_str:<8} | "
              f"Stop: {stop_str:<8} | Target: {target_str:<8} | "
              f"{signal.confidence:.0f}% | {signal.signal_type}")
    
    print("\n" + "=" * 80)
    print("💡 NOTE: These are signals that WOULD have fired if system was running")
    print("   → Actual outcomes require price data for backtesting")
    print("=" * 80)
    
    # Save to file
    output_file = f"backtesting/reports/direct_api_signals_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write(f"DIRECT API SIGNAL TEST - {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total Signals: {len(signals)}\n\n")
        for signal in sorted_signals:
            f.write(f"{signal.symbol} {signal.direction} @ ${signal.entry or signal.price:.2f} | "
                   f"{signal.confidence:.0f}% | {signal.signal_type}\n")
            f.write(f"  {signal.reasoning}\n\n")
    
    print(f"\n💾 Report saved to: {output_file}")

if __name__ == '__main__':
    main()

