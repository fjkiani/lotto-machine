#!/usr/bin/env python3
"""
Rolling 30-Day Window Backtest
Runs multiple 30-day periods with 1-minute data and aggregates results
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
from typing import List, Dict
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from backtesting.simulation.date_range_backtest import DateRangeBacktester
from backtest_with_filters import filter_trades, recalculate_metrics

# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

def get_trading_days(start_date: str, end_date: str) -> List[str]:
    """Get list of trading days (weekdays only)"""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    
    return days

def run_window_backtest(start_date: str, end_date: str, apply_filters: bool = False) -> Dict:
    """Run backtest for a single 30-day window"""
    print(f"\n📅 Window: {start_date} to {end_date}")
    
    backtester = DateRangeBacktester(symbols=['SPY', 'QQQ'])
    if 'options_flow' in backtester.detectors:
        del backtester.detectors['options_flow']
    
    # Get selloff/rally detector
    if 'selloff_rally' not in backtester.detectors:
        return None
    
    detector = backtester.detectors['selloff_rally']
    
    # Collect all trades from all dates in window
    all_trades = []
    trading_days = get_trading_days(start_date, end_date)
    
    for date in trading_days:
        result = detector.backtest_date(['SPY', 'QQQ'], date)
        if result and result.trades:
            all_trades.extend(result.trades)
    
    if not all_trades:
        print(f"   ⚠️  No trades generated")
        return {
            'start_date': start_date,
            'end_date': end_date,
            'trading_days': len(trading_days),
            'original_trades': 0,
            'filtered_trades': 0,
            'original_metrics': None,
            'filtered_metrics': None
        }
    
    # Original metrics
    original_metrics = recalculate_metrics(all_trades)
    
    # Filtered metrics (if requested)
    filtered_metrics = None
    filtered_trades = []
    if apply_filters:
        filtered_trades = filter_trades(
            all_trades,
            allow_rally=False,
            allow_long=False,
            allow_morning=False
        )
        filtered_metrics = recalculate_metrics(filtered_trades)
    
    print(f"   Original: {len(all_trades)} trades, {original_metrics['win_rate']:.1f}% WR, {original_metrics['total_pnl']:+.2f}% P&L")
    if apply_filters and filtered_metrics:
        print(f"   Filtered: {len(filtered_trades)} trades, {filtered_metrics['win_rate']:.1f}% WR, {filtered_metrics['total_pnl']:+.2f}% P&L")
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'trading_days': len(trading_days),
        'original_trades': len(all_trades),
        'filtered_trades': len(filtered_trades),
        'original_metrics': original_metrics,
        'filtered_metrics': filtered_metrics
    }

def main():
    print_header("🔄 ROLLING 30-DAY WINDOW BACKTEST")
    
    # Define rolling windows (each 30 days, using 1-minute data)
    # We can go back ~60 days total (30 days of 1-minute data available)
    today = datetime.now()
    
    windows = [
        # Window 1: Most recent 30 days
        {
            'start': (today - timedelta(days=30)).strftime('%Y-%m-%d'),
            'end': today.strftime('%Y-%m-%d'),
            'name': 'Most Recent 30 Days'
        },
        # Window 2: Previous 30 days (if within 30 days from today)
        {
            'start': (today - timedelta(days=60)).strftime('%Y-%m-%d'),
            'end': (today - timedelta(days=30)).strftime('%Y-%m-%d'),
            'name': 'Previous 30 Days'
        }
    ]
    
    # Also test the specific periods we know work
    known_periods = [
        {
            'start': '2025-12-05',
            'end': '2026-01-04',
            'name': 'Dec 5 - Jan 4 (30 days)'
        },
        {
            'start': '2025-12-29',
            'end': '2026-01-02',
            'name': 'Dec 29 - Jan 2 (5 days)'
        }
    ]
    
    all_windows = windows + known_periods
    
    print_info(f"Testing {len(all_windows)} rolling windows...")
    print_info("Each window uses 1-minute data (most accurate)\n")
    
    # Run backtests
    results = []
    for i, window in enumerate(all_windows, 1):
        print(f"\n[{i}/{len(all_windows)}] {window['name']}")
        result = run_window_backtest(window['start'], window['end'], apply_filters=True)
        if result:
            result['name'] = window['name']
            results.append(result)
    
    # Aggregate results
    print_header("📊 AGGREGATED RESULTS")
    
    # Original (unfiltered)
    all_original_trades = 0
    all_original_wins = 0
    all_original_pnl = 0.0
    
    # Filtered
    all_filtered_trades = 0
    all_filtered_wins = 0
    all_filtered_pnl = 0.0
    
    for result in results:
        if result['original_metrics']:
            all_original_trades += result['original_trades']
            all_original_wins += result['original_metrics']['wins']
            all_original_pnl += result['original_metrics']['total_pnl']
        
        if result['filtered_metrics']:
            all_filtered_trades += result['filtered_trades']
            all_filtered_wins += result['filtered_metrics']['wins']
            all_filtered_pnl += result['filtered_metrics']['total_pnl']
    
    # Calculate aggregated metrics
    original_wr = (all_original_wins / all_original_trades * 100) if all_original_trades > 0 else 0
    filtered_wr = (all_filtered_wins / all_filtered_trades * 100) if all_filtered_trades > 0 else 0
    
    print(f"\n{Colors.BOLD}ORIGINAL (No Filters):{Colors.RESET}")
    print(f"   Total Trades: {all_original_trades}")
    print(f"   Win Rate: {original_wr:.1f}%")
    print(f"   Total P&L: {all_original_pnl:+.2f}%")
    
    print(f"\n{Colors.BOLD}FILTERED (SELLOFF/SHORT/Afternoon Only):{Colors.RESET}")
    print(f"   Total Trades: {all_filtered_trades}")
    print(f"   Win Rate: {filtered_wr:.1f}%")
    print(f"   Total P&L: {all_filtered_pnl:+.2f}%")
    
    # Improvement
    print_header("📈 IMPROVEMENT")
    
    wr_improvement = filtered_wr - original_wr
    pnl_improvement = all_filtered_pnl - all_original_pnl
    trade_reduction = all_original_trades - all_filtered_trades
    trade_reduction_pct = (trade_reduction / all_original_trades * 100) if all_original_trades > 0 else 0
    
    print(f"   Win Rate: {original_wr:.1f}% → {filtered_wr:.1f}% ({wr_improvement:+.1f}%)")
    print(f"   Total P&L: {all_original_pnl:+.2f}% → {all_filtered_pnl:+.2f}% ({pnl_improvement:+.2f}%)")
    print(f"   Trades: {all_original_trades} → {all_filtered_trades} (-{trade_reduction}, -{trade_reduction_pct:.1f}%)")
    
    # Window-by-window breakdown
    print_header("📅 WINDOW-BY-WINDOW BREAKDOWN")
    
    for result in results:
        print(f"\n{result['name']} ({result['start_date']} to {result['end_date']}):")
        print(f"   Trading Days: {result['trading_days']}")
        
        if result['original_metrics']:
            print(f"   Original: {result['original_trades']} trades, {result['original_metrics']['win_rate']:.1f}% WR, {result['original_metrics']['total_pnl']:+.2f}% P&L")
        
        if result['filtered_metrics']:
            print(f"   Filtered: {result['filtered_trades']} trades, {result['filtered_metrics']['win_rate']:.1f}% WR, {result['filtered_metrics']['total_pnl']:+.2f}% P&L")
    
    # Save results
    output_file = Path('backtesting/reports/rolling_windows_backtest.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'windows_tested': len(results),
        'aggregated': {
            'original': {
                'total_trades': all_original_trades,
                'win_rate': original_wr,
                'total_pnl': all_original_pnl
            },
            'filtered': {
                'total_trades': all_filtered_trades,
                'win_rate': filtered_wr,
                'total_pnl': all_filtered_pnl
            },
            'improvement': {
                'win_rate_change': wr_improvement,
                'pnl_change': pnl_improvement,
                'trade_reduction': trade_reduction,
                'trade_reduction_pct': trade_reduction_pct
            }
        },
        'windows': results
    }
    
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n📁 Results saved to: {output_file}")
    print()

if __name__ == "__main__":
    main()

