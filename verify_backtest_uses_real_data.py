#!/usr/bin/env python3
"""
Verify if backtest is using real historical data or just latest data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backtesting.simulation.selloff_rally_detector import SelloffRallyDetector
import yfinance as yf
from datetime import datetime, timedelta

detector = SelloffRallyDetector()

print("=" * 70)
print("🔍 VERIFYING: Are backtest results using real historical data?")
print("=" * 70)

# Test with different dates
dates = ['2025-12-29', '2025-12-30', '2026-01-02']

for date in dates:
    print(f"\n📅 Testing {date}:")
    
    # Check what get_intraday_data returns with date parameter (FIXED)
    data = detector.get_intraday_data('SPY', period="1d", interval="1m", date=date)
    
    if not data.empty:
        first_bar = data.index[0]
        last_bar = data.index[-1]
        
        # Extract date from timestamp
        if hasattr(first_bar, 'date'):
            data_date = first_bar.date().strftime('%Y-%m-%d')
        elif hasattr(first_bar, 'strftime'):
            data_date = first_bar.strftime('%Y-%m-%d')
        else:
            data_date = str(first_bar)[:10]
        
        print(f"   Data returned: {len(data)} bars")
        print(f"   Date range: {first_bar} to {last_bar}")
        print(f"   Extracted date: {data_date}")
        print(f"   Price range: ${data['Low'].min():.2f} - ${data['High'].max():.2f}")
        
        if data_date == date:
            print(f"   ✅ CORRECT: Using data for {date}")
        else:
            print(f"   ❌ WRONG: Requested {date}, but got {data_date}")
            print(f"   ⚠️  BUG: get_intraday_data() uses period='1d' which always gets LATEST data!")
            print(f"   ⚠️  This means all dates use the same (most recent) trading day's data!")
    else:
        print(f"   ❌ No data returned")

print("\n" + "=" * 70)
print("🔍 ROOT CAUSE ANALYSIS")
print("=" * 70)
print("""
The issue is in base_detector.py::get_intraday_data():

    def get_intraday_data(self, symbol: str, period: str = "1d", interval: str = "1m"):
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)  # ❌ Always gets LATEST data
        return data

When backtest_date() calls this with period="1d", it gets the LAST 1 day of data,
NOT the specific date requested. So all dates show identical results because
they're all using the same (latest) trading day's data.

FIX NEEDED:
- Use start/end parameters instead of period
- Filter data to the specific date requested
- Or use a different data source that supports historical dates
""")

