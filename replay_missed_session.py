#!/usr/bin/env python3
"""
🔄 REPLAY MISSED SESSION
Reconstruct what SHOULD have happened when monitor was offline
"""

import sys
import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class DPLevel:
    price: float
    volume: int
    level_type: str

@dataclass
class LevelHit:
    timestamp: datetime
    symbol: str
    level: DPLevel
    hit_price: float
    distance_pct: float
    move_after: float
    outcome: str

class MissedSessionReplay:
    """Replay what should have happened during missed session"""
    
    def __init__(self, db_path: str = "data/dp_learning.db"):
        self.db_path = db_path
    
    def get_known_levels(self, symbol: str, limit: int = 10) -> List[DPLevel]:
        """Get known DP levels from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT level_price, level_volume, level_type
            FROM dp_interactions
            WHERE symbol = ?
            ORDER BY level_volume DESC
            LIMIT ?
        """, (symbol, limit))
        
        levels = []
        for price, volume, level_type in cursor.fetchall():
            levels.append(DPLevel(
                price=price,
                volume=volume or 0,
                level_type=level_type or "UNKNOWN"
            ))
        
        conn.close()
        return levels
    
    def get_intraday_data(self, symbol: str, date: str) -> pd.DataFrame:
        """Fetch intraday price data"""
        ticker = yf.Ticker(symbol)
        
        # Get that specific day's data (1-minute bars)
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)
        
        df = ticker.history(start=start, end=end, interval='1m')
        
        if df.empty:
            # Try 5-minute bars
            df = ticker.history(start=start, end=end, interval='5m')
        
        return df
    
    def detect_level_hits(self, df: pd.DataFrame, levels: List[DPLevel], symbol: str) -> List[LevelHit]:
        """Detect when price hit each DP level"""
        hits = []
        
        for level in levels:
            # Find bars where price crossed the level
            level_hits = df[(df['Low'] <= level.price) & (df['High'] >= level.price)]
            
            if not level_hits.empty:
                # Take the first hit
                first_hit_idx = level_hits.index[0]
                first_hit = level_hits.iloc[0]
                
                # Calculate distance from level to close
                distance_pct = abs(first_hit['Close'] - level.price) / level.price * 100
                
                # Calculate move after (next 10 bars)
                try:
                    idx_pos = df.index.get_loc(first_hit_idx)
                    if idx_pos + 10 < len(df):
                        future_bars = df.iloc[idx_pos:idx_pos+10]
                        max_up = (future_bars['High'].max() - level.price) / level.price * 100
                        max_down = (level.price - future_bars['Low'].min()) / level.price * 100
                        
                        if max_up > max_down:
                            move_after = max_up
                            outcome = "BREAK" if level.level_type == "RESISTANCE" else "BOUNCE"
                        else:
                            move_after = -max_down
                            outcome = "BOUNCE" if level.level_type == "SUPPORT" else "FADE"
                    else:
                        move_after = 0
                        outcome = "PENDING"
                except:
                    move_after = 0
                    outcome = "UNKNOWN"
                
                hit = LevelHit(
                    timestamp=first_hit_idx,
                    symbol=symbol,
                    level=level,
                    hit_price=first_hit['Close'],
                    distance_pct=distance_pct,
                    move_after=move_after,
                    outcome=outcome
                )
                hits.append(hit)
        
        # Sort by time
        hits.sort(key=lambda x: x.timestamp)
        return hits
    
    def generate_alerts(self, hits: List[LevelHit]) -> Tuple[List[Dict], List[Dict]]:
        """Generate DP alerts and synthesis alerts"""
        dp_alerts = []
        synthesis_alerts = []
        
        alert_buffer = []
        
        for i, hit in enumerate(hits, 1):
            # DP Alert
            dp_alert = {
                'timestamp': hit.timestamp,
                'type': 'DP_ALERT',
                'symbol': hit.symbol,
                'level_price': hit.level.price,
                'level_volume': hit.level.volume,
                'level_type': hit.level.level_type,
                'hit_price': hit.hit_price,
                'distance_pct': hit.distance_pct,
                'outcome': hit.outcome,
                'move_after': hit.move_after,
                'action': 'LONG' if hit.outcome in ['BOUNCE', 'BREAK'] else 'SHORT',
                'confidence': self._calculate_confidence(hit)
            }
            dp_alerts.append(dp_alert)
            alert_buffer.append(dp_alert)
            
            # Check if synthesis should fire (2+ alerts)
            if len(alert_buffer) >= 2:
                # Calculate confluence
                avg_confidence = sum(a['confidence'] for a in alert_buffer) / len(alert_buffer)
                
                if avg_confidence >= 60:
                    synthesis_alert = {
                        'timestamp': hit.timestamp,
                        'type': 'SYNTHESIS',
                        'symbol': hit.symbol,
                        'alert_count': len(alert_buffer),
                        'confluence': avg_confidence,
                        'levels_hit': [f"${a['level_price']:.2f}" for a in alert_buffer],
                        'actions': [a['action'] for a in alert_buffer],
                        'reasoning': self._generate_reasoning(alert_buffer)
                    }
                    synthesis_alerts.append(synthesis_alert)
        
        return dp_alerts, synthesis_alerts
    
    def _calculate_confidence(self, hit: LevelHit) -> float:
        """Calculate confidence score (0-100)"""
        score = 50
        
        # Level volume significance
        if hit.level.volume >= 2_000_000:
            score += 25
        elif hit.level.volume >= 1_000_000:
            score += 15
        elif hit.level.volume >= 500_000:
            score += 5
        
        # Distance to level (closer = better)
        if hit.distance_pct < 0.05:
            score += 15
        elif hit.distance_pct < 0.10:
            score += 10
        elif hit.distance_pct < 0.20:
            score += 5
        
        # Outcome quality
        if hit.outcome in ['BOUNCE', 'BREAK']:
            score += 10
        
        return min(score, 100)
    
    def _generate_reasoning(self, alerts: List[Dict]) -> str:
        """Generate reasoning for synthesis"""
        symbols = set(a['symbol'] for a in alerts)
        actions = [a['action'] for a in alerts]
        levels = [f"${a['level_price']:.2f}" for a in alerts]
        
        if len(set(actions)) == 1:
            # All same direction
            return f"Multiple {actions[0]} signals confluent: {', '.join(levels)}"
        else:
            # Mixed
            return f"Mixed signals at {', '.join(levels)} - {len(set(symbols))} symbols active"
    
    def print_report(self, date: str, symbol: str, dp_alerts: List[Dict], synthesis_alerts: List[Dict]):
        """Print formatted report"""
        print("=" * 80)
        print(f"🔄 REPLAY: WHAT WE SHOULD HAVE CAUGHT - {date}")
        print("=" * 80)
        print(f"\nSymbol: {symbol}")
        print(f"Session: Market Hours (9:30 AM - 4:00 PM ET)")
        
        if not dp_alerts:
            print("\n❌ No level hits detected during session")
            return
        
        print(f"\n📊 SUMMARY:")
        print(f"   DP Alerts: {len(dp_alerts)}")
        print(f"   Synthesis Alerts: {len(synthesis_alerts)}")
        print(f"   Total Signals: {len(dp_alerts) + len(synthesis_alerts)}")
        
        print("\n" + "=" * 80)
        print("🎯 DP ALERTS (What monitor should have sent):")
        print("=" * 80)
        
        for i, alert in enumerate(dp_alerts, 1):
            ts = alert['timestamp'].strftime('%H:%M')
            print(f"\n{i}. {ts} | {alert['symbol']} @ ${alert['level_price']:.2f}")
            print(f"   Level Volume: {alert['level_volume']:,} shares")
            print(f"   Level Type: {alert['level_type']}")
            print(f"   Hit Price: ${alert['hit_price']:.2f} (distance: {alert['distance_pct']:.2f}%)")
            print(f"   Outcome: {alert['outcome']} | Move: {alert['move_after']:+.2f}%")
            print(f"   Action: {alert['action']} | Confidence: {alert['confidence']:.0f}%")
        
        if synthesis_alerts:
            print("\n" + "=" * 80)
            print("🧠 SYNTHESIS ALERTS (Unified intelligence):")
            print("=" * 80)
            
            for i, alert in enumerate(synthesis_alerts, 1):
                ts = alert['timestamp'].strftime('%H:%M')
                print(f"\n{i}. {ts} | {alert['symbol']} SYNTHESIS")
                print(f"   Alert Count: {alert['alert_count']}")
                print(f"   Confluence: {alert['confluence']:.0f}%")
                print(f"   Levels: {', '.join(alert['levels_hit'])}")
                print(f"   Actions: {', '.join(set(alert['actions']))}")
                print(f"   Reasoning: {alert['reasoning']}")
        
        print("\n" + "=" * 80)
        print("💡 WHAT WE LEARNED:")
        print("=" * 80)
        
        winning_trades = [a for a in dp_alerts if a['move_after'] > 0]
        losing_trades = [a for a in dp_alerts if a['move_after'] < 0]
        
        if dp_alerts:
            win_rate = len(winning_trades) / len(dp_alerts) * 100
            avg_win = sum(a['move_after'] for a in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(a['move_after'] for a in losing_trades) / len(losing_trades) if losing_trades else 0
            
            print(f"\n   Win Rate: {win_rate:.0f}% ({len(winning_trades)}/{len(dp_alerts)})")
            print(f"   Avg Win: +{avg_win:.2f}%")
            print(f"   Avg Loss: {avg_loss:.2f}%")
            
            if win_rate >= 70:
                print("\n   ✅ HIGH QUALITY SIGNALS - System would have performed well")
            elif win_rate >= 50:
                print("\n   ⚠️  MIXED SIGNALS - System would have been breakeven")
            else:
                print("\n   ❌ LOW QUALITY SIGNALS - System would have lost money")
        
        print("\n" + "=" * 80)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Replay missed trading session')
    parser.add_argument('--date', required=True, help='Date (YYYY-MM-DD)')
    parser.add_argument('--symbol', default='SPY', help='Symbol (default: SPY)')
    
    args = parser.parse_args()
    
    replay = MissedSessionReplay()
    
    print(f"\n🔍 Loading known DP levels for {args.symbol}...")
    levels = replay.get_known_levels(args.symbol)
    print(f"   Found {len(levels)} levels")
    
    print(f"\n📈 Fetching price data for {args.date}...")
    df = replay.get_intraday_data(args.symbol, args.date)
    
    if df.empty:
        print(f"   ❌ No price data available for {args.date}")
        return
    
    print(f"   Loaded {len(df)} bars")
    print(f"   Range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")
    
    print(f"\n🎯 Detecting level hits...")
    hits = replay.detect_level_hits(df, levels, args.symbol)
    print(f"   Found {len(hits)} level hits")
    
    print(f"\n🚨 Generating alerts...")
    dp_alerts, synthesis_alerts = replay.generate_alerts(hits)
    
    replay.print_report(args.date, args.symbol, dp_alerts, synthesis_alerts)

if __name__ == "__main__":
    main()

