"""
Alert Logger Component - Database Logging

Extracted from run_all_monitors.py for clean separation of concerns.
"""

import logging
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AlertLogger:
    """
    Handles alert logging to database.
    
    Responsibilities:
    - Initialize database schema
    - Log all alerts to database
    - Ensure persistence even if Discord fails
    """
    
    def __init__(self, db_path: str = "data/alerts_history.db"):
        """
        Initialize Alert Logger.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._init_database()
        logger.info(f"📝 AlertLogger initialized: {self.db_path}")
    
    def _init_database(self):
        """Initialize database schema"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    content TEXT,
                    embed_json TEXT,
                    source TEXT,
                    symbol TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON alerts(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(alert_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol ON alerts(symbol)
            """)
            
            conn.commit()
            conn.close()
            logger.debug(f"   ✅ Alert database initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to initialize alert database: {e}")
    
    def log_alert(
        self,
        alert_type: str,
        embed: Dict[str, Any],
        content: Optional[str] = None,
        source: str = "monitor",
        symbol: Optional[str] = None
    ) -> bool:
        """
        Log alert to database.
        
        Args:
            alert_type: Type of alert (fed_watch, trump_exploit, etc.)
            embed: Discord embed dict
            content: Optional content text
            source: Source of alert (fed_monitor, trump_monitor, etc.)
            symbol: Optional symbol (SPY, QQQ, etc.)
        
        Returns:
            True if logged successfully
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.utcnow().isoformat()
            title = embed.get('title', '')
            description = embed.get('description', '')
            embed_json = json.dumps(embed)
            
            cursor.execute("""
                INSERT INTO alerts (timestamp, alert_type, title, description, content, embed_json, source, symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, alert_type, title, description, content, embed_json, source, symbol))
            
            conn.commit()
            conn.close()
            logger.debug(f"   📝 Alert logged to database: {alert_type}")
            return True
        except Exception as e:
            logger.debug(f"   ⚠️ Failed to log alert to database: {e}")
            return False
    
    def get_recent_alerts(
        self,
        limit: int = 50,
        alert_type: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> list:
        """
        Get recent alerts from database.
        
        Args:
            limit: Maximum number of alerts to return
            alert_type: Filter by alert type (optional)
            symbol: Filter by symbol (optional)
        
        Returns:
            List of alert dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []
            
            if alert_type:
                query += " AND alert_type = ?"
                params.append(alert_type)
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert to dicts
            columns = [desc[0] for desc in cursor.description]
            alerts = [dict(zip(columns, row)) for row in rows]
            
            conn.close()
            return alerts
        except Exception as e:
            logger.error(f"   ❌ Failed to get alerts from database: {e}")
            return []

