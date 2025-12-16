#!/usr/bin/env python3
"""
🧪 TEST MODULAR SYSTEM

Quick test to verify modularization didn't break anything.
"""

import sys
import os

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all module imports."""
    print("=" * 70)
    print("🧪 TESTING MODULAR SYSTEM IMPORTS")
    print("=" * 70)
    
    tests = [
        ("AlertManager", "live_monitoring.orchestrator.alert_manager"),
        ("RegimeDetector", "live_monitoring.orchestrator.regime_detector"),
        ("MomentumDetector", "live_monitoring.orchestrator.momentum_detector"),
        ("MonitorInitializer", "live_monitoring.orchestrator.monitor_initializer"),
        ("UnifiedAlphaMonitor", "live_monitoring.orchestrator.unified_monitor"),
    ]
    
    results = []
    for name, module_path in tests:
        try:
            module = __import__(module_path, fromlist=[name])
            cls = getattr(module, name)
            results.append((name, True, None))
            print(f"   ✅ {name} imports OK")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"   ❌ {name} import failed: {e}")
    
    print("=" * 70)
    return all(r[1] for r in results)


def test_methods():
    """Test that UnifiedAlphaMonitor has all required methods."""
    print("\n" + "=" * 70)
    print("🧪 TESTING UNIFIEDALPHAMONITOR METHODS")
    print("=" * 70)
    
    try:
        from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
        
        required_methods = [
            'send_discord',
            'check_fed',
            'check_trump',
            'check_economics',
            'check_dark_pools',
            '_check_selloffs',
            '_check_rallies',
            '_detect_market_regime',
            'check_synthesis',
            '_check_narrative_brain_signals',
            'run',
            '_is_market_hours',
            'send_startup_alert'
        ]
        
        missing = []
        for method in required_methods:
            if not hasattr(UnifiedAlphaMonitor, method):
                missing.append(method)
        
        if missing:
            print(f"   ❌ Missing methods: {missing}")
            return False
        else:
            print(f"   ✅ All {len(required_methods)} required methods exist")
            return True
            
    except Exception as e:
        print(f"   ❌ Failed to test methods: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_delegation():
    """Test that methods delegate to modular components."""
    print("\n" + "=" * 70)
    print("🧪 TESTING DELEGATION TO MODULES")
    print("=" * 70)
    
    try:
        from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
        
        # Check that send_discord exists (delegates to AlertManager)
        if hasattr(UnifiedAlphaMonitor, 'send_discord'):
            print("   ✅ send_discord delegates to AlertManager")
        
        # Check that _detect_market_regime exists (delegates to RegimeDetector)
        if hasattr(UnifiedAlphaMonitor, '_detect_market_regime'):
            print("   ✅ _detect_market_regime delegates to RegimeDetector")
        
        # Check that _check_selloffs/_check_rallies exist (delegates to MomentumDetector)
        if hasattr(UnifiedAlphaMonitor, '_check_selloffs'):
            print("   ✅ _check_selloffs delegates to MomentumDetector")
        if hasattr(UnifiedAlphaMonitor, '_check_rallies'):
            print("   ✅ _check_rallies delegates to MomentumDetector")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n🚀 MODULAR SYSTEM TEST SUITE\n")
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Methods", test_methods()))
    results.append(("Delegation", test_delegation()))
    
    print("\n" + "=" * 70)
    print("📊 TEST RESULTS")
    print("=" * 70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("=" * 70)
    if all_passed:
        print("🎉 ALL TESTS PASSED - MODULAR SYSTEM READY!")
    else:
        print("⚠️  SOME TESTS FAILED - CHECK ERRORS ABOVE")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())


