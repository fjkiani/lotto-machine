#!/usr/bin/env python3
"""
Deep audit of backtest performance to understand why win rate is below 50%
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from backtesting.simulation.date_range_backtest import DateRangeBacktester

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

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

def analyze_trades(detector, date_str):
    """Analyze individual trades for a date"""
    result = detector.backtest_date(['SPY', 'QQQ'], date_str)
    
    if not result or not result.trades:
        return None
    
    trades = result.trades
    
    analysis = {
        'date': date_str,
        'total_trades': len(trades),
        'wins': [t for t in trades if t.outcome == 'WIN'],
        'losses': [t for t in trades if t.outcome == 'LOSS'],
        'timeouts': [t for t in trades if t.outcome == 'TIMEOUT'],
        'by_direction': defaultdict(list),
        'by_signal_type': defaultdict(list),
        'risk_reward_ratios': [],
        'entry_times': [],
        'hold_times': []
    }
    
    for trade in trades:
        # Group by direction
        analysis['by_direction'][trade.signal.direction].append(trade)
        
        # Group by signal type
        analysis['by_signal_type'][trade.signal.signal_type].append(trade)
        
        # Calculate R/R
        entry = trade.signal.entry_price
        stop = trade.signal.stop_price
        target = trade.signal.target_price
        
        if trade.signal.direction == 'LONG':
            risk = abs(entry - stop) / entry * 100
            reward = abs(target - entry) / entry * 100
        else:  # SHORT
            risk = abs(stop - entry) / entry * 100
            reward = abs(entry - target) / entry * 100
        
        if risk > 0:
            rr = reward / risk
            analysis['risk_reward_ratios'].append(rr)
        
        # Entry time
        if hasattr(trade.signal.timestamp, 'hour'):
            analysis['entry_times'].append(trade.signal.timestamp.hour)
        
        # Hold time
        if trade.bars_held:
            analysis['hold_times'].append(trade.bars_held)
    
    return analysis

def main():
    print_header("🔍 DEEP PERFORMANCE AUDIT")
    
    # Run backtest for each day
    backtester = DateRangeBacktester(symbols=['SPY', 'QQQ'])
    if 'options_flow' in backtester.detectors:
        del backtester.detectors['options_flow']
    
    dates = ['2025-12-29', '2025-12-30', '2025-12-31', '2026-01-01', '2026-01-02']
    
    all_analyses = []
    all_trades = []
    
    for date in dates:
        print(f"\n📅 Analyzing {date}...")
        analysis = analyze_trades(backtester.detectors['selloff_rally'], date)
        if analysis:
            all_analyses.append(analysis)
            all_trades.extend(analysis['wins'] + analysis['losses'] + analysis['timeouts'])
    
    # Overall statistics
    print_header("📊 OVERALL STATISTICS")
    
    total_trades = len(all_trades)
    total_wins = sum(1 for t in all_trades if t.outcome == 'WIN')
    total_losses = sum(1 for t in all_trades if t.outcome == 'LOSS')
    total_timeouts = sum(1 for t in all_trades if t.outcome == 'TIMEOUT')
    
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    
    print_info(f"Total Trades: {total_trades}")
    print_info(f"Wins: {total_wins} ({total_wins/total_trades*100:.1f}%)")
    print_info(f"Losses: {total_losses} ({total_losses/total_trades*100:.1f}%)")
    print_info(f"Timeouts: {total_timeouts} ({total_timeouts/total_trades*100:.1f}%)")
    print_info(f"Win Rate: {win_rate:.1f}%")
    
    # P&L breakdown
    total_pnl = sum(t.pnl_pct for t in all_trades)
    avg_win = sum(t.pnl_pct for t in all_trades if t.outcome == 'WIN') / total_wins if total_wins > 0 else 0
    avg_loss = sum(t.pnl_pct for t in all_trades if t.outcome == 'LOSS') / total_losses if total_losses > 0 else 0
    
    print_info(f"\nP&L Analysis:")
    print_info(f"Total P&L: {total_pnl:+.2f}%")
    print_info(f"Avg Win: {avg_win:+.2f}%")
    print_info(f"Avg Loss: {avg_loss:+.2f}%")
    
    if avg_loss != 0:
        profit_factor = abs(avg_win * total_wins / (avg_loss * total_losses)) if total_losses > 0 else float('inf')
        print_info(f"Profit Factor: {profit_factor:.2f}")
    
    # Risk/Reward analysis
    print_header("📈 RISK/REWARD ANALYSIS")
    
    all_rr = []
    for analysis in all_analyses:
        all_rr.extend(analysis['risk_reward_ratios'])
    
    if all_rr:
        avg_rr = sum(all_rr) / len(all_rr)
        min_rr = min(all_rr)
        max_rr = max(all_rr)
        
        print_info(f"Avg R/R: {avg_rr:.2f}:1")
        print_info(f"Min R/R: {min_rr:.2f}:1")
        print_info(f"Max R/R: {max_rr:.2f}:1")
        
        # Check if R/R compensates for win rate
        if avg_rr >= 1.5 and win_rate >= 40:
            print_success(f"R/R ({avg_rr:.2f}:1) may compensate for {win_rate:.1f}% win rate")
        elif avg_rr < 1.5:
            print_warning(f"R/R ({avg_rr:.2f}:1) is too low - need higher win rate or better R/R")
    
    # By direction
    print_header("📊 BY DIRECTION")
    
    long_trades = [t for t in all_trades if t.signal.direction == 'LONG']
    short_trades = [t for t in all_trades if t.signal.direction == 'SHORT']
    
    if long_trades:
        long_wins = sum(1 for t in long_trades if t.outcome == 'WIN')
        long_wr = long_wins / len(long_trades) * 100
        long_pnl = sum(t.pnl_pct for t in long_trades)
        print_info(f"LONG: {len(long_trades)} trades | {long_wr:.1f}% WR | {long_pnl:+.2f}% P&L")
    
    if short_trades:
        short_wins = sum(1 for t in short_trades if t.outcome == 'WIN')
        short_wr = short_wins / len(short_trades) * 100
        short_pnl = sum(t.pnl_pct for t in short_trades)
        print_info(f"SHORT: {len(short_trades)} trades | {short_wr:.1f}% WR | {short_pnl:+.2f}% P&L")
    
    # By signal type
    print_header("📊 BY SIGNAL TYPE")
    
    selloff_trades = [t for t in all_trades if t.signal.signal_type == 'SELLOFF']
    rally_trades = [t for t in all_trades if t.signal.signal_type == 'RALLY']
    
    if selloff_trades:
        selloff_wins = sum(1 for t in selloff_trades if t.outcome == 'WIN')
        selloff_wr = selloff_wins / len(selloff_trades) * 100
        selloff_pnl = sum(t.pnl_pct for t in selloff_trades)
        print_info(f"SELLOFF: {len(selloff_trades)} trades | {selloff_wr:.1f}% WR | {selloff_pnl:+.2f}% P&L")
    
    if rally_trades:
        rally_wins = sum(1 for t in rally_trades if t.outcome == 'WIN')
        rally_wr = rally_wins / len(rally_trades) * 100
        rally_pnl = sum(t.pnl_pct for t in rally_trades)
        print_info(f"RALLY: {len(rally_trades)} trades | {rally_wr:.1f}% WR | {rally_pnl:+.2f}% P&L")
    
    # Time of day analysis
    print_header("⏰ TIME OF DAY ANALYSIS")
    
    morning_trades = [t for t in all_trades if hasattr(t.signal.timestamp, 'hour') and 9 <= t.signal.timestamp.hour < 12]
    afternoon_trades = [t for t in all_trades if hasattr(t.signal.timestamp, 'hour') and 12 <= t.signal.timestamp.hour < 16]
    
    if morning_trades:
        morning_wins = sum(1 for t in morning_trades if t.outcome == 'WIN')
        morning_wr = morning_wins / len(morning_trades) * 100
        morning_pnl = sum(t.pnl_pct for t in morning_trades)
        print_info(f"Morning (9-12): {len(morning_trades)} trades | {morning_wr:.1f}% WR | {morning_pnl:+.2f}% P&L")
    
    if afternoon_trades:
        afternoon_wins = sum(1 for t in afternoon_trades if t.outcome == 'WIN')
        afternoon_wr = afternoon_wins / len(afternoon_trades) * 100
        afternoon_pnl = sum(t.pnl_pct for t in afternoon_trades)
        print_info(f"Afternoon (12-16): {len(afternoon_trades)} trades | {afternoon_wr:.1f}% WR | {afternoon_pnl:+.2f}% P&L")
    
    # Loss analysis
    print_header("❌ LOSS ANALYSIS")
    
    if total_losses > 0:
        losses = [t for t in all_trades if t.outcome == 'LOSS']
        
        # Biggest losses
        losses_sorted = sorted(losses, key=lambda x: x.pnl_pct)
        print_info("Biggest Losses:")
        for i, trade in enumerate(losses_sorted[:5], 1):
            print(f"   {i}. {trade.signal.symbol} {trade.signal.direction} @ ${trade.signal.entry_price:.2f} -> {trade.pnl_pct:+.2f}%")
            print(f"      Signal: {trade.signal.signal_type} | Confidence: {trade.signal.confidence:.0f}%")
            if hasattr(trade.signal.timestamp, 'strftime'):
                print(f"      Time: {trade.signal.timestamp.strftime('%H:%M')}")
        
        # Check if losses hit stop or target
        stop_losses = [t for t in losses if abs(t.pnl_pct - (-0.20)) < 0.01]  # Hit stop loss
        print_info(f"\nLosses that hit stop loss: {len(stop_losses)}/{total_losses} ({len(stop_losses)/total_losses*100:.1f}%)")
    
    # Win analysis
    print_header("✅ WIN ANALYSIS")
    
    if total_wins > 0:
        wins = [t for t in all_trades if t.outcome == 'WIN']
        
        # Biggest wins
        wins_sorted = sorted(wins, key=lambda x: x.pnl_pct, reverse=True)
        print_info("Biggest Wins:")
        for i, trade in enumerate(wins_sorted[:5], 1):
            print(f"   {i}. {trade.signal.symbol} {trade.signal.direction} @ ${trade.signal.entry_price:.2f} -> {trade.pnl_pct:+.2f}%")
            print(f"      Signal: {trade.signal.signal_type} | Confidence: {trade.signal.confidence:.0f}%")
            if hasattr(trade.signal.timestamp, 'strftime'):
                print(f"      Time: {trade.signal.timestamp.strftime('%H:%M')}")
    
    # Recommendations
    print_header("💡 RECOMMENDATIONS")
    
    recommendations = []
    
    if win_rate < 50:
        recommendations.append(f"❌ Win rate {win_rate:.1f}% is below 50% threshold")
        recommendations.append("   → Need to improve signal quality or adjust thresholds")
    
    if avg_rr and avg_rr < 1.5:
        recommendations.append(f"⚠️  Avg R/R {avg_rr:.2f}:1 is below 1.5:1 target")
        recommendations.append("   → Consider wider targets or tighter stops")
    
    if total_losses > total_wins * 1.5:
        recommendations.append(f"⚠️  Losses ({total_losses}) significantly outnumber wins ({total_wins})")
        recommendations.append("   → May need stricter entry criteria")
    
    if not recommendations:
        recommendations.append("✅ No major issues detected")
    
    for rec in recommendations:
        print(rec)
    
    print()

if __name__ == "__main__":
    main()

