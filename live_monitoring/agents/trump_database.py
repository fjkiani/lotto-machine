#!/usr/bin/env python3
"""
TRUMP STATEMENT DATABASE
========================
SQLite-based storage for Trump statements and market reactions.
The foundation of our data-driven approach.
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from trump_data_models import (
    TrumpStatement, StatementSource, TopicCorrelation, 
    Prediction, AgentAccuracy
)

logger = logging.getLogger(__name__)


class TrumpDatabase:
    """
    SQLite database for Trump statements and predictions.
    Stores everything we need to learn from.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize database"""
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / 'data' / 'trump_intelligence.db')
        
        self.db_path = db_path
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema
        self._init_schema()
        
        logger.info(f"📊 Trump Database initialized: {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_schema(self):
        """Create database tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Statements table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statements (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    url TEXT,
                    entities TEXT,  -- JSON array
                    topics TEXT,    -- JSON array
                    sentiment REAL DEFAULT 0,
                    intensity REAL DEFAULT 0,
                    urgency REAL DEFAULT 0,
                    embedding TEXT,  -- JSON array
                    spy_price_at_statement REAL,
                    spy_change_1min REAL,
                    spy_change_5min REAL,
                    spy_change_15min REAL,
                    spy_change_1hr REAL,
                    spy_change_1day REAL,
                    vix_at_statement REAL,
                    vix_change_1hr REAL,
                    symbol_impacts TEXT,  -- JSON dict
                    is_market_hours INTEGER DEFAULT 0,
                    market_data_collected INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # Topic correlations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS topic_correlations (
                    topic TEXT PRIMARY KEY,
                    statement_count INTEGER DEFAULT 0,
                    avg_spy_change_1hr REAL DEFAULT 0,
                    std_spy_change_1hr REAL DEFAULT 0,
                    median_spy_change_1hr REAL DEFAULT 0,
                    bullish_count INTEGER DEFAULT 0,
                    bearish_count INTEGER DEFAULT 0,
                    neutral_count INTEGER DEFAULT 0,
                    predicted_direction_accuracy REAL DEFAULT 0,
                    premarket_avg_impact REAL DEFAULT 0,
                    rth_avg_impact REAL DEFAULT 0,
                    afterhours_avg_impact REAL DEFAULT 0,
                    last_updated TEXT NOT NULL
                )
            ''')
            
            # Predictions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id TEXT PRIMARY KEY,
                    statement_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    predicted_direction TEXT NOT NULL,
                    predicted_magnitude REAL NOT NULL,
                    confidence REAL NOT NULL,
                    reasoning TEXT,
                    actual_direction TEXT,
                    actual_magnitude REAL,
                    was_direction_correct INTEGER,
                    magnitude_error REAL,
                    position_taken INTEGER DEFAULT 0,
                    position_size REAL DEFAULT 0,
                    profit_loss REAL,
                    contributing_agents TEXT,  -- JSON array
                    similar_statements_used TEXT,  -- JSON array
                    FOREIGN KEY (statement_id) REFERENCES statements(id)
                )
            ''')
            
            # Agent accuracy table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_accuracy (
                    agent_name TEXT PRIMARY KEY,
                    total_predictions INTEGER DEFAULT 0,
                    correct_predictions INTEGER DEFAULT 0,
                    rolling_correct INTEGER DEFAULT 0,
                    rolling_total INTEGER DEFAULT 0,
                    topic_accuracy TEXT,  -- JSON dict
                    high_confidence_accuracy REAL DEFAULT 0.5,
                    medium_confidence_accuracy REAL DEFAULT 0.5,
                    low_confidence_accuracy REAL DEFAULT 0.5,
                    last_updated TEXT NOT NULL
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_statements_timestamp ON statements(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_statements_topics ON statements(topics)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_predictions_statement ON predictions(statement_id)')
            
            conn.commit()
    
    # ==================== STATEMENT OPERATIONS ====================
    
    def save_statement(self, statement: TrumpStatement) -> bool:
        """Save a statement to the database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO statements 
                    (id, timestamp, source, raw_text, url, entities, topics, 
                     sentiment, intensity, urgency, embedding,
                     spy_price_at_statement, spy_change_1min, spy_change_5min,
                     spy_change_15min, spy_change_1hr, spy_change_1day,
                     vix_at_statement, vix_change_1hr, symbol_impacts,
                     is_market_hours, market_data_collected, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    statement.id,
                    statement.timestamp.isoformat(),
                    statement.source.value,
                    statement.raw_text,
                    statement.url,
                    json.dumps(statement.entities),
                    json.dumps(statement.topics),
                    statement.sentiment,
                    statement.intensity,
                    statement.urgency,
                    json.dumps(statement.embedding) if statement.embedding else None,
                    statement.spy_price_at_statement,
                    statement.spy_change_1min,
                    statement.spy_change_5min,
                    statement.spy_change_15min,
                    statement.spy_change_1hr,
                    statement.spy_change_1day,
                    statement.vix_at_statement,
                    statement.vix_change_1hr,
                    json.dumps(statement.symbol_impacts),
                    1 if statement.is_market_hours else 0,
                    1 if statement.market_data_collected else 0,
                    statement.created_at.isoformat()
                ))
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving statement: {e}")
            return False
    
    def get_statement(self, statement_id: str) -> Optional[TrumpStatement]:
        """Get a statement by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM statements WHERE id = ?', (statement_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_statement(row)
                return None
                
        except Exception as e:
            logger.error(f"Error getting statement: {e}")
            return None
    
    def get_statements_by_topic(self, topic: str, limit: int = 100) -> List[TrumpStatement]:
        """Get statements by topic"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Search in JSON array
                cursor.execute('''
                    SELECT * FROM statements 
                    WHERE topics LIKE ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (f'%"{topic}"%', limit))
                
                rows = cursor.fetchall()
                return [self._row_to_statement(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting statements by topic: {e}")
            return []
    
    def get_recent_statements(self, hours: int = 24, limit: int = 100) -> List[TrumpStatement]:
        """Get recent statements"""
        try:
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM statements 
                    WHERE timestamp > ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (cutoff, limit))
                
                rows = cursor.fetchall()
                return [self._row_to_statement(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting recent statements: {e}")
            return []
    
    def get_statements_needing_market_data(self, limit: int = 50) -> List[TrumpStatement]:
        """Get statements that need market reaction data"""
        try:
            # Get statements older than 1 hour that don't have market data
            cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM statements 
                    WHERE market_data_collected = 0 
                    AND timestamp < ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (cutoff, limit))
                
                rows = cursor.fetchall()
                return [self._row_to_statement(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting statements needing market data: {e}")
            return []
    
    def get_all_statements_with_market_data(self) -> List[TrumpStatement]:
        """Get all statements that have market reaction data"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM statements 
                    WHERE market_data_collected = 1 
                    ORDER BY timestamp DESC
                ''')
                
                rows = cursor.fetchall()
                return [self._row_to_statement(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting statements with market data: {e}")
            return []
    
    def statement_exists(self, text_hash: str) -> bool:
        """Check if a similar statement already exists (by text hash)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM statements WHERE id = ?', (text_hash,))
                return cursor.fetchone() is not None
        except:
            return False
    
    def _row_to_statement(self, row: sqlite3.Row) -> TrumpStatement:
        """Convert database row to TrumpStatement"""
        return TrumpStatement(
            id=row['id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            source=StatementSource(row['source']),
            raw_text=row['raw_text'],
            url=row['url'],
            entities=json.loads(row['entities']) if row['entities'] else [],
            topics=json.loads(row['topics']) if row['topics'] else [],
            sentiment=row['sentiment'] or 0.0,
            intensity=row['intensity'] or 0.0,
            urgency=row['urgency'] or 0.0,
            embedding=json.loads(row['embedding']) if row['embedding'] else None,
            spy_price_at_statement=row['spy_price_at_statement'],
            spy_change_1min=row['spy_change_1min'],
            spy_change_5min=row['spy_change_5min'],
            spy_change_15min=row['spy_change_15min'],
            spy_change_1hr=row['spy_change_1hr'],
            spy_change_1day=row['spy_change_1day'],
            vix_at_statement=row['vix_at_statement'],
            vix_change_1hr=row['vix_change_1hr'],
            symbol_impacts=json.loads(row['symbol_impacts']) if row['symbol_impacts'] else {},
            is_market_hours=bool(row['is_market_hours']),
            market_data_collected=bool(row['market_data_collected']),
            created_at=datetime.fromisoformat(row['created_at'])
        )
    
    # ==================== CORRELATION OPERATIONS ====================
    
    def save_topic_correlation(self, correlation: TopicCorrelation) -> bool:
        """Save topic correlation"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO topic_correlations
                    (topic, statement_count, avg_spy_change_1hr, std_spy_change_1hr,
                     median_spy_change_1hr, bullish_count, bearish_count, neutral_count,
                     predicted_direction_accuracy, premarket_avg_impact,
                     rth_avg_impact, afterhours_avg_impact, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    correlation.topic,
                    correlation.statement_count,
                    correlation.avg_spy_change_1hr,
                    correlation.std_spy_change_1hr,
                    correlation.median_spy_change_1hr,
                    correlation.bullish_count,
                    correlation.bearish_count,
                    correlation.neutral_count,
                    correlation.predicted_direction_accuracy,
                    correlation.premarket_avg_impact,
                    correlation.rth_avg_impact,
                    correlation.afterhours_avg_impact,
                    correlation.last_updated.isoformat()
                ))
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving correlation: {e}")
            return False
    
    def get_topic_correlation(self, topic: str) -> Optional[TopicCorrelation]:
        """Get correlation for a topic"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM topic_correlations WHERE topic = ?', (topic,))
                row = cursor.fetchone()
                
                if row:
                    return TopicCorrelation(
                        topic=row['topic'],
                        statement_count=row['statement_count'],
                        avg_spy_change_1hr=row['avg_spy_change_1hr'],
                        std_spy_change_1hr=row['std_spy_change_1hr'],
                        median_spy_change_1hr=row['median_spy_change_1hr'],
                        bullish_count=row['bullish_count'],
                        bearish_count=row['bearish_count'],
                        neutral_count=row['neutral_count'],
                        predicted_direction_accuracy=row['predicted_direction_accuracy'],
                        premarket_avg_impact=row['premarket_avg_impact'],
                        rth_avg_impact=row['rth_avg_impact'],
                        afterhours_avg_impact=row['afterhours_avg_impact'],
                        last_updated=datetime.fromisoformat(row['last_updated'])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error getting correlation: {e}")
            return None
    
    def get_all_correlations(self) -> List[TopicCorrelation]:
        """Get all topic correlations"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM topic_correlations ORDER BY statement_count DESC')
                rows = cursor.fetchall()
                
                correlations = []
                for row in rows:
                    correlations.append(TopicCorrelation(
                        topic=row['topic'],
                        statement_count=row['statement_count'],
                        avg_spy_change_1hr=row['avg_spy_change_1hr'],
                        std_spy_change_1hr=row['std_spy_change_1hr'],
                        median_spy_change_1hr=row['median_spy_change_1hr'],
                        bullish_count=row['bullish_count'],
                        bearish_count=row['bearish_count'],
                        neutral_count=row['neutral_count'],
                        predicted_direction_accuracy=row['predicted_direction_accuracy'],
                        premarket_avg_impact=row['premarket_avg_impact'],
                        rth_avg_impact=row['rth_avg_impact'],
                        afterhours_avg_impact=row['afterhours_avg_impact'],
                        last_updated=datetime.fromisoformat(row['last_updated'])
                    ))
                return correlations
                
        except Exception as e:
            logger.error(f"Error getting all correlations: {e}")
            return []
    
    # ==================== PREDICTION OPERATIONS ====================
    
    def save_prediction(self, prediction: Prediction) -> bool:
        """Save a prediction"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO predictions
                    (id, statement_id, timestamp, predicted_direction, predicted_magnitude,
                     confidence, reasoning, actual_direction, actual_magnitude,
                     was_direction_correct, magnitude_error, position_taken,
                     position_size, profit_loss, contributing_agents, similar_statements_used)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prediction.id,
                    prediction.statement_id,
                    prediction.timestamp.isoformat(),
                    prediction.predicted_direction,
                    prediction.predicted_magnitude,
                    prediction.confidence,
                    prediction.reasoning,
                    prediction.actual_direction,
                    prediction.actual_magnitude,
                    1 if prediction.was_direction_correct else 0 if prediction.was_direction_correct is not None else None,
                    prediction.magnitude_error,
                    1 if prediction.position_taken else 0,
                    prediction.position_size,
                    prediction.profit_loss,
                    json.dumps(prediction.contributing_agents),
                    json.dumps(prediction.similar_statements_used)
                ))
                
                return True
                
        except Exception as e:
            logger.error(f"Error saving prediction: {e}")
            return False
    
    def get_prediction_accuracy(self) -> Dict[str, Any]:
        """Get overall prediction accuracy stats"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Total predictions
                cursor.execute('SELECT COUNT(*) FROM predictions')
                total = cursor.fetchone()[0]
                
                # Correct predictions
                cursor.execute('SELECT COUNT(*) FROM predictions WHERE was_direction_correct = 1')
                correct = cursor.fetchone()[0]
                
                # By confidence level
                cursor.execute('''
                    SELECT 
                        CASE 
                            WHEN confidence > 0.7 THEN 'high'
                            WHEN confidence > 0.4 THEN 'medium'
                            ELSE 'low'
                        END as conf_level,
                        COUNT(*) as total,
                        SUM(CASE WHEN was_direction_correct = 1 THEN 1 ELSE 0 END) as correct
                    FROM predictions
                    WHERE was_direction_correct IS NOT NULL
                    GROUP BY conf_level
                ''')
                
                by_confidence = {}
                for row in cursor.fetchall():
                    by_confidence[row['conf_level']] = {
                        'total': row['total'],
                        'correct': row['correct'],
                        'accuracy': row['correct'] / row['total'] if row['total'] > 0 else 0
                    }
                
                return {
                    'total_predictions': total,
                    'correct_predictions': correct,
                    'overall_accuracy': correct / total if total > 0 else 0,
                    'by_confidence': by_confidence
                }
                
        except Exception as e:
            logger.error(f"Error getting prediction accuracy: {e}")
            return {}
    
    # ==================== STATS ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Statement counts
                cursor.execute('SELECT COUNT(*) FROM statements')
                total_statements = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM statements WHERE market_data_collected = 1')
                with_market_data = cursor.fetchone()[0]
                
                # Topic counts
                cursor.execute('SELECT COUNT(*) FROM topic_correlations')
                topic_count = cursor.fetchone()[0]
                
                # Prediction counts
                cursor.execute('SELECT COUNT(*) FROM predictions')
                prediction_count = cursor.fetchone()[0]
                
                # Recent activity
                cursor.execute('''
                    SELECT COUNT(*) FROM statements 
                    WHERE timestamp > datetime('now', '-24 hours')
                ''')
                last_24h = cursor.fetchone()[0]
                
                return {
                    'total_statements': total_statements,
                    'statements_with_market_data': with_market_data,
                    'topic_correlations': topic_count,
                    'total_predictions': prediction_count,
                    'statements_last_24h': last_24h
                }
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}


if __name__ == "__main__":
    # Test the database
    logging.basicConfig(level=logging.INFO)
    
    db = TrumpDatabase()
    
    # Create test statement
    test_statement = TrumpStatement(
        id=TrumpStatement.generate_id("Test tariff statement about China", datetime.now()),
        timestamp=datetime.now(),
        source=StatementSource.NEWS,
        raw_text="Test tariff statement about China",
        entities=["China"],
        topics=["tariff", "china"]
    )
    
    # Save it
    db.save_statement(test_statement)
    print(f"✅ Saved test statement")
    
    # Get stats
    stats = db.get_stats()
    print(f"📊 Database stats: {stats}")


