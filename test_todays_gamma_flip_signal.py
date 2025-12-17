#!/usr/bin/env python3
"""
Test if we would have caught TODAY's gamma flip SHORT signal.

Target Signal:
- Entry: 6,795-6,800 retest (likely $679.50-$680.00 for SPY)
- Action: SHORT
- T1: 6,750 (-50pts)
- T2: 6,720 (-80pts)
- Stop: 6,820 TIGHT

This signal would have occurred when:
1. Price was retesting gamma flip level around $679.50-$680.00
2. Price was BELOW the flip (negative gamma)
3. System should generate SHORT signal
"""
from dotenv import load_dotenv
import os
import sys
from datetime import datetime, timedelta
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from live_monitoring.core.gamma_exposure import GammaExposureTracker
import yfinance as yf
import pandas as pd

print("="*80)
print("🔍 TESTING: Would We Have Caught Today's Gamma Flip SHORT?")
print("="*80)
print()

# Target signal details
target_entry_min = 679.50
target_entry_max = 680.00
target_action = "SHORT"
target_stop = 682.00

print(f"🎯 TARGET SIGNAL:")
print(f"   Entry Zone: ${target_entry_min:.2f}-${target_entry_max:.2f}")
print(f"   Action: {target_action}")
print(f"   Stop: ${target_stop:.2f}")
print()

# Get intraday data to find when price was in entry zone
symbol = 'SPY'
ticker = yf.Ticker(symbol)
hist_1m = ticker.history(period='1d', interval='1m')

if hist_1m.empty:
    print("❌ No intraday data available")
    sys.exit(1)

# Find times when price was in entry zone
entry_zone_times = []
for timestamp, row in hist_1m.iterrows():
    price = float(row['Close'])
    if target_entry_min <= price <= target_entry_max:
        entry_zone_times.append((timestamp, price))

print(f"📊 INTRADAY ANALYSIS:")
print(f"   Total bars: {len(hist_1m)}")
print(f"   Times in entry zone ({target_entry_min:.2f}-{target_entry_max:.2f}): {len(entry_zone_times)}")
print()

if entry_zone_times:
    print(f"   Entry zone hits:")
    for i, (ts, price) in enumerate(entry_zone_times[:5], 1):
        print(f"      {i}. {ts.strftime('%H:%M')} - ${price:.2f}")
    print()
    
    # Test gamma flip detection at first entry zone hit
    test_time, test_price = entry_zone_times[0]
    print(f"🧪 TESTING GAMMA FLIP DETECTION:")
    print(f"   Time: {test_time.strftime('%H:%M:%S')}")
    print(f"   Price: ${test_price:.2f}")
    print()
    
    tracker = GammaExposureTracker()
    gamma_data = tracker.calculate_gamma_exposure(symbol, test_price)
    
    if gamma_data:
        print(f"   ✅ Gamma Flip Level: ${gamma_data.gamma_flip_level:.2f}")
        print(f"   ✅ Current Regime: {gamma_data.current_regime}")
        print()
        
        # Check if flip level is in target range
        flip_level = gamma_data.gamma_flip_level
        if target_entry_min <= flip_level <= target_entry_max:
            print(f"   ✅ ✅ ✅ FLIP LEVEL MATCHES TARGET ENTRY ZONE!")
        else:
            print(f"   ⚠️  Flip level (${flip_level:.2f}) outside target zone (${target_entry_min:.2f}-${target_entry_max:.2f})")
            print(f"      Difference: ${abs(flip_level - (target_entry_min + target_entry_max)/2):.2f}")
        print()
        
        # Test flip signal detection
        flip_signal = tracker.detect_gamma_flip_signal(gamma_data)
        
        if flip_signal:
            print(f"   ✅ GAMMA FLIP SIGNAL DETECTED!")
            print()
            print(f"      Action: {flip_signal['action']}")
            print(f"      Entry Zone: ${flip_signal['entry_range'][0]:.2f}-${flip_signal['entry_range'][1]:.2f}")
            print(f"      Stop: ${flip_signal['stop_price']:.2f}")
            print(f"      Target 1: ${flip_signal['target1']:.2f}")
            print(f"      Target 2: ${flip_signal['target2']:.2f}")
            print()
            
            # Compare to target
            if flip_signal['action'] == target_action:
                print(f"   ✅ ✅ ✅ ACTION MATCHES TARGET ({target_action})!")
            else:
                print(f"   ❌ Action mismatch: {flip_signal['action']} vs {target_action}")
            
            entry_match = (target_entry_min <= flip_signal['entry_range'][0] <= target_entry_max or
                          target_entry_min <= flip_signal['entry_range'][1] <= target_entry_max)
            if entry_match:
                print(f"   ✅ Entry zone overlaps with target!")
            else:
                print(f"   ⚠️  Entry zone doesn't match target")
            
            stop_diff = abs(flip_signal['stop_price'] - target_stop)
            if stop_diff < 5.0:  # Within $5
                print(f"   ✅ Stop price close to target (${stop_diff:.2f} difference)")
            else:
                print(f"   ⚠️  Stop price differs: ${stop_diff:.2f}")
        else:
            print(f"   ❌ NO GAMMA FLIP SIGNAL DETECTED")
            print()
            if gamma_data.gamma_flip_level:
                distance = abs(test_price - gamma_data.gamma_flip_level) / test_price * 100
                print(f"      Distance to flip: {distance:.2f}%")
                print(f"      (Need <0.5% for retest signal)")
                print(f"      Regime: {gamma_data.current_regime}")
else:
    print(f"⚠️  Price never entered target entry zone today")
    print(f"   (This could mean signal was from a different day or different interpretation)")

print()
print("="*80)
print("💡 CONCLUSION:")
print("="*80)
print()
print("If flip signal was detected with SHORT action and entry zone matches,")
print("then YES, we would have caught today's signal!")
print()
print("="*80)

