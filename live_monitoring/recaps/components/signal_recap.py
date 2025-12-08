"""
📈 SIGNAL RECAP COMPONENT
Recaps signals generated last week and their outcomes
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SignalOutcome:
    """Outcome of a signal"""
    symbol: str
    signal_type: str
    action: str  # "BUY", "SELL"
    entry_price: float
    target_price: float
    stop_price: float
    timestamp: datetime
    outcome: Optional[str]  # "WIN", "LOSS", "PENDING"
    pnl_pct: Optional[float]


@dataclass
class SignalRecapResult:
    """Result of signal recap"""
    week_start: str
    week_end: str
    total_signals: int
    signals: List[SignalOutcome]
    win_rate: float
    avg_win: float
    avg_loss: float
    best_signal: Optional[SignalOutcome]
    worst_signal: Optional[SignalOutcome]
    summary: str


class SignalRecap:
    """
    Recaps signals from last week.
    
    What it does:
    - Queries signal database for last week
    - Calculates win rate and P&L
    - Identifies best/worst signals
    - Analyzes signal performance by type
    """
    
    def __init__(self, db_path: str = None, csv_path: str = None):
        """
        Initialize signal recap.
        
        Args:
            db_path: Path to signals database (optional)
            csv_path: Path to signals CSV log (optional, defaults to logs/live_monitoring/signals.csv)
        """
        from pathlib import Path
        base_path = Path(__file__).parent.parent.parent.parent
        
        if db_path is None:
            self.db_path = str(base_path / "data" / "signals.db")
        else:
            self.db_path = db_path
        
        if csv_path is None:
            self.csv_path = base_path / "logs" / "live_monitoring" / "signals.csv"
        else:
            self.csv_path = Path(csv_path)
    
    def generate_recap(self, week_start: Optional[str] = None,
                      week_end: Optional[str] = None) -> SignalRecapResult:
        """
        Generate recap for last week's signals.
        
        Args:
            week_start: Start date (YYYY-MM-DD), defaults to last Monday
            week_end: End date (YYYY-MM-DD), defaults to last Friday
        
        Returns:
            SignalRecapResult with analysis
        """
        # Calculate week dates
        today = datetime.now()
        last_friday = today - timedelta(days=(today.weekday() + 3) % 7)
        if last_friday > today:
            last_friday -= timedelta(days=7)
        
        last_monday = last_friday - timedelta(days=4)
        
        if week_start:
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
        else:
            week_start_date = last_monday
        
        if week_end:
            week_end_date = datetime.strptime(week_end, '%Y-%m-%d')
        else:
            week_end_date = last_friday
        
        week_start_str = week_start_date.strftime('%Y-%m-%d')
        week_end_str = week_end_date.strftime('%Y-%m-%d')
        
        logger.info(f"📈 Generating signal recap: {week_start_str} to {week_end_str}")
        
        # Query signals
        signals = self._query_signals(week_start_str, week_end_str)
        
        # Calculate metrics
        win_rate, avg_win, avg_loss = self._calculate_metrics(signals)
        best_signal, worst_signal = self._identify_extremes(signals)
        
        # Generate summary
        summary = self._generate_summary(signals, win_rate, avg_win, avg_loss, best_signal, worst_signal)
        
        return SignalRecapResult(
            week_start=week_start_str,
            week_end=week_end_str,
            total_signals=len(signals),
            signals=signals,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_signal=best_signal,
            worst_signal=worst_signal,
            summary=summary
        )
    
    def _query_signals(self, week_start: str, week_end: str) -> List[SignalOutcome]:
        """Query signals from CSV log or database"""
        signals = []
        
        # Try CSV first (more likely to have data)
        if self.csv_path.exists():
            try:
                import csv
                with open(self.csv_path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        timestamp_str = row.get('timestamp', '')
                        if not timestamp_str:
                            continue
                        
                        try:
                            signal_date = datetime.strptime(timestamp_str.split()[0], '%Y-%m-%d')
                            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
                            week_end_date = datetime.strptime(week_end, '%Y-%m-%d')
                            
                            if week_start_date <= signal_date <= week_end_date:
                                entry = float(row.get('entry_price', 0) or 0)
                                target = float(row.get('take_profit', 0) or 0)
                                stop = float(row.get('stop_loss', 0) or 0)
                                
                                signals.append(SignalOutcome(
                                    symbol=row.get('symbol', 'UNKNOWN'),
                                    signal_type=row.get('signal_type', 'UNKNOWN'),
                                    action=row.get('action', 'UNKNOWN'),
                                    entry_price=entry,
                                    target_price=target,
                                    stop_price=stop,
                                    timestamp=datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S'),
                                    outcome=None,  # CSV doesn't have outcome
                                    pnl_pct=None
                                ))
                        except (ValueError, KeyError) as e:
                            continue
                
                if signals:
                    logger.info(f"   Found {len(signals)} signals from CSV")
                    return signals
            except Exception as e:
                logger.warning(f"⚠️  Failed to read CSV: {e}")
        
        # Fallback to database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='signals'
            ''')
            
            if not cursor.fetchone():
                logger.warning("⚠️  Signals table does not exist")
                conn.close()
                return []
            
            # Query signals
            cursor.execute('''
                SELECT 
                    symbol,
                    signal_type,
                    action,
                    entry_price,
                    target_price,
                    stop_price,
                    timestamp,
                    outcome,
                    pnl_pct
                FROM signals
                WHERE date(timestamp) >= date(?)
                  AND date(timestamp) <= date(?)
                ORDER BY timestamp
            ''', (week_start, week_end))
            
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                symbol, signal_type, action, entry, target, stop, timestamp_str, outcome, pnl = row
                
                signals.append(SignalOutcome(
                    symbol=symbol,
                    signal_type=signal_type or "UNKNOWN",
                    action=action or "UNKNOWN",
                    entry_price=entry or 0.0,
                    target_price=target or 0.0,
                    stop_price=stop or 0.0,
                    timestamp=datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(),
                    outcome=outcome,
                    pnl_pct=pnl
                ))
            
            logger.info(f"   Found {len(signals)} signals from database")
            return signals
            
        except sqlite3.OperationalError as e:
            logger.warning(f"⚠️  Database query failed: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error querying signals: {e}")
            return []
    
    def _calculate_metrics(self, signals: List[SignalOutcome]) -> tuple:
        """Calculate win rate and average P&L"""
        if not signals:
            return 0.0, 0.0, 0.0
        
        completed = [s for s in signals if s.outcome in ["WIN", "LOSS"]]
        if not completed:
            return 0.0, 0.0, 0.0
        
        wins = [s for s in completed if s.outcome == "WIN"]
        losses = [s for s in completed if s.outcome == "LOSS"]
        
        win_rate = (len(wins) / len(completed) * 100) if completed else 0.0
        avg_win = sum(s.pnl_pct for s in wins if s.pnl_pct) / len(wins) if wins else 0.0
        avg_loss = sum(s.pnl_pct for s in losses if s.pnl_pct) / len(losses) if losses else 0.0
        
        return win_rate, avg_win, avg_loss
    
    def _identify_extremes(self, signals: List[SignalOutcome]) -> tuple:
        """Identify best and worst signals"""
        completed = [s for s in signals if s.outcome and s.pnl_pct is not None]
        
        if not completed:
            return None, None
        
        best = max(completed, key=lambda s: s.pnl_pct or 0)
        worst = min(completed, key=lambda s: s.pnl_pct or 0)
        
        return best, worst
    
    def _generate_summary(self, signals: List[SignalOutcome], win_rate: float,
                         avg_win: float, avg_loss: float, best: Optional[SignalOutcome],
                         worst: Optional[SignalOutcome]) -> str:
        """Generate human-readable summary"""
        if not signals:
            return "No signals generated last week."
        
        summary = f"**Signal Recap ({len(signals)} signals):**\n\n"
        summary += f"📊 **Performance:**\n"
        summary += f"   • Win Rate: {win_rate:.1f}%\n"
        summary += f"   • Avg Win: +{avg_win:.2f}%\n"
        summary += f"   • Avg Loss: {avg_loss:.2f}%\n\n"
        
        if best:
            summary += f"🏆 **Best Signal:**\n"
            summary += f"   • {best.symbol} {best.action} @ ${best.entry_price:.2f}\n"
            summary += f"   • P&L: +{best.pnl_pct:.2f}%\n\n"
        
        if worst:
            summary += f"⚠️  **Worst Signal:**\n"
            summary += f"   • {worst.symbol} {worst.action} @ ${worst.entry_price:.2f}\n"
            summary += f"   • P&L: {worst.pnl_pct:.2f}%\n"
        
        return summary

