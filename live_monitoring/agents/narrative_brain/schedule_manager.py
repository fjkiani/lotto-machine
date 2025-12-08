"""
Schedule Manager for Narrative Brain

Handles timing of different alert types:
- Pre-market: 8:30 AM ET
- Intra-day: Smart timing based on market activity
- Events: Real-time as they happen
- End-of-day: 4:00 PM ET
"""

import logging
from datetime import datetime, time, timedelta
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ScheduleManager:
    """Manages timing and scheduling of narrative updates"""

    def __init__(self):
        self.last_pre_market = None
        self.last_intra_day = datetime.now() - timedelta(hours=2)  # Start 2h ago
        self.last_end_of_day = None

    def should_run_pre_market(self) -> bool:
        """Check if it's time for pre-market outlook (8:30 AM ET)"""
        now = datetime.now()

        # Only run once per day, between 8:30-9:30 AM ET
        if not self._is_pre_market_time(now):
            return False

        # Check if we already ran today
        if self.last_pre_market:
            if now.date() == self.last_pre_market.date():
                return False  # Already ran today

        return True

    def should_run_intra_day(self, market_is_active: bool = True) -> bool:
        """Check if it's appropriate for intra-day update"""
        if not market_is_active:
            return False

        now = datetime.now()

        # Must be during market hours (9:30 AM - 4:00 PM ET)
        if not self._is_market_hours(now):
            return False

        # Minimum 2 hours between intra-day updates
        time_since_last = now - self.last_intra_day
        if time_since_last < timedelta(hours=2):
            return False

        # Don't run too close to market close (within 30 min)
        if self._is_near_market_close(now):
            return False

        return True

    def should_run_end_of_day(self) -> bool:
        """Check if it's time for end-of-day summary (4:00 PM ET)"""
        now = datetime.now()

        # Only run between 4:00-4:30 PM ET
        if not self._is_end_of_day_time(now):
            return False

        # Check if we already ran today
        if self.last_end_of_day:
            if now.date() == self.last_end_of_day.date():
                return False  # Already ran today

        return True

    def mark_pre_market_sent(self):
        """Mark that pre-market outlook was sent"""
        self.last_pre_market = datetime.now()

    def mark_intra_day_sent(self):
        """Mark that intra-day update was sent"""
        self.last_intra_day = datetime.now()

    def mark_end_of_day_sent(self):
        """Mark that end-of-day summary was sent"""
        self.last_end_of_day = datetime.now()

    def get_next_scheduled_time(self) -> Optional[datetime]:
        """Get the next scheduled update time"""
        now = datetime.now()

        # Check pre-market tomorrow
        tomorrow = now + timedelta(days=1)
        pre_market_tomorrow = datetime.combine(tomorrow.date(), time(8, 30))

        # Check next intra-day opportunity
        next_intra_day = self.last_intra_day + timedelta(hours=2)
        if next_intra_day < now:
            next_intra_day = now + timedelta(minutes=30)  # Next available slot

        # Check end-of-day today
        eod_today = datetime.combine(now.date(), time(16, 0))

        # Return the soonest
        candidates = [pre_market_tomorrow, next_intra_day, eod_today]
        valid_candidates = [c for c in candidates if c > now]

        if valid_candidates:
            return min(valid_candidates)

        return None

    def _is_pre_market_time(self, dt: datetime) -> bool:
        """Check if given time is pre-market window (8:30-9:30 AM ET)"""
        hour = dt.hour
        minute = dt.minute
        return (hour == 8 and minute >= 30) or (hour == 9 and minute <= 30)

    def _is_market_hours(self, dt: datetime) -> bool:
        """Check if given time is during market hours (9:30 AM - 4:00 PM ET)"""
        hour = dt.hour
        minute = dt.minute

        market_open = (hour == 9 and minute >= 30) or (hour > 9)
        market_close = hour < 16

        return market_open and market_close

    def _is_near_market_close(self, dt: datetime) -> bool:
        """Check if within 30 minutes of market close"""
        hour = dt.hour
        minute = dt.minute

        # Market closes at 4:00 PM
        return hour == 15 and minute >= 30

    def _is_end_of_day_time(self, dt: datetime) -> bool:
        """Check if given time is end-of-day window (4:00-4:30 PM ET)"""
        hour = dt.hour
        minute = dt.minute
        return hour == 16 and minute <= 30


class NarrativeScheduler:
    """High-level scheduler that coordinates timing with narrative brain"""

    def __init__(self, narrative_brain):
        self.brain = narrative_brain
        self.schedule_manager = ScheduleManager()
        self.logger = logging.getLogger(__name__)

    def check_and_run_scheduled_updates(self):
        """Check all timing conditions and run updates if appropriate"""

        # Pre-market outlook
        if self.schedule_manager.should_run_pre_market():
            self.logger.info("🌅 Running pre-market outlook...")
            update = self.brain.generate_pre_market_outlook()
            if update:
                self.schedule_manager.mark_pre_market_sent()
                self.logger.info("✅ Pre-market outlook sent")

        # End-of-day summary
        if self.schedule_manager.should_run_end_of_day():
            self.logger.info("📊 Running end-of-day summary...")
            # TODO: Implement end-of-day summary generation
            self.schedule_manager.mark_end_of_day_sent()
            self.logger.info("✅ End-of-day summary sent")

    def can_run_intra_day_update(self) -> bool:
        """Check if intra-day update can be run (called by external triggers)"""
        return self.schedule_manager.should_run_intra_day()

    def mark_intra_day_update_sent(self):
        """Mark that an intra-day update was sent"""
        self.schedule_manager.mark_intra_day_sent()



