"""
Base checker class for all monitoring checkers.

All checkers inherit from this base class to ensure consistent interface.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CheckerAlert:
    """
    Standard alert format returned by checkers.
    
    Attributes:
        embed: Discord embed dictionary
        content: Alert content string (optional)
        alert_type: Type of alert (e.g., "fed_watch", "dp_alert")
        source: Source checker name (e.g., "fed_checker")
        symbol: Optional symbol (e.g., "SPY", "QQQ")
    """
    embed: dict
    content: str
    alert_type: str
    source: str
    symbol: Optional[str] = None


class BaseChecker(ABC):
    """
    Base class for all monitoring checkers.
    
    Each checker handles a single responsibility and returns
    a list of CheckerAlert objects when checks are run.
    
    Usage:
        class MyChecker(BaseChecker):
            @property
            def name(self) -> str:
                return "my_checker"
            
            def check(self) -> List[CheckerAlert]:
                alerts = []
                # ... check logic ...
                if should_alert:
                    alerts.append(CheckerAlert(...))
                return alerts
    """
    
    def __init__(self, alert_manager):
        """
        Initialize checker.
        
        Args:
            alert_manager: AlertManager instance for sending alerts
        """
        self.alert_manager = alert_manager
        self.enabled = True
        self._last_check_time = None
    
    @abstractmethod
    def check(self) -> List[CheckerAlert]:
        """
        Run check and return list of alerts to send.
        
        Returns:
            List of CheckerAlert objects (empty list if no alerts)
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Checker name for logging and identification.
        
        Returns:
            String name (e.g., "fed_checker")
        """
        pass
    
    def should_run(self, interval_seconds: int) -> bool:
        """
        Check if checker should run based on interval.
        
        Args:
            interval_seconds: Minimum seconds between runs
            
        Returns:
            True if checker should run, False otherwise
        """
        from datetime import datetime
        
        if self._last_check_time is None:
            return True
        
        elapsed = (datetime.now() - self._last_check_time).total_seconds()
        return elapsed >= interval_seconds
    
    def mark_run(self):
        """Mark that checker has been run (updates last_check_time)."""
        from datetime import datetime
        self._last_check_time = datetime.now()
    
    def send_alerts(self, alerts: List[CheckerAlert]) -> int:
        """
        Send alerts via AlertManager.
        
        Args:
            alerts: List of CheckerAlert objects
            
        Returns:
            Number of alerts successfully sent
        """
        if not self.enabled:
            logger.debug(f"   ⏭️ {self.name} disabled - skipping")
            return 0
        
        sent_count = 0
        for alert in alerts:
            try:
                success = self.alert_manager.send_discord(
                    embed=alert.embed,
                    content=alert.content,
                    alert_type=alert.alert_type,
                    source=alert.source,
                    symbol=alert.symbol
                )
                if success:
                    sent_count += 1
            except Exception as e:
                logger.error(f"   ❌ Error sending alert from {self.name}: {e}")
        
        return sent_count

