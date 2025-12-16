#!/usr/bin/env python3
"""
🔄 PRODUCTION DAY REPLAY
Replays what SHOULD have happened vs what actually happened

Usage:
    python3 replay_production_day.py --date 2025-12-11
"""

import argparse
from datetime import datetime
from backtesting.simulation.production_replay import ProductionReplaySimulator

def main():
    parser = argparse.ArgumentParser(description='Replay production day')
    parser.add_argument('--date', type=str, required=True, help='Date to replay (YYYY-MM-DD)')
    parser.add_argument('--symbol', type=str, default='SPY', help='Symbol to replay (default: SPY)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print(f"🔄 REPLAYING PRODUCTION DAY: {args.date}")
    print("=" * 80)
    print()
    
    simulator = ProductionReplaySimulator()
    result = simulator.replay_session(args.date, args.symbol)
    
    print(f"📊 REPLAY RESULTS:")
    print("-" * 80)
    print(f"  DP Levels Available: {result.dp_levels_available}")
    print(f"  DP Prints Available: {result.dp_prints_available}")
    print(f"  Expected Signals: {result.expected_signals}")
    print(f"  Actual Signals Fired (RTH): {result.actual_signals}")
    print()
    
    if result.threshold_hits:
        print("📏 THRESHOLD ANALYSIS:")
        print("-" * 80)
        print(f"  Levels >= 500K shares: {result.threshold_hits.get('500k_plus', 0)}")
        print(f"  Levels >= 1M shares: {result.threshold_hits.get('1m_plus', 0)}")
        print(f"  Levels >= 2M shares: {result.threshold_hits.get('2m_plus', 0)}")
        print(f"  Levels >= 5M shares: {result.threshold_hits.get('5m_plus', 0)}")
        print()
    
    print("🚨 SIGNAL GAP ANALYSIS:")
    print("-" * 80)
    if result.signal_gap_reasons:
        for reason in result.signal_gap_reasons:
            print(f"  {reason}")
    else:
        print("  ✅ No gap detected - signals fired as expected")
    print()
    
    if result.missing_signals:
        print("❌ MISSING SIGNALS (Should have fired but didn't):")
        print("-" * 80)
        for i, signal in enumerate(result.missing_signals[:10], 1):
            print(f"  {i}. {signal.get('symbol')} {signal.get('level_type')} ${signal.get('price', 0):.2f} - {signal.get('volume', 0):,} shares")
            print(f"     Reason: {signal.get('reason')}")
        
        if len(result.missing_signals) > 10:
            print(f"  ... and {len(result.missing_signals) - 10} more")
        print()
    
    print("=" * 80)
    
    # Now replay all symbols
    print()
    print("🔄 REPLAYING ALL SYMBOLS...")
    print()
    
    for symbol in ['SPY', 'QQQ']:
        print(f"\n{symbol}:")
        print("-" * 80)
        result = simulator.replay_session(args.date, symbol)
        print(f"  DP Levels: {result.dp_levels_available}")
        print(f"  Expected Signals: {result.expected_signals}")
        print(f"  Actual Signals: {result.actual_signals}")
        print(f"  Gap: {result.expected_signals - result.actual_signals}")
        
        if result.signal_gap_reasons:
            print(f"  Issues:")
            for reason in result.signal_gap_reasons[:3]:
                print(f"    {reason}")

if __name__ == '__main__':
    main()


