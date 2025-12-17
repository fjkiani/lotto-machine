#!/usr/bin/env python3
"""Test the new gamma flip detection method"""
from dotenv import load_dotenv
import os
import sys
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from live_monitoring.core.gamma_exposure import GammaExposureTracker
import yfinance as yf

print("="*80)
print("🎯 TESTING NEW GAMMA FLIP DETECTION")
print("="*80)
print()

tracker = GammaExposureTracker()
symbol = 'SPY'
ticker = yf.Ticker(symbol)
hist = ticker.history(period='1d')
current_price = float(hist['Close'].iloc[-1])

print(f"📊 {symbol} Price: ${current_price:.2f}")
print()

gamma_data = tracker.calculate_gamma_exposure(symbol, current_price)

if gamma_data:
    print(f"✅ Gamma Flip Level: ${gamma_data.gamma_flip_level:.2f}")
    print(f"   Regime: {gamma_data.current_regime}")
    print()
    
    # Test flip detection
    flip_signal = tracker.detect_gamma_flip_signal(gamma_data)
    
    if flip_signal:
        print("✅ ✅ ✅ GAMMA FLIP SIGNAL DETECTED!")
        print()
        print(f"   Signal Type: {flip_signal['signal_type']}")
        print(f"   Action: {flip_signal['action']}")
        print(f"   Direction: {flip_signal['direction']}")
        print(f"   Entry Zone: ${flip_signal['entry_range'][0]:.2f}-${flip_signal['entry_range'][1]:.2f}")
        print(f"   Stop: ${flip_signal['stop_price']:.2f}")
        print(f"   Target 1: ${flip_signal['target1']:.2f} (R/R: {flip_signal['risk_reward1']:.1f}:1)")
        print(f"   Target 2: ${flip_signal['target2']:.2f} (R/R: {flip_signal['risk_reward2']:.1f}:1)")
        print(f"   Confidence: {flip_signal['confidence']:.0%}")
        print()
        print("   Reasoning:")
        for r in flip_signal['reasoning']:
            print(f"      • {r}")
    else:
        print("❌ No gamma flip signal")
        print()
        if gamma_data.gamma_flip_level:
            distance = abs(current_price - gamma_data.gamma_flip_level) / current_price * 100
            print(f"   Distance to flip: {distance:.2f}%")
            print(f"   (Need <0.5% for retest signal)")
            print(f"   Regime: {gamma_data.current_regime}")

print()
print("="*80)

