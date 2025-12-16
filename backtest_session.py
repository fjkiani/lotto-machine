#!/usr/bin/env python3
"""
🎯 SESSION BACKTEST
Easy-to-use backtest script using the modular framework

Usage:
    python3 backtest_session.py --date 2025-12-05
    python3 backtest_session.py --date 2025-12-05 --start-time 09:30 --end-time 16:00
    python3 backtest_session.py --date-range 2025-12-01 2025-12-05
"""

import argparse
import sys
from backtesting import (
    DataLoader,
    TradeSimulator,
    CurrentSystemSimulator,
    NarrativeBrainSimulator,
    PerformanceAnalyzer,
    ReportGenerator,
    TradingParams
)

def main():
    parser = argparse.ArgumentParser(description='Backtest DP alert systems')
    parser.add_argument('--date', type=str, help='Date to backtest (YYYY-MM-DD)')
    parser.add_argument('--date-range', nargs=2, metavar=('START', 'END'), 
                       help='Date range to backtest (YYYY-MM-DD YYYY-MM-DD)')
    parser.add_argument('--start-time', type=str, default='09:30', 
                       help='Session start time (HH:MM)')
    parser.add_argument('--end-time', type=str, default='16:00',
                       help='Session end time (HH:MM)')
    parser.add_argument('--stop-loss', type=float, default=0.25,
                       help='Stop loss percentage')
    parser.add_argument('--take-profit', type=float, default=0.40,
                       help='Take profit percentage')
    parser.add_argument('--narrative-threshold', type=float, default=70.0,
                       help='Narrative Brain minimum confluence')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.date and not args.date_range:
        parser.error("Must specify either --date or --date-range")
    
    # Create configuration
    params = TradingParams(
        stop_loss_pct=args.stop_loss,
        take_profit_pct=args.take_profit,
        narrative_min_confluence=args.narrative_threshold
    )
    
    # Load data
    loader = DataLoader()
    if args.date:
        alerts = loader.load_session(args.date, args.start_time, args.end_time)
        date_label = args.date
    else:
        alerts = loader.load_date_range(args.date_range[0], args.date_range[1])
        date_label = f"{args.date_range[0]} to {args.date_range[1]}"
    
    if not alerts:
        print(f"❌ No alerts found for {date_label}")
        return 1
    
    print(f"📊 Loaded {len(alerts)} alerts for {date_label}")
    print()
    
    # Initialize simulators
    trade_simulator = TradeSimulator(params)
    current_simulator = CurrentSystemSimulator(trade_simulator, params)
    narrative_simulator = NarrativeBrainSimulator(trade_simulator, params)
    
    # Run simulations
    print("🧪 Running simulations...")
    current_trades = current_simulator.simulate(alerts)
    narrative_trades = narrative_simulator.simulate(alerts)
    
    # Analyze performance
    analyzer = PerformanceAnalyzer()
    current_metrics = analyzer.analyze(current_trades)
    narrative_metrics = analyzer.analyze(narrative_trades)
    comparison = analyzer.compare(current_metrics, narrative_metrics)
    
    # Generate report
    report = ReportGenerator.generate_report(
        date=date_label,
        current_metrics=current_metrics,
        narrative_metrics=narrative_metrics,
        comparison=comparison
    )
    
    print(report)
    print()
    
    # Trade details
    if current_trades:
        print("📋 CURRENT SYSTEM TRADES:")
        print(ReportGenerator.generate_trade_details(current_trades))
        print()
    
    if narrative_trades:
        print("📋 NARRATIVE BRAIN TRADES:")
        print(ReportGenerator.generate_trade_details(narrative_trades))
        print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())



