#!/usr/bin/env python3
"""
Backtest with audit recommendations applied:
1. Disable RALLY signals (only SELLOFF)
2. Disable LONG trades (only SHORT)
3. Skip morning trades (9-12) (only afternoon 12-16)
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import json

sys.path.insert(0, str(Path(__file__).parent))

from backtesting.simulation.date_range_backtest import DateRangeBacktester, DailyBacktestResult, RangeBacktestResult
from backtesting.simulation.base_detector import Signal, TradeResult

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

def filter_trades(trades: List[TradeResult], 
                  allow_rally: bool = False,
                  allow_long: bool = False,
                  allow_morning: bool = False) -> List[TradeResult]:
    """
    Filter trades based on audit recommendations.
    
    Args:
        trades: List of TradeResult objects
        allow_rally: If False, filter out RALLY signals
        allow_long: If False, filter out LONG trades
        allow_morning: If False, filter out morning trades (9-12)
    
    Returns:
        Filtered list of trades
    """
    filtered = []
    
    for trade in trades:
        signal = trade.signal
        
        # Filter 1: RALLY signals
        if not allow_rally and signal.signal_type == 'RALLY':
            continue
        
        # Filter 2: LONG trades
        if not allow_long and signal.direction == 'LONG':
            continue
        
        # Filter 3: Morning trades (9-12)
        if not allow_morning:
            if hasattr(signal.timestamp, 'hour'):
                hour = signal.timestamp.hour
                if 9 <= hour < 12:
                    continue
            elif hasattr(signal.timestamp, 'strftime'):
                # Try to parse timestamp
                try:
                    ts = datetime.fromisoformat(str(signal.timestamp))
                    if 9 <= ts.hour < 12:
                        continue
                except:
                    pass
        
        filtered.append(trade)
    
    return filtered

def recalculate_metrics(trades: List[TradeResult]) -> Dict:
    """Recalculate metrics from filtered trades"""
    if not trades:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'timeouts': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'avg_pnl': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0
        }
    
    wins = [t for t in trades if t.outcome == 'WIN']
    losses = [t for t in trades if t.outcome == 'LOSS']
    timeouts = [t for t in trades if t.outcome == 'TIMEOUT']
    
    total_pnl = sum(t.pnl_pct for t in trades)
    avg_pnl = total_pnl / len(trades) if trades else 0
    avg_win = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
    
    # Profit factor
    total_wins = sum(t.pnl_pct for t in wins) if wins else 0
    total_losses = abs(sum(t.pnl_pct for t in losses)) if losses else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)
    
    return {
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'timeouts': len(timeouts),
        'win_rate': len(wins) / len(trades) * 100 if trades else 0,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor
    }

def main():
    print_header("🎯 BACKTEST WITH AUDIT FILTERS")
    
    # Run original backtest
    print_info("Running original backtest...")
    backtester = DateRangeBacktester(symbols=['SPY', 'QQQ'])
    
    # Remove options_flow (0% WR)
    if 'options_flow' in backtester.detectors:
        del backtester.detectors['options_flow']
    
    dates = ['2025-12-29', '2025-12-30', '2025-12-31', '2026-01-01', '2026-01-02']
    
    # Run backtest for each date
    original_results = []
    filtered_results = []
    
    for date in dates:
        print(f"\n📅 Processing {date}...")
        
        # Get selloff/rally results
        if 'selloff_rally' not in backtester.detectors:
            continue
        
        detector = backtester.detectors['selloff_rally']
        result = detector.backtest_date(['SPY', 'QQQ'], date)
        
        if not result or not result.trades:
            continue
        
        # Original trades
        original_trades = result.trades
        original_metrics = recalculate_metrics(original_trades)
        original_results.append({
            'date': date,
            'metrics': original_metrics,
            'trades': original_trades
        })
        
        # Filtered trades (SELLOFF only, SHORT only, Afternoon only)
        filtered_trades = filter_trades(
            original_trades,
            allow_rally=False,  # Disable RALLY
            allow_long=False,   # Disable LONG
            allow_morning=False # Disable morning
        )
        
        filtered_metrics = recalculate_metrics(filtered_trades)
        filtered_results.append({
            'date': date,
            'metrics': filtered_metrics,
            'trades': filtered_trades
        })
        
        print(f"   Original: {len(original_trades)} trades, {original_metrics['win_rate']:.1f}% WR, {original_metrics['total_pnl']:+.2f}% P&L")
        print(f"   Filtered: {len(filtered_trades)} trades, {filtered_metrics['win_rate']:.1f}% WR, {filtered_metrics['total_pnl']:+.2f}% P&L")
    
    # Aggregate results
    print_header("📊 COMPARISON: ORIGINAL vs FILTERED")
    
    # Original totals
    all_original_trades = []
    for r in original_results:
        all_original_trades.extend(r['trades'])
    
    original_totals = recalculate_metrics(all_original_trades)
    
    # Filtered totals
    all_filtered_trades = []
    for r in filtered_results:
        all_filtered_trades.extend(r['trades'])
    
    filtered_totals = recalculate_metrics(all_filtered_trades)
    
    # Print comparison
    print(f"\n{Colors.BOLD}ORIGINAL (No Filters):{Colors.RESET}")
    print(f"   Total Trades: {original_totals['total_trades']}")
    print(f"   Win Rate: {original_totals['win_rate']:.1f}%")
    print(f"   Total P&L: {original_totals['total_pnl']:+.2f}%")
    print(f"   Avg Win: {original_totals['avg_win']:+.2f}%")
    print(f"   Avg Loss: {original_totals['avg_loss']:+.2f}%")
    print(f"   Profit Factor: {original_totals['profit_factor']:.2f}")
    
    print(f"\n{Colors.BOLD}FILTERED (SELLOFF/SHORT/Afternoon Only):{Colors.RESET}")
    print(f"   Total Trades: {filtered_totals['total_trades']}")
    print(f"   Win Rate: {filtered_totals['win_rate']:.1f}%")
    print(f"   Total P&L: {filtered_totals['total_pnl']:+.2f}%")
    print(f"   Avg Win: {filtered_totals['avg_win']:+.2f}%")
    print(f"   Avg Loss: {filtered_totals['avg_loss']:+.2f}%")
    print(f"   Profit Factor: {filtered_totals['profit_factor']:.2f}")
    
    # Calculate improvement
    print_header("📈 IMPROVEMENT ANALYSIS")
    
    wr_improvement = filtered_totals['win_rate'] - original_totals['win_rate']
    pnl_improvement = filtered_totals['total_pnl'] - original_totals['total_pnl']
    trade_reduction = original_totals['total_trades'] - filtered_totals['total_trades']
    trade_reduction_pct = (trade_reduction / original_totals['total_trades'] * 100) if original_totals['total_trades'] > 0 else 0
    
    print(f"   Win Rate: {original_totals['win_rate']:.1f}% → {filtered_totals['win_rate']:.1f}% ({wr_improvement:+.1f}%)")
    print(f"   Total P&L: {original_totals['total_pnl']:+.2f}% → {filtered_totals['total_pnl']:+.2f}% ({pnl_improvement:+.2f}%)")
    print(f"   Trades: {original_totals['total_trades']} → {filtered_totals['total_trades']} (-{trade_reduction}, -{trade_reduction_pct:.1f}%)")
    print(f"   Profit Factor: {original_totals['profit_factor']:.2f} → {filtered_totals['profit_factor']:.2f}")
    
    # Validation
    print_header("✅ VALIDATION")
    
    if filtered_totals['win_rate'] >= 50:
        print_success(f"Win rate {filtered_totals['win_rate']:.1f}% meets 50% threshold!")
    else:
        print_error(f"Win rate {filtered_totals['win_rate']:.1f}% below 50% threshold")
    
    if filtered_totals['total_pnl'] > 0:
        print_success(f"P&L {filtered_totals['total_pnl']:+.2f}% is profitable!")
    else:
        print_error(f"P&L {filtered_totals['total_pnl']:+.2f}% is losing")
    
    if filtered_totals['profit_factor'] >= 1.5:
        print_success(f"Profit factor {filtered_totals['profit_factor']:.2f} is strong!")
    else:
        print_warning(f"Profit factor {filtered_totals['profit_factor']:.2f} is below 1.5")
    
    # Save results
    output_file = Path('backtesting/reports/backtest_filtered_comparison.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    comparison = {
        'timestamp': datetime.now().isoformat(),
        'dates': dates,
        'original': original_totals,
        'filtered': filtered_totals,
        'improvement': {
            'win_rate_change': wr_improvement,
            'pnl_change': pnl_improvement,
            'trade_reduction': trade_reduction,
            'trade_reduction_pct': trade_reduction_pct
        },
        'filters_applied': {
            'disable_rally': True,
            'disable_long': True,
            'disable_morning': True
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    
    print(f"\n📁 Results saved to: {output_file}")
    print()

if __name__ == "__main__":
    main()

