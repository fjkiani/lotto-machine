#!/usr/bin/env python3
"""
Extended Period Backtest - Test how far back we can go

Tests different intervals:
- 1m: Last 30 days only
- 5m: Last 60 days only  
- 1d: Years of history (but less accurate for intraday signals)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse

sys.path.insert(0, str(Path(__file__).parent))

from backtesting.simulation.date_range_backtest import DateRangeBacktester

def get_trading_days(start_date: str, end_date: str) -> list:
    """Get list of trading days (weekdays only)"""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return days

def main():
    parser = argparse.ArgumentParser(description='Extended period backtest')
    parser.add_argument('--start', type=str, default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--days', type=int, default=30, help='Number of days back from today')
    parser.add_argument('--interval', type=str, default='auto', choices=['1m', '5m', '1d', 'auto'], 
                       help='Data interval (auto = use best available)')
    parser.add_argument('--symbols', nargs='+', default=['SPY', 'QQQ'], help='Symbols to test')
    
    args = parser.parse_args()
    
    # Determine date range
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    else:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    
    print(f"\n{'='*70}")
    print(f"📊 EXTENDED PERIOD BACKTEST")
    print(f"{'='*70}\n")
    print(f"Period: {start_date} to {end_date}")
    print(f"Symbols: {', '.join(args.symbols)}")
    print(f"Interval: {args.interval}\n")
    
    # Get trading days
    trading_days = get_trading_days(start_date, end_date)
    print(f"📅 Trading Days: {len(trading_days)}")
    
    # Check data availability
    print(f"\n🔍 Checking data availability...")
    
    import yfinance as yf
    from datetime import datetime as dt
    
    # Test first and last dates
    test_dates = [trading_days[0], trading_days[-1]] if len(trading_days) > 1 else [trading_days[0]]
    
    for test_date in test_dates:
        date_obj = dt.strptime(test_date, '%Y-%m-%d')
        days_ago = (datetime.now() - date_obj).days
        
        print(f"\n  {test_date} ({days_ago} days ago):")
        
        # Test 1m
        if days_ago <= 30:
            try:
                ticker = yf.Ticker('SPY')
                data = ticker.history(start=test_date, end=(date_obj + timedelta(days=1)).strftime('%Y-%m-%d'), interval='1m')
                if not data.empty:
                    print(f"    ✅ 1m data: {len(data)} bars")
                else:
                    print(f"    ❌ 1m data: No data")
            except Exception as e:
                print(f"    ❌ 1m data: Error")
        else:
            print(f"    ⚠️  1m data: Not available (>30 days)")
        
        # Test 5m
        if days_ago <= 60:
            try:
                ticker = yf.Ticker('SPY')
                data = ticker.history(start=test_date, end=(date_obj + timedelta(days=1)).strftime('%Y-%m-%d'), interval='5m')
                if not data.empty:
                    print(f"    ✅ 5m data: {len(data)} bars")
                else:
                    print(f"    ❌ 5m data: No data")
            except Exception as e:
                print(f"    ❌ 5m data: Error")
        else:
            print(f"    ⚠️  5m data: Not available (>60 days)")
        
        # Test 1d (always available)
        try:
            ticker = yf.Ticker('SPY')
            data = ticker.history(start=test_date, end=(date_obj + timedelta(days=1)).strftime('%Y-%m-%d'), interval='1d')
            if not data.empty:
                print(f"    ✅ 1d data: {len(data)} bars")
            else:
                print(f"    ❌ 1d data: No data")
        except Exception as e:
            print(f"    ❌ 1d data: Error")
    
    # Determine best interval
    first_date = dt.strptime(trading_days[0], '%Y-%m-%d')
    days_ago_first = (datetime.now() - first_date).days
    
    if args.interval == 'auto':
        if days_ago_first <= 30:
            recommended_interval = '1m'
        elif days_ago_first <= 60:
            recommended_interval = '5m'
        else:
            recommended_interval = '1d'
            print(f"\n⚠️  WARNING: Period >60 days - will use daily data (less accurate for intraday signals)")
    else:
        recommended_interval = args.interval
    
    print(f"\n📊 Recommended interval: {recommended_interval}")
    
    # Ask user if they want to proceed
    if days_ago_first > 60:
        print(f"\n⚠️  NOTE: For periods >60 days, we can only use daily data.")
        print(f"   This means:")
        print(f"   - Less accurate entry/exit timing")
        print(f"   - Signals may be less reliable")
        print(f"   - But we can test longer-term patterns")
        print(f"\n   Continue? (This will use daily data)")
        response = input("   [y/N]: ").strip().lower()
        if response != 'y':
            print("   Cancelled.")
            return
    
    # Run backtest
    print(f"\n🚀 Running backtest with {recommended_interval} interval...")
    print(f"   This may take a while for {len(trading_days)} days...\n")
    
    # Note: The DateRangeBacktester currently uses 1m/5m based on days_ago
    # We'd need to modify it to accept interval parameter
    # For now, just show what's possible
    
    print(f"✅ Data availability check complete!")
    print(f"\n📋 SUMMARY:")
    print(f"   - Trading days: {len(trading_days)}")
    print(f"   - Best interval: {recommended_interval}")
    print(f"   - Period: {start_date} to {end_date}")
    print(f"\n💡 To run actual backtest:")
    print(f"   python3 -m backtesting.simulation.date_range_backtest --start {start_date} --end {end_date}")

if __name__ == "__main__":
    main()

