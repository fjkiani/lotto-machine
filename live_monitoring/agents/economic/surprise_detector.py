"""
Instant Surprise Detector - Phase 3

Detects and reacts to economic surprises INSTANTLY (<1s latency).

Monitors Trading Economics for actual values during release windows.
Calculates surprise magnitude and generates instant trade signals.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SurpriseSignal:
    """Instant surprise signal"""
    event_name: str
    actual: str
    forecast: str
    previous: str
    surprise: float
    magnitude: str  # LARGE_BEAT, BEAT, INLINE, MISS, LARGE_MISS
    fed_shift: float  # Predicted Fed Watch shift
    direction: str  # UP or DOWN
    action: str  # LONG or SHORT
    symbol: str  # SPY or TLT
    confidence: float
    reasoning: str


class InstantSurpriseDetector:
    """
    Detects and reacts to economic surprises INSTANTLY.
    
    Monitors: Trading Economics for actual values
    Triggers: On any HIGH importance event release
    Latency: <1 second from release
    """
    
    def __init__(
        self,
        te_wrapper,
        fed_predictor=None,
        alert_callback=None
    ):
        """
        Initialize Surprise Detector.
        
        Args:
            te_wrapper: TradingEconomicsWrapper instance
            fed_predictor: FedShiftPredictor instance (optional)
            alert_callback: Function to call when signal generated
        """
        self.te_wrapper = te_wrapper
        self.fed_predictor = fed_predictor
        self.alert_callback = alert_callback
        
        # Track pending releases
        self.pending_releases: Dict[str, Dict] = {}  # event_name -> event_data
        
        # Track monitoring tasks
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("⚡ InstantSurpriseDetector initialized")
    
    def register_event(self, event):
        """
        Register an event for monitoring.
        
        Called when pre-event alert is sent (4h before).
        """
        release_time = self._parse_release_time(event)
        if not release_time:
            return
        
        # Calculate release window
        start_time = release_time - timedelta(minutes=30)
        end_time = release_time + timedelta(minutes=5)
        
        self.pending_releases[event.event] = {
            'event': event,
            'release_time': release_time,
            'start_time': start_time,
            'end_time': end_time,
            'monitored': False
        }
        
        logger.info(f"   📝 Registered {event.event} for monitoring (release: {release_time.strftime('%H:%M')})")
    
    async def monitor_release_window(self, event_name: str):
        """
        Monitor a specific event's release window.
        
        Polls Trading Economics every 10 seconds during release window.
        Detects actual value and generates instant signal.
        """
        if event_name not in self.pending_releases:
            logger.warning(f"   ⚠️ Event {event_name} not registered")
            return
        
        release_data = self.pending_releases[event_name]
        event = release_data['event']
        start_time = release_data['start_time']
        end_time = release_data['end_time']
        
        logger.info(f"   ⏰ Monitoring {event.event} release window: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        
        # Wait until start time
        now = datetime.now()
        if now < start_time:
            wait_seconds = (start_time - now).total_seconds()
            logger.info(f"   ⏳ Waiting {wait_seconds/60:.1f} minutes until release window...")
            await asyncio.sleep(wait_seconds)
        
        # Poll during release window
        while datetime.now() < end_time:
            try:
                # Fetch updated events
                updated_events = self.te_wrapper.get_us_events(date=event.date)
                
                # Find matching event
                matching = [e for e in updated_events if e.event == event.event]
                
                if matching and matching[0].actual:
                    # DATA RELEASED!
                    actual_event = matching[0]
                    
                    logger.info(f"   🚨 DATA RELEASED: {event.event} = {actual_event.actual}")
                    
                    # Calculate surprise
                    surprise = self.te_wrapper.calculate_surprise(
                        actual=actual_event.actual,
                        forecast=event.forecast or "0",
                        previous=event.previous or "0"
                    )
                    
                    # Handle release
                    signal = await self._handle_release(event, actual_event, surprise)
                    
                    if signal:
                        # Mark as monitored
                        release_data['monitored'] = True
                        
                        # Send alert
                        if self.alert_callback:
                            self.alert_callback(signal)
                        
                        logger.info(f"   ✅ INSTANT SIGNAL GENERATED: {signal.action} {signal.symbol} (surprise: {surprise:+.2%})")
                    
                    # Stop monitoring (data released)
                    break
                
                # Wait 10 seconds before next poll
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"   ❌ Monitoring error: {e}")
                await asyncio.sleep(10)
        
        # Clean up
        if event_name in self.pending_releases:
            del self.pending_releases[event_name]
    
    async def _handle_release(
        self,
        event,
        actual_event,
        surprise: float
    ) -> Optional[SurpriseSignal]:
        """
        Handle data release - generate INSTANT signal.
        """
        try:
            # Classify surprise magnitude
            if surprise > 0.2:
                magnitude = "LARGE_BEAT"
            elif surprise > 0.05:
                magnitude = "BEAT"
            elif surprise > -0.05:
                magnitude = "INLINE"
            elif surprise > -0.2:
                magnitude = "MISS"
            else:
                magnitude = "LARGE_MISS"
            
            # Predict Fed Watch shift
            fed_shift = 0.0
            if self.fed_predictor:
                fed_shift = self.fed_predictor.predict_shift(
                    category=event.category.value,
                    surprise=surprise
                )
            else:
                # Simple heuristic
                if event.category.value == "INFLATION":
                    fed_shift = -surprise * 25.0  # Hot inflation = lower cut prob
                elif event.category.value == "EMPLOYMENT":
                    fed_shift = -surprise * 15.0  # Strong jobs = lower cut prob
                else:
                    fed_shift = -surprise * 10.0
            
            # Determine direction and action
            if magnitude in ["LARGE_BEAT", "BEAT"]:
                # Data stronger than expected
                if event.category.value == "INFLATION":
                    # Hot inflation = HAWKISH = SHORT TLT
                    direction = "DOWN"
                    action = "SHORT"
                    symbol = "TLT"
                    reasoning = f"{event.event} BEAT ({surprise:+.1%}) → Hot inflation → Fed more HAWKISH → SHORT TLT"
                else:
                    # Strong growth/jobs = RISK ON = LONG SPY
                    direction = "UP"
                    action = "LONG"
                    symbol = "SPY"
                    reasoning = f"{event.event} BEAT ({surprise:+.1%}) → Strong data → RISK ON → LONG SPY"
            elif magnitude in ["LARGE_MISS", "MISS"]:
                # Data weaker than expected
                if event.category.value == "INFLATION":
                    # Cool inflation = DOVISH = LONG TLT
                    direction = "UP"
                    action = "LONG"
                    symbol = "TLT"
                    reasoning = f"{event.event} MISS ({surprise:+.1%}) → Cool inflation → Fed more DOVISH → LONG TLT"
                else:
                    # Weak growth/jobs = RISK OFF = SHORT SPY
                    direction = "DOWN"
                    action = "SHORT"
                    symbol = "SPY"
                    reasoning = f"{event.event} MISS ({surprise:+.1%}) → Weak data → RISK OFF → SHORT SPY"
            else:
                # INLINE - no clear signal
                return None
            
            # Calculate confidence based on surprise magnitude
            confidence = min(abs(surprise) * 200, 90)  # Cap at 90%
            if magnitude in ["LARGE_BEAT", "LARGE_MISS"]:
                confidence = 85  # High confidence for large surprises
            
            return SurpriseSignal(
                event_name=event.event,
                actual=actual_event.actual,
                forecast=event.forecast or "N/A",
                previous=event.previous or "N/A",
                surprise=surprise,
                magnitude=magnitude,
                fed_shift=fed_shift,
                direction=direction,
                action=action,
                symbol=symbol,
                confidence=confidence,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"   ❌ Failed to handle release: {e}")
            return None
    
    def _parse_release_time(self, event) -> Optional[datetime]:
        """Parse release time from event"""
        try:
            # Parse time (handle AM/PM format)
            time_str = event.time
            if 'AM' in time_str or 'PM' in time_str:
                time_obj = datetime.strptime(time_str, "%I:%M %p")
                time_24h = time_obj.strftime("%H:%M")
            else:
                time_24h = event.time
            
            # Combine with date
            release_dt = datetime.strptime(f"{event.date} {time_24h}", "%Y-%m-%d %H:%M")
            return release_dt
        except Exception as e:
            logger.debug(f"Failed to parse release time: {e}")
            return None
    
    async def start_monitoring(self):
        """
        Start monitoring all pending releases.
        
        Creates async tasks for each release window.
        """
        for event_name, release_data in list(self.pending_releases.items()):
            if not release_data.get('monitored', False):
                task = asyncio.create_task(
                    self.monitor_release_window(event_name)
                )
                self.monitoring_tasks[event_name] = task
                logger.info(f"   🚀 Started monitoring task for {event_name}")
    
    def stop_monitoring(self, event_name: str):
        """Stop monitoring a specific event"""
        if event_name in self.monitoring_tasks:
            self.monitoring_tasks[event_name].cancel()
            del self.monitoring_tasks[event_name]
            logger.info(f"   ⏹️  Stopped monitoring {event_name}")

