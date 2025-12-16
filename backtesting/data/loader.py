"""
📊 DATA LOADER
Loads DP alerts from database for any date/session
"""

import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class DPAlert:
    """DP Alert with all necessary data for backtesting"""
    timestamp: datetime
    symbol: str
    level_price: float
    level_volume: int
    level_type: str  # SUPPORT or RESISTANCE
    outcome: str  # BOUNCE, BREAK, FADE, PENDING
    max_move_pct: float
    confluence_score: float
    volume_vs_avg: float
    touch_count: int
    momentum_pct: float
    market_trend: str

class DataLoader:
    """Loads DP alerts from database"""
    
    def __init__(self, db_path: str = "data/dp_learning.db"):
        self.db_path = db_path
    
    def load_session(self, date: str, start_time: str = "09:30", end_time: str = "16:00") -> List[DPAlert]:
        """
        Load DP alerts for a specific trading session
        
        Args:
            date: Date in YYYY-MM-DD format
            start_time: Session start time (HH:MM)
            end_time: Session end time (HH:MM)
        
        Returns:
            List of DPAlert objects
        """
        start_datetime = f"{date}T{start_time}:00"
        end_datetime = f"{date}T{end_time}:00"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, symbol, level_price, level_volume, level_type, outcome, max_move_pct,
                   volume_vs_avg, touch_count, momentum_pct, market_trend
            FROM dp_interactions
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        ''', [start_datetime, end_datetime])
        
        alerts = []
        for row in cursor.fetchall():
            # Calculate confluence score
            confluence = self._calculate_confluence(
                volume_vs_avg=row[7] or 1.0,
                touch_count=row[8] or 1,
                momentum_pct=row[9] or 0.0,
                level_volume=row[3] or 0
            )
            
            alert = DPAlert(
                timestamp=datetime.fromisoformat(row[0]),
                symbol=row[1],
                level_price=row[2],
                level_volume=row[3],
                level_type=row[4],
                outcome=row[5] or 'UNKNOWN',
                max_move_pct=row[6] or 0,
                confluence_score=confluence,
                volume_vs_avg=row[7] or 1.0,
                touch_count=row[8] or 1,
                momentum_pct=row[9] or 0.0,
                market_trend=row[10] or "NEUTRAL"
            )
            alerts.append(alert)
        
        conn.close()
        return alerts
    
    def load_date_range(self, start_date: str, end_date: str) -> List[DPAlert]:
        """
        Load DP alerts for a date range
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            List of DPAlert objects
        """
        start_datetime = f"{start_date}T00:00:00"
        end_datetime = f"{end_date}T23:59:59"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT timestamp, symbol, level_price, level_volume, level_type, outcome, max_move_pct,
                   volume_vs_avg, touch_count, momentum_pct, market_trend
            FROM dp_interactions
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
        ''', [start_datetime, end_datetime])
        
        alerts = []
        for row in cursor.fetchall():
            confluence = self._calculate_confluence(
                volume_vs_avg=row[7] or 1.0,
                touch_count=row[8] or 1,
                momentum_pct=row[9] or 0.0,
                level_volume=row[3] or 0
            )
            
            alert = DPAlert(
                timestamp=datetime.fromisoformat(row[0]),
                symbol=row[1],
                level_price=row[2],
                level_volume=row[3],
                level_type=row[4],
                outcome=row[5] or 'UNKNOWN',
                max_move_pct=row[6] or 0,
                confluence_score=confluence,
                volume_vs_avg=row[7] or 1.0,
                touch_count=row[8] or 1,
                momentum_pct=row[9] or 0.0,
                market_trend=row[10] or "NEUTRAL"
            )
            alerts.append(alert)
        
        conn.close()
        return alerts
    
    @staticmethod
    def _calculate_confluence(volume_vs_avg: float, touch_count: int, momentum_pct: float, level_volume: int) -> float:
        """Calculate confluence score (0-100)"""
        score = 50  # Base score
        
        # Volume strength
        if volume_vs_avg >= 2.0:
            score += 20
        elif volume_vs_avg >= 1.5:
            score += 10
        
        # Touch count
        score += min(touch_count - 1, 3) * 10
        
        # Momentum alignment
        if abs(momentum_pct) >= 0.5:
            score += 15
        elif abs(momentum_pct) >= 0.25:
            score += 5
        
        # Level significance
        if level_volume >= 500000:
            score += 10
        
        return min(score, 100)



