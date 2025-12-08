#!/usr/bin/env python3
"""
🎯 THRESHOLD SENSITIVITY ANALYSIS
Test different Narrative Brain thresholds to find optimal balance
"""

import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class DPAlert:
    timestamp: datetime
    symbol: str
    level_price: float
    level_type: str
    outcome: str
    max_move_pct: float
    confluence_score: float

def load_data() -> List[DPAlert]:
    """Load historical DP alerts"""
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
        confluence = 50
        volume_vs_avg = row[6] or 1.0
        touch_count = row[7] or 1
        momentum_pct = row[8] or 0.0
        level_volume = row[9] or 0
        
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
        
        alerts.append(DPAlert(
            timestamp=datetime.fromisoformat(row[0]),
            symbol=row[1],
            level_price=row[2],
            level_type=row[3],
            outcome=row[4] or 'UNKNOWN',
            max_move_pct=row[5] or 0,
            confluence_score=confluence
        ))

    conn.close()
    return alerts

def calculate_pnl(alert: DPAlert) -> float:
    """Calculate trade P&L"""
    stop_loss_pct = 0.25
    take_profit_pct = 0.40
    
    if alert.level_type == 'SUPPORT':
        if alert.outcome == 'BOUNCE':
            return take_profit_pct if alert.max_move_pct >= take_profit_pct else -stop_loss_pct
        else:
            return -stop_loss_pct
    else:
        if alert.outcome == 'BOUNCE':
            return take_profit_pct if alert.max_move_pct >= take_profit_pct else -stop_loss_pct
        else:
            return -stop_loss_pct

def test_threshold(alerts: List[DPAlert], min_confluence: float, min_alerts: int) -> Dict:
    """Test a specific threshold configuration"""
    trades = []
    buffer = []
    last_send = None
    
    for alert in alerts:
        window = alert.timestamp.replace(minute=alert.timestamp.minute // 2 * 2, second=0, microsecond=0)
        buffer.append(alert)
        
        time_check = last_send is None or (window - last_send).total_seconds() >= 120
        
        if time_check and buffer:
            avg_conf = sum(a.confluence_score for a in buffer) / len(buffer)
            
            should_send = (
                avg_conf >= min_confluence or
                (avg_conf >= min_confluence - 10 and len(buffer) >= min_alerts) or
                len(buffer) >= 5
            )
            
            if should_send:
                best = max(buffer, key=lambda a: a.confluence_score)
                pnl = calculate_pnl(best)
                trades.append({'alert': best, 'pnl': pnl})
                last_send = window
                buffer = []
    
    if not trades:
        return {'trades': 0, 'wins': 0, 'win_rate': 0, 'total_pnl': 0, 'avg_pnl': 0}
    
    wins = sum(1 for t in trades if t['pnl'] > 0)
    total_pnl = sum(t['pnl'] for t in trades)
    
    return {
        'trades': len(trades),
        'wins': wins,
        'win_rate': wins / len(trades) * 100,
        'total_pnl': total_pnl,
        'avg_pnl': total_pnl / len(trades)
    }

def main():
    print("🎯 NARRATIVE BRAIN THRESHOLD SENSITIVITY ANALYSIS")
    print("=" * 70)
    print("Testing different confluence thresholds to find optimal balance")
    print()
    
    alerts = load_data()
    print(f"📊 Testing with {len(alerts)} historical alerts")
    print()
    
    # Test different thresholds
    thresholds = [
        (50, 2, "Very Low (≥50% or 2+ alerts)"),
        (55, 2, "Low (≥55% or 2+ alerts)"),
        (60, 2, "Medium (≥60% or 2+ alerts)"),
        (65, 3, "Medium-High (≥65% or 3+ alerts)"),
        (70, 3, "High (≥70% or 3+ alerts)"),
        (75, 3, "Very High (≥75% or 3+ alerts)"),
        (80, 3, "Exceptional (≥80% or 3+ alerts)"),
    ]
    
    print("📊 RESULTS BY THRESHOLD:")
    print("=" * 70)
    print(f"{'Threshold':<30} {'Trades':<8} {'Win Rate':<10} {'Avg P&L':<10} {'Total P&L':<10}")
    print("-" * 70)
    
    results = []
    for min_conf, min_alerts, label in thresholds:
        result = test_threshold(alerts, min_conf, min_alerts)
        results.append((label, result))
        print(f"{label:<30} {result['trades']:<8} {result['win_rate']:>6.1f}%   {result['avg_pnl']:>+7.2f}%   {result['total_pnl']:>+7.2f}%")
    
    # Find best threshold
    print()
    print("🎯 ANALYSIS:")
    print("=" * 70)
    
    # Best win rate
    best_wr = max(results, key=lambda x: x[1]['win_rate'])
    print(f"✅ Best Win Rate: {best_wr[0]} ({best_wr[1]['win_rate']:.1f}%)")
    
    # Best total P&L
    best_pnl = max(results, key=lambda x: x[1]['total_pnl'])
    print(f"✅ Best Total P&L: {best_pnl[0]} ({best_pnl[1]['total_pnl']:+.2f}%)")
    
    # Best efficiency (P&L per trade)
    best_eff = max([r for r in results if r[1]['trades'] > 0], key=lambda x: x[1]['avg_pnl'])
    print(f"✅ Best Efficiency: {best_eff[0]} ({best_eff[1]['avg_pnl']:+.2f}% per trade)")
    
    print()
    print("💡 RECOMMENDATION:")
    print("=" * 70)
    
    # Current system baseline
    baseline = test_threshold(alerts, 0, 1)  # Always send
    print(f"Current System (always sends): {baseline['trades']} trades, {baseline['win_rate']:.1f}% win rate, {baseline['total_pnl']:+.2f}% P&L")
    
    # Find threshold that beats baseline
    better = [r for r in results if r[1]['total_pnl'] > baseline['total_pnl']]
    if better:
        best = max(better, key=lambda x: x[1]['total_pnl'])
        print(f"✅ Narrative Brain ({best[0]}): {best[1]['trades']} trades, {best[1]['win_rate']:.1f}% win rate, {best[1]['total_pnl']:+.2f}% P&L")
        print(f"   Improvement: {best[1]['total_pnl'] - baseline['total_pnl']:+.2f}% better P&L")
    else:
        print("⚠️  All thresholds perform similarly or worse")
        print("   This suggests the data quality is the issue, not the filtering")

if __name__ == "__main__":
    main()


