#!/usr/bin/env python3
"""
Test Narrative Enrichment in Signal Generation
Validates that narrative intelligence is wired and working.
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime

# Add paths
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'core'))
sys.path.append(str(Path(__file__).parent / 'core'))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from live_monitoring.core.signal_generator import SignalGenerator
from ultra_institutional_engine import InstitutionalContext

def test_narrative_enrichment():
    """
    Test that narrative enrichment is working in signal generation.
    """
    print("=" * 120)
    print("🧪 TESTING NARRATIVE ENRICHMENT IN SIGNAL GENERATION")
    print("=" * 120)
    
    # Create signal generator with narrative enabled
    print("\n🔧 Initializing SignalGenerator with narrative enrichment...")
    signal_gen = SignalGenerator(
        use_narrative=True,
        use_sentiment=False,  # Disable for cleaner test
        use_gamma=False,      # Disable for cleaner test
        use_lottery_mode=False  # Disable for cleaner test
    )
    
    # Create mock institutional context (simplified for testing)
    print("\n📊 Creating mock institutional context...")
    
    # Mock context with strong bearish institutional flow
    inst_context = InstitutionalContext(
        symbol="SPY",
        date=datetime.now().strftime("%Y-%m-%d"),
        dp_battlegrounds=[660.0, 662.0, 665.0],  # Support/resistance levels
        dp_total_volume=5_000_000,
        dp_buy_sell_ratio=0.35,  # BEARISH (35% buy, 65% sell)
        short_volume_pct=55.0,
        short_interest_pct=12.0,
        days_to_cover=2.5,
        put_call_ratio=1.35,  # BEARISH (more puts)
        max_pain_strike=660.0,
        gamma_pressure=0.45,
        institutional_buying_pressure=0.35,  # BEARISH
        squeeze_potential=0.25,
        borrow_fee_pct=0.5,
        ftd_volume=100000,
        vix_level=18.5
    )
    
    # Generate signals for SPY
    print("\n🎯 Generating signals for SPY @ $662.50...")
    current_price = 662.50
    
    signals = signal_gen.generate_signals(
        symbol="SPY",
        current_price=current_price,
        inst_context=inst_context,
        minute_bars=None,
        account_value=100000.0
    )
    
    # Display results
    print("\n" + "=" * 120)
    print(f"📊 SIGNAL GENERATION RESULTS ({len(signals)} signals)")
    print("=" * 120)
    
    if not signals:
        print("⚠️  No signals generated (thresholds not met or narrative vetoed)")
    else:
        for i, signal in enumerate(signals, 1):
            print(f"\n🎯 SIGNAL #{i}:")
            print(f"   Symbol: {signal.symbol}")
            print(f"   Action: {signal.action.value}")
            print(f"   Type: {signal.signal_type.value}")
            print(f"   Entry: ${signal.entry_price:.2f}")
            print(f"   Target: ${signal.target_price:.2f}")
            print(f"   Stop: ${signal.stop_price:.2f}")
            print(f"   Confidence: {signal.confidence:.0%}")
            print(f"   Master Signal: {'YES' if signal.is_master_signal else 'NO'}")
            print(f"   Rationale: {signal.rationale}")
            if signal.warnings:
                print(f"   Warnings: {', '.join(signal.warnings)}")
    
    print("\n" + "=" * 120)
    print("✅ Test complete!")
    print("=" * 120)
    
    # Check if narrative was applied
    if signals:
        narrative_applied = any("NARRATIVE:" in s.rationale for s in signals)
        if narrative_applied:
            print("\n✅ NARRATIVE ENRICHMENT VERIFIED - Causal chains added to rationale!")
        else:
            print("\n⚠️  Narrative enrichment may have been skipped (check logs for API errors)")
    
    print("\n📋 Check logs above for narrative enrichment details (confidence boosts/vetoes)")

if __name__ == "__main__":
    test_narrative_enrichment()

