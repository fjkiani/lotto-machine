#!/usr/bin/env python3
"""
Validation Script for Signal Structure Refactor

Run this BEFORE refactoring to see what needs fixing
Run this AFTER refactoring to validate everything works
"""

import sys
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.append(str(Path(__file__).parent.parent / 'live_monitoring' / 'core'))
sys.path.append(str(Path(__file__).parent.parent / 'core'))
sys.path.append(str(Path(__file__).parent.parent))

from live_monitoring.core.signal_generator import SignalGenerator
from live_monitoring.core.lottery_signals import SignalAction, SignalType, LiveSignal

# Import test fixture
sys.path.append(str(Path(__file__).parent))
from fixtures.signal_test_data import create_test_institutional_context


def validate_signal_structure(signal, signal_name: str) -> dict:
    """
    Validate signal uses new structure
    
    Returns:
        dict with validation results
    """
    results = {
        'signal_name': signal_name,
        'has_new_fields': {},
        'has_old_fields': {},
        'type_correct': {},
        'passed': True
    }
    
    # Check NEW structure fields
    new_fields = {
        'action': True,
        'signal_type': True,
        'stop_price': True,
        'target_price': True,
        'rationale': True,
        'entry_price': True,
        'timestamp': True,
        'confidence': True
    }
    
    for field in new_fields:
        has_field = hasattr(signal, field)
        results['has_new_fields'][field] = has_field
        if not has_field:
            results['passed'] = False
            print(f"   ❌ Missing NEW field: {field}")
        else:
            print(f"   ✅ Has NEW field: {field}")
    
    # Check OLD structure fields (should NOT exist)
    old_fields = {
        'stop_loss': False,  # Should be stop_price
        'take_profit': False,  # Should be target_price
        'primary_reason': False,  # Should be rationale
        'current_price': False  # Should use entry_price
    }
    
    for field, should_exist in old_fields.items():
        has_field = hasattr(signal, field)
        results['has_old_fields'][field] = has_field
        if has_field and not should_exist:
            results['passed'] = False
            print(f"   ⚠️  WARNING: Has OLD field (should remove): {field}")
        elif not has_field and not should_exist:
            print(f"   ✅ No OLD field: {field} (correct)")
    
    # Check types (should be enums, but strings OK for now)
    if hasattr(signal, 'action'):
        if isinstance(signal.action, SignalAction):
            results['type_correct']['action'] = True
            print(f"   ✅ action type: SignalAction enum (correct)")
        elif isinstance(signal.action, str):
            results['type_correct']['action'] = False
            print(f"   ⚠️  action type: string (should be SignalAction enum)")
        else:
            results['type_correct']['action'] = False
            print(f"   ❌ action type: {type(signal.action)} (unexpected)")
    
    if hasattr(signal, 'signal_type'):
        if isinstance(signal.signal_type, SignalType):
            results['type_correct']['signal_type'] = True
            print(f"   ✅ signal_type: SignalType enum (correct)")
        elif isinstance(signal.signal_type, str):
            results['type_correct']['signal_type'] = False
            print(f"   ⚠️  signal_type: string (should be SignalType enum)")
        else:
            results['type_correct']['signal_type'] = False
            print(f"   ❌ signal_type: {type(signal.signal_type)} (unexpected)")
    
    return results


def main():
    """Run validation tests"""
    print("\n" + "="*80)
    print("🔍 SIGNAL STRUCTURE VALIDATION")
    print("="*80 + "\n")
    
    # Initialize generator
    print("📊 Initializing SignalGenerator...")
    generator = SignalGenerator(
        use_lottery_mode=False,
        api_key=None,
        use_sentiment=False,
        use_gamma=False
    )
    print("✅ SignalGenerator initialized\n")
    
    # Create test context
    print("📊 Creating test context...")
    test_context = create_test_institutional_context()
    print("✅ Test context created\n")
    
    results = []
    
    # Test 1: Squeeze signal
    print("="*80)
    print("TEST 1: _create_squeeze_signal()")
    print("="*80)
    try:
        signal = generator._create_squeeze_signal(
            symbol='SPY',
            price=662.50,
            context=test_context
        )
        if signal:
            result = validate_signal_structure(signal, "SQUEEZE")
            results.append(result)
        else:
            print("   ⚠️  Signal not generated (conditions not met)")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 2: Gamma signal
    print("="*80)
    print("TEST 2: _create_gamma_signal()")
    print("="*80)
    try:
        signal = generator._create_gamma_signal(
            symbol='SPY',
            price=662.50,
            context=test_context
        )
        if signal:
            result = validate_signal_structure(signal, "GAMMA")
            results.append(result)
        else:
            print("   ⚠️  Signal not generated (conditions not met)")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 3: DP signal
    print("="*80)
    print("TEST 3: _create_dp_signal()")
    print("="*80)
    try:
        signal = generator._create_dp_signal(
            symbol='SPY',
            price=662.50,
            context=test_context
        )
        if signal:
            result = validate_signal_structure(signal, "DP")
            results.append(result)
        else:
            print("   ⚠️  Signal not generated (conditions not met)")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 4: Breakdown signal
    print("="*80)
    print("TEST 4: _create_breakdown_signal()")
    print("="*80)
    try:
        signal = generator._create_breakdown_signal(
            symbol='SPY',
            price=658.00,  # Below support
            context=test_context
        )
        if signal:
            result = validate_signal_structure(signal, "BREAKDOWN")
            results.append(result)
        else:
            print("   ⚠️  Signal not generated (conditions not met)")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Test 5: Bearish flow signal
    print("="*80)
    print("TEST 5: _create_bearish_flow_signal()")
    print("="*80)
    try:
        # Modify context for bearish
        test_context.dp_buy_sell_ratio = 0.65
        test_context.dp_total_volume = 2_000_000
        
        signal = generator._create_bearish_flow_signal(
            symbol='SPY',
            price=662.50,
            context=test_context
        )
        if signal:
            result = validate_signal_structure(signal, "BEARISH_FLOW")
            results.append(result)
        else:
            print("   ⚠️  Signal not generated (conditions not met)")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
    
    # Summary
    print("="*80)
    print("📊 VALIDATION SUMMARY")
    print("="*80)
    
    if results:
        passed = sum(1 for r in results if r['passed'])
        total = len(results)
        print(f"\n✅ Passed: {passed}/{total}")
        
        for result in results:
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"   {status}: {result['signal_name']}")
    else:
        print("\n⚠️  No signals generated to validate (conditions not met)")
        print("   This is OK - signals only generate when thresholds are met")
    
    print("\n" + "="*80)
    print("Next step: Refactor signal creation methods to fix failures")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()

