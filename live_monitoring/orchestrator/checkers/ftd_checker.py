"""
FTD Checker - Detects FTD-based opportunities.

Extracted from unified_monitor.py for modularity.

This checker analyzes Failure to Deliver (FTD) data to predict
forced covering events and potential squeezes, leveraging the T+35 settlement cycle.
"""

import logging
from datetime import datetime
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class FTDChecker(BaseChecker):
    """
    Checks for FTD-based opportunities.
    
    Responsibilities:
    - Scan FTD candidates for signals
    - Generate alerts for T+35 windows, spikes, covering pressure
    - Track T+35 calendar for upcoming deadlines
    """
    
    def __init__(
        self,
        alert_manager,
        ftd_analyzer=None,
        ftd_candidates=None,
        unified_mode=False
    ):
        """
        Initialize FTD checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            ftd_analyzer: FTDAnalyzer instance
            ftd_candidates: List of FTD candidate symbols
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        self.ftd_analyzer = ftd_analyzer
        self.ftd_candidates = ftd_candidates or []
    
    @property
    def name(self) -> str:
        """Return checker name for identification."""
        return "ftd_checker"

    def check(self) -> List[CheckerAlert]:
        """
        Check for FTD-based opportunities.
        
        Returns:
            List of CheckerAlert objects (empty if no signals)
        """
        if not self.ftd_analyzer:
            return []
        
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        logger.info("📈 Checking FTD opportunities...")
        
        try:
            alerts = []
            
            # Scan FTD candidates
            signals = self.ftd_analyzer.get_ftd_candidates(self.ftd_candidates, min_score=50)
            
            if not signals:
                logger.info("   📊 No FTD signals found.")
            else:
                for signal in signals:
                    # Check for duplicate alerts
                    alert_key = f"ftd_{signal.symbol}_{today}"
                    if self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60 * 24):
                        logger.debug(f"   ⏭️ Skipping duplicate FTD alert for {signal.symbol}")
                        continue
                    
                    alert = self._create_ftd_signal_alert(signal)
                    if alert:
                        alerts.append(alert)
                        self.alert_manager.add_alert_to_history(alert_key)
                        logger.info(f"   📈 FTD signal sent for {signal.symbol}!")
            
            # Also check T+35 calendar for upcoming deadlines
            calendar = self.ftd_analyzer.get_t35_calendar(self.ftd_candidates)
            upcoming = [c for c in calendar if c['days_until'] <= 7]  # Within 7 days
            
            if upcoming:
                logger.info(f"   📅 {len(upcoming)} upcoming T+35 deadlines within 7 days")
                for event in upcoming[:3]:  # Top 3
                    alert_key = f"t35_calendar_{event['symbol']}_{event['t35_date']}"
                    if not self.alert_manager.is_alert_duplicate(alert_key, cooldown_minutes=60 * 24):
                        alert = self._create_t35_calendar_alert(event)
                        if alert:
                            alerts.append(alert)
            
            return alerts
                
        except Exception as e:
            logger.error(f"   ❌ FTD check error: {e}")
            return []
    
    def _create_ftd_signal_alert(self, signal) -> Optional[CheckerAlert]:
        """Create a CheckerAlert from an FTD signal."""
        # Determine color based on signal type
        if signal.signal_type == "T35_WINDOW":
            color = 0xff0000  # Red - urgent
            emoji = "🚨"
        elif signal.signal_type == "SPIKE":
            color = 0xff6600  # Orange - high priority
            emoji = "📈"
        elif signal.signal_type == "COVERING_PRESSURE":
            color = 0xffcc00  # Yellow - medium
            emoji = "⚠️"
        else:
            color = 0x00ccff  # Blue - info
            emoji = "📊"
        
        embed = {
            "title": f"{emoji} FTD SIGNAL: {signal.symbol}",
            "color": color,
            "description": f"**Type:** {signal.signal_type}\n"
                           f"**Score:** {signal.score:.0f}/100",
            "fields": [
                {"name": "📊 Current FTD", "value": f"{signal.current_ftd:,}", "inline": True},
                {"name": "📈 Spike Ratio", "value": f"{signal.ftd_spike_ratio:.1f}x", "inline": True},
                {"name": "⏰ Days to T+35", "value": f"{signal.days_to_t35}", "inline": True},
                {"name": "💰 Entry", "value": f"${signal.entry_price:.2f}", "inline": True},
                {"name": "🛑 Stop", "value": f"${signal.stop_price:.2f}", "inline": True},
                {"name": "🎯 Target", "value": f"${signal.target_price:.2f}", "inline": True},
                {"name": "⚖️ R/R Ratio", "value": f"{signal.risk_reward_ratio:.1f}:1", "inline": True},
            ],
            "footer": {"text": f"Exploitation Phase 4 • FTD Analyzer"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if signal.reasoning:
            embed["fields"].append({
                "name": "📝 Reasoning",
                "value": "\n".join(signal.reasoning[:3]),
                "inline": False
            })
        
        if signal.warnings:
            embed["fields"].append({
                "name": "⚠️ Warnings",
                "value": "\n".join(signal.warnings[:3]),
                "inline": False
            })
        
        content = f"{emoji} **FTD SIGNAL** | {signal.symbol} {signal.signal_type} | Score: {signal.score:.0f}/100"
        
        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="ftd_signal",
            source="ftd_checker",
            symbol=signal.symbol
        )
    
    def _create_t35_calendar_alert(self, event: dict) -> Optional[CheckerAlert]:
        """Create a CheckerAlert for a T+35 calendar event."""
        embed = {
            "title": f"📅 T+35 DEADLINE: {event['symbol']}",
            "color": 0xff6600 if event['days_until'] <= 3 else 0xffcc00,
            "description": f"**Forced buy-in deadline approaching!**",
            "fields": [
                {"name": "📅 T+35 Date", "value": event['t35_date'], "inline": True},
                {"name": "⏰ Days Until", "value": f"{event['days_until']}", "inline": True},
                {"name": "📊 FTD Quantity", "value": f"{event['ftd_quantity']:,}", "inline": True},
            ],
            "footer": {"text": f"Exploitation Phase 4 • T+35 Calendar"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        content = f"📅 **T+35 DEADLINE** | {event['symbol']} in {event['days_until']} days"
        
        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="t35_calendar",
            source="ftd_checker",
            symbol=event['symbol']
        )

