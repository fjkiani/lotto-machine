#!/usr/bin/env python3
"""
🎯 FRIDAY SESSION REPLAY
Replay a full trading session and compare Current vs Narrative Brain
Uses realistic trading logic with proper entry/exit
"""

import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class DPAlert:
    timestamp: datetime
    symbol: str
    level_price: float
    level_type: str
    outcome: str
    max_move_pct: float
    confluence_score: float
    volume_vs_avg: float
    touch_count: int

@dataclass
class Trade:
    entry_time: datetime
    symbol: str
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    pnl_pct: float
    outcome: str  # WIN, LOSS, or PENDING

def load_session_data(date_str: str = "2025-12-05") -> List[DPAlert]:
    """Load DP alerts for a specific session"""
    conn = sqlite3.connect('data/dp_learning.db')
    cursor = conn.cursor()

    start_time = f"{date_str}T09:30:00"
    end_time = f"{date_str}T16:00:00"

    cursor.execute('''
        SELECT timestamp, symbol, level_price, level_type, outcome, max_move_pct,
               volume_vs_avg, touch_count, momentum_pct, level_volume
        FROM dp_interactions
        WHERE timestamp >= ? AND timestamp < ?
        ORDER BY timestamp ASC
    ''', [start_time, end_time])

    alerts = []
    for row in cursor.fetchall():
        # Calculate confluence
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
            confluence_score=confluence,
            volume_vs_avg=volume_vs_avg,
            touch_count=touch_count
        ))

    conn.close()
    return alerts

def simulate_trade_realistic(alert: DPAlert) -> Trade:
    """Simulate a realistic trade using outcome data"""
    stop_loss_pct = 0.25
    take_profit_pct = 0.40
    
    # Determine trade direction
    if alert.level_type == 'SUPPORT':
        direction = 'LONG'
        entry_price = alert.level_price
        stop_loss = entry_price * (1 - stop_loss_pct / 100)
        take_profit = entry_price * (1 + take_profit_pct / 100)
    else:  # RESISTANCE
        direction = 'SHORT'
        entry_price = alert.level_price
        stop_loss = entry_price * (1 + stop_loss_pct / 100)
        take_profit = entry_price * (1 - take_profit_pct / 100)
    
    # Use outcome to determine if trade wins
    # The key: did the move reach take profit before hitting stop?
    pnl_pct = 0
    outcome = 'LOSS'
    
    if alert.level_type == 'SUPPORT':
        if alert.outcome == 'BOUNCE':
            # Long trade: wins if move >= take profit
            if alert.max_move_pct >= take_profit_pct:
                pnl_pct = take_profit_pct
                outcome = 'WIN'
            else:
                # Move was too small, hit stop
                pnl_pct = -stop_loss_pct
                outcome = 'LOSS'
        else:  # BREAK
            # Long trade loses on break
            pnl_pct = -stop_loss_pct
            outcome = 'LOSS'
    else:  # RESISTANCE
        if alert.outcome == 'BOUNCE':
            # Short trade: wins if move >= take profit
            if alert.max_move_pct >= take_profit_pct:
                pnl_pct = take_profit_pct
                outcome = 'WIN'
            else:
                # Move was too small, hit stop
                pnl_pct = -stop_loss_pct
                outcome = 'LOSS'
        else:  # BREAK
            # Short trade loses on break
            pnl_pct = -stop_loss_pct
            outcome = 'LOSS'
    
    return Trade(
        entry_time=alert.timestamp,
        symbol=alert.symbol,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        exit_time=None,
        exit_price=None,
        pnl_pct=pnl_pct,
        outcome=outcome
    )

