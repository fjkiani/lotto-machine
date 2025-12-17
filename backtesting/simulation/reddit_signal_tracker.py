"""
📊 REDDIT SIGNAL TRACKER - Track and Validate Signal Performance

This module tracks Reddit signals as they're generated and validates
them against actual price action over time.

Key Features:
1. Records signals when generated (with timestamp, price, sentiment)
2. Updates price action 1d, 3d, 5d, 10d later
3. Calculates actual win/loss rates by signal type
4. Builds historical performance database for future optimization

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import yfinance as yf
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrackedSignal:
    """A signal being tracked for validation"""
    id: int
    symbol: str
    signal_date: datetime
    signal_type: str
    action: str  # LONG, SHORT, AVOID
    strength: float
    entry_price: float
    sentiment_at_signal: float
    reasoning: str
    
    # Tracking data (filled in later)
    price_1d: Optional[float] = None
    price_3d: Optional[float] = None
    price_5d: Optional[float] = None
    price_10d: Optional[float] = None
    return_1d: Optional[float] = None
    return_3d: Optional[float] = None
    return_5d: Optional[float] = None
    return_10d: Optional[float] = None
    outcome: Optional[str] = None  # WIN, LOSS, NEUTRAL
    validated: bool = False


class RedditSignalTracker:
    """
    Track Reddit signals and validate performance over time.
    """
    
    DB_PATH = "data/reddit_signal_tracking.db"
    
    def __init__(self):
        """Initialize the signal tracker."""
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_date TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                action TEXT NOT NULL,
                strength REAL,
                entry_price REAL,
                sentiment_at_signal REAL,
                reasoning TEXT,
                
                -- Price tracking
                price_1d REAL,
                price_3d REAL,
                price_5d REAL,
                price_10d REAL,
                
                -- Returns
                return_1d REAL,
                return_3d REAL,
                return_5d REAL,
                return_10d REAL,
                
                -- Outcome
                outcome TEXT,
                validated INTEGER DEFAULT 0,
                
                -- Metadata
                created_at TEXT,
                updated_at TEXT,
                
                UNIQUE(symbol, signal_date, signal_type)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(signal_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type)')
        
        conn.commit()
        conn.close()
    
    def record_signal(self, 
                      symbol: str,
                      signal_type: str,
                      action: str,
                      entry_price: float,
                      signal_strength: float = None,
                      strength: float = None,
                      sentiment: float = 0.0,
                      reasoning: str = None) -> int:
        """
        Record a new signal for tracking.
        
        Returns:
            Signal ID
        """
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.now()
        
        # Handle both strength and signal_strength parameter names
        actual_strength = signal_strength or strength or 0.0
        
        # Handle reasoning - accept string or list
        if isinstance(reasoning, list):
            reasoning_str = json.dumps(reasoning)
        elif reasoning:
            reasoning_str = reasoning
        else:
            reasoning_str = ""
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO signals 
                (symbol, signal_date, signal_type, action, strength, entry_price, 
                 sentiment_at_signal, reasoning, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                now.strftime('%Y-%m-%d %H:%M:%S'),
                signal_type,
                action,
                actual_strength,
                entry_price,
                sentiment,
                reasoning_str,
                now.isoformat(),
                now.isoformat()
            ))
            conn.commit()
            signal_id = cursor.lastrowid
            logger.info(f"📝 Recorded signal {signal_id}: {symbol} {action} ({signal_type})")
            return signal_id
        except Exception as e:
            logger.error(f"Error recording signal: {e}")
            return -1
        finally:
            conn.close()
    
    def update_prices(self):
        """
        Update price data for all unvalidated signals.
        
        Checks each signal and fills in 1d, 3d, 5d, 10d prices based on time elapsed.
        """
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        # Get signals that need updating
        cursor.execute('''
            SELECT id, symbol, signal_date, entry_price, action,
                   price_1d, price_3d, price_5d, price_10d
            FROM signals
            WHERE validated = 0
        ''')
        
        signals = cursor.fetchall()
        
        for row in signals:
            signal_id = row[0]
            symbol = row[1]
            signal_date = datetime.strptime(row[2], '%Y-%m-%d %H:%M:%S')
            entry_price = row[3]
            action = row[4]
            
            days_since = (datetime.now() - signal_date).days
            
            try:
                # Get current price
                ticker = yf.Ticker(symbol)
                hist = ticker.history(
                    start=signal_date.strftime('%Y-%m-%d'),
                    end=(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                )
                
                if hist.empty:
                    continue
                
                updates = {}
                
                # Update prices based on time elapsed
                if days_since >= 1 and row[5] is None and len(hist) >= 2:
                    updates['price_1d'] = float(hist['Close'].iloc[1])
                    updates['return_1d'] = (updates['price_1d'] - entry_price) / entry_price * 100
                
                if days_since >= 3 and row[6] is None and len(hist) >= 4:
                    updates['price_3d'] = float(hist['Close'].iloc[3])
                    updates['return_3d'] = (updates['price_3d'] - entry_price) / entry_price * 100
                
                if days_since >= 5 and row[7] is None and len(hist) >= 6:
                    updates['price_5d'] = float(hist['Close'].iloc[5])
                    updates['return_5d'] = (updates['price_5d'] - entry_price) / entry_price * 100
                
                if days_since >= 10 and row[8] is None and len(hist) >= 11:
                    updates['price_10d'] = float(hist['Close'].iloc[10])
                    updates['return_10d'] = (updates['price_10d'] - entry_price) / entry_price * 100
                    
                    # Determine outcome
                    if action == 'LONG':
                        updates['outcome'] = 'WIN' if updates['return_10d'] > 1 else 'LOSS' if updates['return_10d'] < -1 else 'NEUTRAL'
                    elif action == 'SHORT':
                        updates['outcome'] = 'WIN' if updates['return_10d'] < -1 else 'LOSS' if updates['return_10d'] > 1 else 'NEUTRAL'
                    else:
                        updates['outcome'] = 'NEUTRAL'
                    
                    updates['validated'] = 1
                
                if updates:
                    set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                    values = list(updates.values()) + [datetime.now().isoformat(), signal_id]
                    
                    cursor.execute(f'''
                        UPDATE signals 
                        SET {set_clause}, updated_at = ?
                        WHERE id = ?
                    ''', values)
                    
                    logger.debug(f"Updated signal {signal_id} with {list(updates.keys())}")
            
            except Exception as e:
                logger.debug(f"Error updating signal {signal_id}: {e}")
        
        conn.commit()
        conn.close()
    
    def get_performance_stats(self) -> Dict:
        """
        Calculate performance statistics for tracked signals.
        """
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        stats = {
            'total_signals': 0,
            'validated_signals': 0,
            'pending_signals': 0,
            'by_signal_type': {},
            'by_action': {},
            'overall_win_rate': 0,
            'avg_return_5d': 0
        }
        
        # Total counts
        cursor.execute('SELECT COUNT(*) FROM signals')
        stats['total_signals'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM signals WHERE validated = 1')
        stats['validated_signals'] = cursor.fetchone()[0]
        
        stats['pending_signals'] = stats['total_signals'] - stats['validated_signals']
        
        # By signal type
        cursor.execute('''
            SELECT signal_type, 
                   COUNT(*) as total,
                   SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                   AVG(return_5d) as avg_return
            FROM signals
            WHERE validated = 1
            GROUP BY signal_type
        ''')
        
        for row in cursor.fetchall():
            stats['by_signal_type'][row[0]] = {
                'total': row[1],
                'wins': row[2],
                'win_rate': row[2] / row[1] * 100 if row[1] > 0 else 0,
                'avg_return': row[3] or 0
            }
        
        # By action
        cursor.execute('''
            SELECT action,
                   COUNT(*) as total,
                   SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                   AVG(return_5d) as avg_return
            FROM signals
            WHERE validated = 1 AND action IN ('LONG', 'SHORT')
            GROUP BY action
        ''')
        
        for row in cursor.fetchall():
            stats['by_action'][row[0]] = {
                'total': row[1],
                'wins': row[2],
                'win_rate': row[2] / row[1] * 100 if row[1] > 0 else 0,
                'avg_return': row[3] or 0
            }
        
        # Overall
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END),
                   AVG(return_5d)
            FROM signals
            WHERE validated = 1 AND action IN ('LONG', 'SHORT')
        ''')
        
        row = cursor.fetchone()
        if row[0] > 0:
            stats['overall_win_rate'] = row[1] / row[0] * 100
            stats['avg_return_5d'] = row[2] or 0
        
        conn.close()
        return stats
    
    def get_recent_signals(self, limit: int = 20) -> List[Dict]:
        """Get recent signals with tracking data."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, symbol, signal_date, signal_type, action, strength, 
                   entry_price, return_1d, return_3d, return_5d, return_10d, outcome, validated
            FROM signals
            ORDER BY signal_date DESC
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'symbol': row[1],
                'date': row[2],
                'type': row[3],
                'action': row[4],
                'strength': row[5],
                'entry_price': row[6],
                'return_1d': row[7],
                'return_3d': row[8],
                'return_5d': row[9],
                'return_10d': row[10],
                'outcome': row[11],
                'validated': bool(row[12])
            })
        
        conn.close()
        return results
    
    def get_performance_by_signal_type(self) -> Dict:
        """
        Get win rates and performance by signal type.
        Used for algorithm improvement.
        """
        return self.get_performance_stats()
    
    def print_report(self):
        """Print a performance report."""
        stats = self.get_performance_stats()
        recent = self.get_recent_signals(10)
        
        print("="*80)
        print("📊 REDDIT SIGNAL TRACKING REPORT")
        print("="*80)
        print(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print(f"\n📈 SIGNAL COUNTS:")
        print(f"   Total Signals: {stats['total_signals']}")
        print(f"   Validated: {stats['validated_signals']}")
        print(f"   Pending: {stats['pending_signals']}")
        
        if stats['validated_signals'] > 0:
            print(f"\n🎯 OVERALL PERFORMANCE:")
            print(f"   Win Rate: {stats['overall_win_rate']:.1f}%")
            print(f"   Avg 5D Return: {stats['avg_return_5d']:+.2f}%")
            
            print(f"\n📊 BY SIGNAL TYPE:")
            for sig_type, data in stats['by_signal_type'].items():
                print(f"   {sig_type:25} | {data['total']:3} signals | "
                      f"WR: {data['win_rate']:5.1f}% | Avg: {data['avg_return']:+.2f}%")
            
            print(f"\n📊 BY ACTION:")
            for action, data in stats['by_action'].items():
                print(f"   {action:10} | {data['total']:3} signals | "
                      f"WR: {data['win_rate']:5.1f}% | Avg: {data['avg_return']:+.2f}%")
        
        if recent:
            print(f"\n📋 RECENT SIGNALS:")
            print("-"*100)
            for sig in recent:
                status = '✅' if sig['validated'] else '⏳'
                outcome = sig['outcome'] or 'pending'
                ret_5d = f"{sig['return_5d']:+.1f}%" if sig['return_5d'] else 'N/A'
                print(f"   {status} {sig['date'][:10]} | {sig['symbol']:5} | {sig['type']:20} | "
                      f"{sig['action']:5} | ${sig['entry_price']:7.2f} | 5D: {ret_5d:>7} | {outcome}")
        
        print(f"\n{'='*80}")


def record_current_signals():
    """Record current Reddit signals for tracking."""
    import sys
    sys.path.insert(0, '.')
    
    from backtesting.simulation.reddit_real_backtest import RealRedditBacktester
    
    print("="*80)
    print("📝 RECORDING CURRENT REDDIT SIGNALS FOR TRACKING")
    print("="*80)
    
    tracker = RedditSignalTracker()
    backtester = RealRedditBacktester()
    
    symbols = ['TSLA', 'NVDA', 'AAPL', 'META', 'GME', 'PLTR', 'AMD', 'AMZN', 'MSFT', 'GOOGL']
    
    results = backtester.analyze_current_signals(symbols)
    
    recorded = 0
    for symbol, data in results.items():
        signal = data.get('signal')
        price = data.get('price_data', {})
        reddit = data.get('reddit_data', {})
        
        if signal and signal.get('type') and signal.get('action') != 'NEUTRAL':
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
                print(f"   ✅ {symbol}: {signal['action']} ({signal['type']}) @ ${price.get('current_price', 0):.2f}")
    
    print(f"\n📊 Recorded {recorded} signals for tracking")
    
    # Print current stats
    tracker.print_report()


if __name__ == "__main__":
    record_current_signals()

