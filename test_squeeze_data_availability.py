#!/usr/bin/env python3
"""
🔥 SQUEEZE DATA AVAILABILITY TEST
Tests what data we can actually get for historical squeeze backtesting.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
import logging

logging.basicConfig(level=logging.WARNING)

def test_data_availability():
    """Test what historical data is available"""
    
    api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
    if not api_key:
        print("❌ No API key!")
        return
    
    client = UltimateChartExchangeClient(api_key, tier=3)
    
    print("="*70)
    print("🔥 SQUEEZE DATA AVAILABILITY TEST")
    print("="*70)
    print()
    
    # Test dates: Recent, 30 days ago, 90 days ago, Jan 2021 (GME squeeze)
    test_dates = [
        ("Today", datetime.now().strftime('%Y-%m-%d')),
        ("30 days ago", (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')),
        ("90 days ago", (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')),
        ("Jan 2021 (GME squeeze)", "2021-01-15"),
    ]
    
    symbols = ['GME', 'AMC', 'LCID']  # High SI stocks
    
    for symbol in symbols:
        print(f"\n{'='*70}")
        print(f"📊 {symbol}")
        print('='*70)
        
        for label, test_date in test_dates:
            print(f"\n📅 {label} ({test_date}):")
            
            # Short Interest Daily
            try:
                si_daily = client.get_short_interest_daily(symbol, date=test_date)
                if si_daily and isinstance(si_daily, list):
                    # Check if we got data for the requested date
                    matching = [d for d in si_daily if d.get('date') == test_date]
                    if matching:
                        si_pct = float(matching[0].get('short_interest', 0))
                        print(f"   ✅ Short Interest: {si_pct:.1f}% (found for {test_date})")
                    else:
                        # Check what dates we got
                        dates = [d.get('date') for d in si_daily[:5]]
                        print(f"   ⚠️  Short Interest: Got {len(si_daily)} records, but not for {test_date}")
                        print(f"      Available dates: {dates}")
                else:
                    print(f"   ❌ Short Interest: No data")
            except Exception as e:
                print(f"   ❌ Short Interest: Error - {e}")
            
            # Borrow Fee
            try:
                borrow = client.get_borrow_fee(symbol, date=test_date)
                if borrow and borrow.fee_rate > 0:
                    print(f"   ✅ Borrow Fee: {borrow.fee_rate:.1f}%")
                elif borrow:
                    print(f"   ⚠️  Borrow Fee: 0.0% (might be unavailable)")
                else:
                    print(f"   ❌ Borrow Fee: No data")
            except Exception as e:
                print(f"   ❌ Borrow Fee: Error - {e}")
            
            # FTD Data
            try:
                start_date = (datetime.strptime(test_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
                ftds = client.get_failure_to_deliver(symbol, start_date=start_date)
                if ftds:
                    # Check if we have data around the test date
                    matching = [f for f in ftds if f.date == test_date]
                    if matching:
                        qty = matching[0].quantity
                        print(f"   ✅ FTD: {qty:,} shares on {test_date}")
                    else:
                        # Show what we got
                        recent = [f for f in ftds if f.quantity > 0][:3]
                        if recent:
                            print(f"   ⚠️  FTD: {len(ftds)} records, but not for {test_date}")
                            print(f"      Sample: {[(f.date, f.quantity) for f in recent]}")
                        else:
                            print(f"   ⚠️  FTD: {len(ftds)} records, all zero quantity")
                else:
                    print(f"   ❌ FTD: No data")
            except Exception as e:
                print(f"   ❌ FTD: Error - {e}")
            
            # DP Levels
            try:
                dp_levels = client.get_dark_pool_levels(symbol, date=test_date)
                if dp_levels and len(dp_levels) > 0:
                    print(f"   ✅ DP Levels: {len(dp_levels)} levels")
                else:
                    print(f"   ⚠️  DP Levels: 0 levels (might be unavailable)")
            except Exception as e:
                print(f"   ❌ DP Levels: Error - {e}")

if __name__ == "__main__":
    test_data_availability()


