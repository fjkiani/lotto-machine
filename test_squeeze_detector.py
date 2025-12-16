#!/usr/bin/env python3
"""
🔥 SQUEEZE DETECTOR TEST - PHASE 1 VALIDATION
==============================================

Tests the squeeze detector with live SPY/QQQ data.
Validates all components are working.
"""

import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_squeeze_detector():
    """Test the squeeze detector with live data."""
    
    print("\n" + "="*70)
    print("🔥 SQUEEZE DETECTOR - PHASE 1 TEST")
    print("="*70)
    
    # Check API key
    api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
    if not api_key:
        print("❌ No ChartExchange API key found!")
        print("   Set CHARTEXCHANGE_API_KEY or CHART_EXCHANGE_API_KEY in .env")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...")
    
    # Import and initialize
    try:
        from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
        from live_monitoring.exploitation.squeeze_detector import SqueezeDetector, SqueezeSignal
        from live_monitoring.core.lottery_signals import LiveSignal, SignalType
        
        print("✅ All imports successful")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Create client and detector
    print("\n📡 Initializing ChartExchange client...")
    client = UltimateChartExchangeClient(api_key, tier=3)
    detector = SqueezeDetector(client)
    print("✅ Squeeze detector initialized")
    
    # Test symbols
    test_symbols = ['SPY', 'QQQ']
    results = {}
    
    for symbol in test_symbols:
        print(f"\n{'='*50}")
        print(f"🔍 Analyzing {symbol}...")
        print('='*50)
        
        # Analyze
        signal = detector.analyze(symbol)
        results[symbol] = signal
        
        if signal:
            print(f"\n✅ SQUEEZE SIGNAL FOUND!")
            print(f"   Score: {signal.score:.1f}/100")
            print(f"\n   Component Scores:")
            print(f"   ├── SI Score:     {signal.si_score:.1f}/40 (SI: {signal.short_interest_pct:.1f}%)")
            print(f"   ├── Borrow Score: {signal.borrow_fee_score:.1f}/30 (Fee: {signal.borrow_fee_pct:.1f}%)")
            print(f"   ├── FTD Score:    {signal.ftd_score:.1f}/20 (Spike: {signal.ftd_spike_ratio:.1f}x)")
            print(f"   └── DP Score:     {signal.dp_support_score:.1f}/10 (Buying: {signal.dp_buying_pressure:.0%})")
            print(f"\n   Trade Setup:")
            print(f"   ├── Entry:  ${signal.entry_price:.2f}")
            print(f"   ├── Stop:   ${signal.stop_price:.2f}")
            print(f"   ├── Target: ${signal.target_price:.2f}")
            print(f"   └── R/R:    {signal.risk_reward_ratio:.1f}:1")
            
            if signal.reasoning:
                print(f"\n   Reasoning:")
                for r in signal.reasoning:
                    print(f"   • {r}")
            
            if signal.warnings:
                print(f"\n   ⚠️ Warnings:")
                for w in signal.warnings:
                    print(f"   • {w}")
            
            # Test conversion to LiveSignal
            live_signal = detector.to_live_signal(signal)
            print(f"\n   ✅ Converted to LiveSignal:")
            print(f"      Signal Type: {live_signal.signal_type}")
            print(f"      Confidence: {live_signal.confidence:.0%}")
            print(f"      Is Master: {live_signal.is_master_signal}")
        else:
            print(f"\n   ❌ No squeeze signal (score below threshold)")
    
    # Test watchlist scan
    print(f"\n{'='*50}")
    print("📋 Testing watchlist scan...")
    print('='*50)
    
    signals = detector.scan_watchlist(test_symbols)
    print(f"   Found {len(signals)} signals above threshold")
    
    for sig in signals:
        print(f"   • {sig.symbol}: Score {sig.score:.1f}/100")
    
    # Summary
    print(f"\n{'='*70}")
    print("📊 TEST SUMMARY")
    print('='*70)
    
    total_signals = sum(1 for s in results.values() if s is not None)
    print(f"   Symbols tested: {len(test_symbols)}")
    print(f"   Signals found:  {total_signals}")
    
    if total_signals > 0:
        avg_score = sum(s.score for s in results.values() if s) / total_signals
        print(f"   Avg score:      {avg_score:.1f}")
    
    print(f"\n✅ PHASE 1 TEST COMPLETE!")
    print("="*70)
    
    return True


def test_integration_with_monitor():
    """Test integration with UnifiedAlphaMonitor."""
    
    print("\n" + "="*70)
    print("🎯 TESTING INTEGRATION WITH UNIFIED MONITOR")
    print("="*70)
    
    try:
        from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
        
        print("📡 Initializing UnifiedAlphaMonitor...")
        monitor = UnifiedAlphaMonitor()
        
        print(f"\n   Squeeze Enabled: {'✅' if monitor.squeeze_enabled else '❌'}")
        print(f"   Squeeze Detector: {'✅' if monitor.squeeze_detector else '❌'}")
        
        if monitor.squeeze_enabled and monitor.squeeze_detector:
            print("\n🔥 Testing squeeze check via monitor...")
            monitor.check_squeeze_setups()
            print("✅ Integration test complete!")
        else:
            print("\n⚠️ Squeeze detector not enabled in monitor")
            print("   Check API key and initialization")
        
        return monitor.squeeze_enabled
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔥🔥🔥 SQUEEZE DETECTOR PHASE 1 VALIDATION 🔥🔥🔥\n")
    
    # Run detector test
    detector_ok = test_squeeze_detector()
    
    if detector_ok:
        # Run integration test
        integration_ok = test_integration_with_monitor()
        
        print("\n" + "="*70)
        print("🎯 FINAL RESULTS")
        print("="*70)
        print(f"   Detector Test:    {'✅ PASSED' if detector_ok else '❌ FAILED'}")
        print(f"   Integration Test: {'✅ PASSED' if integration_ok else '❌ FAILED'}")
        print("="*70)
    else:
        print("\n❌ Detector test failed - skipping integration test")


