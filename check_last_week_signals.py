#!/usr/bin/env python3
"""
Check what signals were generated last week
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Check backtest results
print("=" * 70)
print("📊 LAST WEEK SIGNALS (Backtest Results)")
print("=" * 70)

# Read the latest backtest report
report_path = "backtesting/reports/backtest_2025-12-28_2026-01-04.json"
if os.path.exists(report_path):
    import json
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    print(f"\n📅 Date Range: {report['start_date']} to {report['end_date']}")
    print(f"📊 Trading Days: {report['trading_days']}")
    print(f"\n📈 SUMMARY:")
    print(f"   Total Signals: {report['summary']['total_signals']}")
    print(f"   Total Trades: {report['summary']['total_trades']}")
    print(f"   Win Rate: {report['summary']['win_rate']:.1f}%")
    print(f"   Total P&L: {report['summary']['total_pnl']:+.2f}%")
    
    print(f"\n📊 BY SIGNAL TYPE:")
    for signal_type, data in report['by_signal_type'].items():
        if isinstance(data, dict):
            print(f"   {signal_type}: {data['signals']} signals | {data['win_rate']:.1f}% WR | {data['pnl']:+.2f}% P&L")
        else:
            print(f"   {signal_type}: {data} alerts")
    
    print(f"\n📅 DAILY BREAKDOWN:")
    for daily in report['daily_results']:
        emoji = "🟢" if daily['total_pnl'] >= 0 else "🔴"
        print(f"   {emoji} {daily['date']}: {daily['total_signals']} signals | {daily['win_rate']:.0f}% WR | {daily['total_pnl']:+.2f}% P&L | {daily['market_direction']}")
        if 'selloff_rally' in daily:
            sr = daily['selloff_rally']
            print(f"      └─ Selloff/Rally: {sr['signals']} signals | {sr['win_rate']:.1f}% WR | {sr['pnl']:+.2f}% P&L")

# Check production alerts database
print("\n" + "=" * 70)
print("🔔 PRODUCTION ALERTS (From Database)")
print("=" * 70)

try:
    from backtesting.data.alerts_loader import AlertsLoader
    
    loader = AlertsLoader()
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    alerts = loader.load_date_range(week_ago, today)
    
    if alerts:
        print(f"\n📊 Found {len(alerts)} production alerts")
        
        # Group by date
        by_date = {}
        for alert in alerts:
            date = alert.timestamp.strftime('%Y-%m-%d')
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(alert)
        
        print(f"\n📅 BY DATE:")
        for date in sorted(by_date.keys(), reverse=True):
            day_alerts = by_date[date]
            print(f"\n   📅 {date}: {len(day_alerts)} alerts")
            
            # Group by type
            by_type = {}
            for alert in day_alerts:
                alert_type = alert.alert_type or alert.source or 'unknown'
                by_type[alert_type] = by_type.get(alert_type, 0) + 1
            
            for alert_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
                print(f"      {alert_type}: {count}")
    else:
        print("\n⚠️  No production alerts found in database")
        print("   (This is normal if system wasn't running)")
        
except Exception as e:
    print(f"\n⚠️  Could not load production alerts: {e}")

print("\n" + "=" * 70)

