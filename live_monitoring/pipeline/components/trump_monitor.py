"""
Trump Monitor Component - Modular Trump Intelligence

Extracted from run_all_monitors.py for clean separation of concerns.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class TrumpMonitor:
    """
    Monitors Trump news and generates exploit signals.
    
    Responsibilities:
    - Track Trump news and sentiment
    - Generate exploit signals
    - Deduplicate by topic (cooldown)
    - Filter by exploit score
    """
    
    def __init__(
        self,
        trump_pulse,
        trump_news_monitor,
        unified_mode: bool = False,
        alert_callback=None,
        cooldown_minutes: int = 60,
        min_exploit_score: int = 60
    ):
        """
        Initialize Trump Monitor.
        
        Args:
            trump_pulse: TrumpPulse instance
            trump_news_monitor: TrumpNewsMonitor instance
            unified_mode: If True, suppress individual alerts (for synthesis)
            alert_callback: Function to call when alert should be sent
            cooldown_minutes: Minutes to wait before alerting on same topic again
            min_exploit_score: Minimum exploit score to alert (0-100)
        """
        self.trump_pulse = trump_pulse
        self.trump_news = trump_news_monitor
        self.unified_mode = unified_mode
        self.alert_callback = alert_callback
        self.cooldown_minutes = cooldown_minutes
        self.min_exploit_score = min_exploit_score
        
        # Topic tracking for deduplication
        self.topic_tracker: Dict[str, datetime] = {}  # topic -> last_alert_time
        
        logger.info("🎯 TrumpMonitor initialized")
    
    def check(self) -> Dict[str, Any]:
        """
        Check Trump intelligence.
        
        Returns:
            Dict with situation, exploits, and alerts
        """
        result = {
            'situation': None,
            'exploits': [],
            'alerts': []
        }
        
        try:
            # Get current pulse
            situation = self.trump_pulse.get_current_situation()
            result['situation'] = situation
            
            # Get exploitable news
            exploitable = self.trump_news.get_exploitable_news()
            result['exploits'] = exploitable
            
            # Process top 3 exploits
            for exp in exploitable[:3]:
                # Extract topics from headline
                headline_lower = exp.news.headline.lower()
                topics = self._extract_topics(headline_lower)
                topic_key = topics[0] if topics else 'unknown'
                
                # Check cooldown
                if self._is_on_cooldown(topic_key):
                    logger.debug(f"   📊 Trump topic '{topic_key}' on cooldown - skipping")
                    continue
                
                # Update tracker
                self.topic_tracker[topic_key] = datetime.now()
                
                # Filter by exploit score
                if exp.exploit_score < self.min_exploit_score:
                    continue
                
                # In unified mode, only send CRITICAL (score >= 90)
                is_critical = exp.exploit_score >= 90
                
                if not self.unified_mode or is_critical:
                    # Create alert
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
                    
                    alert = {
                        'type': 'trump_exploit',
                        'embed': embed,
                        'content': None,
                        'source': 'trump_monitor',
                        'symbol': ",".join(exp.suggested_symbols[:3]) if exp.suggested_symbols else None
                    }
                    result['alerts'].append(alert)
                    
                    # Send via callback
                    if self.alert_callback:
                        self.alert_callback(alert)
                    
                    logger.info(f"   ✅ Trump alert sent: {topic_key} (Score: {exp.exploit_score:.0f})")
                else:
                    logger.debug(f"   📊 Trump exploit buffered for synthesis: {exp.suggested_action} (Score: {exp.exploit_score:.0f})")
            
            activity = getattr(situation, 'activity_level', 'N/A')
            sentiment = getattr(situation, 'overall_sentiment', 'UNKNOWN')
            logger.info(f"   Sentiment: {sentiment} | Exploits: {len(exploitable)}")
            
        except Exception as e:
            logger.error(f"   ❌ Trump check error: {e}")
            result['error'] = str(e)
        
        return result
    
    def _extract_topics(self, headline_lower: str) -> List[str]:
        """Extract topics from headline for deduplication"""
        topics = []
        
        if 'farm' in headline_lower or 'farmer' in headline_lower or 'agriculture' in headline_lower:
            topics.append('farm_aid')
        if 'tariff' in headline_lower or 'trade war' in headline_lower or 'china' in headline_lower:
            topics.append('trade_war')
        if 'ai' in headline_lower or 'artificial intelligence' in headline_lower:
            topics.append('ai_regulation')
        if 'ukraine' in headline_lower or 'zelensk' in headline_lower:
            topics.append('ukraine')
        if 'trade deal' in headline_lower or 'britain' in headline_lower or 'uk' in headline_lower:
            topics.append('uk_trade')
        
        # If no specific topic, use first 3 significant words
        if not topics:
            words = re.findall(r'\b[a-z]{4,}\b', headline_lower)
            topics = ['_'.join(words[:3])] if words else ['unknown']
        
        return topics
    
    def _is_on_cooldown(self, topic_key: str) -> bool:
        """Check if topic is on cooldown"""
        last_alert_time = self.topic_tracker.get(topic_key)
        if not last_alert_time:
            return False
        
        minutes_since = (datetime.now() - last_alert_time).total_seconds() / 60
        return minutes_since < self.cooldown_minutes

