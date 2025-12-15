"""
Fed Monitor Component - Modular Fed Watch + Fed Officials

Extracted from run_all_monitors.py for clean separation of concerns.
"""

import logging
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FedStatus:
    """Fed Watch status"""
    prob_cut: float
    prob_hold: float
    most_likely_outcome: str


class FedMonitor:
    """
    Monitors Fed Watch probabilities and Fed official comments.
    
    Responsibilities:
    - Track Fed Watch probability changes
    - Monitor Fed official comments
    - Alert on significant changes
    - Deduplicate comments
    """
    
    def __init__(
        self,
        fed_watch_monitor,
        fed_officials_monitor,
        unified_mode: bool = False,
        alert_callback=None
    ):
        """
        Initialize Fed Monitor.
        
        Args:
            fed_watch_monitor: FedWatchMonitor instance
            fed_officials_monitor: FedOfficialsMonitor instance
            unified_mode: If True, suppress individual alerts (for synthesis)
            alert_callback: Function to call when alert should be sent
        """
        self.fed_watch = fed_watch_monitor
        self.fed_officials = fed_officials_monitor
        self.unified_mode = unified_mode
        self.alert_callback = alert_callback
        
        # State tracking
        self.prev_status: Optional[FedStatus] = None
        self.seen_comments = set()  # Track sent comments
        
        logger.info("🏦 FedMonitor initialized")
    
    def check(self) -> Dict[str, Any]:
        """
        Check Fed Watch and officials.
        
        Returns:
            Dict with status and any alerts generated
        """
        result = {
            'status': None,
            'alerts': [],
            'comments': []
        }
        
        try:
            # Get current Fed Watch status
            status = self.fed_watch.get_current_status(force_refresh=True)
            result['status'] = FedStatus(
                prob_cut=status.prob_cut,
                prob_hold=status.prob_hold,
                most_likely_outcome=status.most_likely_outcome
            )
            
            # Check for significant changes
            if self.prev_status:
                cut_change = abs(status.prob_cut - self.prev_status.prob_cut)
                hold_change = abs(status.prob_hold - self.prev_status.prob_hold)
                
                # Threshold: 15% in unified mode, 10% otherwise
                threshold = 15.0 if self.unified_mode else 10.0
                
                if cut_change >= threshold or hold_change >= threshold:
                    logger.info(f"   🚨 MAJOR CHANGE! Cut: {status.prob_cut:.1f}% ({cut_change:+.1f}%)")
                    
                    # Create alert
                    embed = {
                        "title": "🏦 FED WATCH ALERT - Major Probability Change!",
                        "color": 15548997,
                        "fields": [
                            {"name": "📉 Cut Probability", "value": f"{status.prob_cut:.1f}%", "inline": True},
                            {"name": "➡️ Hold Probability", "value": f"{status.prob_hold:.1f}%", "inline": True},
                            {"name": "🎯 Most Likely", "value": status.most_likely_outcome, "inline": True},
                        ],
                        "footer": {"text": "CME FedWatch | Rate expectations move markets!"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    alert = {
                        'type': 'fed_watch',
                        'embed': embed,
                        'content': "@everyone 🏦 Fed rate probability change!",
                        'source': 'fed_monitor',
                        'symbol': 'SPY'
                    }
                    result['alerts'].append(alert)
                    
                    # Send via callback if provided
                    if self.alert_callback:
                        self.alert_callback(alert)
                elif cut_change >= 5.0 or hold_change >= 5.0:
                    logger.info(f"   📊 Moderate change: Cut: {status.prob_cut:.1f}% ({cut_change:+.1f}%) - buffered for synthesis")
            
            self.prev_status = result['status']
            logger.info(f"   Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Most Likely: {status.most_likely_outcome}")
            
            # Check Fed officials
            logger.info("   🎤 Checking Fed officials...")
            report = self.fed_officials.get_report()
            
            if report.comments:
                for comment in report.comments[:3]:
                    # Create unique ID from hash
                    content_hash = hashlib.md5(
                        f"{comment.official.name}:{comment.content}".encode()
                    ).hexdigest()[:12]
                    comment_id = f"{comment.official.name}:{content_hash}"
                    
                    # Deduplicate
                    if comment_id in self.seen_comments:
                        continue
                    
                    self.seen_comments.add(comment_id)
                    
                    # Keep set size manageable (last 100)
                    if len(self.seen_comments) > 100:
                        self.seen_comments = set(list(self.seen_comments)[-100:])
                    
                    # In unified mode, only send CRITICAL (Powell with high confidence)
                    is_critical = comment.official.name == "Jerome Powell" and comment.confidence >= 0.8
                    should_alert = comment.official.name == "Jerome Powell" or comment.confidence >= 0.5
                    
                    if should_alert and (not self.unified_mode or is_critical):
                        sent_emoji = {"HAWKISH": "🦅", "DOVISH": "🕊️", "NEUTRAL": "➡️"}.get(comment.sentiment, "❓")
                        embed = {
                            "title": f"🎤 {comment.official.name} - {comment.sentiment}",
                            "color": 3066993 if comment.sentiment == "DOVISH" else 15548997 if comment.sentiment == "HAWKISH" else 3447003,
                            "description": f'"{comment.content[:200]}..."',
                            "fields": [
                                {"name": f"{sent_emoji} Sentiment", "value": comment.sentiment, "inline": True},
                                {"name": "📊 Impact", "value": comment.market_impact, "inline": True},
                            ],
                            "footer": {"text": "Fed Officials Monitor"},
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        alert = {
                            'type': 'fed_official',
                            'embed': embed,
                            'content': None,
                            'source': 'fed_monitor',
                            'symbol': 'SPY'
                        }
                        result['alerts'].append(alert)
                        result['comments'].append(comment)
                        
                        # Send via callback
                        if self.alert_callback:
                            self.alert_callback(alert)
                    elif should_alert:
                        logger.debug(f"   📊 Fed comment buffered for synthesis: {comment.official.name} - {comment.sentiment}")
                        result['comments'].append(comment)
            
        except Exception as e:
            logger.error(f"   ❌ Fed check error: {e}")
            result['error'] = str(e)
        
        return result
    
    def get_status(self) -> Optional[FedStatus]:
        """Get current Fed Watch status"""
        return self.prev_status

