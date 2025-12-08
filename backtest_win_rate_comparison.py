#!/usr/bin/env python3
"""
🎯 WIN RATE COMPARISON: Current System vs Narrative Brain Control
Tests actual trading performance, not just alert frequency
"""

import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class DPAlert:
    """Historical DP alert with outcome"""
    timestamp: datetime
    symbol: str
    level_price: float
    level_type: str
    outcome: str
    max_move_pct: float
    confluence_score: float

def load_historical_data() -> List[DPAlert]:
    """Load real DP interactions with outcomes"""
    conn = sqlite3.connect('data/dp_learning.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT timestamp, symbol, level_price, level_type, outcome, max_move_pct,
               volume_vs_avg, touch_count, momentum_pct, level_volume
        FROM dp_interactions
        WHERE timestamp >= ? AND outcome != 'PENDING'
        ORDER BY timestamp ASC
    ''', [(datetime.now() - timedelta(days=7)).isoformat()])

    alerts = []
    for row in cursor.fetchall():
        # Calculate confluence (same as backtest)
        confluence = 50  # Base
        volume_vs_avg = row[6] or 1.0  # volume_vs_avg
        touch_count = row[7] or 1  # touch_count
        momentum_pct = row[8] or 0.0  # momentum_pct
        level_volume = row[9] or 0  # level_volume
        
        if volume_vs_avg >= 2.0:
            confluence += 20
        elif volume_vs_avg >= 1.5:
            confluence += 10
            
        confluence += min(touch_count - 1, 3) * 10
        
        if abs(momentum_pct) >= 0.5:
            confluence += 15
        elif abs(momentum_pct) >= 0.25:
            confluence += 5
            
        if level_volume >= 500000:
            confluence += 10
            
        confluence = min(confluence, 100)
        
        alert = DPAlert(
            timestamp=datetime.fromisoformat(row[0]),  # timestamp
            symbol=row[1],  # symbol
            level_price=row[2],  # level_price
            level_type=row[3],  # level_type
            outcome=row[4] or 'UNKNOWN',  # outcome
            max_move_pct=row[5] or 0,  # max_move_pct
            confluence_score=confluence
        )
        alerts.append(alert)

    conn.close()
    return alerts

def calculate_trade_pnl(alert: DPAlert) -> float:
    """Calculate realistic P&L for a trade based on outcome"""
    stop_loss_pct = 0.25
    take_profit_pct = 0.40
    
    if alert.level_type == 'SUPPORT':
        if alert.outcome == 'BOUNCE':
            # Long trade: wins if move >= target
            if alert.max_move_pct >= take_profit_pct:
                return take_profit_pct  # Hit target
            elif alert.max_move_pct > 0:
                return -stop_loss_pct  # Small move, hit stop
            else:
                return -stop_loss_pct  # No move, hit stop
        else:  # BREAK
            # Long trade: loses on break
            return -stop_loss_pct
    else:  # RESISTANCE
        if alert.outcome == 'BOUNCE':
            # Short trade: wins if move >= target
            if alert.max_move_pct >= take_profit_pct:
                return take_profit_pct
            elif alert.max_move_pct > 0:
                return -stop_loss_pct
            else:
                return -stop_loss_pct
        else:  # BREAK
            # Short trade: loses on break
            return -stop_loss_pct

def simulate_current_system(alerts: List[DPAlert]) -> Dict:
    """Current system: Sends synthesis every 2 min if alerts exist"""
    trades = []
    current_buffer = []
    last_send_time = None
    
    # Group into 2-minute windows (synthesis runs every 2 min)
    for alert in alerts:
        # Round to 2-minute window
        window_key = alert.timestamp.replace(
            minute=alert.timestamp.minute // 2 * 2,
            second=0,
            microsecond=0
        )
        
        current_buffer.append(alert)
        
        # Current system: Send if been 2+ minutes since last send
        should_send = (
            last_send_time is None or
            (window_key - last_send_time).total_seconds() >= 120
        )
        
        if should_send and current_buffer:
            # Take all buffered alerts as one synthesis
            # Trade on the highest confluence alert in the batch
            best_alert = max(current_buffer, key=lambda a: a.confluence_score)
            pnl = calculate_trade_pnl(best_alert)
            
            trades.append({
                'timestamp': window_key,
                'alert': best_alert,
                'pnl': pnl,
                'confluence': best_alert.confluence_score,
                'alerts_in_batch': len(current_buffer)
            })
            
            last_send_time = window_key
            current_buffer = []
    
    return calculate_performance(trades)

def simulate_narrative_brain(alerts: List[DPAlert]) -> Dict:
    """Narrative Brain: Only sends when confluence is high"""
    trades = []
    current_buffer = []
    last_send_time = None
    
    # Group into 2-minute windows
    for alert in alerts:
        window_key = alert.timestamp.replace(
            minute=alert.timestamp.minute // 2 * 2,
            second=0,
            microsecond=0
        )
        
        current_buffer.append(alert)
        
        # Check if we should send (every 2 min)
        time_check = (
            last_send_time is None or
            (window_key - last_send_time).total_seconds() >= 120
        )
        
        if time_check and current_buffer:
            # Calculate average confluence
            avg_confluence = sum(a.confluence_score for a in current_buffer) / len(current_buffer)
            
            # Narrative Brain decision logic
            should_send = (
                avg_confluence >= 80 or  # Exceptional
                (avg_confluence >= 70 and len(current_buffer) >= 3) or  # Strong + confirmation
                len(current_buffer) >= 5  # Critical mass
            )
            
            if should_send:
                # Trade on best alert in batch
                best_alert = max(current_buffer, key=lambda a: a.confluence_score)
                pnl = calculate_trade_pnl(best_alert)
                
                trades.append({
                    'timestamp': window_key,
                    'alert': best_alert,
                    'pnl': pnl,
                    'confluence': best_alert.confluence_score,
                    'avg_confluence': avg_confluence,
                    'alerts_in_batch': len(current_buffer)
                })
                
                last_send_time = window_key
                current_buffer = []
            # If not sending, keep buffer for next check
    
    return calculate_performance(trades)

def calculate_performance(trades: List[Dict]) -> Dict:
    """Calculate win rate and P&L metrics"""
    if not trades:
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'avg_pnl': 0,
            'total_pnl': 0
        }
    
    winning = sum(1 for t in trades if t['pnl'] > 0)
    losing = sum(1 for t in trades if t['pnl'] < 0)
    total_pnl = sum(t['pnl'] for t in trades)
    
    return {
        'total_trades': len(trades),
        'winning_trades': winning,
        'losing_trades': losing,
        'win_rate': (winning / len(trades) * 100) if trades else 0,
        'avg_pnl': total_pnl / len(trades) if trades else 0,
        'total_pnl': total_pnl,
        'trades': trades
    }

def main():
    print("🎯 WIN RATE COMPARISON: Current vs Narrative Brain")
    print("=" * 70)
    print("Testing ACTUAL trading performance on real historical data")
    print()
    
    # Load data
    alerts = load_historical_data()
    print(f"📊 Loaded {len(alerts)} historical DP alerts with outcomes")
    
    if not alerts:
        print("❌ No data found!")
        return
    
    # Show data quality
    print(f"\n📈 Data Quality:")
    avg_confluence = sum(a.confluence_score for a in alerts) / len(alerts)
    print(f"  Average Confluence: {avg_confluence:.1f}")
    print(f"  High Confluence (≥70): {sum(1 for a in alerts if a.confluence_score >= 70)} alerts")
    print(f"  Medium Confluence (50-69): {sum(1 for a in alerts if 50 <= a.confluence_score < 70)} alerts")
    print(f"  Low Confluence (<50): {sum(1 for a in alerts if a.confluence_score < 50)} alerts")
    
    # Run simulations
    print("\n🧪 RUNNING BACKTESTS...\n")
    
    current_perf = simulate_current_system(alerts)
    narrative_perf = simulate_narrative_brain(alerts)
    
    # Results
    print("📊 CURRENT SYSTEM (Always Sends):")
    print(f"  Total Trades: {current_perf['total_trades']}")
    print(f"  Winning Trades: {current_perf['winning_trades']}")
    print(f"  Losing Trades: {current_perf['losing_trades']}")
    print(f"  Win Rate: {current_perf['win_rate']:.1f}%")
    print(f"  Avg P&L per Trade: {current_perf['avg_pnl']:+.2f}%")
    print(f"  Total P&L: {current_perf['total_pnl']:+.2f}%")
    
    print("\n🧠 NARRATIVE BRAIN (Smart Filtering):")
    print(f"  Total Trades: {narrative_perf['total_trades']}")
    print(f"  Winning Trades: {narrative_perf['winning_trades']}")
    print(f"  Losing Trades: {narrative_perf['losing_trades']}")
    print(f"  Win Rate: {narrative_perf['win_rate']:.1f}%")
    print(f"  Avg P&L per Trade: {narrative_perf['avg_pnl']:+.2f}%")
    print(f"  Total P&L: {narrative_perf['total_pnl']:+.2f}%")
    
    # Comparison
    print("\n🎯 COMPARISON:")
    win_rate_diff = narrative_perf['win_rate'] - current_perf['win_rate']
    trade_reduction = current_perf['total_trades'] - narrative_perf['total_trades']
    
    print(f"  Win Rate Change: {win_rate_diff:+.1f}%")
    print(f"  Trade Reduction: {trade_reduction} fewer trades ({trade_reduction/current_perf['total_trades']*100:.1f}% fewer)")
    print(f"  Avg P&L Change: {narrative_perf['avg_pnl'] - current_perf['avg_pnl']:+.2f}%")
    
    # Analysis
    print("\n💡 ANALYSIS:")
    if win_rate_diff > 0:
        print(f"  ✅ Narrative Brain IMPROVES win rate by {win_rate_diff:.1f}%")
        print(f"  ✅ Quality filtering works - fewer trades, better win rate")
    elif win_rate_diff < -5:
        print(f"  ❌ Narrative Brain REDUCES win rate by {abs(win_rate_diff):.1f}%")
        print(f"  ⚠️  Filtering may be too aggressive - missing profitable trades")
    else:
        print(f"  ⚠️  Win rate similar ({win_rate_diff:+.1f}%)")
        print(f"  ✅ But Narrative Brain reduces spam by {trade_reduction} trades")
    
    # Show sample trades
    if narrative_perf['trades']:
        print("\n📋 SAMPLE NARRATIVE BRAIN TRADES:")
        for i, trade in enumerate(narrative_perf['trades'][:5]):
            result = "✅ WIN" if trade['pnl'] > 0 else "❌ LOSS"
            print(f"  {i+1}. {trade['timestamp'].strftime('%m-%d %H:%M')} | "
                  f"Conf:{trade['confluence']:.0f} | {result} | P&L: {trade['pnl']:+.2f}%")

if __name__ == "__main__":
    main()

