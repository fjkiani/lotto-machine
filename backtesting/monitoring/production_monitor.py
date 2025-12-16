"""
🔍 PRODUCTION MONITOR
Real-time monitoring to prevent Dec 11 issues
"""

from dataclasses import dataclass
from typing import Optional, Callable
from datetime import datetime, timedelta
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class MonitorConfig:
    """Production monitor configuration"""
    check_interval_seconds: int = 60  # Check every minute
    max_data_age_hours: float = 1.0  # Reject data older than 1 hour
    max_uptime_gap_minutes: int = 30  # Alert if gap > 30 min
    rth_start_hour: int = 9
    rth_start_minute: int = 30
    rth_end_hour: int = 16
    rth_end_minute: int = 0
    alert_callback: Optional[Callable] = None

class ProductionMonitor:
    """Real-time production health monitoring"""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.last_check_time: Optional[datetime] = None
        self.last_activity_time: Optional[datetime] = None
        self.consecutive_failures = 0
        self.is_rth = False
    
    def check_rth(self) -> bool:
        """Check if currently in RTH"""
        now = datetime.now()
        current_time = now.time()
        
        rth_start = datetime.strptime(
            f"{self.config.rth_start_hour:02d}:{self.config.rth_start_minute:02d}",
            "%H:%M"
        ).time()
        
        rth_end = datetime.strptime(
            f"{self.config.rth_end_hour:02d}:{self.config.rth_end_minute:02d}",
            "%H:%M"
        ).time()
        
        is_weekday = now.weekday() < 5
        
        self.is_rth = is_weekday and (rth_start <= current_time < rth_end)
        return self.is_rth
    
    def validate_data_age(self, data_timestamp: datetime, source: str = "unknown") -> bool:
        """Validate data is fresh enough"""
        age_hours = (datetime.now() - data_timestamp).total_seconds() / 3600
        
        if age_hours > self.config.max_data_age_hours:
            logger.warning(f"⚠️  STALE DATA: {source} is {age_hours:.1f} hours old (max {self.config.max_data_age_hours}h)")
            if self.config.alert_callback:
                self.config.alert_callback({
                    'type': 'stale_data',
                    'source': source,
                    'age_hours': age_hours,
                    'message': f"Data from {source} is {age_hours:.1f} hours old - rejecting"
                })
            return False
        
        return True
    
    def check_uptime(self) -> bool:
        """Check if system is still running"""
        now = datetime.now()
        
        if self.last_activity_time:
            gap_minutes = (now - self.last_activity_time).total_seconds() / 60
            
            if gap_minutes > self.config.max_uptime_gap_minutes:
                if self.is_rth:
                    logger.error(f"❌ SYSTEM DOWN: No activity for {gap_minutes:.0f} minutes during RTH!")
                    if self.config.alert_callback:
                        self.config.alert_callback({
                            'type': 'system_down',
                            'gap_minutes': gap_minutes,
                            'is_rth': True,
                            'message': f"System appears down - no activity for {gap_minutes:.0f} minutes during RTH"
                        })
                    return False
                else:
                    logger.warning(f"⚠️  No activity for {gap_minutes:.0f} minutes (outside RTH)")
        
        return True
    
    def record_activity(self):
        """Record that system is active"""
        self.last_activity_time = datetime.now()
        self.consecutive_failures = 0
    
    def should_generate_signals(self, data_timestamp: Optional[datetime] = None) -> tuple[bool, str]:
        """
        Determine if signals should be generated
        
        Returns:
            (should_generate, reason)
        """
        # Check RTH
        if not self.check_rth():
            return False, "Outside RTH - skipping signal generation"
        
        # Check uptime
        if not self.check_uptime():
            return False, "System appears down - no recent activity"
        
        # Check data freshness
        if data_timestamp:
            if not self.validate_data_age(data_timestamp, "DP_API"):
                return False, f"Data is stale ({data_timestamp})"
        
        return True, "All checks passed"
    
    def run_continuous_check(self):
        """Run continuous health monitoring (blocking)"""
        logger.info("🔍 Starting production health monitor...")
        
        while True:
            try:
                self.check_rth()
                self.check_uptime()
                
                time.sleep(self.config.check_interval_seconds)
            except KeyboardInterrupt:
                logger.info("🛑 Stopping production monitor...")
                break
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
                time.sleep(self.config.check_interval_seconds)


