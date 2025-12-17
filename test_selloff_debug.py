#!/usr/bin/env python3
"""
Deep dive debug - trace through the selloff detection logic step by step.
"""
from dotenv import load_dotenv
import os
import sys
from datetime import datetime, timedelta

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

import yfinance as yf
import pandas as pd

print("="*80)
print("🔍 SELLOFF DETECTION DEEP DIVE - SPY")
print("="*80)
print()

# Get SPY data
ticker = yf.Ticker('SPY')
hist = ticker.history(period='1d', interval='1m')

minute_bars = hist.tail(30)
closes = minute_bars["Close"]
volumes = minute_bars["Volume"]

current_price = float(minute_bars['Close'].iloc[-1])
day_open = float(minute_bars["Open"].iloc[0])

print(f"📊 DATA:")
print(f"   Bars: {len(minute_bars)}")
print(f"   Open: ${day_open:.2f}")
print(f"   Current: ${current_price:.2f}")
print()

# METHOD 1: From Open
pct_from_open = (current_price - day_open) / day_open
from_open_triggered = pct_from_open <= -0.0025
print(f"METHOD 1 - FROM OPEN:")
print(f"   Change: {pct_from_open*100:.2f}%")
print(f"   Threshold: -0.25%")
print(f"   Triggered: {from_open_triggered}")
print()

# METHOD 2: Consecutive Red Bars
consecutive_red = 0
for i in range(len(closes) - 1, max(0, len(closes) - 10), -1):
    if closes.iloc[i] < closes.iloc[i-1]:
        consecutive_red += 1
    else:
        break

momentum_triggered = consecutive_red >= 3
print(f"METHOD 2 - MOMENTUM:")
print(f"   Consecutive red: {consecutive_red}")
print(f"   Threshold: 3+")
print(f"   Triggered: {momentum_triggered}")
print()

# METHOD 3: Rolling
lookback = min(10, len(closes))
recent_closes = closes.tail(lookback)
start_price = float(recent_closes.iloc[0])
end_price = float(recent_closes.iloc[-1])
rolling_change = (end_price - start_price) / start_price
rolling_triggered = rolling_change <= -0.002

print(f"METHOD 3 - ROLLING:")
print(f"   Lookback: {lookback} bars")
print(f"   Change: {rolling_change*100:.2f}%")
print(f"   Threshold: -0.2%")
print(f"   Triggered: {rolling_triggered}")
print()

# TRIGGERS HIT
triggers_hit = sum([from_open_triggered, momentum_triggered, rolling_triggered])
print(f"🎯 TRIGGERS HIT: {triggers_hit}/3")
print()

if triggers_hit == 0:
    print("❌ NO TRIGGERS - Signal returns None")
    print()
else:
    print("✅ At least 1 trigger hit - continues to volume check...")
    print()
    
    # VOLUME CHECK
    avg_volume = float(volumes.iloc[:-1].mean()) if len(volumes) > 1 else 0
    last_volume = float(volumes.iloc[-1])
    volume_elevated = avg_volume > 0 and last_volume > avg_volume * 1.0
    
    print(f"VOLUME CHECK:")
    print(f"   Avg volume: {avg_volume:,.0f}")
    print(f"   Last volume: {last_volume:,.0f}")
    print(f"   Elevated: {volume_elevated}")
    print()
    
    # SKIP CONDITION
    if not volume_elevated and triggers_hit < 2:
        print("❌ SKIP: Volume not elevated AND triggers < 2")
        print("   This might be the bug!")
        print()
    else:
        print("✅ Passes volume check - should generate signal")
        print()
        
        # BASE CONFIDENCE
        base_confidence = 0.50 + (triggers_hit * 0.15)
        print(f"BASE CONFIDENCE: {base_confidence:.2%}")
        
        # Boosts
        if abs(pct_from_open) >= 0.005:
            base_confidence += 0.10
            print(f"   + 10% boost (>0.5% from open)")
        
        if consecutive_red >= 5:
            base_confidence += 0.10
            print(f"   + 10% boost (5+ red bars)")
        
        confidence = min(base_confidence, 0.95)
        print(f"FINAL CONFIDENCE: {confidence:.2%}")
        print()
        
        # Check against threshold
        print(f"MIN CONFIDENCE THRESHOLD: ???")
        print(f"   (Check signal_generator.min_high_confidence)")

print("="*80)

