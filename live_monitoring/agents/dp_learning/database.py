"""
🧠 DP Learning Engine - Database
================================
SQLite persistence for dark pool interactions and patterns.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from .models import DPInteraction, DPOutcome, DPPattern, Outcome, LevelType, ApproachDirection

logger = logging.getLogger(__name__)


class DPDatabase:
    """SQLite database for dark pool learning."""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent.parent / "data" / "dp_learning.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info(f"📊 DPDatabase initialized: {self.db_path}")
    
    def _init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Interactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dp_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                
                level_price REAL NOT NULL,
                level_volume INTEGER NOT NULL,
                level_type TEXT NOT NULL,
                level_date TEXT,
                
                approach_price REAL,
                approach_direction TEXT,
                distance_pct REAL,
                touch_count INTEGER DEFAULT 1,
                
                market_trend TEXT,
                volume_vs_avg REAL,
                momentum_pct REAL,
                vix_level REAL,
                time_of_day TEXT,
                
                outcome TEXT DEFAULT 'PENDING',
                outcome_timestamp TEXT,
                max_move_pct REAL DEFAULT 0,
                time_to_outcome_min INTEGER DEFAULT 0,
                
                price_at_5min REAL,
                price_at_15min REAL,
                price_at_30min REAL,
                price_at_60min REAL,
                
                notes TEXT
            )
        """)
        
        # Patterns table (cached learned patterns)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dp_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT UNIQUE NOT NULL,
                total_samples INTEGER DEFAULT 0,
                bounce_count INTEGER DEFAULT 0,
                break_count INTEGER DEFAULT 0,
                fade_count INTEGER DEFAULT 0,
                last_updated TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_interaction(self, interaction: DPInteraction) -> int:
        """Save a new interaction, return the ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO dp_interactions (
                timestamp, symbol, level_price, level_volume, level_type, level_date,
                approach_price, approach_direction, distance_pct, touch_count,
                market_trend, volume_vs_avg, momentum_pct, vix_level, time_of_day,
                outcome, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            interaction.timestamp.isoformat(),
            interaction.symbol,
            interaction.level_price,
            interaction.level_volume,
            interaction.level_type.value,
            interaction.level_date,
            interaction.approach_price,
            interaction.approach_direction.value,
            interaction.distance_pct,
            interaction.touch_count,
            interaction.market_trend,
            interaction.volume_vs_avg,
            interaction.momentum_pct,
            interaction.vix_level,
            interaction.time_of_day,
            interaction.outcome.value,
            interaction.notes
        ))
        
        interaction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"💾 Saved interaction #{interaction_id}: {interaction.symbol} @ ${interaction.level_price:.2f}")
        return interaction_id
    
    def update_outcome(self, interaction_id: int, outcome: DPOutcome):
        """Update an interaction with its outcome."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE dp_interactions SET
                outcome = ?,
                outcome_timestamp = ?,
                max_move_pct = ?,
                time_to_outcome_min = ?,
                price_at_5min = ?,
                price_at_15min = ?,
                price_at_30min = ?,
                price_at_60min = ?
            WHERE id = ?
        """, (
            outcome.outcome.value,
            datetime.now().isoformat(),
            outcome.max_move_pct,
            outcome.time_to_outcome_min,
            outcome.price_at_5min,
            outcome.price_at_15min,
            outcome.price_at_30min,
            outcome.price_at_60min,
            interaction_id
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"📝 Updated outcome for #{interaction_id}: {outcome.outcome.value}")
    
    def get_interaction(self, interaction_id: int) -> Optional[DPInteraction]:
        """Get a single interaction by ID."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM dp_interactions WHERE id = ?", (interaction_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_interaction(row, cursor.description)
        return None
    
    def get_pending_interactions(self) -> List[DPInteraction]:
        """Get all interactions waiting for outcome."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM dp_interactions WHERE outcome = 'PENDING'")
        rows = cursor.fetchall()
        description = cursor.description
        conn.close()
        
        return [self._row_to_interaction(row, description) for row in rows]
    
    def get_all_interactions(self, symbol: str = None, limit: int = 100) -> List[DPInteraction]:
        """Get recent interactions, optionally filtered by symbol."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        if symbol:
            cursor.execute(
                "SELECT * FROM dp_interactions WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM dp_interactions ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        
        rows = cursor.fetchall()
        description = cursor.description
        conn.close()
        
        return [self._row_to_interaction(row, description) for row in rows]
    
    def get_completed_interactions(self, limit: int = 100) -> List[DPInteraction]:
        """Get interactions with known outcomes (for learning)."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM dp_interactions 
            WHERE outcome IN ('BOUNCE', 'BREAK', 'FADE')
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        description = cursor.description
        conn.close()
        
        return [self._row_to_interaction(row, description) for row in rows]
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM dp_interactions")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dp_interactions WHERE outcome = 'PENDING'")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dp_interactions WHERE outcome = 'BOUNCE'")
        bounces = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dp_interactions WHERE outcome = 'BREAK'")
        breaks = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total': total,
            'pending': pending,
            'completed': total - pending,
            'bounces': bounces,
            'breaks': breaks,
            'bounce_rate': bounces / (bounces + breaks) if (bounces + breaks) > 0 else 0
        }
    
    def _row_to_interaction(self, row, description) -> DPInteraction:
        """Convert a database row to a DPInteraction object."""
        cols = [col[0] for col in description]
        data = dict(zip(cols, row))
        
        return DPInteraction(
            id=data.get('id'),
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now(),
            symbol=data.get('symbol', ''),
            level_price=data.get('level_price', 0),
            level_volume=data.get('level_volume', 0),
            level_type=LevelType(data.get('level_type', 'RESISTANCE')),
            level_date=data.get('level_date', ''),
            approach_price=data.get('approach_price', 0),
            approach_direction=ApproachDirection(data.get('approach_direction', 'FROM_BELOW')),
            distance_pct=data.get('distance_pct', 0),
            touch_count=data.get('touch_count', 1),
            market_trend=data.get('market_trend', 'UNKNOWN'),
            volume_vs_avg=data.get('volume_vs_avg', 1.0),
            momentum_pct=data.get('momentum_pct', 0),
            vix_level=data.get('vix_level', 0),
            time_of_day=data.get('time_of_day', 'UNKNOWN'),
            outcome=Outcome(data.get('outcome', 'PENDING')),
            outcome_timestamp=datetime.fromisoformat(data['outcome_timestamp']) if data.get('outcome_timestamp') else None,
            max_move_pct=data.get('max_move_pct', 0),
            time_to_outcome_min=data.get('time_to_outcome_min', 0),
            notes=data.get('notes', '')
        )




