#!/usr/bin/env python3
"""
🔥 REDDIT BACKTESTING MASTER SCRIPT

This script provides a complete Reddit signal backtesting workflow:

1. REAL DATA ANALYSIS - Uses actual ChartExchange Reddit data + yfinance prices
2. SIGNAL GENERATION - Uses production RedditExploiter to generate signals
3. HISTORICAL VALIDATION - Checks if similar price patterns led to profitable trades
4. SIGNAL TRACKING - Records signals for forward validation over time
5. PERFORMANCE REPORTING - Tracks win rates by signal type

Usage:
    python3 backtest_reddit_full.py --analyze      # Analyze current signals
    python3 backtest_reddit_full.py --record       # Record signals for tracking
    python3 backtest_reddit_full.py --update       # Update tracked signals with new prices
    python3 backtest_reddit_full.py --report       # Show performance report
    python3 backtest_reddit_full.py --all          # Do everything

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backtesting.simulation.reddit_real_backtest import RealRedditBacktester
from backtesting.simulation.reddit_signal_tracker import RedditSignalTracker
from backtesting.simulation.reddit_enhanced_backtest import EnhancedRedditBacktester


def analyze_current_signals():
    """Analyze current Reddit signals using real data."""
    print("\n" + "="*80)
    print("🔍 ANALYZING CURRENT REDDIT SIGNALS (REAL DATA)")
    print("="*80)
    
    backtester = RealRedditBacktester()
    
    # Extended symbol list including potential movers
    symbols = [
        # Mega-caps
        'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'AMD',
        # Popular Reddit stocks  
        'GME', 'PLTR', 'SOFI', 'RIVN', 'LCID', 'NIO',
        # Other active stocks
        'COIN', 'HOOD', 'MARA', 'RIOT'
    ]
    
    print(f"\nSymbols: {', '.join(symbols)}")
    print(f"Data Sources: ChartExchange Reddit API + yfinance")
    
    results = backtester.analyze_current_signals(symbols)
    
    # Summarize actionable signals
    actionable = []
    watch = []
    avoid = []
    
    for symbol, data in results.items():
        signal = data.get('signal', {})
        if not signal:
            continue
            
        if signal.get('action') in ['LONG', 'SHORT']:
            actionable.append({
                'symbol': symbol,
                'action': signal['action'],
                'type': signal.get('type'),
                'strength': signal.get('strength', 0),
                'price': data.get('price_data', {}).get('current_price', 0),
                'sentiment': data.get('reddit_data', {}).get('avg_sentiment', 0),
                'validation': data.get('historical_validation', {}).get('pattern_match', 'N/A')
            })
        elif signal.get('action') in ['WATCH_LONG', 'WATCH_SHORT']:
            watch.append(symbol)
        elif signal.get('action') == 'AVOID':
            avoid.append(symbol)
    
    print(f"\n{'─'*80}")
    print(f"📊 SIGNAL SUMMARY")
    print(f"{'─'*80}")
    
    if actionable:
        print(f"\n🎯 ACTIONABLE SIGNALS ({len(actionable)}):")
        for a in sorted(actionable, key=lambda x: x['strength'], reverse=True):
            emoji = '🚀' if a['action'] == 'LONG' else '📉'
            print(f"   {emoji} {a['symbol']:5} | {a['action']:5} | {a['type']:20} | "
                  f"Str: {a['strength']:3.0f}% | ${a['price']:.2f} | Val: {a['validation']}")
    
    if watch:
        print(f"\n👀 WATCH LIST ({len(watch)}): {', '.join(watch)}")
    
    if avoid:
        print(f"\n⚠️ AVOID ({len(avoid)}): {', '.join(avoid)}")
    
    return results


def record_signals():
    """Record current signals for forward tracking."""
    print("\n" + "="*80)
    print("📝 RECORDING SIGNALS FOR TRACKING")
    print("="*80)
    
    tracker = RedditSignalTracker()
    backtester = RealRedditBacktester()
    
    symbols = [
        'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'AMD',
        'GME', 'PLTR', 'SOFI', 'RIVN', 'LCID', 'NIO',
        'COIN', 'HOOD', 'MARA', 'RIOT'
    ]
    
    results = backtester.analyze_current_signals(symbols)
    
    recorded = 0
    for symbol, data in results.items():
        signal = data.get('signal')
        price = data.get('price_data', {})
        reddit = data.get('reddit_data', {})
        
        if signal and signal.get('type') and signal.get('action') not in ['NEUTRAL', None]:
            signal_id = tracker.record_signal(
                symbol=symbol,
                signal_type=signal['type'],
                action=signal['action'],
                strength=signal.get('strength', 0),
                entry_price=price.get('current_price', 0),
                sentiment=reddit.get('avg_sentiment', 0),
                reasoning=signal.get('reasoning', [])
            )
            
            if signal_id > 0:
                recorded += 1
                action_emoji = '🚀' if signal['action'] == 'LONG' else '📉' if signal['action'] == 'SHORT' else '⚠️'
                print(f"   {action_emoji} {symbol}: {signal['action']} ({signal['type']}) @ ${price.get('current_price', 0):.2f}")
    
    print(f"\n✅ Recorded {recorded} signals for tracking")


def update_tracked_signals():
    """Update tracked signals with current prices."""
    print("\n" + "="*80)
    print("🔄 UPDATING TRACKED SIGNALS")
    print("="*80)
    
    tracker = RedditSignalTracker()
    tracker.update_prices()
    
    print("✅ Price updates complete")


def show_report():
    """Show performance report."""
    tracker = RedditSignalTracker()
    tracker.print_report()


def run_enhanced_analysis():
    """Run enhanced analysis with DP + institutional data."""
    print("\n" + "="*80)
    print("🔥 ENHANCED ANALYSIS (Reddit + DP + Institutional)")
    print("="*80)
    
    backtester = EnhancedRedditBacktester()
    
    symbols = [
        'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'AMD',
        'GME', 'PLTR', 'SOFI', 'RIVN', 'COIN', 'HOOD', 'MARA'
    ]
    
    results = backtester.run_full_analysis(symbols)
    backtester.print_report(results)
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Reddit Signal Backtesting')
    parser.add_argument('--analyze', action='store_true', help='Analyze current signals (basic)')
    parser.add_argument('--enhanced', action='store_true', help='Enhanced analysis with DP + institutional')
    parser.add_argument('--record', action='store_true', help='Record signals for tracking')
    parser.add_argument('--update', action='store_true', help='Update tracked signal prices')
    parser.add_argument('--report', action='store_true', help='Show performance report')
    parser.add_argument('--all', action='store_true', help='Do everything')
    
    args = parser.parse_args()
    
    if not any([args.analyze, args.enhanced, args.record, args.update, args.report, args.all]):
        # Default: show enhanced analysis
        args.enhanced = True
    
    print("="*80)
    print("🔥 REDDIT SIGNAL BACKTESTING SYSTEM")
    print("="*80)
    print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.enhanced or args.all:
        run_enhanced_analysis()
    
    if args.analyze:
        analyze_current_signals()
    
    if args.all or args.record:
        record_signals()
    
    if args.all or args.update:
        update_tracked_signals()
    
    if args.all or args.report:
        show_report()
    
    print("\n" + "="*80)
    print("✅ BACKTESTING COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

