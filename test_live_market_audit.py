#!/usr/bin/env python3
"""
Quick live market audit - what should be triggering?
"""
from dotenv import load_dotenv
import os
import sys

# Load env
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
from datetime import datetime, timedelta
import yfinance as yf

print("="*80)
print("🔍 LIVE MARKET DATA AUDIT - What Should Trigger?")
print("="*80)
print()

# Initialize client
api_key = os.getenv('CHARTEXCHANGE_API_KEY')
client = UltimateChartExchangeClient(api_key, tier=3)

symbols = ['SPY', 'QQQ']
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

for symbol in symbols:
    print(f"\n📊 {symbol} ANALYSIS:")
    print("-" * 80)
    
    # Get current price
    ticker = yf.Ticker(symbol)
    current_price = ticker.info.get('regularMarketPrice', 0)
    print(f"   Current Price: ${current_price:.2f}")
    
    # 1. Check DP Levels
    try:
        dp_levels = client.get_dark_pool_levels(symbol, date=yesterday)
        if dp_levels and len(dp_levels) > 0:
            print(f"\n   🏦 DARK POOL LEVELS: {len(dp_levels)} found")
            
            # Find nearest levels (convert to float)
            nearest = sorted(dp_levels, key=lambda x: abs(float(x.get('level', 0)) - current_price))[:3]
            for i, level in enumerate(nearest, 1):
                level_price = float(level.get('level', 0))
                volume = int(level.get('volume', 0))
                dist = ((level_price - current_price) / current_price) * 100
                direction = "above" if level_price > current_price else "below"
                
                print(f"      {i}. ${level_price:.2f} ({dist:+.2f}%, {direction}) - {volume:,} shares")
                
                # Check if at a level (within 0.3%)
                if abs(dist) < 0.3:
                    print(f"         🎯 PRICE AT BATTLEGROUND! Should trigger DP alert")
        else:
            print(f"   🏦 DARK POOL LEVELS: None (T+1 delay expected)")
    except Exception as e:
        print(f"   ⚠️  DP Levels error: {e}")
    
    # 2. Check Short Interest
    try:
        short_data = client.get_short_interest(symbol)
        if short_data and len(short_data) > 0:
            latest = short_data[0]
            short_pct = latest.get('short_interest_pct', 0)
            print(f"\n   🔥 SHORT INTEREST: {short_pct:.1f}%")
            
            if short_pct > 15:
                print(f"      🎯 HIGH SHORT INTEREST! Squeeze potential exists")
        else:
            print(f"   🔥 SHORT INTEREST: No data")
    except Exception as e:
        print(f"   ⚠️  Short Interest error: {e}")
    
    # 3. Check Reddit Mentions
    try:
        reddit_data = client.get_reddit_mentions(symbol, days=7)
        if reddit_data and len(reddit_data) > 0:
            total_mentions = sum(m.get('mentions', 0) for m in reddit_data)
            recent = reddit_data[0].get('mentions', 0) if reddit_data else 0
            avg = total_mentions / 7
            velocity = recent / avg if avg > 0 else 0
            
            print(f"\n   📱 REDDIT ACTIVITY:")
            print(f"      Total (7d): {total_mentions}")
            print(f"      Recent: {recent}")
            print(f"      Velocity: {velocity:.1f}x")
            
            if velocity > 3.0:
                print(f"      🎯 HIGH VELOCITY! Should trigger Reddit signal")
        else:
            print(f"   📱 REDDIT ACTIVITY: No recent mentions")
    except Exception as e:
        print(f"   ⚠️  Reddit error: {e}")

print()
print("="*80)
print("💡 VERDICT:")
print("="*80)
print()
print("Based on live API data:")
print("   • If DP levels near price → DP alert should exist")
print("   • If high short interest → Squeeze signal should exist")  
print("   • If high Reddit velocity → Reddit signal should exist")
print("   • If none of above → System correctly NOT alerting (no opportunities)")
print()
print("="*80)

