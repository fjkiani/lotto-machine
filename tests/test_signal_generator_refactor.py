#!/usr/bin/env python3
"""
Validation Tests for Signal Generator Refactor

These tests validate that signal creation methods use the NEW structure
Run these BEFORE refactoring to see what needs fixing
"""

import sys
import pytest
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.append(str(Path(__file__).parent.parent / 'live_monitoring' / 'core'))
sys.path.append(str(Path(__file__).parent.parent / 'core'))

from signal_generator import SignalGenerator
from lottery_signals import SignalAction, SignalType, LiveSignal, LotterySignal
from tests.fixtures.signal_test_data import (
    create_test_institutional_context,
    TEST_SQUEEZE_CONTEXT,
    TEST_SELLOFF_CONTEXT,
    EXPECTED_SQUEEZE_SIGNAL,
    EXPECTED_SELLOFF_SIGNAL
)


class TestSignalGeneratorRefactor:
    """Test signal generator uses new structure"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.generator = SignalGenerator(
            use_lottery_mode=False,
            api_key=None  # Use None for testing
        )
        self.test_context = create_test_institutional_context()
    
    def test_squeeze_signal_structure(self):
        """Test squeeze signal has correct new structure"""
        signal = self.generator._create_squeeze_signal(
            symbol='SPY',
            price=TEST_SQUEEZE_CONTEXT['current_price'],
            context=self.test_context
        )
        
        if signal is None:
            pytest.skip("Squeeze signal not generated (conditions not met)")
        
        # Validate NEW structure exists
        assert hasattr(signal, 'action'), "Missing 'action' field"
        assert hasattr(signal, 'signal_type'), "Missing 'signal_type' field"
        assert hasattr(signal, 'stop_price'), "Missing 'stop_price' field"
        assert hasattr(signal, 'target_price'), "Missing 'target_price' field"
        assert hasattr(signal, 'rationale'), "Missing 'rationale' field"
        
        # Validate types
        assert isinstance(signal.action, (SignalAction, str)), f"action is {type(signal.action)}, expected SignalAction or str"
        assert isinstance(signal.signal_type, (SignalType, str)), f"signal_type is {type(signal.signal_type)}, expected SignalType or str"
        
        # Validate OLD structure REMOVED (if present, log warning)
        if hasattr(signal, 'stop_loss'):
            print(f"⚠️  WARNING: Old field 'stop_loss' still exists (should be 'stop_price')")
        if hasattr(signal, 'take_profit'):
            print(f"⚠️  WARNING: Old field 'take_profit' still exists (should be 'target_price')")
        if hasattr(signal, 'primary_reason'):
            print(f"⚠️  WARNING: Old field 'primary_reason' still exists (should be 'rationale')")
        
        # If using new structure, validate values
        if isinstance(signal.action, SignalAction):
            assert signal.action == SignalAction.BUY, f"Expected BUY, got {signal.action}"
        if isinstance(signal.signal_type, SignalType):
            assert signal.signal_type == SignalType.SQUEEZE, f"Expected SQUEEZE, got {signal.signal_type}"
    
    def test_gamma_signal_structure(self):
        """Test gamma signal has correct new structure"""
        signal = self.generator._create_gamma_signal(
            symbol='SPY',
            price=662.50,
            context=self.test_context
        )
        
        if signal is None:
            pytest.skip("Gamma signal not generated (conditions not met)")
        
        # Validate NEW structure
        assert hasattr(signal, 'action'), "Missing 'action' field"
        assert hasattr(signal, 'signal_type'), "Missing 'signal_type' field"
        assert hasattr(signal, 'stop_price'), "Missing 'stop_price' field"
        assert hasattr(signal, 'target_price'), "Missing 'target_price' field"
        assert hasattr(signal, 'rationale'), "Missing 'rationale' field"
    
    def test_dp_signal_structure(self):
        """Test DP breakout/bounce signal has correct new structure"""
        signal = self.generator._create_dp_signal(
            symbol='SPY',
            price=662.50,
            context=self.test_context
        )
        
        if signal is None:
            pytest.skip("DP signal not generated (conditions not met)")
        
        # Validate NEW structure
        assert hasattr(signal, 'action'), "Missing 'action' field"
        assert hasattr(signal, 'signal_type'), "Missing 'signal_type' field"
        assert hasattr(signal, 'stop_price'), "Missing 'stop_price' field"
        assert hasattr(signal, 'target_price'), "Missing 'target_price' field"
        assert hasattr(signal, 'rationale'), "Missing 'rationale' field"
    
    def test_breakdown_signal_structure(self):
        """Test breakdown signal has correct new structure"""
        signal = self.generator._create_breakdown_signal(
            symbol='SPY',
            price=658.00,  # Below support
            context=self.test_context
        )
        
        if signal is None:
            pytest.skip("Breakdown signal not generated (conditions not met)")
        
        # Validate NEW structure
        assert hasattr(signal, 'action'), "Missing 'action' field"
        assert hasattr(signal, 'signal_type'), "Missing 'signal_type' field"
        assert hasattr(signal, 'stop_price'), "Missing 'stop_price' field"
        assert hasattr(signal, 'target_price'), "Missing 'target_price' field"
        assert hasattr(signal, 'rationale'), "Missing 'rationale' field"
        
        # Should be SELL signal
        if isinstance(signal.action, SignalAction):
            assert signal.action == SignalAction.SELL, f"Expected SELL, got {signal.action}"
    
    def test_bearish_flow_signal_structure(self):
        """Test bearish flow signal has correct new structure"""
        # Modify context for bearish flow
        self.test_context.dp_buy_sell_ratio = 0.65  # Bearish
        self.test_context.dp_total_volume = 2_000_000  # High volume
        
        signal = self.generator._create_bearish_flow_signal(
            symbol='SPY',
            price=662.50,
            context=self.test_context
        )
        
        if signal is None:
            pytest.skip("Bearish flow signal not generated (conditions not met)")
        
        # Validate NEW structure
        assert hasattr(signal, 'action'), "Missing 'action' field"
        assert hasattr(signal, 'signal_type'), "Missing 'signal_type' field"
        assert hasattr(signal, 'stop_price'), "Missing 'stop_price' field"
        assert hasattr(signal, 'target_price'), "Missing 'target_price' field"
        assert hasattr(signal, 'rationale'), "Missing 'rationale' field"
        
        # Should be SELL signal
        if isinstance(signal.action, SignalAction):
            assert signal.action == SignalAction.SELL, f"Expected SELL, got {signal.action}"
    
    def test_all_signals_use_new_structure(self):
        """Test that ALL generated signals use new structure"""
        # Generate all signals
        signals = self.generator._generate_regular_signals(
            symbol='SPY',
            current_price=662.50,
            inst_context=self.test_context,
            minute_bars=None
        )
        
        for signal in signals:
            # Validate NEW structure exists
            assert hasattr(signal, 'action'), f"Signal missing 'action': {type(signal)}"
            assert hasattr(signal, 'signal_type'), f"Signal missing 'signal_type': {type(signal)}"
            assert hasattr(signal, 'stop_price'), f"Signal missing 'stop_price': {type(signal)}"
            assert hasattr(signal, 'target_price'), f"Signal missing 'target_price': {type(signal)}"
            assert hasattr(signal, 'rationale'), f"Signal missing 'rationale': {type(signal)}"
            
            # Validate types (can be enum or string for now, but prefer enum)
            assert isinstance(signal.action, (SignalAction, str)), f"action is {type(signal.action)}"
            assert isinstance(signal.signal_type, (SignalType, str)), f"signal_type is {type(signal.signal_type)}"
            
            # Check for old fields
            old_fields = ['stop_loss', 'take_profit', 'primary_reason', 'current_price']
            for old_field in old_fields:
                if hasattr(signal, old_field):
                    print(f"⚠️  WARNING: Signal still has old field '{old_field}'")

