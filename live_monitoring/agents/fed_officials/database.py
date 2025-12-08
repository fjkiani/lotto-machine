"""
💾 Database Layer - Learn from Historical Data
==============================================
Stores comments, learns patterns, tracks performance.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

from .models import (
    FedComment, FedOfficial, QueryPerformance,
    SentimentPattern, MarketImpactPattern
)

logger = logging.getLogger(__name__)


class FedOfficialsDatabase:
    """SQLite database for Fed intelligence."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(__file__).parent.parent.parent.parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "fed_officials.db")
        
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Comments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                official_name TEXT NOT NULL,
                headline TEXT,
                content TEXT NOT NULL,
                source TEXT,
                url TEXT,
                sentiment TEXT,
                sentiment_confidence REAL,
                sentiment_reasoning TEXT,
                predicted_market_impact TEXT,
                actual_market_impact TEXT,
                impact_accuracy REAL,
                comment_hash TEXT UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Officials table (learned from data)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS officials (
                name TEXT PRIMARY KEY,
                position TEXT,
                voting_member INTEGER,
                historical_sentiment TEXT,
                market_impact_score REAL,
                comment_frequency INTEGER,
                detected_keywords TEXT,  -- JSON array
                first_seen TEXT,
                last_seen TEXT
            )
        """)
        
        # Query performance tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_performance (
                query_template TEXT PRIMARY KEY,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                avg_comments_found REAL DEFAULT 0.0,
                last_used TEXT
            )
        """)
        
        # Sentiment patterns (learned)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_patterns (
                phrase TEXT PRIMARY KEY,
                sentiment TEXT,
                confidence REAL,
                sample_count INTEGER,
                last_seen TEXT
            )
        """)
        
        # Market impact patterns (learned)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_impact_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                official_name TEXT,
                sentiment TEXT,
                avg_spy_move_1hr REAL,
                avg_spy_move_4hr REAL,
                sample_count INTEGER,
                accuracy REAL,
                last_updated TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"📊 Fed Officials Database initialized: {self.db_path}")
    
    def save_comment(self, comment: FedComment) -> int:
        """Save a comment and return its ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO comments (
                    timestamp, official_name, headline, content, source, url,
                    sentiment, sentiment_confidence, sentiment_reasoning,
                    predicted_market_impact, actual_market_impact, impact_accuracy,
                    comment_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                comment.timestamp.isoformat(),
                comment.official_name,
                comment.headline,
                comment.content,
                comment.source,
                comment.url,
                comment.sentiment,
                comment.sentiment_confidence,
                comment.sentiment_reasoning,
                comment.predicted_market_impact,
                comment.actual_market_impact,
                comment.impact_accuracy,
                comment.comment_hash,
            ))
            
            comment_id = cursor.lastrowid
            conn.commit()
            return comment_id
        except sqlite3.IntegrityError:
            # Duplicate hash
            return 0
        finally:
            conn.close()
    
    def get_recent_comments(self, hours: int = 24, limit: int = 50) -> List[FedComment]:
        """Get recent comments."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff = datetime.now().timestamp() - (hours * 3600)
        
        cursor.execute("""
            SELECT * FROM comments
            WHERE datetime(timestamp) > datetime(?, 'unixepoch')
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        comments = []
        for row in rows:
            comments.append(FedComment(
                timestamp=datetime.fromisoformat(row['timestamp']),
                official_name=row['official_name'],
                headline=row['headline'] or '',
                content=row['content'],
                source=row['source'] or '',
                url=row['url'],
                sentiment=row['sentiment'] or 'NEUTRAL',
                sentiment_confidence=row['sentiment_confidence'] or 0.0,
                sentiment_reasoning=row['sentiment_reasoning'] or '',
                predicted_market_impact=row['predicted_market_impact'] or 'UNKNOWN',
                actual_market_impact=row['actual_market_impact'],
                impact_accuracy=row['impact_accuracy'],
                comment_hash=row['comment_hash'] or '',
            ))
        
        return comments
    
    def update_official(self, official: FedOfficial):
        """Update or create an official (learned from data)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO officials (
                name, position, voting_member, historical_sentiment,
                market_impact_score, comment_frequency, detected_keywords,
                first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            official.name,
            official.position.value if official.position else None,
            int(official.voting_member),
            official.historical_sentiment,
            official.market_impact_score,
            official.comment_frequency,
            json.dumps(official.detected_keywords),
            official.first_seen.isoformat() if official.first_seen else None,
            official.last_seen.isoformat() if official.last_seen else None,
        ))
        
        conn.commit()
        conn.close()
    
    def get_officials(self) -> List[FedOfficial]:
        """Get all tracked officials (learned from data)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM officials ORDER BY comment_frequency DESC")
        rows = cursor.fetchall()
        conn.close()
        
        officials = []
        for row in rows:
            from .models import FedPosition
            position = None
            if row['position']:
                try:
                    position = FedPosition(row['position'])
                except:
                    pass
            
            officials.append(FedOfficial(
                name=row['name'],
                position=position,
                voting_member=bool(row['voting_member']),
                historical_sentiment=row['historical_sentiment'] or 'NEUTRAL',
                market_impact_score=row['market_impact_score'] or 1.0,
                comment_frequency=row['comment_frequency'] or 0,
                detected_keywords=json.loads(row['detected_keywords'] or '[]'),
                first_seen=datetime.fromisoformat(row['first_seen']) if row['first_seen'] else None,
                last_seen=datetime.fromisoformat(row['last_seen']) if row['last_seen'] else None,
            ))
        
        return officials
    
    def track_query_performance(self, query_template: str, success: bool, comments_found: int):
        """Track which queries work best."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO query_performance (query_template, success_count, failure_count, avg_comments_found, last_used)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(query_template) DO UPDATE SET
                success_count = success_count + ?,
                failure_count = failure_count + ?,
                avg_comments_found = (avg_comments_found * (success_count + failure_count) + ?) / (success_count + failure_count + 1),
                last_used = ?
        """, (
            query_template,
            1 if success else 0,
            0 if success else 1,
            comments_found,
            datetime.now().isoformat(),
            # Update values
            1 if success else 0,
            0 if success else 1,
            comments_found,
            datetime.now().isoformat(),
        ))
        
        conn.commit()
        conn.close()
    
    def get_best_queries(self, limit: int = 5) -> List[str]:
        """Get best-performing query templates."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT query_template FROM query_performance
            WHERE success_count > 0
            ORDER BY (success_count * 1.0 / (success_count + failure_count)) DESC,
                     avg_comments_found DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [row['query_template'] for row in rows]
    
    def save_sentiment_pattern(self, pattern: SentimentPattern):
        """Save a learned sentiment pattern."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO sentiment_patterns (phrase, sentiment, confidence, sample_count, last_seen)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pattern.phrase,
            pattern.sentiment,
            pattern.confidence,
            pattern.sample_count,
            pattern.last_seen.isoformat() if pattern.last_seen else None,
        ))
        
        conn.commit()
        conn.close()
    
    def get_sentiment_patterns(self, limit: int = 100) -> List[SentimentPattern]:
        """Get learned sentiment patterns."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM sentiment_patterns
            ORDER BY confidence DESC, sample_count DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        patterns = []
        for row in rows:
            patterns.append(SentimentPattern(
                phrase=row['phrase'],
                sentiment=row['sentiment'],
                confidence=row['confidence'],
                sample_count=row['sample_count'],
                last_seen=datetime.fromisoformat(row['last_seen']) if row['last_seen'] else None,
            ))
        
        return patterns




