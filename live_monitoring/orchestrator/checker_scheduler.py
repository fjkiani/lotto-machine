"""
⏱️ CHECKER SCHEDULER

Manages the interval-based scheduling of all 15+ checker modules.
Each checker runs on its own interval (e.g., Fed every 5 min, DP every 5 min,
FTD hourly, Earnings every 4h).

Extracted from unified_monitor.py run() loop for modularity.
"""

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class CheckerSchedule:
    """Configuration for a single checker's schedule."""

    def __init__(self, name: str, checker: Any, interval: int, requires_market_hours: bool = True,
                 custom_handler: Optional[Callable] = None):
        """
        Args:
            name: Checker identifier (e.g., 'fed', 'trump', 'dark_pool')
            checker: Checker instance with .check() method
            interval: Seconds between runs
            requires_market_hours: If True, only runs during RTH
            custom_handler: Optional custom handler (for checkers needing special logic like synthesis)
        """
        self.name = name
        self.checker = checker
        self.interval = interval
        self.requires_market_hours = requires_market_hours
        self.custom_handler = custom_handler
        self.last_run: Optional[datetime] = None
        self.run_immediately = False  # If True, run on first tick

    def is_due(self, now: datetime, is_market_hours: bool) -> bool:
        """Check if this checker should run now."""
        if self.checker is None:
            return False
        if self.requires_market_hours and not is_market_hours:
            return False
        if self.last_run is None:
            return self.run_immediately
        elapsed = (now - self.last_run).total_seconds()
        return elapsed >= self.interval

    def mark_run(self, now: datetime):
        self.last_run = now


class CheckerScheduler:
    """
    Manages all checker schedules and dispatches them on interval.

    Usage:
        scheduler = CheckerScheduler(run_checker_fn, send_discord_fn)
        scheduler.register('fed', fed_checker, interval=300)
        scheduler.register('dark_pool', dp_checker, interval=300, requires_market_hours=True)
        ...
        # In run loop:
        scheduler.tick(now, is_market_hours)
    """

    def __init__(
        self,
        run_checker_with_health: Callable,
        send_discord: Callable,
    ):
        self.run_checker_with_health = run_checker_with_health
        self.send_discord = send_discord
        self.schedules: Dict[str, CheckerSchedule] = {}
        self._custom_handlers: Dict[str, Callable] = {}

    def register(
        self,
        name: str,
        checker: Any,
        interval: int,
        requires_market_hours: bool = True,
        run_immediately: bool = False,
        custom_handler: Optional[Callable] = None,
    ):
        """Register a checker with its scheduling parameters."""
        schedule = CheckerSchedule(
            name=name,
            checker=checker,
            interval=interval,
            requires_market_hours=requires_market_hours,
            custom_handler=custom_handler,
        )
        schedule.run_immediately = run_immediately
        self.schedules[name] = schedule
        if custom_handler:
            self._custom_handlers[name] = custom_handler

    def reset_timers(self, now: datetime, set_initial: List[str] = None):
        """
        Reset all timers. Optionally set initial last_run for specific checkers
        (to prevent them from running immediately on startup).
        """
        set_initial = set_initial or []
        for name, schedule in self.schedules.items():
            if name in set_initial:
                schedule.last_run = now
            # Checkers with run_immediately=True keep last_run=None

    def tick(self, now: datetime, is_market_hours: bool) -> int:
        """
        Run all due checkers. Returns total number of alerts dispatched.
        """
        total_alerts = 0

        for name, schedule in self.schedules.items():
            if not schedule.is_due(now, is_market_hours):
                continue

            try:
                if schedule.custom_handler:
                    # Custom handler manages its own dispatch
                    alerts_count = schedule.custom_handler(now, is_market_hours)
                    total_alerts += (alerts_count or 0)
                else:
                    # Standard pattern: run checker, dispatch alerts
                    alerts = self.run_checker_with_health(name, schedule.checker.check)
                    for alert in alerts:
                        self.send_discord(
                            alert.embed,
                            alert.content,
                            getattr(alert, 'alert_type', name),
                            getattr(alert, 'source', f"{name}_checker"),
                            getattr(alert, 'symbol', None),
                        )
                    total_alerts += len(alerts)

                schedule.mark_run(now)

            except Exception as e:
                logger.error(f"   ❌ {name} checker error: {e}")
                schedule.mark_run(now)  # Prevent infinite retry

        return total_alerts

    @property
    def checker_count(self) -> int:
        return len([s for s in self.schedules.values() if s.checker is not None])

    def get_status(self) -> Dict[str, Dict]:
        """Get status of all registered checkers."""
        status = {}
        for name, schedule in self.schedules.items():
            status[name] = {
                "enabled": schedule.checker is not None,
                "interval": schedule.interval,
                "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
                "requires_market_hours": schedule.requires_market_hours,
            }
        return status
