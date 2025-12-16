#!/usr/bin/env python3
"""
Quick diagnostic to check why no alerts are being sent
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("🔍 ALERT SYSTEM DIAGNOSTIC")
print("=" * 70)

# 1. Check if script is running
print("\n1️⃣ CHECKING IF SCRIPT IS RUNNING...")
import subprocess
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
if 'run_all_monitors.py' in result.stdout:
    print("   ✅ Script is running")
    for line in result.stdout.split('\n'):
        if 'run_all_monitors.py' in line:
            print(f"   📋 {line[:100]}")
else:
    print("   ❌ Script is NOT running!")
    print("   💡 Run: python3 run_all_monitors.py")

# 2. Check Discord webhook
print("\n2️⃣ CHECKING DISCORD WEBHOOK...")
webhook = os.getenv('DISCORD_WEBHOOK_URL')
if webhook:
    print(f"   ✅ Webhook is set: {webhook[:30]}...")
else:
    print("   ❌ DISCORD_WEBHOOK_URL not set!")

# 3. Check market hours
print("\n3️⃣ CHECKING MARKET HOURS...")
now = datetime.now()
is_market_hours = 9 <= now.hour < 16 and now.weekday() < 5
print(f"   Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Market hours: {'✅ YES' if is_market_hours else '❌ NO (market closed)'}")

# 4. Check current prices
print("\n4️⃣ CHECKING CURRENT PRICES...")
try:
    import yfinance as yf
    for symbol in ['SPY', 'QQQ']:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                print(f"   {symbol}: ${price:.2f}")
            else:
                print(f"   {symbol}: ❌ No data")
        except Exception as e:
            print(f"   {symbol}: ❌ Error - {e}")
except ImportError:
    print("   ❌ yfinance not installed")

# 5. Check DP levels proximity
print("\n5️⃣ CHECKING DP LEVELS PROXIMITY...")
try:
    from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
    
    api_key = os.getenv('CHARTEXCHANGE_API_KEY')
    if not api_key:
        print("   ❌ CHARTEXCHANGE_API_KEY not set!")
    else:
        client = UltimateChartExchangeClient(api_key)
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        for symbol in ['SPY', 'QQQ']:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d', interval='1m')
                if hist.empty:
                    continue
                current_price = float(hist['Close'].iloc[-1])
                
                dp_levels = client.get_dark_pool_levels(symbol, yesterday)
                if dp_levels:
                    print(f"   {symbol} @ ${current_price:.2f}:")
                    for level in dp_levels[:5]:
                        level_price = float(level.get('level', 0))
                        distance_pct = abs(current_price - level_price) / level_price * 100
                        volume = int(level.get('volume', 0))
                        status = "✅ CLOSE" if distance_pct <= 0.5 else "⚠️ FAR"
                        print(f"      {status} - ${level_price:.2f} ({distance_pct:.2f}% away, {volume:,} shares)")
                else:
                    print(f"   {symbol}: ❌ No DP levels found")
            except Exception as e:
                print(f"   {symbol}: ❌ Error - {e}")
except Exception as e:
    print(f"   ❌ DP check error: {e}")

# 6. Check recent alerts buffer
print("\n6️⃣ CHECKING ALERT SYSTEM STATUS...")
print("   💡 If script is running, check logs for:")
print("      - 'No DP alerts triggered' = Price not close enough to battlegrounds")
print("      - 'Synthesis: X% Y' (no alert needed) = Threshold not met")
print("      - 'UNIFIED MODE: ENABLED' = Individual alerts suppressed")

# 7. Recommendations
print("\n" + "=" * 70)
print("💡 RECOMMENDATIONS:")
print("=" * 70)

if not webhook:
    print("   ❌ Set DISCORD_WEBHOOK_URL in .env file")
if 'run_all_monitors.py' not in result.stdout:
    print("   ❌ Start the monitoring script: python3 run_all_monitors.py")
if not is_market_hours:
    print("   ⚠️  Market is closed - alerts only fire during market hours (9:30 AM - 4:00 PM ET)")
else:
    print("   ✅ Market is open - alerts should fire if conditions are met")
    print("   💡 If still no alerts:")
    print("      - Price may not be close enough to DP battlegrounds (<0.5%)")
    print("      - Synthesis threshold may not be met (need confluence)")
    print("      - Check logs for 'No DP alerts triggered' messages")

print("\n" + "=" * 70)


