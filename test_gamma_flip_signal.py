#!/usr/bin/env python3
"""
Test if our gamma tracker would have caught the "GAMMA FLIP SHORT" signal today.

Signal details:
- Entry: 6,795-6,800 retest (gamma flip level)
- T1: 6,750 (-50pts)
- T2: 6,720 (-80pts)
- Stop: 6,820 TIGHT
- 30% size only

This is a gamma FLIP signal (not a gamma ramp), which requires:
1. Calculating gamma flip level (where GEX crosses zero)
2. Detecting when price retests this level
3. Generating SHORT signal when below flip (negative gamma = amplifying down)
"""
from dotenv import load_dotenv
import os
import sys
from datetime import datetime

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from live_monitoring.core.gamma_exposure import GammaExposureTracker
from live_monitoring.exploitation.gamma_tracker import GammaTracker
import yfinance as yf

print("="*80)
print("🔍 GAMMA FLIP SIGNAL TEST - Dec 17, 2025")
print("="*80)
print()

symbol = 'SPY'
ticker = yf.Ticker(symbol)
hist = ticker.history(period='1d')
current_price = float(hist['Close'].iloc[-1])

print(f"📊 {symbol} Current Price: ${current_price:.2f}")
print(f"🎯 Target Signal Entry: $6,795-6,800 (gamma flip level)")
print()

# Test 1: Gamma Exposure Tracker (calculates flip level)
print("="*80)
print("TEST 1: Gamma Exposure Tracker (Flip Level Calculation)")
print("="*80)
print()

gamma_exposure_tracker = GammaExposureTracker()
gamma_data = gamma_exposure_tracker.calculate_gamma_exposure(symbol, current_price)

if gamma_data:
    print("✅ Gamma exposure calculated!")
    print()
    print(f"   Gamma Flip Level: ${gamma_data.gamma_flip_level:.2f}" if gamma_data.gamma_flip_level else "   ⚠️  No flip level detected")
    print(f"   Current Regime: {gamma_data.current_regime}")
    print(f"   Total GEX: {gamma_data.total_gex:,.0f} shares")
    print()
    
    if gamma_data.gamma_flip_level:
        flip_level = gamma_data.gamma_flip_level
        distance_to_flip = abs(current_price - flip_level)
        distance_pct = (distance_to_flip / current_price) * 100
        
        print(f"   📍 Distance to Flip: ${distance_to_flip:.2f} ({distance_pct:.2f}%)")
        print()
        
        # Check if flip level matches target signal
        target_range = (6795, 6800)
        if target_range[0] <= flip_level <= target_range[1]:
            print(f"   ✅ ✅ ✅ FLIP LEVEL MATCHES TARGET SIGNAL!")
            print(f"      Target: ${target_range[0]}-${target_range[1]}")
            print(f"      Our Flip: ${flip_level:.2f}")
        else:
            print(f"   ⚠️  Flip level doesn't match target")
            print(f"      Target: ${target_range[0]}-${target_range[1]}")
            print(f"      Our Flip: ${flip_level:.2f}")
            print(f"      Difference: ${abs(flip_level - (target_range[0] + target_range[1])/2):.2f}")
        
        # Check if price is retesting flip level (within 0.5%)
        if distance_pct < 0.5:
            print()
            print(f"   🎯 PRICE AT GAMMA FLIP LEVEL!")
            print(f"      Current: ${current_price:.2f}")
            print(f"      Flip: ${flip_level:.2f}")
            print(f"      Distance: {distance_pct:.2f}%")
            print()
            
            # Check regime
            if gamma_data.current_regime == 'NEGATIVE':
                print(f"   ✅ NEGATIVE GAMMA REGIME")
                print(f"      Below flip = negative gamma = amplifying moves DOWN")
                print(f"      🚨 SHOULD GENERATE SHORT SIGNAL!")
            elif gamma_data.current_regime == 'POSITIVE':
                print(f"   ⚠️  POSITIVE GAMMA REGIME")
                print(f"      Above flip = positive gamma = stabilizing")
                print(f"      Would NOT generate short signal")
        else:
            print()
            print(f"   ⚠️  Price not at flip level")
            print(f"      Need to be within 0.5% of flip for retest signal")
    else:
        print("   ❌ No gamma flip level detected - cannot generate flip signal")
else:
    print("❌ Failed to calculate gamma exposure")

print()
print("="*80)
print("TEST 2: Gamma Tracker (Current Implementation)")
print("="*80)
print()

# Test 2: Current Gamma Tracker (max pain based)
gamma_tracker = GammaTracker()
signal = gamma_tracker.analyze(symbol)

if signal:
    print("✅ Gamma signal generated!")
    print()
    print(f"   Direction: {signal.direction}")
    print(f"   Score: {signal.score:.1f}/100")
    print(f"   P/C Ratio: {signal.put_call_ratio:.2f}")
    print(f"   Max Pain: ${signal.max_pain:.2f}")
    print(f"   Action: {signal.action}")
    print(f"   Entry: ${signal.entry_price:.2f}")
    print(f"   Target: ${signal.target_price:.2f}")
    print(f"   Stop: ${signal.stop_price:.2f}")
    print()
    
    # Compare to target signal
    target_entry = (6795 + 6800) / 2
    target_stop = 6820
    target_t1 = 6750
    
    print(f"   🎯 COMPARISON TO TARGET SIGNAL:")
    print(f"      Target Entry: ${target_entry:.0f}")
    print(f"      Our Entry: ${signal.entry_price:.2f}")
    print(f"      Match: {'✅' if abs(signal.entry_price - target_entry) < 10 else '❌'}")
    print()
    print(f"      Target Stop: ${target_stop:.0f}")
    print(f"      Our Stop: ${signal.stop_price:.2f}")
    print()
    print(f"      Target T1: ${target_t1:.0f}")
    print(f"      Our Target: ${signal.target_price:.2f}")
    print()
    
    if signal.action == 'SHORT' and signal.direction == 'DOWN':
        print("   ✅ Signal is SHORT/DOWN - matches target!")
    else:
        print(f"   ⚠️  Signal is {signal.action}/{signal.direction} - does NOT match target SHORT")
else:
    print("❌ No gamma signal generated")
    print()
    print("   This means our current gamma tracker (max pain based) would NOT")
    print("   have caught the gamma flip signal!")

print()
print("="*80)
print("💡 CONCLUSION:")
print("="*80)
print()
print("GAMMA FLIP signals require:")
print("   1. ✅ Calculate gamma flip level (we have this in gamma_exposure.py)")
print("   2. ❌ Detect price retesting flip level (we DON'T have this)")
print("   3. ❌ Generate SHORT when below flip (we DON'T have this)")
print()
print("Our current gamma tracker focuses on:")
print("   - Max pain calculation")
print("   - P/C ratio extremes")
print("   - Gamma ramp signals (not flip signals)")
print()
print("🎯 RECOMMENDATION:")
print("   Add gamma flip detection to generate signals when:")
print("   - Price retests gamma flip level (within 0.5%)")
print("   - Below flip = negative gamma = SHORT signal")
print("   - Above flip = positive gamma = LONG signal")
print()
print("="*80)

