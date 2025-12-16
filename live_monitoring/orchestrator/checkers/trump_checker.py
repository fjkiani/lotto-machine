"""
Trump Checker - Monitors Trump intelligence and exploitable news.

Extracted from unified_monitor.py for modularity.
"""

import logging
import re
from datetime import datetime
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class TrumpChecker(BaseChecker):
    """
    Checks Trump intelligence and exploitable news.
    
    Responsibilities:
    - Monitor Trump Pulse for current situation
    - Track exploitable news with exploit scores
    - Topic-based deduplication (farm aid, trade war, etc.)
    - Alert on high-score exploits (>=60)
    """
    
    def __init__(self, alert_manager, trump_pulse=None, trump_news=None, unified_mode=False):
        """
        Initialize Trump checker.
        
        Args:
            alert_manager: AlertManager instance
            trump_pulse: TrumpPulse instance (optional)
            trump_news: TrumpNews instance (optional)
            unified_mode: Whether unified mode is enabled (affects alerting)
        """
        super().__init__(alert_manager)
        self.trump_pulse = trump_pulse
        self.trump_news = trump_news
        self.unified_mode = unified_mode
        
        # State tracking
        self.trump_topic_tracker = {}
        self.trump_cooldown_minutes = 60
    
    @property
    def name(self) -> str:
        return "trump_checker"
    
    def check(self) -> List[CheckerAlert]:
        """
        Check Trump intelligence.
        
        Returns:
            List of CheckerAlert objects
        """
        alerts = []
        
        if not self.trump_pulse or not self.trump_news:
            return alerts
        
        logger.info("🎯 Checking Trump Intelligence...")
        
        try:
            situation = self.trump_pulse.get_current_situation()
            exploitable = self.trump_news.get_exploitable_news()
            
            for exp in exploitable[:3]:
                headline_lower = exp.news.headline.lower()
                
                # Extract topics from headline
                topics = []
                if 'farm' in headline_lower or 'farmer' in headline_lower:
                    topics.append('farm_aid')
                if 'tariff' in headline_lower or 'trade war' in headline_lower:
                    topics.append('trade_war')
                
                if not topics:
                    # Extract general topic from words
                    words = re.findall(r'\b[a-z]{4,}\b', headline_lower)
                    topics = ['_'.join(words[:3])] if words else ['unknown']
                
                now = datetime.now()
                topic_key = topics[0] if topics else 'unknown'
                
                # Check cooldown
                last_alert_time = self.trump_topic_tracker.get(topic_key)
                if last_alert_time:
                    minutes_since = (now - last_alert_time).total_seconds() / 60
                    if minutes_since < self.trump_cooldown_minutes:
                        continue
                
                self.trump_topic_tracker[topic_key] = now
                
                # Filter by exploit score
                if exp.exploit_score < 60:
                    continue
                
                is_critical = exp.exploit_score >= 90
                
                # Alert logic based on unified mode
                if not self.unified_mode or is_critical:
                    embed = {
                        "title": f"🎯 TRUMP EXPLOIT: {exp.suggested_action} (Score: {exp.exploit_score:.0f})",
                        "color": 16776960,
                        "description": exp.news.headline[:200],
                        "fields": [
                            {"name": "📊 Action", "value": exp.suggested_action, "inline": True},
                            {"name": "📈 Symbols", "value": ", ".join(exp.suggested_symbols[:3]), "inline": True},
                            {"name": "💯 Confidence", "value": f"{exp.confidence:.0f}%", "inline": True},
                        ],
                        "footer": {"text": f"Trump Intelligence | Topic: {topic_key}"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    symbol = ",".join(exp.suggested_symbols[:3]) if exp.suggested_symbols else None
                    
                    alerts.append(CheckerAlert(
                        embed=embed,
                        content="",
                        alert_type="trump_exploit",
                        source="trump_monitor",
                        symbol=symbol
                    ))
            
        except Exception as e:
            logger.error(f"   ❌ Trump check error: {e}")
        
        return alerts

