#!/usr/bin/env python3
"""
Test Fixtures for Signal Structure Refactor

Test data for validating signal creation methods use new structure
"""

import sys
from pathlib import Path

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent / 'live_monitoring' / 'core'))

from lottery_signals import SignalAction, SignalType
from datetime import datetime
from ultra_institutional_engine import InstitutionalContext


# Test data for each signal type
TEST_SQUEEZE_CONTEXT = {
    'symbol': 'SPY',
    'current_price': 662.50,
    'dp_support': 660.00,
    'short_interest': 15.5,
    'days_to_cover': 3.2,
    'put_call_ratio': 0.45,
    'confidence': 0.82
}

TEST_SELLOFF_CONTEXT = {
    'symbol': 'QQQ',
    'current_price': 450.20,
    'momentum': -0.87,
    'volume_spike': 2.3,
    'confidence': 0.78
}

TEST_GAMMA_CONTEXT = {
    'symbol': 'SPY',
    'current_price': 662.50,
    'dp_support': 660.00,
    'put_call_ratio': 0.45,
    'max_pain': 665.00,
    'confidence': 0.80
}

TEST_BREAKOUT_CONTEXT = {
    'symbol': 'SPY',
    'current_price': 662.50,
    'dp_resistance': 660.00,
    'dp_buy_sell_ratio': 1.6,
    'confidence': 0.85
}

TEST_BREAKDOWN_CONTEXT = {
    'symbol': 'SPY',
    'current_price': 658.00,
    'dp_support': 660.00,
    'dp_buy_sell_ratio': 0.65,
    'put_call_ratio': 1.3,
    'confidence': 0.75
}

# Expected outputs (NEW structure)
EXPECTED_SQUEEZE_SIGNAL = {
    'symbol': 'SPY',
    'action': SignalAction.BUY,
    'signal_type': SignalType.SQUEEZE,
    'entry_price': 662.50,
    'stop_price': 658.00,  # Was 'stop_loss'
    'target_price': 672.00,  # Was 'take_profit'
    'confidence': 0.82,
    'rationale': 'SQUEEZE SETUP'  # Was 'primary_reason'
}

EXPECTED_SELLOFF_SIGNAL = {
    'symbol': 'QQQ',
    'action': SignalAction.SELL,
    'signal_type': SignalType.SELLOFF,
    'entry_price': 450.20,
    'stop_price': 454.70,  # 1% above
    'target_price': 441.20,  # 2% below
    'confidence': 0.78,
    'rationale': 'REAL-TIME SELLOFF'  # Was 'primary_reason'
}


def create_test_institutional_context() -> InstitutionalContext:
    """
    Create a test InstitutionalContext for testing
    
    Returns:
        InstitutionalContext with test data
    """
    # Create context with all required fields
    context = InstitutionalContext(
        symbol='SPY',
        date='2025-01-20',
        # Dark Pool
        dp_battlegrounds=[660.00, 665.00, 670.00],
        dp_total_volume=5_000_000,
        dp_buy_sell_ratio=1.6,
        dp_avg_print_size=50000.0,
        dark_pool_pct=35.0,
        # Short Data
        short_volume_pct=15.5,
        short_interest=100_000_000,
        days_to_cover=3.2,
        borrow_fee_rate=3.5,
        # Options
        max_pain=665.00,
        put_call_ratio=0.45,
        total_option_oi=10_000_000,
        # Composite Scores
        institutional_buying_pressure=0.70,
        squeeze_potential=0.75,
        gamma_pressure=0.72
    )
    
    return context

