"""
📈 Market Impact Learner - Learns from Actual Price Moves
==========================================================
NOT hardcoded weights! Learns: Official + Sentiment → Actual Market Move
"""

import logging
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional
from .database import FedOfficialsDatabase
from .models import MarketImpactPattern

logger = logging.getLogger(__name__)


class ImpactLearner:
    """Learns market impact from actual price movements."""
    
    def __init__(self, database: FedOfficialsDatabase):
        self.db = database
    
    def predict_impact(self, official_name: str, sentiment: str) -> tuple:
        """
        Predict market impact based on learned patterns.
        
        Returns: (predicted_impact, confidence, reasoning)
        """
        # Query learned patterns
        conn = self.db.db_path
        import sqlite3
        conn_db = sqlite3.connect(conn)
        conn_db.row_factory = sqlite3.Row
        cursor = conn_db.cursor()
        
        cursor.execute("""
            SELECT * FROM market_impact_patterns
            WHERE official_name = ? AND sentiment = ?
            ORDER BY sample_count DESC, accuracy DESC
            LIMIT 1
        """, (official_name, sentiment))
        
        row = cursor.fetchone()
        conn_db.close()
        
        if row:
            # Found learned pattern
            avg_move = row['avg_spy_move_1hr']
            confidence = row['accuracy']
            
            if avg_move > 0.1:
                impact = "BULLISH"
            elif avg_move < -0.1:
                impact = "BEARISH"
            else:
                impact = "NEUTRAL"
            
            reasoning = f"Learned: {official_name} {sentiment} → {avg_move:.2f}% avg SPY move (n={row['sample_count']})"
            return impact, confidence, reasoning
        
        # No pattern yet - use defaults based on sentiment
        if sentiment == "HAWKISH":
            return "BEARISH", 0.5, "Hawkish = higher rates = bearish (default)"
        elif sentiment == "DOVISH":
            return "BULLISH", 0.5, "Dovish = lower rates = bullish (default)"
        else:
            return "NEUTRAL", 0.3, "Neutral sentiment (default)"
    
    def learn_from_outcome(self, comment_id: int, official_name: str, sentiment: str):
        """
        Learn from actual market outcome after a comment.
        
        Should be called 1-4 hours after comment to see actual impact.
        """
        try:
            # Get comment timestamp
            import sqlite3
            conn = sqlite3.connect(self.db.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT timestamp FROM comments WHERE id = ?", (comment_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return
            
            comment_time = datetime.fromisoformat(row['timestamp'])
            conn.close()
            
            # Get SPY price at comment time and 1hr/4hr later
            spy_1hr = self._get_spy_move(comment_time, hours=1)
            spy_4hr = self._get_spy_move(comment_time, hours=4)
            
            if spy_1hr is None:
                return
            
            # Update pattern
            self._update_pattern(official_name, sentiment, spy_1hr, spy_4hr)
            
            logger.info(f"📚 Learned: {official_name} {sentiment} → {spy_1hr:.2f}% SPY (1hr)")
        
        except Exception as e:
            logger.warning(f"Impact learning error: {e}")
    
    def _get_spy_move(self, comment_time: datetime, hours: int) -> Optional[float]:
        """Get SPY price move X hours after comment."""
        try:
            ticker = yf.Ticker("SPY")
            
            # Get minute data around comment time
            start = comment_time - timedelta(minutes=30)
            end = comment_time + timedelta(hours=hours+1)
            
            hist = ticker.history(start=start, end=end, interval='1m')
            if hist.empty:
                return None
            
            # Price at comment time (or closest)
            comment_idx = hist.index.get_indexer([comment_time], method='nearest')[0]
            if comment_idx < 0:
                return None
            
            price_at_comment = float(hist['Close'].iloc[comment_idx])
            
            # Price X hours later
            later_time = comment_time + timedelta(hours=hours)
            later_idx = hist.index.get_indexer([later_time], method='nearest')[0]
            if later_idx < 0 or later_idx >= len(hist):
                return None
            
            price_later = float(hist['Close'].iloc[later_idx])
            
            # Calculate % move
            move_pct = ((price_later - price_at_comment) / price_at_comment) * 100
            return move_pct
        
        except Exception as e:
            logger.debug(f"SPY move calculation error: {e}")
            return None
    
    def _update_pattern(self, official_name: str, sentiment: str, move_1hr: float, move_4hr: float):
        """Update learned pattern in database."""
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        # Check if pattern exists
        cursor.execute("""
            SELECT * FROM market_impact_patterns
            WHERE official_name = ? AND sentiment = ?
        """, (official_name, sentiment))
        
        row = cursor.fetchone()
        
        if row:
            # Update existing
            sample_count = row[5] + 1
            avg_1hr = (row[3] * row[5] + move_1hr) / sample_count
            avg_4hr = (row[4] * row[5] + move_4hr) / sample_count
            
            # Simple accuracy: how often prediction matched direction
            predicted = "BULLISH" if avg_1hr > 0 else "BEARISH" if avg_1hr < 0 else "NEUTRAL"
            actual = "BULLISH" if move_1hr > 0 else "BEARISH" if move_1hr < 0 else "NEUTRAL"
            accuracy = (row[6] * row[5] + (1.0 if predicted == actual else 0.0)) / sample_count
            
            cursor.execute("""
                UPDATE market_impact_patterns
                SET avg_spy_move_1hr = ?, avg_spy_move_4hr = ?,
                    sample_count = ?, accuracy = ?, last_updated = ?
                WHERE official_name = ? AND sentiment = ?
            """, (avg_1hr, avg_4hr, sample_count, accuracy, datetime.now().isoformat(), official_name, sentiment))
        else:
            # Create new
            predicted = "BULLISH" if move_1hr > 0 else "BEARISH" if move_1hr < 0 else "NEUTRAL"
            actual = "BULLISH" if move_1hr > 0 else "BEARISH" if move_1hr < 0 else "NEUTRAL"
            accuracy = 1.0 if predicted == actual else 0.0
            
            cursor.execute("""
                INSERT INTO market_impact_patterns
                (official_name, sentiment, avg_spy_move_1hr, avg_spy_move_4hr, sample_count, accuracy, last_updated)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (official_name, sentiment, move_1hr, move_4hr, accuracy, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()


