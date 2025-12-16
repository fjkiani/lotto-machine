#!/usr/bin/env python3
"""
🔧 Test Gamma Tracker P/C Ratio Thresholds

Tests different threshold combinations to find optimal settings.
"""

import os
import sys
from dotenv import load_dotenv
from live_monitoring.exploitation.gamma_tracker import GammaTracker
import yfinance as yf

load_dotenv()

# Test configurations
TEST_CONFIGS = [
    {
        'name': 'Baseline',
        'MIN_PC_BULLISH': 0.7,
        'MAX_PC_BEARISH': 1.3,
        'MIN_DISTANCE': 1.0
    },
    {
        'name': 'More Selective',
        'MIN_PC_BULLISH': 0.6,
        'MAX_PC_BEARISH': 1.4,
        'MIN_DISTANCE': 1.0
    },
    {
        'name': 'More Signals',
        'MIN_PC_BULLISH': 0.8,
        'MAX_PC_BEARISH': 1.2,
        'MIN_DISTANCE': 0.5
    },
    {
        'name': 'Higher Conviction',
        'MIN_PC_BULLISH': 0.7,
        'MAX_PC_BEARISH': 1.3,
        'MIN_DISTANCE': 1.5
    },
]

def test_config(tracker, config, symbols=['SPY', 'QQQ']):
    """Test a threshold configuration"""
    # Temporarily modify tracker thresholds
    original_min_pc = tracker.MIN_PC_FOR_BULLISH
    original_max_pc = tracker.MAX_PC_FOR_BEARISH
    original_min_dist = tracker.MIN_DISTANCE_PCT
    
    tracker.MIN_PC_FOR_BULLISH = config['MIN_PC_BULLISH']
    tracker.MAX_PC_FOR_BEARISH = config['MAX_PC_BEARISH']
    tracker.MIN_DISTANCE_PCT = config['MIN_DISTANCE']
    
    signals_found = 0
    total_score = 0
    
    for symbol in symbols:
        ticker = yf.Ticker(symbol)
        exps = ticker.options
        
        # Test multiple expirations
        for exp_idx in range(3, min(15, len(exps))):
            try:
                signal = tracker.analyze(symbol, expiration_idx=exp_idx)
                if signal:
                    signals_found += 1
                    total_score += signal.score
                    break  # One signal per symbol
            except:
                continue
    
    # Restore original thresholds
    tracker.MIN_PC_FOR_BULLISH = original_min_pc
    tracker.MAX_PC_FOR_BEARISH = original_max_pc
    tracker.MIN_DISTANCE_PCT = original_min_dist
    
    avg_score = total_score / signals_found if signals_found > 0 else 0
    
    return {
        'signals': signals_found,
        'avg_score': avg_score
    }

def main():
    print("="*70)
    print("🔧 TESTING GAMMA TRACKER P/C RATIO THRESHOLDS")
    print("="*70)
    print()
    
    tracker = GammaTracker()
    
    results = []
    
    for config in TEST_CONFIGS:
        print(f"Testing: {config['name']}")
        print(f"  MIN_PC_BULLISH: {config['MIN_PC_BULLISH']}")
        print(f"  MAX_PC_BEARISH: {config['MAX_PC_BEARISH']}")
        print(f"  MIN_DISTANCE: {config['MIN_DISTANCE']}%")
        
        result = test_config(tracker, config)
        results.append({
            'config': config,
            'signals': result['signals'],
            'avg_score': result['avg_score']
        })
        
        print(f"  ✅ Signals Found: {result['signals']}")
        print(f"  ✅ Avg Score: {result['avg_score']:.1f}/100")
        print()
    
    # Summary table
    print("="*70)
    print("📊 RESULTS SUMMARY")
    print("="*70)
    print(f"{'Config':<20} {'Signals':<10} {'Avg Score':<12} {'Notes'}")
    print("-"*70)
    
    for r in results:
        config = r['config']
        signals = r['signals']
        score = r['avg_score']
        
        notes = []
        if signals == 0:
            notes.append("No signals")
        elif signals >= 2:
            notes.append("Good coverage")
        if score >= 60:
            notes.append("High quality")
        
        notes_str = ", ".join(notes) if notes else "-"
        
        print(f"{config['name']:<20} {signals:<10} {score:<12.1f} {notes_str}")
    
    print("="*70)

if __name__ == "__main__":
    main()


