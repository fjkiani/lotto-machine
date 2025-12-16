#!/usr/bin/env python3
"""
🏥 PRODUCTION HEALTH CHECK
Checks system health for a date and prevents Dec 11 issues

Usage:
    python3 check_production_health.py                    # Today
    python3 check_production_health.py --date 2025-12-11  # Specific date
"""

import argparse
from datetime import datetime
from backtesting.analysis.production_health import ProductionHealthMonitor
from backtesting.reports.health_report import HealthReportGenerator

def main():
    parser = argparse.ArgumentParser(description='Check production system health')
    parser.add_argument('--date', type=str, help='Date to check (YYYY-MM-DD). Default: today')
    
    args = parser.parse_args()
    
    date = args.date or datetime.now().strftime('%Y-%m-%d')
    
    print(f"🏥 Checking production health for {date}...")
    print()
    
    monitor = ProductionHealthMonitor()
    status = monitor.check_health(date)
    report = HealthReportGenerator.generate_report(date, status)
    
    print(report)
    
    # Save report
    output_file = f"backtesting/reports/health_{date}.txt"
    with open(output_file, 'w') as f:
        f.write(report)
    
    print(f"\n💾 Report saved to: {output_file}")
    
    # Exit with error code if unhealthy
    if not status.is_healthy:
        exit(1)

if __name__ == '__main__':
    main()


