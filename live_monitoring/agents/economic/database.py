"""
Economic Intelligence - Database Layer

SQLite persistence for:
- Historical economic releases
- Learned patterns
- Fed Watch history
- Predictions and their accuracy
"""

import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict
from contextlib import contextmanager

from .models import (
    EconomicRelease, LearnedPattern, EventType, 
    DarkPoolContext, Prediction
)

logger = logging.getLogger(__name__)


class EconomicDatabase:
    """
    SQLite database for economic intelligence.
    
    Schema:
    - economic_releases: Historical releases with all context
    - learned_patterns: Learned coefficients by event type
    - fed_watch_history: Fed Watch snapshots over time
    - predictions: Predictions made and their accuracy
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize database.
        
        Args:
            db_path: Path to SQLite file. Defaults to data/economic_intelligence.db
        """
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            db_path = os.path.join(base_dir, 'data', 'economic_intelligence.db')
        
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        
        self._init_schema()
        logger.info(f"📊 EconomicDatabase initialized: {db_path}")
    
    @contextmanager
    def _get_conn(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_schema(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # Economic releases - the core training data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS economic_releases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    time TEXT,
                    event_type TEXT NOT NULL,
                    event_name TEXT,
                    
                    -- Release values
                    actual REAL,
                    forecast REAL,
                    previous REAL,
                    revision REAL,
                    surprise_pct REAL,
                    surprise_sigma REAL,
                    
                    -- Fed Watch impact (TARGET VARIABLE)
                    fed_watch_before REAL,
                    fed_watch_after_1hr REAL,
                    fed_watch_after_24hr REAL,
                    fed_watch_shift_1hr REAL,
                    fed_watch_shift_24hr REAL,
                    
                    -- Market reactions
                    spy_change_1hr REAL,
                    spy_change_24hr REAL,
                    tlt_change_1hr REAL,
                    vix_change_1hr REAL,
                    volume_spike REAL,
                    
                    -- Dark Pool context
                    dp_activity_before REAL,
                    dp_activity_after REAL,
                    dp_buy_ratio_before REAL,
                    dp_buy_ratio_after REAL,
                    dp_battleground_distance REAL,
                    
                    -- Context
                    days_to_fomc INTEGER,
                    current_fed_rate REAL,
                    market_regime TEXT,
                    vix_level REAL,
                    
                    -- Metadata
                    source TEXT,
                    created_at TEXT,
                    
                    UNIQUE(date, event_type)
                )
            """)
            
            # Learned patterns - what we've learned
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT UNIQUE NOT NULL,
                    
                    -- Learned coefficients
                    base_impact REAL,
                    surprise_scaling REAL,
                    fomc_proximity_boost REAL,
                    high_vix_multiplier REAL,
                    dp_confirmation_boost REAL,
                    
                    -- Model quality
                    sample_count INTEGER,
                    r_squared REAL,
                    mean_absolute_error REAL,
                    
                    -- Tracking
                    last_5_predictions TEXT,  -- JSON
                    last_updated TEXT
                )
            """)
            
            # Fed Watch history - for tracking changes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fed_watch_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cut_prob REAL,
                    hold_prob REAL,
                    hike_prob REAL,
                    meeting_date TEXT,
                    source TEXT
                )
            """)
            
            # Predictions - track accuracy
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT,
                    event_date TEXT,
                    
                    -- Prediction
                    predicted_shift REAL,
                    predicted_fed_watch REAL,
                    confidence REAL,
                    
                    -- Actual outcome (filled in later)
                    actual_shift REAL,
                    actual_fed_watch REAL,
                    
                    -- Accuracy
                    error REAL,
                    was_correct_direction INTEGER
                )
            """)
            
            # Create indices for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_releases_type ON economic_releases(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_releases_date ON economic_releases(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fed_watch_time ON fed_watch_history(timestamp)")
    
    # ========================================================================
    # ECONOMIC RELEASES
    # ========================================================================
    
    def save_release(self, release: EconomicRelease):
        """Save an economic release."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            event_type = release.event_type.value if isinstance(release.event_type, EventType) else str(release.event_type)
            
            cursor.execute("""
                INSERT OR REPLACE INTO economic_releases
                (date, time, event_type, event_name,
                 actual, forecast, previous, revision, surprise_pct, surprise_sigma,
                 fed_watch_before, fed_watch_after_1hr, fed_watch_after_24hr,
                 fed_watch_shift_1hr, fed_watch_shift_24hr,
                 spy_change_1hr, spy_change_24hr, tlt_change_1hr, vix_change_1hr, volume_spike,
                 dp_activity_before, dp_activity_after, dp_buy_ratio_before, dp_buy_ratio_after,
                 dp_battleground_distance,
                 days_to_fomc, current_fed_rate, market_regime, vix_level,
                 source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                release.date, release.time, event_type, release.event_name,
                release.actual, release.forecast, release.previous, release.revision,
                release.surprise_pct, release.surprise_sigma,
                release.fed_watch_before, release.fed_watch_after_1hr, release.fed_watch_after_24hr,
                release.fed_watch_shift_1hr, release.fed_watch_shift_24hr,
                release.spy_change_1hr, release.spy_change_24hr, release.tlt_change_1hr,
                release.vix_change_1hr, release.volume_spike,
                release.dp_activity_before, release.dp_activity_after,
                release.dp_buy_ratio_before, release.dp_buy_ratio_after,
                release.dp_battleground_distance,
                release.days_to_fomc, release.current_fed_rate, release.market_regime, release.vix_level,
                release.source, release.created_at
            ))
            
            logger.debug(f"💾 Saved: {release.event_name} on {release.date}")
    
    def save_releases_batch(self, releases: List[EconomicRelease]):
        """Save multiple releases efficiently."""
        for release in releases:
            self.save_release(release)
        logger.info(f"💾 Saved {len(releases)} releases")
    
    def get_releases_by_type(self, event_type: EventType, limit: int = 100) -> List[EconomicRelease]:
        """Get releases for a specific event type."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            type_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
            
            cursor.execute("""
                SELECT * FROM economic_releases
                WHERE event_type = ?
                ORDER BY date DESC
                LIMIT ?
            """, (type_str, limit))
            
            return [self._row_to_release(row) for row in cursor.fetchall()]
    
    def get_all_releases(self, min_fed_watch_data: bool = True) -> List[EconomicRelease]:
        """Get all releases, optionally filtering for complete data."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            if min_fed_watch_data:
                cursor.execute("""
                    SELECT * FROM economic_releases
                    WHERE fed_watch_shift_1hr IS NOT NULL
                    AND fed_watch_shift_1hr != 0
                    ORDER BY date DESC
                """)
            else:
                cursor.execute("SELECT * FROM economic_releases ORDER BY date DESC")
            
            return [self._row_to_release(row) for row in cursor.fetchall()]
    
    def _row_to_release(self, row) -> EconomicRelease:
        """Convert database row to EconomicRelease."""
        return EconomicRelease(
            date=row['date'],
            time=row['time'] or "08:30",
            event_type=row['event_type'],
            event_name=row['event_name'] or row['event_type'],
            actual=row['actual'] or 0,
            forecast=row['forecast'] or 0,
            previous=row['previous'] or 0,
            revision=row['revision'],
            surprise_pct=row['surprise_pct'] or 0,
            surprise_sigma=row['surprise_sigma'] or 0,
            fed_watch_before=row['fed_watch_before'] or 50,
            fed_watch_after_1hr=row['fed_watch_after_1hr'] or 50,
            fed_watch_after_24hr=row['fed_watch_after_24hr'] or 50,
            fed_watch_shift_1hr=row['fed_watch_shift_1hr'] or 0,
            fed_watch_shift_24hr=row['fed_watch_shift_24hr'] or 0,
            spy_change_1hr=row['spy_change_1hr'] or 0,
            spy_change_24hr=row['spy_change_24hr'] or 0,
            tlt_change_1hr=row['tlt_change_1hr'] or 0,
            vix_change_1hr=row['vix_change_1hr'] or 0,
            volume_spike=row['volume_spike'] or 1,
            dp_activity_before=row['dp_activity_before'] or 0,
            dp_activity_after=row['dp_activity_after'] or 0,
            dp_buy_ratio_before=row['dp_buy_ratio_before'] or 0.5,
            dp_buy_ratio_after=row['dp_buy_ratio_after'] or 0.5,
            dp_battleground_distance=row['dp_battleground_distance'] or 0,
            days_to_fomc=row['days_to_fomc'] or 30,
            current_fed_rate=row['current_fed_rate'] or 4.5,
            market_regime=row['market_regime'] or "NORMAL",
            vix_level=row['vix_level'] or 15,
            source=row['source'] or "database",
            created_at=row['created_at'] or ""
        )
    
    # ========================================================================
    # LEARNED PATTERNS
    # ========================================================================
    
    def save_pattern(self, pattern: LearnedPattern):
        """Save a learned pattern."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            event_type = pattern.event_type.value if isinstance(pattern.event_type, EventType) else str(pattern.event_type)
            
            cursor.execute("""
                INSERT OR REPLACE INTO learned_patterns
                (event_type, base_impact, surprise_scaling, fomc_proximity_boost,
                 high_vix_multiplier, dp_confirmation_boost,
                 sample_count, r_squared, mean_absolute_error,
                 last_5_predictions, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_type, pattern.base_impact, pattern.surprise_scaling,
                pattern.fomc_proximity_boost, pattern.high_vix_multiplier,
                pattern.dp_confirmation_boost, pattern.sample_count,
                pattern.r_squared, pattern.mean_absolute_error,
                json.dumps(pattern.last_5_predictions),
                pattern.last_updated or datetime.now().isoformat()
            ))
    
    def get_pattern(self, event_type: EventType) -> Optional[LearnedPattern]:
        """Get learned pattern for an event type."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            type_str = event_type.value if isinstance(event_type, EventType) else str(event_type)
            
            cursor.execute("""
                SELECT * FROM learned_patterns WHERE event_type = ?
            """, (type_str,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return LearnedPattern(
                event_type=event_type,
                base_impact=row['base_impact'] or 0,
                surprise_scaling=row['surprise_scaling'] or 1,
                fomc_proximity_boost=row['fomc_proximity_boost'] or 0,
                high_vix_multiplier=row['high_vix_multiplier'] or 1,
                dp_confirmation_boost=row['dp_confirmation_boost'] or 0,
                sample_count=row['sample_count'] or 0,
                r_squared=row['r_squared'] or 0,
                mean_absolute_error=row['mean_absolute_error'] or 0,
                last_5_predictions=json.loads(row['last_5_predictions'] or '[]'),
                last_updated=row['last_updated'] or ""
            )
    
    def get_all_patterns(self) -> Dict[str, LearnedPattern]:
        """Get all learned patterns."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM learned_patterns")
            
            patterns = {}
            for row in cursor.fetchall():
                patterns[row['event_type']] = LearnedPattern(
                    event_type=row['event_type'],
                    base_impact=row['base_impact'] or 0,
                    surprise_scaling=row['surprise_scaling'] or 1,
                    fomc_proximity_boost=row['fomc_proximity_boost'] or 0,
                    high_vix_multiplier=row['high_vix_multiplier'] or 1,
                    dp_confirmation_boost=row['dp_confirmation_boost'] or 0,
                    sample_count=row['sample_count'] or 0,
                    r_squared=row['r_squared'] or 0,
                    mean_absolute_error=row['mean_absolute_error'] or 0,
                    last_5_predictions=json.loads(row['last_5_predictions'] or '[]'),
                    last_updated=row['last_updated'] or ""
                )
            
            return patterns
    
    # ========================================================================
    # FED WATCH HISTORY
    # ========================================================================
    
    def save_fed_watch(self, cut_prob: float, hold_prob: float, hike_prob: float = 0,
                       meeting_date: str = None, source: str = "perplexity"):
        """Save Fed Watch snapshot."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fed_watch_history
                (timestamp, cut_prob, hold_prob, hike_prob, meeting_date, source)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                cut_prob, hold_prob, hike_prob,
                meeting_date or "December 2025",
                source
            ))
    
    def get_fed_watch_at_time(self, target_time: str) -> Optional[Dict]:
        """Get Fed Watch closest to a specific time."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM fed_watch_history
                WHERE timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (target_time,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "timestamp": row['timestamp'],
                    "cut": row['cut_prob'],
                    "hold": row['hold_prob'],
                    "hike": row['hike_prob']
                }
            return None
    
    # ========================================================================
    # PREDICTIONS TRACKING
    # ========================================================================
    
    def save_prediction(self, prediction: Prediction, event_date: str):
        """Save a prediction for later accuracy tracking."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            event_type = prediction.event_type.value if isinstance(prediction.event_type, EventType) else str(prediction.event_type)
            
            cursor.execute("""
                INSERT INTO predictions
                (timestamp, event_type, event_date, predicted_shift, predicted_fed_watch, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                prediction.timestamp,
                event_type,
                event_date,
                prediction.predicted_shift,
                prediction.predicted_fed_watch,
                prediction.confidence
            ))
    
    def update_prediction_outcome(self, event_date: str, event_type: str,
                                  actual_shift: float, actual_fed_watch: float):
        """Update prediction with actual outcome."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE predictions
                SET actual_shift = ?,
                    actual_fed_watch = ?,
                    error = ABS(predicted_shift - ?),
                    was_correct_direction = CASE
                        WHEN (predicted_shift > 0 AND ? > 0) OR (predicted_shift < 0 AND ? < 0) THEN 1
                        ELSE 0
                    END
                WHERE event_date = ? AND event_type = ?
            """, (actual_shift, actual_fed_watch, actual_shift, actual_shift, actual_shift, event_date, event_type))
    
    # ========================================================================
    # STATS
    # ========================================================================
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM economic_releases")
            release_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM economic_releases WHERE fed_watch_shift_1hr IS NOT NULL AND fed_watch_shift_1hr != 0")
            complete_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM learned_patterns")
            pattern_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM fed_watch_history")
            fed_watch_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM predictions WHERE actual_shift IS NOT NULL")
            prediction_accuracy_count = cursor.fetchone()[0]
            
            # Get accuracy if we have predictions
            accuracy = None
            if prediction_accuracy_count > 0:
                cursor.execute("SELECT AVG(was_correct_direction) FROM predictions WHERE actual_shift IS NOT NULL")
                accuracy = cursor.fetchone()[0]
            
            return {
                "total_releases": release_count,
                "complete_releases": complete_count,
                "learned_patterns": pattern_count,
                "fed_watch_snapshots": fed_watch_count,
                "predictions_tracked": prediction_accuracy_count,
                "prediction_accuracy": accuracy
            }

