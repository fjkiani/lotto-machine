#!/usr/bin/env python3
"""
🔍 PRODUCTION DIAGNOSTICS
Diagnoses why signals did/didn't fire using the backtesting framework

Usage:
    python3 diagnose_production.py                    # Today
    python3 diagnose_production.py --date 2025-12-11  # Specific date
    python3 diagnose_production.py --date-range 2025-12-10 2025-12-11  # Range
"""

import argparse
from datetime import datetime
from backtesting.analysis.diagnostics import ProductionDiagnostics
from backtesting.reports.diagnostic_report import DiagnosticReportGenerator

def main():
    parser = argparse.ArgumentParser(description='Diagnose production signal generation')
    parser.add_argument('--date', type=str, help='Date to diagnose (YYYY-MM-DD). Default: today')
    parser.add_argument('--date-range', nargs=2, metavar=('START', 'END'),
                       help='Date range to diagnose (YYYY-MM-DD YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    diagnostics = ProductionDiagnostics()
    report_gen = DiagnosticReportGenerator()
    
    if args.date_range:
        start_date, end_date = args.date_range
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            print(f"\n{'='*80}")
            print(f"Diagnosing {date_str}...")
            print('='*80)
            
            result = diagnostics.diagnose_date(date_str)
            report = report_gen.generate_report(result)
            print(report)
            
            # Save report
            output_file = f"backtesting/reports/diagnostic_{date_str}.txt"
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"\n💾 Report saved to: {output_file}")
            
            from datetime import timedelta
            current += timedelta(days=1)
    
    else:
        date = args.date or datetime.now().strftime('%Y-%m-%d')
        
        print(f"🔍 Diagnosing {date}...")
        print()
        
        result = diagnostics.diagnose_date(date)
        report = report_gen.generate_report(result)
        
        print(report)
        
        # Save report
        output_file = f"backtesting/reports/diagnostic_{date}.txt"
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"\n💾 Report saved to: {output_file}")

if __name__ == '__main__':
    main()

