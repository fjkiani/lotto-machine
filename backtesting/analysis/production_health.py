"""
🏥 PRODUCTION HEALTH MONITOR
Tracks system uptime, data freshness, and prevents issues like Dec 11
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3
import os
import sys

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@dataclass
class HealthStatus:
    """System health status"""
    is_healthy: bool
    issues: List[str]
    uptime_pct: float
    data_freshness: Dict[str, any]
    last_activity: Optional[datetime]
    rth_coverage: float
    recommendations: List[str]

@dataclass
class DataStalenessCheck:
    """Data staleness validation"""
    is_stale: bool
    data_age_hours: float
    max_allowed_hours: float
    source: str
    timestamp: Optional[datetime]
    recommendation: str

class ProductionHealthMonitor:
    """Monitors production system health and prevents issues"""
    
    def __init__(self, alerts_db_path: str = "data/alerts_history.db",
                 dp_db_path: str = "data/dp_learning.db"):
        self.alerts_db_path = alerts_db_path
        self.dp_db_path = dp_db_path
        self.max_data_age_hours = 1.0  # 1 hour max age
        self.max_uptime_gap_minutes = 30  # 30 min gap = system down
    
    def check_health(self, date: str) -> HealthStatus:
        """
        Comprehensive health check for a date
        
        Checks:
        - System uptime during RTH
        - Data freshness
        - Signal timing
        - Coverage gaps
        """
        issues = []
        
        # Check uptime
        uptime_pct, uptime_issues = self._check_uptime(date)
        issues.extend(uptime_issues)
        
        # Check data freshness
        data_freshness, freshness_issues = self._check_data_freshness(date)
        issues.extend(freshness_issues)
        
        # Check RTH coverage
        rth_coverage, coverage_issues = self._check_rth_coverage(date)
        issues.extend(coverage_issues)
        
        # Get last activity
        last_activity = self._get_last_activity(date)
        
        # Determine if healthy
        is_healthy = (
            uptime_pct >= 0.95 and  # 95%+ uptime
            not any('STALE' in issue for issue in issues) and
            rth_coverage >= 0.80  # 80%+ RTH coverage
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues, uptime_pct, rth_coverage)
        
        return HealthStatus(
            is_healthy=is_healthy,
            issues=issues,
            uptime_pct=uptime_pct,
            data_freshness=data_freshness,
            last_activity=last_activity,
            rth_coverage=rth_coverage,
            recommendations=recommendations
        )
    
    def _check_uptime(self, date: str) -> tuple[float, List[str]]:
        """Check system uptime during RTH"""
        conn = sqlite3.connect(self.alerts_db_path)
        cursor = conn.cursor()
        
        # Get all alerts for the date
        start = f"{date}T00:00:00"
        end = f"{date}T23:59:59.999999"
        
        cursor.execute('''
            SELECT timestamp
            FROM alerts
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        ''', [start, end])
        
        timestamps = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]
        conn.close()
        
        if not timestamps:
            return 0.0, ["❌ NO ACTIVITY - System not running"]
        
        # Check RTH coverage (9:30 AM - 4:00 PM)
        rth_start = datetime.strptime(f"{date}T09:30:00", '%Y-%m-%dT%H:%M:%S')
        rth_end = datetime.strptime(f"{date}T16:00:00", '%Y-%m-%dT%H:%M:%S')
        rth_duration = (rth_end - rth_start).total_seconds() / 60  # minutes
        
        # Find gaps
        gaps = []
        for i in range(len(timestamps) - 1):
            gap = (timestamps[i+1] - timestamps[i]).total_seconds() / 60
            if gap > self.max_uptime_gap_minutes:
                gaps.append((timestamps[i], timestamps[i+1], gap))
        
        # Calculate uptime
        if timestamps:
            first_activity = timestamps[0]
            last_activity = timestamps[-1]
            total_duration = (last_activity - first_activity).total_seconds() / 60
            
            # Subtract gap time
            gap_time = sum(gap[2] for gap in gaps)
            uptime_minutes = total_duration - gap_time
            uptime_pct = (uptime_minutes / rth_duration) * 100 if rth_duration > 0 else 0
        else:
            uptime_pct = 0.0
        
        issues = []
        if uptime_pct < 50:
            issues.append(f"❌ CRITICAL: Only {uptime_pct:.0f}% uptime during RTH")
        elif uptime_pct < 80:
            issues.append(f"⚠️  LOW: {uptime_pct:.0f}% uptime during RTH")
        
        if gaps:
            for gap_start, gap_end, gap_minutes in gaps[:3]:  # Show top 3
                if gap_start >= rth_start and gap_end <= rth_end:
                    issues.append(f"⚠️  GAP: {gap_minutes:.0f} min gap at {gap_start.strftime('%H:%M')}")
        
        return min(uptime_pct, 100.0), issues
    
    def _check_data_freshness(self, date: str) -> tuple[Dict[str, any], List[str]]:
        """Check if data is fresh (not stale)"""
        freshness = {}
        issues = []
        
        # Check DP data
        try:
            from .data_checker import DataAvailabilityChecker
            checker = DataAvailabilityChecker()
            api_checks = checker.check_all_sources(date, "SPY")
            
            # Check DP levels
            dp_levels = api_checks.get('dp_levels', {})
            if dp_levels.get('available'):
                # Assume data is from date (would need actual timestamp from API)
                # For now, check if it's reasonable
                freshness['dp_levels'] = {
                    'available': True,
                    'age_hours': 0.0,  # Would need actual timestamp
                    'is_stale': False
                }
            else:
                freshness['dp_levels'] = {
                    'available': False,
                    'error': dp_levels.get('error', 'Unknown')
                }
        except Exception as e:
            freshness['dp_levels'] = {
                'available': False,
                'error': str(e)
            }
        
        # Check alerts for timing (if alerts fired after hours, data might be stale)
        conn = sqlite3.connect(self.alerts_db_path)
        cursor = conn.cursor()
        
        # Check if signals fired during RTH vs after hours
        rth_start = f"{date}T09:30:00"
        rth_end = f"{date}T16:00:00"
        
        cursor.execute('''
            SELECT COUNT(*) FROM alerts
            WHERE timestamp >= ? AND timestamp < ?
            AND alert_type IN ('dp_alert', 'synthesis', 'narrative_brain')
        ''', [rth_start, rth_end])
        
        rth_signals = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM alerts
            WHERE timestamp >= ? AND timestamp < ?
            AND alert_type IN ('dp_alert', 'synthesis', 'narrative_brain')
        ''', [f"{date}T20:00:00", f"{date}T23:59:59"])
        
        evening_signals = cursor.fetchone()[0]
        
        conn.close()
        
        if evening_signals > rth_signals * 2:
            issues.append(f"⚠️  STALE DATA: {evening_signals} signals after hours vs {rth_signals} during RTH")
            issues.append("   → Likely using yesterday's data")
            freshness['timing_anomaly'] = True
        else:
            freshness['timing_anomaly'] = False
        
        return freshness, issues
    
    def _check_rth_coverage(self, date: str) -> tuple[float, List[str]]:
        """Check RTH coverage (9:30 AM - 4:00 PM)"""
        conn = sqlite3.connect(self.alerts_db_path)
        cursor = conn.cursor()
        
        rth_start = f"{date}T09:30:00"
        rth_end = f"{date}T16:00:00"
        
        # Count signals per hour during RTH
        cursor.execute('''
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM alerts
            WHERE timestamp >= ? AND timestamp < ?
            AND alert_type IN ('dp_alert', 'synthesis', 'narrative_brain')
            GROUP BY hour
        ''', [rth_start, rth_end])
        
        hours_with_signals = len(cursor.fetchall())
        total_rth_hours = 6.5  # 9:30 AM - 4:00 PM = 6.5 hours
        coverage = (hours_with_signals / total_rth_hours) * 100
        
        conn.close()
        
        issues = []
        if coverage == 0:
            issues.append("❌ CRITICAL: ZERO RTH coverage - No signals during market hours")
        elif coverage < 50:
            issues.append(f"⚠️  LOW: Only {coverage:.0f}% RTH coverage")
        
        return coverage, issues
    
    def _get_last_activity(self, date: str) -> Optional[datetime]:
        """Get last activity timestamp"""
        conn = sqlite3.connect(self.alerts_db_path)
        cursor = conn.cursor()
        
        start = f"{date}T00:00:00"
        end = f"{date}T23:59:59.999999"
        
        cursor.execute('''
            SELECT MAX(timestamp) FROM alerts
            WHERE timestamp >= ? AND timestamp <= ?
        ''', [start, end])
        
        result = cursor.fetchone()[0]
        conn.close()
        
        if result:
            return datetime.fromisoformat(result)
        return None
    
    def _generate_recommendations(self, issues: List[str], 
                                  uptime_pct: float, 
                                  rth_coverage: float) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if uptime_pct < 50:
            recommendations.append("🔧 CRITICAL: Implement process monitoring")
            recommendations.append("   1. Add systemd/launchd service")
            recommendations.append("   2. Auto-restart on crash")
            recommendations.append("   3. Health check endpoint")
        
        if rth_coverage == 0:
            recommendations.append("🔧 CRITICAL: System not running during RTH")
            recommendations.append("   1. Check process status: ps aux | grep run_all_monitors")
            recommendations.append("   2. Check logs: tail -f logs/monitor_*.log")
            recommendations.append("   3. Implement auto-start on boot")
        
        if any('STALE' in issue for issue in issues):
            recommendations.append("🔧 CRITICAL: Data staleness detected")
            recommendations.append("   1. Add data age validation")
            recommendations.append("   2. Reject signals if data > 1 hour old")
            recommendations.append("   3. Check API for T+1 delay")
        
        if not recommendations:
            recommendations.append("✅ System health is good")
        
        return recommendations
    
    def validate_data_freshness(self, data_timestamp: datetime, 
                              source: str = "unknown") -> DataStalenessCheck:
        """Validate if data is fresh enough to use"""
        now = datetime.now()
        age = (now - data_timestamp).total_seconds() / 3600  # hours
        
        is_stale = age > self.max_data_age_hours
        
        recommendation = ""
        if is_stale:
            recommendation = f"❌ REJECT: Data is {age:.1f} hours old (max {self.max_data_age_hours}h)"
        else:
            recommendation = f"✅ ACCEPT: Data is {age:.1f} hours old"
        
        return DataStalenessCheck(
            is_stale=is_stale,
            data_age_hours=age,
            max_allowed_hours=self.max_data_age_hours,
            source=source,
            timestamp=data_timestamp,
            recommendation=recommendation
        )


