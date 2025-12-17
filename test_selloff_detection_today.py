#!/usr/bin/env python3
"""
Test selloff detection on today's actual market data.
This tests the EXACT code that should be running in production.
"""
from dotenv import load_dotenv
import os
import sys
from datetime import datetime, timedelta

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from live_monitoring.core.signal_generator import SignalGenerator
from live_monitoring.orchestrator.momentum_detector import MomentumDetector
from core.ultra_institutional_engine import UltraInstitutionalEngine
import yfinance as yf

print("="*80)
print("🔍 SELLOFF DETECTION TEST - Dec 17, 2025")
print("="*80)
print()

# Initialize the EXACT same components as production
api_key = os.getenv('CHARTEXCHANGE_API_KEY')
signal_generator = SignalGenerator(api_key=api_key)
institutional_engine = UltraInstitutionalEngine(api_key)
momentum_detector = MomentumDetector(
    signal_generator=signal_generator,
    institutional_engine=institutional_engine
)

print("✅ Initialized production components")
print()

# Test on actual symbols
symbols = ['SPY', 'QQQ']

for symbol in symbols:
    print(f"\n{'='*80}")
    print(f"📊 TESTING: {symbol}")
    print(f"{'='*80}")
    
    # Get actual market data
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period='1d', interval='1m')
    
    if hist.empty:
        print(f"   ❌ No data available")
        continue
    
    day_open = hist['Open'].iloc[0]
    current_price = hist['Close'].iloc[-1]
    pct_from_open = ((current_price - day_open) / day_open) * 100
    
    print(f"\n📈 MARKET DATA:")
    print(f"   Open: ${day_open:.2f}")
    print(f"   Current: ${current_price:.2f}")
    print(f"   Change: {pct_from_open:+.2f}%")
    
    # Call the EXACT method that production uses
    print(f"\n🔍 CALLING PRODUCTION selloff DETECTION...")
    try:
        selloff_signals = momentum_detector.check_selloffs([symbol])
        
        if selloff_signals:
            print(f"\n✅ SELLOFF DETECTED!")
            for sig_data in selloff_signals:
                signal = sig_data['signal']
                print(f"\n   Signal Details:")
                print(f"      Type: {signal.signal_type}")
                print(f"      Action: {signal.action}")
                print(f"      Confidence: {signal.confidence:.1%}")
                print(f"      Entry: ${signal.entry_price:.2f}")
                print(f"      Target: ${signal.target_price:.2f}")
                print(f"      Stop: ${signal.stop_price:.2f}")
                print(f"      Rationale: {signal.rationale}")
                print(f"\n   🚨 THIS SHOULD HAVE BEEN SENT TO DISCORD!")
        else:
            print(f"\n❌ NO SELLOFF DETECTED")
            print(f"\n   WHY NOT? Let's debug...")
            
            # Manual check
            print(f"\n   Manual Detection Check:")
            print(f"      From Open: {pct_from_open:.2f}% (need -0.25%)")
            if pct_from_open <= -0.25:
                print(f"         ✅ Should trigger!")
            else:
                print(f"         ❌ Not triggered")
            
            # Check consecutive red bars
            consecutive_red = 0
            closes = hist['Close']
            for i in range(len(closes) - 1, max(0, len(closes) - 10), -1):
                if closes.iloc[i] < closes.iloc[i-1]:
                    consecutive_red += 1
                else:
                    break
            
            print(f"      Consecutive Red: {consecutive_red} bars (need 3+)")
            if consecutive_red >= 3:
                print(f"         ✅ Should trigger!")
            else:
                print(f"         ❌ Not triggered")
            
            print(f"\n   🐛 BUG: Conditions met but signal not generated!")
            print(f"       Check if:")
            print(f"       1. SignalGenerator is initialized correctly")
            print(f"       2. minute_bars has enough data")
            print(f"       3. Method is being called in production")
            print(f"       4. Confidence threshold too high")
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

print()
print("="*80)
print("💡 CONCLUSION:")
print("="*80)
print()
print("If signals detected above, system is working correctly.")
print("If signals NOT detected, we have a bug in production code!")
print()
print("="*80)

