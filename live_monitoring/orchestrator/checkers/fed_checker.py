"""
Fed Checker - Monitors Fed Watch and Fed Officials.

Extracted from unified_monitor.py for modularity.
"""

import logging
import hashlib
from datetime import datetime
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class FedChecker(BaseChecker):
    """
    Checks Fed Watch probability changes and Fed officials comments.
    
    Responsibilities:
    - Monitor CME FedWatch rate probability changes
    - Alert on major probability shifts (threshold: 10-15%)
    - Monitor Fed officials comments (especially Powell)
    - Deduplicate comments using hash-based tracking
    """
    
    def __init__(self, alert_manager, fed_watch=None, fed_officials=None, unified_mode=False):
        """
        Initialize Fed checker.
        
        Args:
            alert_manager: AlertManager instance
            fed_watch: FedWatch instance (optional)
            fed_officials: FedOfficials instance (optional)
            unified_mode: Whether unified mode is enabled (affects thresholds)
        """
        super().__init__(alert_manager)
        self.fed_watch = fed_watch
        self.fed_officials = fed_officials
        self.unified_mode = unified_mode
        
        # State tracking
        self.prev_fed_status = None
        self.seen_fed_comments = set()
    
    @property
    def name(self) -> str:
        return "fed_checker"
    
    def check(self) -> List[CheckerAlert]:
        """
        Check Fed Watch and officials.
        
        Returns:
            List of CheckerAlert objects
        """
        alerts = []
        
        if not self.fed_watch:
            return alerts
        
        logger.info("🏦 Checking Fed Watch...")
        
        try:
            # Check Fed Watch status
            status = self.fed_watch.get_current_status(force_refresh=True)
            
            if self.prev_fed_status:
                cut_change = abs(status.prob_cut - self.prev_fed_status.prob_cut)
                hold_change = abs(status.prob_hold - self.prev_fed_status.prob_hold)
                
                threshold = 15.0 if self.unified_mode else 10.0
                
                if cut_change >= threshold or hold_change >= threshold:
                    logger.info(f"   🚨 MAJOR CHANGE! Cut: {status.prob_cut:.1f}% ({cut_change:+.1f}%)")
                    
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
                    
                    alerts.append(CheckerAlert(
                        embed=embed,
                        content="@everyone 🏦 Fed rate probability change!",
                        alert_type="fed_watch",
                        source="fed_monitor",
                        symbol=None
                    ))
            
            self.prev_fed_status = status
            logger.info(f"   Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Most Likely: {status.most_likely_outcome}")
            
            # Check Fed officials
            if self.fed_officials:
                logger.info("   🎤 Checking Fed officials...")
                report = self.fed_officials.get_report()
                
                if report.comments:
                    for comment in report.comments[:3]:
                        content_hash = hashlib.md5(
                            f"{comment.official.name}:{comment.content}".encode()
                        ).hexdigest()[:12]
                        comment_id = f"{comment.official.name}:{content_hash}"
                        
                        if comment_id not in self.seen_fed_comments:
                            self.seen_fed_comments.add(comment_id)
                            
                            # Keep only last 100 comments
                            if len(self.seen_fed_comments) > 100:
                                self.seen_fed_comments = set(list(self.seen_fed_comments)[-100:])
                            
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
                                
                                alerts.append(CheckerAlert(
                                    embed=embed,
                                    content="",
                                    alert_type="fed_official",
                                    source="fed_monitor",
                                    symbol="SPY"
                                ))
            
        except Exception as e:
            logger.error(f"   ❌ Fed check error: {e}")
        
        return alerts