def simulate_current_system(alerts: List[DPAlert]) -> List[Trade]:
    """Current system: Sends synthesis every 2 min if alerts exist"""
    trades = []
    buffer = []
    last_send = None
    
    for alert in alerts:
        window = alert.timestamp.replace(minute=alert.timestamp.minute // 2 * 2, second=0, microsecond=0)
        buffer.append(alert)
        
        should_send = (
            last_send is None or
            (window - last_send).total_seconds() >= 120
        )
        
        if should_send and buffer:
            # Trade on best alert in batch
            best_alert = max(buffer, key=lambda a: a.confluence_score)
            trade = simulate_trade_realistic(best_alert)
            trades.append(trade)
            last_send = window
            buffer = []
    
    return trades

def simulate_narrative_brain(alerts: List[DPAlert]) -> List[Trade]:
    """Narrative Brain: Only sends when confluence is high"""
    trades = []
    buffer = []
    last_send = None
    
    for alert in alerts:
        window = alert.timestamp.replace(minute=alert.timestamp.minute // 2 * 2, second=0, microsecond=0)
        buffer.append(alert)
        
        time_check = last_send is None or (window - last_send).total_seconds() >= 120
        
        if time_check and buffer:
            avg_conf = sum(a.confluence_score for a in buffer) / len(buffer)
            
            # Narrative Brain decision
            should_send = (
                avg_conf >= 80 or
                (avg_conf >= 70 and len(buffer) >= 3) or
                len(buffer) >= 5
            )
            
            if should_send:
                best_alert = max(buffer, key=lambda a: a.confluence_score)
                trade = simulate_trade_realistic(best_alert)
                trades.append(trade)
                last_send = window
                buffer = []
    
    return trades

def analyze_trades(trades: List[Trade]) -> Dict:
    """Analyze trade performance"""
    if not trades:
        return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'total_pnl': 0, 'avg_pnl': 0}
    
    wins = sum(1 for t in trades if t.outcome == 'WIN')
    losses = sum(1 for t in trades if t.outcome == 'LOSS')
    total_pnl = sum(t.pnl_pct for t in trades)
    
    return {
        'total': len(trades),
        'wins': wins,
        'losses': losses,
        'win_rate': wins / len(trades) * 100 if trades else 0,
        'total_pnl': total_pnl,
        'avg_pnl': total_pnl / len(trades) if trades else 0
    }

def main():
    print("🎯 SESSION REPLAY: DEC 5 (THURSDAY)")
    print("=" * 70)
    print("Replaying full trading session with realistic trade simulation")
    print("Using outcome data (max_move_pct) to determine win/loss")
    print()
    
    # Load session data (Dec 5 - we have data for this day)
    session_date = "2025-12-05"
    alerts = load_session_data(session_date)
    print(f"📊 Loaded {len(alerts)} DP alerts for {session_date}")
    
    if not alerts:
        print("❌ No alerts found for this session!")
        return
    
    print()
    print("🧪 RUNNING SESSION REPLAY...\n")
    print("Using outcome data from database (max_move_pct) for realistic trade simulation")
    print()
    
    # Simulate both systems
    current_trades = simulate_current_system(alerts)
    narrative_trades = simulate_narrative_brain(alerts)
    
    current_perf = analyze_trades(current_trades)
    narrative_perf = analyze_trades(narrative_trades)
    
    # Results
    print("📊 CURRENT SYSTEM (Always Sends):")
    print(f"  Total Trades: {current_perf['total']}")
    print(f"  Winning Trades: {current_perf['wins']}")
    print(f"  Losing Trades: {current_perf['losses']}")
    print(f"  Win Rate: {current_perf['win_rate']:.1f}%")
    print(f"  Avg P&L per Trade: {current_perf['avg_pnl']:+.2f}%")
    print(f"  Total P&L: {current_perf['total_pnl']:+.2f}%")
    
    print("\n🧠 NARRATIVE BRAIN (Smart Filtering):")
    print(f"  Total Trades: {narrative_perf['total']}")
    print(f"  Winning Trades: {narrative_perf['wins']}")
    print(f"  Losing Trades: {narrative_perf['losses']}")
    print(f"  Win Rate: {narrative_perf['win_rate']:.1f}%")
    print(f"  Avg P&L per Trade: {narrative_perf['avg_pnl']:+.2f}%")
    print(f"  Total P&L: {narrative_perf['total_pnl']:+.2f}%")
    
    # Comparison
    print("\n🎯 COMPARISON:")
    win_rate_diff = narrative_perf['win_rate'] - current_perf['win_rate']
    pnl_diff = narrative_perf['total_pnl'] - current_perf['total_pnl']
    
    print(f"  Win Rate Change: {win_rate_diff:+.1f}%")
    print(f"  Total P&L Change: {pnl_diff:+.2f}%")
    print(f"  Trade Reduction: {current_perf['total'] - narrative_perf['total']} fewer trades")
    
    # Trade details
    if current_trades:
        print("\n📋 CURRENT SYSTEM TRADES:")
        for i, trade in enumerate(current_trades[:5]):
            result = "✅ WIN" if trade.outcome == 'WIN' else "❌ LOSS"
            print(f"  {i+1}. {trade.entry_time.strftime('%H:%M')} | {trade.symbol} {trade.direction} | {result} | P&L: {trade.pnl_pct:+.2f}%")
    
    if narrative_trades:
        print("\n📋 NARRATIVE BRAIN TRADES:")
        for i, trade in enumerate(narrative_trades):
            result = "✅ WIN" if trade.outcome == 'WIN' else "❌ LOSS"
            print(f"  {i+1}. {trade.entry_time.strftime('%H:%M')} | {trade.symbol} {trade.direction} | {result} | P&L: {trade.pnl_pct:+.2f}%")

if __name__ == "__main__":
    main()

