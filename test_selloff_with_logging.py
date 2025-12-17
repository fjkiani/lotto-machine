#!/usr/bin/env python3
"""
Test selloff detection with FULL internal logging to see where it fails.
"""
from dotenv import load_dotenv
import os
import sys
from datetime import datetime, timedelta
import logging

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from live_monitoring.core.signal_generator import SignalGenerator
from core.ultra_institutional_engine import UltraInstitutionalEngine
import yfinance as yf

print("="*80)
print("🔍 SELLOFF DETECTION WITH FULL LOGGING")
print("="*80)
print()

# Initialize
api_key = os.getenv('CHARTEXCHANGE_API_KEY')
signal_generator = SignalGenerator(api_key=api_key)
institutional_engine = UltraInstitutionalEngine(api_key)

# Get SPY data
symbol = 'SPY'
ticker = yf.Ticker(symbol)
hist = ticker.history(period='1d', interval='1m')

if hist.empty:
    print("No data")
    sys.exit(1)

day_open = hist['Open'].iloc[0]
current_price = hist['Close'].iloc[-1]
pct_from_open = ((current_price - day_open) / day_open) * 100

print(f"📊 {symbol}:")
print(f"   Open: ${day_open:.2f}")
print(f"   Current: ${current_price:.2f}")
print(f"   Change: {pct_from_open:+.2f}%")
print()

# Get institutional context
try:
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    inst_context = institutional_engine.build_context(symbol, yesterday)
    print(f"✅ Institutional context built")
except Exception as e:
    print(f"⚠️  No institutional context: {e}")
    inst_context = None

print()
print("🔍 CALLING _detect_realtime_selloff() with FULL data...")
print()

# Call the detection method directly
try:
    selloff_signal = signal_generator._detect_realtime_selloff(
        symbol=symbol,
        current_price=current_price,
        minute_bars=hist,  # Pass full day data
        context=inst_context
    )
    
    if selloff_signal:
        print()
        print("✅ ✅ ✅ SELLOFF DETECTED! ✅ ✅ ✅")
        print()
        print(f"   Type: {selloff_signal.signal_type}")
        print(f"   Action: {selloff_signal.action}")
        print(f"   Confidence: {selloff_signal.confidence:.1%}")
        print(f"   Entry: ${selloff_signal.entry_price:.2f}")
        print(f"   Target: ${selloff_signal.target_price:.2f}")
        print(f"   Stop: ${selloff_signal.stop_price:.2f}")
        print(f"   Rationale: {selloff_signal.rationale}")
        print()
        print("🎯 THIS IS WHAT SHOULD HAVE BEEN SENT TO DISCORD!")
    else:
        print()
        print("❌ NO SELLOFF DETECTED")
        print()
        print("Check the DEBUG logs above to see where it failed:")
        print("   - Did triggers_hit = 0?")
        print("   - Did volume check fail?")
        print("   - Was confidence below threshold?")
        
except Exception as e:
    print()
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
print("="*80)

