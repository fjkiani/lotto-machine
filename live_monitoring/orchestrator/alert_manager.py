"""
🔔 ALERT MANAGER

Handles all Discord alerting, deduplication, and database logging.
"""

import os
import time
import hashlib
import re
import logging
import requests
import sqlite3
import json
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert sending, deduplication, and database logging."""
    
    def __init__(self, discord_webhook: Optional[str] = None, alert_db_path: str = "data/alerts_history.db"):
        self.discord_webhook = discord_webhook or os.getenv('DISCORD_WEBHOOK_URL')
        self.alert_db_path = alert_db_path
        self.sent_alerts: Dict[str, float] = {}  # alert_hash -> timestamp
        self.alert_cooldown_seconds = 300  # 5 minutes cooldown
        
        # Initialize database
        self._init_alert_database()
    
    def _init_alert_database(self):
        """Initialize database for storing all alerts."""
        try:
            os.makedirs(os.path.dirname(self.alert_db_path), exist_ok=True)
            
            conn = sqlite3.connect(self.alert_db_path)
            cursor = conn.cursor()
            
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
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON alerts(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alert_type ON alerts(alert_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON alerts(symbol)")
            
            conn.commit()
            conn.close()
            logger.info(f"   ✅ Alert database initialized: {self.alert_db_path}")
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to initialize alert database: {e}")
    
    def _log_alert_to_database(self, alert_type: str, embed: dict, content: str = None, source: str = "monitor", symbol: str = None):
        """Log alert to database for historical tracking — writes to BOTH SQLite and Supabase."""
        timestamp = datetime.utcnow().isoformat()
        title = embed.get('title', '')
        description = embed.get('description', '')
        embed_json = json.dumps(embed)

        # ── Write to local SQLite (fast, ephemeral on Render) ──
        try:
            conn = sqlite3.connect(self.alert_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts (timestamp, alert_type, title, description, content, embed_json, source, symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, alert_type, title, description, content, embed_json, source, symbol))
            conn.commit()
            conn.close()
            logger.debug(f"   📝 Alert logged to SQLite: {alert_type}")
        except Exception as e:
            logger.debug(f"   ⚠️ Failed to log alert to SQLite: {e}")

        # ── Write to Supabase (persistent, survives Render restarts) ──
        try:
            from core.utils.supabase_storage import is_supabase_available, write_alert
            if is_supabase_available():
                write_alert({
                    "timestamp": timestamp,
                    "alert_type": alert_type,
                    "title": title,
                    "description": description,
                    "content": content,
                    "embed_json": embed_json,
                    "source": source,
                    "symbol": symbol,
                })
                logger.debug(f"   ☁️ Alert logged to Supabase: {alert_type}")
        except Exception as e:
            logger.debug(f"   ⚠️ Supabase alert write failed (non-blocking): {e}")
    
    def _generate_alert_hash(self, embed: dict, content: str, alert_type: str, source: str, symbol: str) -> str:
        """Generate unique hash for alert deduplication.
        
        Uses STRUCTURAL identity only: alert_type + symbol + source + title.
        Deliberately excludes volatile numeric fields (prices, scores, percentages)
        that change every tick — including them caused every health ping and price
        update to bypass dedup and spam Discord.
        """
        title = embed.get('title', '')
        # Strip numbers from title so "$571.23" vs "$571.45" dedup correctly
        title_stripped = re.sub(r'[\d$.,%]+', '', title).strip()
        
        key_data = f"{alert_type}:{symbol or ''}:{source}:{title_stripped}"
        
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def send_discord(self, embed: dict, content: str = None, alert_type: str = "general", source: str = "monitor", symbol: str = None) -> bool:
        """Send Discord notification and log to database with deduplication."""
        logger.info(f"📤 AlertManager.send_discord called: type={alert_type}, source={source}, symbol={symbol}")
        
        alert_hash = self._generate_alert_hash(embed, content, alert_type, source, symbol)
        
        # Check if we've sent this alert recently
        if alert_hash in self.sent_alerts:
            last_sent = self.sent_alerts[alert_hash]
            elapsed = time.time() - last_sent
            if elapsed < self.alert_cooldown_seconds:
                logger.debug(f"   ⏭️ Alert duplicate (sent {elapsed:.0f}s ago) - skipping: {alert_type} {symbol or ''}")
                self._log_alert_to_database(alert_type, embed, content, source, symbol)
                return False
        
        # Mark as sent
        self.sent_alerts[alert_hash] = time.time()
        
        # Cleanup old entries
        if len(self.sent_alerts) > 100:
            cutoff = time.time() - 3600
            self.sent_alerts = {k: v for k, v in self.sent_alerts.items() if v > cutoff}
        
        # Always log to database first
        self._log_alert_to_database(alert_type, embed, content, source, symbol)
        
        # Publish to WebSocket (non-blocking, optional)
        self._publish_to_websocket(embed, content, alert_type, source, symbol)
        
        if not self.discord_webhook:
            logger.warning("   ⚠️ DISCORD_WEBHOOK_URL not set! (Alert logged to database)")
            logger.warning(f"   Webhook value: {self.discord_webhook}")
            return False
        
        logger.info(f"   📤 Sending to Discord webhook: {self.discord_webhook[:30]}...")
        
        try:
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content
            
            logger.info(f"   📦 Payload size: {len(str(payload))} chars")
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            
            if response.status_code in [200, 204]:
                logger.info(f"   ✅ Discord sent successfully (status: {response.status_code})")
                return True
            else:
                logger.error(f"   ❌ Discord returned status {response.status_code}: {response.text[:200]} (Alert logged to database)")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"   ❌ Discord request error: {e} (Alert logged to database)")
            return False
        except Exception as e:
            logger.error(f"   ❌ Discord error: {e} (Alert logged to database)")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def _publish_to_websocket(self, embed: dict, content: str = None, alert_type: str = "general", source: str = "monitor", symbol: str = None):
        """
        Publish alert to WebSocket (non-blocking, optional).
        
        This is a fire-and-forget operation that won't break
        existing functionality if WebSocket is unavailable.
        """
        try:
            # Try to import WebSocket bridge (may not be available)
            from backend.app.integrations.alert_websocket_bridge import publish_alert_to_websocket_sync
            publish_alert_to_websocket_sync(embed, content, alert_type, source, symbol)
        except ImportError:
            # WebSocket bridge not available - this is OK
            pass
        except Exception as e:
            # Log but don't fail - WebSocket is optional
            logger.debug(f"   ⚠️ WebSocket publish failed (non-critical): {e}")

