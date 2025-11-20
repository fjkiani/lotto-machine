"""
Alert Manager & Feedback Loop
Implements Alpha's blueprint for alerts and auto-tuning

Features:
- Push alerts to dashboard, SMS, Telegram, etc.
- Log every event, anomaly, cluster, and narrative for post-mortem
- Feedback & auto-tune: Feed results into model for threshold tweaking
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import asyncio
import json
import sqlite3
from dataclasses import asdict

logger = logging.getLogger(__name__)

class AlertManager:
    """
    Manages alerts and notifications
    
    Output channels:
    - Dashboard (Streamlit)
    - SMS
    - Telegram
    - Email
    - Webhook
    - Database logging
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Alert channels
        self.channels = {
            'dashboard': config.get('dashboard_alerts', True),
            'sms': config.get('sms_alerts', False),
            'telegram': config.get('telegram_alerts', False),
            'email': config.get('email_alerts', False),
            'webhook': config.get('webhook_alerts', False),
            'database': config.get('database_logging', True)
        }
        
        # Alert thresholds
        self.alert_thresholds = {
            'critical': config.get('critical_threshold', 0.9),
            'high': config.get('high_threshold', 0.7),
            'medium': config.get('medium_threshold', 0.5),
            'low': config.get('low_threshold', 0.3)
        }
        
        # Database for logging
        self.db_path = config.get('database_path', 'intelligence_alerts.db')
        self.db_connection = None
        
        # Pending alerts queue
        self.pending_alerts = []
        
        logger.info("AlertManager initialized - ready for multi-channel alerts")
    
    async def initialize(self):
        """Initialize alert manager"""
        try:
            # Initialize database
            await self._initialize_database()
            
            # Initialize external channels
            if self.channels['telegram']:
                await self._initialize_telegram()
            
            if self.channels['sms']:
                await self._initialize_sms()
            
            if self.channels['email']:
                await self._initialize_email()
            
            logger.info("AlertManager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing AlertManager: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.db_connection:
            self.db_connection.close()
    
    async def send_alert(self, alert: Any):
        """Send alert through all configured channels"""
        try:
            # Determine alert level
            alert_level = self._determine_alert_level(alert.conviction_score)
            
            # Format alert message
            message = self._format_alert_message(alert, alert_level)
            
            # Send to all channels
            tasks = []
            
            if self.channels['dashboard']:
                tasks.append(self._send_dashboard_alert(alert, message))
            
            if self.channels['sms'] and alert_level in ['critical', 'high']:
                tasks.append(self._send_sms_alert(message))
            
            if self.channels['telegram'] and alert_level in ['critical', 'high', 'medium']:
                tasks.append(self._send_telegram_alert(message))
            
            if self.channels['email'] and alert_level in ['critical', 'high']:
                tasks.append(self._send_email_alert(alert, message))
            
            if self.channels['webhook']:
                tasks.append(self._send_webhook_alert(alert, message))
            
            if self.channels['database']:
                tasks.append(self._log_alert_to_database(alert, message, alert_level))
            
            # Execute all sends in parallel
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info(f"Alert sent for {alert.ticker} (conviction: {alert.conviction_score:.2f})")
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    async def process_pending_alerts(self):
        """Process any pending alerts"""
        try:
            if not self.pending_alerts:
                return
            
            # Process alerts in batch
            alerts_to_process = self.pending_alerts.copy()
            self.pending_alerts.clear()
            
            for alert in alerts_to_process:
                await self.send_alert(alert)
            
        except Exception as e:
            logger.error(f"Error processing pending alerts: {e}")
    
    def _determine_alert_level(self, conviction_score: float) -> str:
        """Determine alert level based on conviction score"""
        if conviction_score >= self.alert_thresholds['critical']:
            return 'critical'
        elif conviction_score >= self.alert_thresholds['high']:
            return 'high'
        elif conviction_score >= self.alert_thresholds['medium']:
            return 'medium'
        elif conviction_score >= self.alert_thresholds['low']:
            return 'low'
        else:
            return 'info'
    
    def _format_alert_message(self, alert: Any, alert_level: str) -> str:
        """Format alert message for different channels"""
        try:
            # Emoji based on alert level
            emoji_map = {
                'critical': '🚨',
                'high': '⚠️',
                'medium': '📊',
                'low': 'ℹ️',
                'info': '📈'
            }
            
            emoji = emoji_map.get(alert_level, '📈')
            
            # Format message
            message = f"{emoji} ALERT: {alert.ticker}\n"
            message += f"Conviction: {alert.conviction_score:.2f}\n"
            message += f"Anomalies: {', '.join(alert.anomaly_types)}\n"
            message += f"Action: {alert.suggested_action}\n"
            message += f"Risk: {alert.risk_level}\n"
            message += f"Time: {alert.timestamp.strftime('%H:%M:%S')}\n"
            
            if alert.narrative:
                message += f"\nNarrative: {alert.narrative[:200]}..."
            
            return message
            
        except Exception as e:
            logger.error(f"Error formatting alert message: {e}")
            return f"Alert for {alert.ticker} - Conviction: {alert.conviction_score:.2f}"
    
    async def _send_dashboard_alert(self, alert: Any, message: str):
        """Send alert to Streamlit dashboard"""
        try:
            # Store in session state or global variable for dashboard
            # This would integrate with Streamlit's session state
            logger.info(f"DASHBOARD ALERT: {message}")
        except Exception as e:
            logger.error(f"Error sending dashboard alert: {e}")
    
    async def _send_sms_alert(self, message: str):
        """Send SMS alert"""
        try:
            # TODO: Implement SMS service (Twilio, etc.)
            logger.info(f"SMS ALERT: {message}")
        except Exception as e:
            logger.error(f"Error sending SMS alert: {e}")
    
    async def _send_telegram_alert(self, message: str):
        """Send Telegram alert"""
        try:
            # TODO: Implement Telegram Bot API
            logger.info(f"TELEGRAM ALERT: {message}")
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
    
    async def _send_email_alert(self, alert: Any, message: str):
        """Send email alert"""
        try:
            # TODO: Implement email service (SendGrid, etc.)
            logger.info(f"EMAIL ALERT: {message}")
        except Exception as e:
            logger.error(f"Error sending email alert: {e}")
    
    async def _send_webhook_alert(self, alert: Any, message: str):
        """Send webhook alert"""
        try:
            webhook_url = self.config.get('webhook_url')
            if not webhook_url:
                return
            
            # TODO: Implement webhook sending
            logger.info(f"WEBHOOK ALERT: {message}")
        except Exception as e:
            logger.error(f"Error sending webhook alert: {e}")
    
    async def _log_alert_to_database(self, alert: Any, message: str, alert_level: str):
        """Log alert to database for post-mortem analysis"""
        try:
            if not self.db_connection:
                return
            
            cursor = self.db_connection.cursor()
            
            cursor.execute("""
                INSERT INTO alerts (
                    ticker, timestamp, conviction_score, anomaly_types,
                    suggested_action, risk_level, narrative, alert_level,
                    message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.ticker,
                alert.timestamp.isoformat(),
                alert.conviction_score,
                json.dumps(alert.anomaly_types),
                alert.suggested_action,
                alert.risk_level,
                alert.narrative,
                alert_level,
                message,
                datetime.now().isoformat()
            ))
            
            self.db_connection.commit()
            
        except Exception as e:
            logger.error(f"Error logging alert to database: {e}")
    
    async def _initialize_database(self):
        """Initialize SQLite database for logging"""
        try:
            self.db_connection = sqlite3.connect(self.db_path)
            cursor = self.db_connection.cursor()
            
            # Create alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    conviction_score REAL NOT NULL,
                    anomaly_types TEXT NOT NULL,
                    suggested_action TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    narrative TEXT,
                    alert_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Create events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Create anomalies table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    anomaly_type TEXT NOT NULL,
                    severity REAL NOT NULL,
                    details TEXT NOT NULL,
                    conviction_score REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Create performance table for feedback
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id INTEGER,
                    ticker TEXT NOT NULL,
                    alert_timestamp TEXT NOT NULL,
                    actual_price_change REAL,
                    actual_volume_change REAL,
                    prediction_accuracy REAL,
                    feedback_score REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (alert_id) REFERENCES alerts (id)
                )
            """)
            
            self.db_connection.commit()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    async def _initialize_telegram(self):
        """Initialize Telegram bot"""
        try:
            # TODO: Initialize Telegram bot
            pass
        except Exception as e:
            logger.error(f"Error initializing Telegram: {e}")
    
    async def _initialize_sms(self):
        """Initialize SMS service"""
        try:
            # TODO: Initialize SMS service
            pass
        except Exception as e:
            logger.error(f"Error initializing SMS: {e}")
    
    async def _initialize_email(self):
        """Initialize email service"""
        try:
            # TODO: Initialize email service
            pass
        except Exception as e:
            logger.error(f"Error initializing email: {e}")

class FeedbackLoop:
    """
    Feedback loop for auto-tuning thresholds
    
    Features:
    - Track alert performance
    - Adjust thresholds based on accuracy
    - Learn from false positives/negatives
    - Continuous improvement
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Feedback parameters
        self.learning_rate = config.get('learning_rate', 0.1)
        self.min_samples = config.get('min_samples', 10)
        self.feedback_window_days = config.get('feedback_window_days', 7)
        
        # Threshold adjustment limits
        self.max_threshold_adjustment = config.get('max_threshold_adjustment', 0.2)
        
        logger.info("FeedbackLoop initialized - ready for auto-tuning")
    
    async def update_thresholds(self, recent_alerts: List[Any]):
        """Update thresholds based on recent alert performance"""
        try:
            if len(recent_alerts) < self.min_samples:
                return
            
            # Analyze performance
            performance_metrics = await self._analyze_performance(recent_alerts)
            
            # Adjust thresholds
            await self._adjust_thresholds(performance_metrics)
            
            logger.info(f"Thresholds updated based on {len(recent_alerts)} alerts")
            
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")
    
    async def _analyze_performance(self, alerts: List[Any]) -> Dict[str, Any]:
        """Analyze alert performance"""
        try:
            metrics = {
                'total_alerts': len(alerts),
                'accuracy_rate': 0.0,
                'false_positive_rate': 0.0,
                'false_negative_rate': 0.0,
                'avg_conviction_score': 0.0,
                'threshold_adjustments': {}
            }
            
            # Calculate accuracy (simplified - would need actual market data)
            correct_predictions = 0
            for alert in alerts:
                # TODO: Compare alert prediction with actual market movement
                # For now, use a simple heuristic
                if alert.conviction_score > 0.8:
                    correct_predictions += 1
            
            metrics['accuracy_rate'] = correct_predictions / len(alerts) if alerts else 0.0
            metrics['avg_conviction_score'] = sum(a.conviction_score for a in alerts) / len(alerts) if alerts else 0.0
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return {}
    
    async def _adjust_thresholds(self, metrics: Dict[str, Any]):
        """Adjust thresholds based on performance"""
        try:
            accuracy_rate = metrics.get('accuracy_rate', 0.5)
            
            # If accuracy is low, adjust thresholds
            if accuracy_rate < 0.6:  # Low accuracy
                # Increase thresholds to reduce false positives
                adjustment = min(self.max_threshold_adjustment, 0.1)
                logger.info(f"Low accuracy detected ({accuracy_rate:.2f}), increasing thresholds by {adjustment}")
            
            elif accuracy_rate > 0.8:  # High accuracy
                # Decrease thresholds to catch more opportunities
                adjustment = min(self.max_threshold_adjustment, 0.05)
                logger.info(f"High accuracy detected ({accuracy_rate:.2f}), decreasing thresholds by {adjustment}")
            
        except Exception as e:
            logger.error(f"Error adjusting thresholds: {e}")
    
    async def add_feedback(self, alert_id: int, actual_outcome: Dict[str, Any]):
        """Add feedback for a specific alert"""
        try:
            # TODO: Store feedback in database
            logger.debug(f"Added feedback for alert {alert_id}")
        except Exception as e:
            logger.error(f"Error adding feedback: {e}")



