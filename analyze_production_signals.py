#!/usr/bin/env python3
"""
🎯 PRODUCTION SIGNAL ANALYZER
Analyzes what signals fired in production using the backtesting framework

Usage:
    python3 analyze_production_signals.py                    # Today
    python3 analyze_production_signals.py --date 2025-12-11  # Specific date
    python3 analyze_production_signals.py --date-range 2025-12-10 2025-12-11  # Range
    python3 analyze_production_signals.py --session 2025-12-11 09:30 16:00   # Session
"""

import argparse
from datetime import datetime
from backtesting.data.alerts_loader import AlertsLoader
from backtesting.analysis.signal_analyzer import SignalAnalyzer
from backtesting.reports.signal_report import SignalReportGenerator

def main():
    parser = argparse.ArgumentParser(description='Analyze production signals')
    parser.add_argument('--date', type=str, help='Date to analyze (YYYY-MM-DD). Default: today')
    parser.add_argument('--date-range', nargs=2, metavar=('START', 'END'), 
                       help='Date range to analyze (YYYY-MM-DD YYYY-MM-DD)')
    parser.add_argument('--session', nargs=3, metavar=('DATE', 'START', 'END'),
                       help='Trading session (YYYY-MM-DD HH:MM HH:MM)')
    parser.add_argument('--key-only', action='store_true',
                       help='Show only key signals (synthesis, narrative brain, high confluence)')
    parser.add_argument('--tradeable-only', action='store_true',
                       help='Show only tradeable signals (complete setup)')
    
    args = parser.parse_args()
    
    # Load data
    loader = AlertsLoader()
    
    if args.session:
        date, start_time, end_time = args.session
        signals = loader.load_session(date, start_time, end_time)
        date_label = f"{date} {start_time}-{end_time}"
    elif args.date_range:
        start_date, end_date = args.date_range
        signals = loader.load_date_range(start_date, end_date)
        date_label = f"{start_date} to {end_date}"
    elif args.date:
        signals = loader.load_date(args.date)
        date_label = args.date
    else:
        # Default: today
        signals = loader.load_today()
        date_label = datetime.now().strftime('%Y-%m-%d')
    
    if not signals:
        print(f"❌ No signals found for {date_label}")
        return
    
    # Analyze
    analyzer = SignalAnalyzer()
    summary = analyzer.analyze_signals(signals, date_label)
    
    # Filter if requested
    if args.key_only:
        key_signals = analyzer.get_key_signals(signals)
        summary = analyzer.analyze_signals(key_signals, date_label)
    elif args.tradeable_only:
        tradeable = analyzer.get_tradeable_signals(signals)
        summary = analyzer.analyze_signals(tradeable, date_label)
    
    # Generate report
    report_gen = SignalReportGenerator()
    report = report_gen.generate_report(summary)
    
    print(report)
    
    # Save to file
    output_file = f"backtesting/reports/signal_analysis_{date_label.replace(' ', '_').replace(':', '')}.txt"
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"\n💾 Report saved to: {output_file}")

if __name__ == '__main__':
    main()


