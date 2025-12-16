"""
Economic Checker - Monitors economic calendar events.

Extracted from unified_monitor.py for modularity.

This checker monitors upcoming economic events and generates alerts
for high-impact releases that could affect Fed Watch probabilities.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class EconomicChecker(BaseChecker):
    """
    Checks for upcoming economic events and generates alerts.
    
    Responsibilities:
    - Monitor economic calendar for upcoming events
    - Alert on high-impact events (within 24h for HIGH, 4h for MEDIUM)
    - Calculate potential Fed Watch swings
    - Deduplicate events using event ID tracking
    """
    
    def __init__(
        self,
        alert_manager,
        econ_calendar=None,
        econ_engine=None,
        econ_calendar_type=None,
        prev_fed_status=None,
        unified_mode=False
    ):
        """
        Initialize Economic checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            econ_calendar: EconomicCalendar instance
            econ_engine: EconomicEngine instance for generating alerts
            econ_calendar_type: Type of calendar ("api" or other)
            prev_fed_status: Previous Fed status for current cut probability
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        self.econ_calendar = econ_calendar
        self.econ_engine = econ_engine
        self.econ_calendar_type = econ_calendar_type
        self.prev_fed_status = prev_fed_status
        
        # State management
        self.alerted_events = set()
    
    def check(self) -> List[CheckerAlert]:
        """
        Check for upcoming economic events.
        
        Returns:
            List of CheckerAlert objects (empty if no events)
        """
        if not self.econ_calendar:
            return []
        
        logger.info("📊 Checking Economic Calendar...")
        
        try:
            from live_monitoring.agents.economic.calendar import Importance
            
            current_cut_prob = 89.0
            if self.prev_fed_status:
                current_cut_prob = self.prev_fed_status.prob_cut
            
            if self.econ_calendar_type == "api":
                today = datetime.now().strftime('%Y-%m-%d')
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                
                today_data = self.econ_calendar.load_events(date=today, min_impact="medium")
                tomorrow_data = self.econ_calendar.load_events(date=tomorrow, min_impact="medium")
                
                today_events = today_data.get('macro_events', [])
                tomorrow_events = tomorrow_data.get('macro_events', [])
                all_events = today_events + tomorrow_events
                
                # Convert to EventWrapper format (simplified)
                upcoming = []
                for event_dict in all_events:
                    class EventWrapper:
                        def __init__(self, data):
                            self.name = data.get('name', 'Unknown')
                            self.date = data.get('date', today)
                            self.time = data.get('time', '08:30')
                            self.importance = Importance.HIGH if data.get('impact', '').lower() == 'high' else Importance.MEDIUM
                            self.category = None  # Simplified
                            self.typical_surprise_impact = 3.0
                            self.release_frequency = "monthly"
                        
                        def hours_until(self):
                            try:
                                event_dt = datetime.strptime(f"{self.date} {self.time}", "%Y-%m-%d %H:%M")
                                return (event_dt - datetime.now()).total_seconds() / 3600
                            except:
                                return -1
                    
                    upcoming.append(EventWrapper(event_dict))
            else:
                upcoming = self.econ_calendar.get_upcoming_events(days=2, min_importance=Importance.HIGH)
            
            alerts = []
            for event in upcoming:
                event_id = f"{event.date}:{event.name}"
                hours = event.hours_until()
                
                if event_id in self.alerted_events or hours < 0:
                    continue
                
                should_alert = (hours < 24 and event.importance == Importance.HIGH) or hours < 4
                
                if not should_alert:
                    continue
                
                self.alerted_events.add(event_id)
                
                try:
                    alert = self.econ_engine.get_pre_event_alert(
                        event_type=event.name.lower().replace(' ', '_'),
                        event_date=event.date,
                        event_time=event.time,
                        current_fed_watch=current_cut_prob
                    )
                    weak_shift = alert.weak_scenario.predicted_fed_watch_shift
                    strong_shift = alert.strong_scenario.predicted_fed_watch_shift
                    weak_fw = alert.weak_scenario.predicted_fed_watch
                    strong_fw = alert.strong_scenario.predicted_fed_watch
                    swing = abs(weak_shift - strong_shift)
                except Exception as e:
                    logger.debug(f"   ⚠️ Could not get pre-event alert: {e}")
                    swing = event.typical_surprise_impact * 2
                    weak_shift = event.typical_surprise_impact
                    strong_shift = -event.typical_surprise_impact
                    weak_fw = current_cut_prob + weak_shift
                    strong_fw = current_cut_prob + strong_shift
                
                imp_emoji = "🔴" if event.importance == Importance.HIGH else "🟡"
                
                embed = {
                    "title": f"{imp_emoji} ECONOMIC ALERT: {event.name}",
                    "color": 15548997 if event.importance == Importance.HIGH else 16776960,
                    "description": f"⏰ In **{hours:.0f} hours** | Potential **±{swing:.1f}%** Fed Watch swing!",
                    "fields": [
                        {"name": "📅 When", "value": f"{event.date} {event.time} ET", "inline": True},
                        {"name": "📊 Current Cut %", "value": f"{current_cut_prob:.1f}%", "inline": True},
                        {"name": "📉 If WEAK Data", "value": f"Fed Watch → **{weak_fw:.0f}%** ({weak_shift:+.1f}%)\n→ BUY SPY, TLT", "inline": True},
                        {"name": "📈 If STRONG Data", "value": f"Fed Watch → **{strong_fw:.0f}%** ({strong_shift:+.1f}%)\n→ Reduce exposure", "inline": True},
                    ],
                    "footer": {"text": f"Economic Intelligence Engine | {event.release_frequency.upper()} release"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                content = f"⚠️ **{event.name}** in {hours:.0f}h! Potential {swing:.1f}% Fed Watch swing!"
                
                alerts.append(CheckerAlert(
                    embed=embed,
                    content=content,
                    alert_type="economic_event",
                    source="economic_checker"
                ))
            
            return alerts
                
        except Exception as e:
            logger.error(f"   ❌ Economic check error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

