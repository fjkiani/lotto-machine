"""
Economic Monitor Component - Trading Economics Integration + Phase 3

Uses Trading Economics as PRIMARY source for real forecast/previous values.
Falls back to EventLoader (Baby-Pips) or static calendar if needed.

STRATEGY:
1. DISCOVERY: Find events 4-24 hours ahead (hourly check)
2. PRE-EVENT ALERT: Alert 4h before with forecast/previous + Fed Watch scenarios
3. RELEASE MONITORING: Poll for actual value during release window (Phase 3)
4. INSTANT SURPRISE: Detect actual value, calculate surprise, generate signal (<1s)
5. POST-RELEASE: Track outcomes for ML training (Phase 4)
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class EconomicMonitor:
    """
    Monitors economic calendar using Trading Economics (PRIMARY).
    
    Responsibilities:
    - Discover upcoming US HIGH importance events
    - Generate pre-event alerts with forecast/previous values
    - Monitor release windows for actual values
    - Calculate surprise and generate instant signals
    - Track outcomes for ML training
    """
    
    def __init__(
        self,
        econ_engine,
        unified_mode: bool = False,
        alert_callback=None,
        fed_watch_prob: float = 89.0
    ):
        """
        Initialize Economic Monitor.
        
        Args:
            econ_engine: EconomicIntelligenceEngine instance
            unified_mode: If True, suppress individual alerts
            alert_callback: Function to call when alert should be sent
            fed_watch_prob: Current Fed Watch cut probability
        """
        self.econ_engine = econ_engine
        self.unified_mode = unified_mode
        self.alert_callback = alert_callback
        self.fed_watch_prob = fed_watch_prob
        
        # Initialize Trading Economics (PRIMARY)
        self.te_wrapper = None
        try:
            from live_monitoring.enrichment.apis.trading_economics import TradingEconomicsWrapper
            self.te_wrapper = TradingEconomicsWrapper()
            self.calendar_type = "trading_economics"
            logger.info("   ✅ Trading Economics: PRIMARY source")
        except Exception as e:
            logger.warning(f"   ⚠️ Trading Economics failed: {e}")
            self.calendar_type = None
        
        # Fallback 1: EventLoader (Baby-Pips API)
        self.event_loader = None
        if not self.te_wrapper:
            try:
                from live_monitoring.enrichment.apis.event_loader import EventLoader
                self.event_loader = EventLoader()
                self.calendar_type = "event_loader"
                logger.info("   ✅ EventLoader: FALLBACK 1")
            except Exception as e:
                logger.warning(f"   ⚠️ EventLoader failed: {e}")
        
        # Fallback 2: Static EconomicCalendar
        self.static_calendar = None
        if not self.te_wrapper and not self.event_loader:
            try:
                from live_monitoring.agents.economic.calendar import EconomicCalendar
                self.static_calendar = EconomicCalendar()
                self.calendar_type = "static"
                logger.info("   ⚠️ Static Calendar: FALLBACK 2 (no forecast/previous data)")
            except Exception as e:
                logger.error(f"   ❌ All calendar sources failed: {e}")
        
        # Track alerted events
        self.alerted_events = set()
        self.pending_events: Dict[str, Any] = {}  # event_name -> EconomicEvent
        
        # Phase 3: Surprise Detector
        self.surprise_detector = None
        try:
            from live_monitoring.agents.economic.surprise_detector import InstantSurpriseDetector
            from live_monitoring.agents.economic.fed_shift_predictor import FedShiftPredictor
            
            fed_predictor = FedShiftPredictor()
            
            self.surprise_detector = InstantSurpriseDetector(
                te_wrapper=self.te_wrapper,
                fed_predictor=fed_predictor,
                alert_callback=self._handle_surprise_signal
            )
            logger.info("   ✅ Surprise Detector: ACTIVE (Phase 3)")
        except Exception as e:
            logger.warning(f"   ⚠️ Surprise Detector failed: {e}")
        
        # Phase 3: Pre-Event Analyzer
        self.pre_event_analyzer = None
        try:
            from live_monitoring.agents.economic.pre_event_analyzer import PreEventAnalyzer
            
            self.pre_event_analyzer = PreEventAnalyzer(
                econ_engine=self.econ_engine,
                te_wrapper=self.te_wrapper,
                fed_watch_monitor=None,  # Will be set by orchestrator
                dp_monitor=None,  # Will be set by orchestrator
                regime_detector=None  # Will be set by orchestrator
            )
            logger.info("   ✅ Pre-Event Analyzer: ACTIVE (Phase 3)")
        except Exception as e:
            logger.warning(f"   ⚠️ Pre-Event Analyzer failed: {e}")
        
        logger.info(f"📊 EconomicMonitor initialized (source: {self.calendar_type})")
    
    def check(self) -> Dict[str, Any]:
        """
        Check economic calendar for upcoming events.
        
        STRATEGY:
        1. Discover events 4-24 hours ahead
        2. Alert 4h before HIGH importance events
        3. Include forecast/previous values in alerts
        
        Returns:
            Dict with events and alerts
        """
        result = {
            'events': [],
            'alerts': [],
            'pending': []
        }
        
        try:
            # Get upcoming events (PRIMARY: Trading Economics)
            upcoming = self._get_upcoming_events()
            
            if not upcoming:
                logger.info("   📅 No upcoming events found")
                return result
            
            logger.info(f"   📅 Found {len(upcoming)} upcoming events")
            
            # Process each event
            for event in upcoming:
                # Use event name as ID (Trading Economics normalizes this)
                event_id = f"{event.date}:{event.event}"
                hours = event.hours_until()
                
                logger.info(f"   📊 Event: {event.event} on {event.date} {event.time} | {hours:.1f}h away | Importance: {event.importance.name}")
                
                # Skip if already alerted or past
                if event_id in self.alerted_events:
                    logger.debug(f"      ⏭️  Already alerted, skipping")
                    continue
                
                if hours < 0:
                    logger.debug(f"      ⏭️  Event passed, skipping")
                    continue
                
                # Store in pending if 4-24 hours away (for pre-event alerting)
                if 4 <= hours <= 24:
                    self.pending_events[event.event] = event
                    result['pending'].append(event)
                    logger.debug(f"      📝 Added to pending (will alert at T-4h)")
                    continue
                
                # Alert conditions: 4h before HIGH event, or 2h before ANY event
                should_alert = (hours < 4 and event.importance.value >= 3) or (hours < 2 and event.importance.value >= 2)
                
                if not should_alert:
                    continue
                
                self.alerted_events.add(event_id)
                
                # Generate pre-event alert with forecast/previous
                alert = self._generate_pre_event_alert(event, hours)
                if alert:
                    result['alerts'].append(alert)
                    result['events'].append(event)
                    
                    # Phase 3: Register for release window monitoring
                    if self.surprise_detector:
                        self.surprise_detector.register_event(event)
                        logger.debug(f"   📝 Registered {event.event} for release monitoring")
                    
                    # Send via callback
                    if self.alert_callback:
                        self.alert_callback(alert)
                    
                    logger.info(f"   ✅ PRE-EVENT ALERT: {event.event} in {hours:.1f}h")
            
            # Log today's summary
            today_events = self._get_today_events()
            if today_events:
                event_names = [e.event for e in today_events[:5]]
                logger.info(f"   📅 Today: {', '.join(event_names)}")
            else:
                logger.info(f"   📅 No events today")
            
        except Exception as e:
            logger.error(f"   ❌ Economic check error: {e}")
            result['error'] = str(e)
        
        return result
    
    def _get_upcoming_events(self) -> List:
        """Get upcoming events (PRIMARY: Trading Economics)"""
        from live_monitoring.enrichment.apis.trading_economics import Importance
        
        if self.te_wrapper:
            # PRIMARY: Trading Economics (has forecast/previous!)
            try:
                events = self.te_wrapper.get_us_events(
                    importance="high",
                    days_ahead=2
                )
                # Filter for HIGH importance only
                high_events = [e for e in events if e.importance.value >= 3]
                logger.info(f"   📅 Trading Economics: {len(high_events)} HIGH events")
                return high_events
            except Exception as e:
                logger.warning(f"   ⚠️ Trading Economics failed: {e}")
        
        # FALLBACK 1: EventLoader
        if self.event_loader:
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                
                today_data = self.event_loader.load_events(date=today, min_impact="high")
                tomorrow_data = self.event_loader.load_events(date=tomorrow, min_impact="high")
                
                today_events = today_data.get('macro_events', [])
                tomorrow_events = tomorrow_data.get('macro_events', [])
                
                # Convert to EconomicEvent-like format
                events = []
                for event_dict in today_events + tomorrow_events:
                    event = self._create_event_from_dict(event_dict, today)
                    if event:
                        events.append(event)
                
                logger.info(f"   📅 EventLoader: {len(events)} events")
                return events
            except Exception as e:
                logger.warning(f"   ⚠️ EventLoader failed: {e}")
        
        # FALLBACK 2: Static Calendar
        if self.static_calendar:
            try:
                from live_monitoring.agents.economic.calendar import Importance
                upcoming = self.static_calendar.get_upcoming_events(days=2, min_importance=Importance.HIGH)
                logger.info(f"   📅 Static Calendar: {len(upcoming)} events (no forecast/previous)")
                return upcoming
            except Exception as e:
                logger.warning(f"   ⚠️ Static calendar failed: {e}")
        
        return []
    
    def _create_event_from_dict(self, data: Dict, default_date: str):
        """Create EconomicEvent from EventLoader dict"""
        from live_monitoring.enrichment.apis.trading_economics import EconomicEvent, Importance, EventCategory
        
        try:
            # Map EventLoader format to EconomicEvent
            return EconomicEvent(
                date=data.get('date', default_date),
                time=data.get('time', '08:30'),
                country=data.get('country', 'United States'),
                country_code='US',
                event=data.get('name', 'Unknown'),
                importance=Importance.HIGH if data.get('impact', '').lower() == 'high' else Importance.MEDIUM,
                category=EventCategory.OTHER,  # Will be inferred
                forecast=data.get('forecast'),
                previous=data.get('previous')
            )
        except Exception as e:
            logger.debug(f"Failed to create event from dict: {e}")
            return None
    
    def _generate_pre_event_alert(self, event, hours: float) -> Optional[Dict[str, Any]]:
        """
        Generate pre-event alert with forecast/previous values.
        
        Enhanced with Trading Economics data:
        - Real forecast vs previous
        - Fed Watch impact scenarios
        - Suggested positioning
        """
        from live_monitoring.enrichment.apis.trading_economics import Importance
        
        try:
            # Get Fed Watch scenarios
            try:
                alert = self.econ_engine.get_pre_event_alert(
                    event_type=event.event.lower().replace(' ', '_'),
                    event_date=event.date,
                    event_time=event.time,
                    current_fed_watch=self.fed_watch_prob
                )
                
                weak_shift = alert.weak_scenario.predicted_fed_watch_shift
                strong_shift = alert.strong_scenario.predicted_fed_watch_shift
                weak_fw = alert.weak_scenario.predicted_fed_watch
                strong_fw = alert.strong_scenario.predicted_fed_watch
                swing = abs(weak_shift - strong_shift)
                
            except Exception as e:
                logger.debug(f"Prediction error: {e}")
                # Use static estimate
                swing = 3.0 * 2  # Default swing
                weak_shift = 3.0
                strong_shift = -3.0
                weak_fw = self.fed_watch_prob + weak_shift
                strong_fw = self.fed_watch_prob + strong_shift
            
            # Build alert with forecast/previous (if available from Trading Economics)
            imp_emoji = "🔴" if event.importance.value >= 3 else "🟡"
            
            # Forecast/Previous fields (if available)
            forecast_field = {"name": "📈 Forecast", "value": event.forecast or "N/A", "inline": True}
            previous_field = {"name": "📉 Previous", "value": event.previous or "N/A", "inline": True}
            
            fields = [
                {"name": "📅 When", "value": f"{event.date} {event.time} ET", "inline": True},
                {"name": "📊 Current Cut %", "value": f"{self.fed_watch_prob:.1f}%", "inline": True},
                {"name": "🎯 Category", "value": event.category.value.upper(), "inline": True},
            ]
            
            # Add forecast/previous if available
            if event.forecast or event.previous:
                fields.append(forecast_field)
                fields.append(previous_field)
            
            fields.extend([
                {"name": "📉 If WEAK Data", "value": f"Fed Watch → **{weak_fw:.0f}%** ({weak_shift:+.1f}%)\n→ BUY SPY, TLT", "inline": True},
                {"name": "📈 If STRONG Data", "value": f"Fed Watch → **{strong_fw:.0f}%** ({strong_shift:+.1f}%)\n→ Reduce exposure", "inline": True},
            ])
            
            embed = {
                "title": f"{imp_emoji} ECONOMIC ALERT: {event.event}",
                "color": 15548997 if event.importance.value >= 3 else 16776960,
                "description": f"⏰ In **{hours:.0f} hours** | Potential **±{swing:.1f}%** Fed Watch swing!",
                "fields": fields,
                "footer": {"text": f"Trading Economics | {self.calendar_type.upper()}"},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Enhanced content with forecast context
            if event.forecast and event.previous:
                content = f"⚠️ **{event.event}** in {hours:.0f}h!\n📈 Forecast: {event.forecast} | Previous: {event.previous}\n🎯 Potential {swing:.1f}% Fed Watch swing!"
            else:
                content = f"⚠️ **{event.event}** in {hours:.0f}h! Potential {swing:.1f}% Fed Watch swing!"
            
            return {
                'type': 'economic_event',
                'embed': embed,
                'content': content,
                'source': 'economic_monitor',
                'symbol': None,
                'event': event  # Include full event object
            }
            
        except Exception as e:
            logger.error(f"Failed to generate alert: {e}")
            return None
    
    def _get_today_events(self) -> List:
        """Get today's events"""
        if self.te_wrapper:
            try:
                return self.te_wrapper.get_us_events(date=datetime.now().strftime('%Y-%m-%d'))
            except:
                pass
        
        if self.event_loader:
            try:
                today_data = self.event_loader.load_events(date=datetime.now().strftime('%Y-%m-%d'), min_impact="medium")
                events = today_data.get('macro_events', [])
                return [self._create_event_from_dict(e, datetime.now().strftime('%Y-%m-%d')) for e in events]
            except:
                pass
        
        if self.static_calendar:
            try:
                return self.static_calendar.get_today_events()
            except:
                pass
        
        return []
    
    def discover_upcoming_events(self, hours_ahead: int = 24) -> List:
        """
        Discover events 4-24 hours ahead.
        
        Called hourly to find events that need pre-event alerts.
        
        Args:
            hours_ahead: How many hours to look ahead
        
        Returns:
            List of upcoming events
        """
        if not self.te_wrapper:
            return []
        
        try:
            events = self.te_wrapper.get_upcoming_us_events(hours_ahead=hours_ahead)
            # Filter for HIGH importance only
            high_events = [e for e in events if e.importance.value >= 3]
            
            # Store in pending for pre-event alerting
            for event in high_events:
                if 4 <= event.hours_until() <= 24:
                    self.pending_events[event.event] = event
            
            return high_events
        except Exception as e:
            logger.error(f"Failed to discover events: {e}")
            return []
    
    def check_pending_events(self) -> List[Dict[str, Any]]:
        """
        Check pending events and alert if 4h before release.
        
        Called every 15 minutes to catch events entering 4h window.
        
        Returns:
            List of alerts generated
        """
        alerts = []
        
        for event_name, event in list(self.pending_events.items()):
            hours = event.hours_until()
            
            # Alert at 4h mark
            if 3.5 <= hours <= 4.5:
                event_id = f"{event.date}:{event.event}"
                if event_id not in self.alerted_events:
                    alert = self._generate_pre_event_alert(event, hours)
                    if alert:
                        alerts.append(alert)
                        self.alerted_events.add(event_id)
                        
                        if self.alert_callback:
                            self.alert_callback(alert)
                        
                        logger.info(f"   ✅ PRE-EVENT ALERT: {event.event} in {hours:.1f}h")
            
            # Remove if past
            if hours < 0:
                del self.pending_events[event_name]
        
        return alerts
    
    def update_fed_watch_prob(self, prob: float):
        """Update current Fed Watch probability"""
        self.fed_watch_prob = prob
    
    def _handle_surprise_signal(self, signal):
        """
        Handle instant surprise signal from SurpriseDetector.
        
        Creates Discord alert for instant surprise detection.
        """
        try:
            # Create alert embed
            magnitude_emoji = {
                "LARGE_BEAT": "🔥",
                "BEAT": "📈",
                "INLINE": "➡️",
                "MISS": "📉",
                "LARGE_MISS": "❄️"
            }.get(signal.magnitude, "❓")
            
            color = {
                "LARGE_BEAT": 15158332,  # Red
                "BEAT": 16776960,  # Yellow
                "INLINE": 3447003,  # Blue
                "MISS": 3066993,  # Green
                "LARGE_MISS": 3066993  # Green
            }.get(signal.magnitude, 9807270)  # Gray
            
            embed = {
                "title": f"🚨 INSTANT SURPRISE: {signal.event_name}",
                "color": color,
                "description": f"{magnitude_emoji} **{signal.magnitude}** | Surprise: **{signal.surprise:+.1%}**",
                "fields": [
                    {"name": "📊 Actual", "value": signal.actual, "inline": True},
                    {"name": "📈 Forecast", "value": signal.forecast, "inline": True},
                    {"name": "📉 Previous", "value": signal.previous, "inline": True},
                    {"name": "🏦 Fed Watch Shift", "value": f"{signal.fed_shift:+.1f}%", "inline": True},
                    {"name": "🎯 Action", "value": f"**{signal.action} {signal.symbol}**", "inline": True},
                    {"name": "💯 Confidence", "value": f"{signal.confidence:.0%}", "inline": True},
                    {"name": "💡 Reasoning", "value": signal.reasoning, "inline": False},
                ],
                "footer": {"text": "Instant Surprise Detector | <1s latency"},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            content = f"🚨 **{signal.event_name} RELEASED!** {signal.magnitude} ({signal.surprise:+.1%} surprise) → **{signal.action} {signal.symbol}**"
            
            alert_dict = {
                'type': 'economic_surprise',
                'embed': embed,
                'content': content,
                'source': 'surprise_detector',
                'symbol': signal.symbol
            }
            
            # Send via callback
            if self.alert_callback:
                self.alert_callback(alert_dict)
            
            logger.info(f"   ⚡ INSTANT SURPRISE ALERT: {signal.event_name} = {signal.actual} ({signal.magnitude})")
            
        except Exception as e:
            logger.error(f"Failed to handle surprise signal: {e}")
    
    async def start_release_monitoring(self):
        """
        Start monitoring all registered release windows.
        
        Called by orchestrator to begin async monitoring.
        """
        if self.surprise_detector:
            await self.surprise_detector.start_monitoring()
    
    def set_fed_watch_monitor(self, fed_monitor):
        """Set Fed Watch monitor for pre-event analyzer"""
        if self.pre_event_analyzer:
            self.pre_event_analyzer.fed_watch_monitor = fed_monitor
    
    def set_dp_monitor(self, dp_monitor):
        """Set DP monitor for pre-event analyzer"""
        if self.pre_event_analyzer:
            self.pre_event_analyzer.dp_monitor = dp_monitor
