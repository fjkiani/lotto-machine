"""
📱 REDDIT SIGNAL ANALYZER
Extends signal analyzer to handle Reddit exploitation signals

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
import sqlite3
import os


@dataclass
class RedditSignal:
    """Reddit signal from tracker database"""
    id: int
    symbol: str
    signal_date: str
    signal_type: str
    action: str
    strength: float
    entry_price: float
    sentiment_at_signal: float
    reasoning: str
    price_1d: Optional[float] = None
    price_3d: Optional[float] = None
    price_5d: Optional[float] = None
    return_1d: Optional[float] = None
    return_3d: Optional[float] = None
    return_5d: Optional[float] = None
    outcome: Optional[str] = None
    validated: bool = False
    
    @property
    def timestamp(self) -> datetime:
        """Convert signal_date to datetime"""
        return datetime.fromisoformat(self.signal_date)


@dataclass
class RedditSignalSummary:
    """Summary of Reddit signals for a date"""
    date: str
    total_signals: int
    signal_types: Dict[str, int]
    actions: Dict[str, int]
    symbols: Dict[str, int]
    avg_strength: float
    signals: List[RedditSignal]
    
    # Actionable breakdown
    long_signals: int
    watch_signals: int
    avoid_signals: int
    
    # Performance (if validated)
    validated_signals: int
    win_rate_1d: Optional[float] = None
    win_rate_3d: Optional[float] = None
    avg_return_1d: Optional[float] = None
    avg_return_3d: Optional[float] = None


class RedditSignalAnalyzer:
    """Analyzes Reddit exploitation signals"""
    
    DB_PATH = "data/reddit_signal_tracking.db"
    
    def __init__(self):
        """Initialize analyzer"""
        self.db_path = self.DB_PATH
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Reddit signal database not found: {self.db_path}")
    
    def load_signals_for_date(self, date: str) -> List[RedditSignal]:
        """
        Load all Reddit signals for a given date.
        
        Args:
            date: Date string in YYYY-MM-DD format
            
        Returns:
            List of RedditSignal objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT 
                id, symbol, signal_date, signal_type, action, 
                strength, entry_price, sentiment_at_signal, reasoning,
                price_1d, price_3d, price_5d,
                return_1d, return_3d, return_5d,
                outcome, validated
            FROM signals
            WHERE DATE(signal_date) = ?
            ORDER BY signal_date DESC, strength DESC
        ''', (date,))
        
        signals = []
        for row in cursor.fetchall():
            signals.append(RedditSignal(
                id=row[0],
                symbol=row[1],
                signal_date=row[2],
                signal_type=row[3],
                action=row[4],
                strength=row[5],
                entry_price=row[6],
                sentiment_at_signal=row[7],
                reasoning=row[8],
                price_1d=row[9],
                price_3d=row[10],
                price_5d=row[11],
                return_1d=row[12],
                return_3d=row[13],
                return_5d=row[14],
                outcome=row[15],
                validated=bool(row[16])
            ))
        
        conn.close()
        return signals
    
    def analyze_signals(self, signals: List[RedditSignal], date: str) -> RedditSignalSummary:
        """
        Analyze Reddit signals for a date.
        
        Args:
            signals: List of RedditSignal objects
            date: Date string in YYYY-MM-DD format
            
        Returns:
            RedditSignalSummary
        """
        if not signals:
            return RedditSignalSummary(
                date=date,
                total_signals=0,
                signal_types={},
                actions={},
                symbols={},
                avg_strength=0.0,
                signals=[],
                long_signals=0,
                watch_signals=0,
                avoid_signals=0,
                validated_signals=0
            )
        
        # Count metrics
        signal_types = {}
        actions = {}
        symbols = {}
        strength_sum = 0.0
        long_count = 0
        watch_count = 0
        avoid_count = 0
        validated_count = 0
        
        wins_1d = []
        wins_3d = []
        returns_1d = []
        returns_3d = []
        
        for signal in signals:
            # Count types
            signal_types[signal.signal_type] = signal_types.get(signal.signal_type, 0) + 1
            actions[signal.action] = actions.get(signal.action, 0) + 1
            symbols[signal.symbol] = symbols.get(signal.symbol, 0) + 1
            
            # Sum strength
            strength_sum += signal.strength
            
            # Count actions
            if signal.action == 'LONG':
                long_count += 1
            elif signal.action in ['WATCH_LONG', 'WATCH_SHORT']:
                watch_count += 1
            elif signal.action == 'AVOID':
                avoid_count += 1
            
            # Performance tracking
            if signal.validated:
                validated_count += 1
                
                if signal.return_1d is not None:
                    returns_1d.append(signal.return_1d)
                    if signal.return_1d > 0:
                        wins_1d.append(1)
                    else:
                        wins_1d.append(0)
                
                if signal.return_3d is not None:
                    returns_3d.append(signal.return_3d)
                    if signal.return_3d > 0:
                        wins_3d.append(1)
                    else:
                        wins_3d.append(0)
        
        # Calculate averages
        avg_strength = strength_sum / len(signals) if signals else 0.0
        win_rate_1d = sum(wins_1d) / len(wins_1d) * 100 if wins_1d else None
        win_rate_3d = sum(wins_3d) / len(wins_3d) * 100 if wins_3d else None
        avg_return_1d = sum(returns_1d) / len(returns_1d) if returns_1d else None
        avg_return_3d = sum(returns_3d) / len(returns_3d) if returns_3d else None
        
        return RedditSignalSummary(
            date=date,
            total_signals=len(signals),
            signal_types=signal_types,
            actions=actions,
            symbols=symbols,
            avg_strength=avg_strength,
            signals=signals,
            long_signals=long_count,
            watch_signals=watch_count,
            avoid_signals=avoid_count,
            validated_signals=validated_count,
            win_rate_1d=win_rate_1d,
            win_rate_3d=win_rate_3d,
            avg_return_1d=avg_return_1d,
            avg_return_3d=avg_return_3d
        )
    
    def get_top_signals(
        self, 
        signals: List[RedditSignal], 
        min_strength: float = 70.0,
        action: Optional[str] = None
    ) -> List[RedditSignal]:
        """
        Get high-quality signals.
        
        Args:
            signals: List of RedditSignal objects
            min_strength: Minimum strength threshold
            action: Optional action filter (LONG, WATCH_LONG, AVOID)
            
        Returns:
            List of filtered RedditSignal objects
        """
        filtered = []
        
        for signal in signals:
            # Strength filter
            if signal.strength < min_strength:
                continue
            
            # Action filter
            if action and signal.action != action:
                continue
            
            filtered.append(signal)
        
        return sorted(filtered, key=lambda x: x.strength, reverse=True)

