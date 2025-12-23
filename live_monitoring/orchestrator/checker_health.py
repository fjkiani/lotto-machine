"""
🩺 CHECKER HEALTH REGISTRY
Tracks health, status, and metrics for all checkers.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum

class CheckerStatus(Enum):
    HEALTHY = "healthy"        # Working normally
    WARNING = "warning"        # Hasn't run in expected interval
    ERROR = "error"            # Last run failed
    DISABLED = "disabled"      # Intentionally disabled
    NOT_APPLICABLE = "n/a"     # Only runs at specific times

@dataclass
class CheckerHealth:
    """Health status for a single checker."""
    name: str
    display_name: str
    emoji: str
    status: CheckerStatus
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    alerts_today: int = 0
    alerts_24h: int = 0
    win_rate_7d: Optional[float] = None
    total_trades_7d: int = 0
    expected_interval: int = 3600  # seconds
    run_conditions: str = "RTH"  # When it should run

class CheckerHealthRegistry:
    """
    Central registry for all checker health metrics.
    Uses SQLite for persistence.
    """
    
    def __init__(self, db_path: str = "data/checker_health.db"):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()
        self._register_all_checkers()
    
    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Checker runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checker_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checker_name TEXT NOT NULL,
                run_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN,
                alerts_generated INT DEFAULT 0,
                error_message TEXT
            )
        """)
        
        # Alert tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checker_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checker_name TEXT NOT NULL,
                alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                alert_type TEXT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                outcome TEXT,  -- WIN, LOSS, PENDING
                pnl_pct REAL
            )
        """)
        
        # Win rate tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checker_win_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checker_name TEXT NOT NULL,
                date TEXT NOT NULL,
                win_rate REAL,
                total_trades INT,
                total_pnl_pct REAL,
                UNIQUE(checker_name, date)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _register_all_checkers(self):
        """Register all checkers with their configs."""
        self.checkers = {
            'fed': CheckerHealth(
                name='fed', display_name='Fed Watch', emoji='🏦',
                status=CheckerStatus.HEALTHY, expected_interval=300,
                run_conditions="24/7"
            ),
            'trump': CheckerHealth(
                name='trump', display_name='Trump Intel', emoji='🎯',
                status=CheckerStatus.HEALTHY, expected_interval=180,
                run_conditions="24/7"
            ),
            'economic': CheckerHealth(
                name='economic', display_name='Economic AI', emoji='📊',
                status=CheckerStatus.HEALTHY, expected_interval=3600,
                run_conditions="24/7"
            ),
            'selloff_rally': CheckerHealth(
                name='selloff_rally', display_name='Selloff/Rally', emoji='🚨',
                status=CheckerStatus.HEALTHY, expected_interval=60,
                run_conditions="RTH only"
            ),
            'dark_pool': CheckerHealth(
                name='dark_pool', display_name='Dark Pool', emoji='🔒',
                status=CheckerStatus.HEALTHY, expected_interval=60,
                run_conditions="RTH only"
            ),
            'reddit': CheckerHealth(
                name='reddit', display_name='Reddit Exploiter', emoji='📱',
                status=CheckerStatus.HEALTHY, expected_interval=3600,
                run_conditions="RTH only"
            ),
            'squeeze': CheckerHealth(
                name='squeeze', display_name='Squeeze Detector', emoji='🔥',
                status=CheckerStatus.HEALTHY, expected_interval=3600,
                run_conditions="RTH only"
            ),
            'gamma': CheckerHealth(
                name='gamma', display_name='Gamma Tracker', emoji='📊',
                status=CheckerStatus.HEALTHY, expected_interval=1800,
                run_conditions="RTH only"
            ),
            'premarket_gap': CheckerHealth(
                name='premarket_gap', display_name='Pre-Market Gap', emoji='🌅',
                status=CheckerStatus.NOT_APPLICABLE, expected_interval=300,
                run_conditions="Pre-market 8:00-9:30 ET"
            ),
            'options_flow': CheckerHealth(
                name='options_flow', display_name='Options Flow', emoji='📊',
                status=CheckerStatus.HEALTHY, expected_interval=1800,
                run_conditions="RTH only"
            ),
            'gamma_flip': CheckerHealth(
                name='gamma_flip', display_name='Gamma Flip', emoji='🎲',
                status=CheckerStatus.HEALTHY, expected_interval=1800,
                run_conditions="RTH only"
            ),
            'news_intelligence': CheckerHealth(
                name='news_intelligence', display_name='News Intel', emoji='📰',
                status=CheckerStatus.HEALTHY, expected_interval=900,
                run_conditions="RTH only"
            ),
            'synthesis': CheckerHealth(
                name='synthesis', display_name='Signal Brain', emoji='🧠',
                status=CheckerStatus.HEALTHY, expected_interval=60,
                run_conditions="RTH only"
            ),
            'ftd': CheckerHealth(
                name='ftd', display_name='FTD Analyzer', emoji='📈',
                status=CheckerStatus.HEALTHY, expected_interval=3600,
                run_conditions="RTH only"
            ),
        }
    
    def record_run(self, checker_name: str, success: bool, alerts_generated: int = 0, error: str = None):
        """Record a checker run."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO checker_runs (checker_name, success, alerts_generated, error_message)
            VALUES (?, ?, ?, ?)
        """, (checker_name, success, alerts_generated, error))
        conn.commit()
        conn.close()
        
        # Update in-memory status
        if checker_name in self.checkers:
            self.checkers[checker_name].last_run = datetime.now()
            if success:
                self.checkers[checker_name].last_success = datetime.now()
                self.checkers[checker_name].status = CheckerStatus.HEALTHY
            else:
                self.checkers[checker_name].last_error = error
                self.checkers[checker_name].status = CheckerStatus.ERROR
    
    def record_alert(self, checker_name: str, alert_type: str, symbol: str = None,
                     direction: str = None, entry_price: float = None):
        """Record an alert generated by a checker."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO checker_alerts (checker_name, alert_type, symbol, direction, entry_price)
            VALUES (?, ?, ?, ?, ?)
        """, (checker_name, alert_type, symbol, direction, entry_price))
        conn.commit()
        conn.close()
    
    def get_alerts_count(self, checker_name: str, hours: int = 24) -> int:
        """Get count of alerts in last N hours."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(hours=hours)
        cursor.execute("""
            SELECT COUNT(*) FROM checker_alerts
            WHERE checker_name = ? AND alert_time > ?
        """, (checker_name, cutoff.isoformat()))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def get_last_run(self, checker_name: str) -> Optional[datetime]:
        """Get last run time for a checker."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT run_time FROM checker_runs
            WHERE checker_name = ? ORDER BY run_time DESC LIMIT 1
        """, (checker_name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            try:
                return datetime.fromisoformat(row[0])
            except (ValueError, TypeError):
                # Handle different datetime formats
                return datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        return None
    
    def get_health_summary(self) -> Dict[str, CheckerHealth]:
        """Get health summary for all checkers."""
        # Update from database
        for name, health in self.checkers.items():
            health.last_run = self.get_last_run(name)
            health.alerts_24h = self.get_alerts_count(name, hours=24)
            health.alerts_today = self.get_alerts_count(name, hours=self._hours_since_midnight())
            
            # Determine status based on last run
            if health.last_run:
                time_since_run = (datetime.now() - health.last_run).total_seconds()
                if time_since_run > health.expected_interval * 2:
                    health.status = CheckerStatus.WARNING
            elif health.status != CheckerStatus.NOT_APPLICABLE:
                # Never run but should have
                health.status = CheckerStatus.WARNING
        
        return self.checkers
    
    def _hours_since_midnight(self) -> int:
        """Get hours since midnight."""
        now = datetime.now()
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return int((now - midnight).total_seconds() / 3600)
    
    def format_time_ago(self, dt: Optional[datetime]) -> str:
        """Format datetime as 'X ago' string."""
        if not dt:
            return "Never"
        
        delta = datetime.now() - dt
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)}s ago"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        else:
            return f"{int(seconds / 86400)}d ago"
    
    def update_win_rate(self, checker_name: str, win_rate: float, total_trades: int):
        """Update win rate for a checker."""
        if checker_name in self.checkers:
            self.checkers[checker_name].win_rate_7d = win_rate
            self.checkers[checker_name].total_trades_7d = total_trades
            
            # Also store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT OR REPLACE INTO checker_win_rates (checker_name, date, win_rate, total_trades)
                VALUES (?, ?, ?, ?)
            """, (checker_name, today, win_rate, total_trades))
            conn.commit()
            conn.close()
    
    def get_dp_learning_stats(self) -> Dict:
        """Pull stats from DP learning database."""
        db_path = 'data/dp_learning.db'
        if not os.path.exists(db_path):
            return {}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get overall bounce rate
            cursor.execute("""
                SELECT outcome, COUNT(*) 
                FROM dp_interactions 
                WHERE outcome IS NOT NULL 
                GROUP BY outcome
            """)
            outcomes = dict(cursor.fetchall())
            bounces = outcomes.get('BOUNCE', 0)
            breaks = outcomes.get('BREAK', 0) + outcomes.get('BREAKDOWN', 0)
            total = bounces + breaks
            
            bounce_rate = bounces / total * 100 if total > 0 else 0
            
            conn.close()
            return {
                'bounce_rate': bounce_rate,
                'total_interactions': total,
                'bounces': bounces,
                'breaks': breaks
            }
        except Exception as e:
            # Database might not exist or have different schema
            return {}
    
    def generate_health_embed(self) -> dict:
        """Generate Discord embed for health status."""
        health = self.get_health_summary()
        
        # Get DP learning stats
        dp_stats = self.get_dp_learning_stats()
        
        # Build status table
        fields = []
        
        for name, h in health.items():
            # Status emoji
            status_emoji = {
                CheckerStatus.HEALTHY: "✅",
                CheckerStatus.WARNING: "⚠️",
                CheckerStatus.ERROR: "❌",
                CheckerStatus.DISABLED: "⏸️",
                CheckerStatus.NOT_APPLICABLE: "⏸️"
            }.get(h.status, "❓")
            
            # Format value
            time_ago = self.format_time_ago(h.last_run)
            alerts = h.alerts_24h
            win_rate = f"{h.win_rate_7d:.1f}%" if h.win_rate_7d else "N/A"
            
            value = f"{status_emoji} {alerts} alerts | {time_ago}"
            if h.win_rate_7d:
                value += f"\nWR: {win_rate} ({h.total_trades_7d} trades)"
            
            fields.append({
                "name": f"{h.emoji} {h.display_name}",
                "value": value,
                "inline": True
            })
        
        # Add DP learning stats if available
        if dp_stats and dp_stats.get('total_interactions', 0) > 0:
            fields.append({
                "name": "🔒 Dark Pool Learning",
                "value": f"**{dp_stats['bounce_rate']:.1f}% bounce rate**\n{dp_stats['total_interactions']} interactions tracked",
                "inline": False
            })
        
        # Add warnings section
        warnings = []
        for name, h in health.items():
            if h.status == CheckerStatus.WARNING:
                warnings.append(f"• {h.display_name}: Hasn't run in {self.format_time_ago(h.last_run)}")
            elif h.status == CheckerStatus.ERROR:
                warnings.append(f"• {h.display_name}: ERROR - {h.last_error}")
        
        if warnings:
            fields.append({
                "name": "⚠️ HEALTH ALERTS",
                "value": "\n".join(warnings[:5]),
                "inline": False
            })
        
        # Determine embed color
        has_warnings = len(warnings) > 0
        has_errors = any(h.status == CheckerStatus.ERROR for h in health.values())
        
        if has_errors:
            color = 15158332  # Red
        elif has_warnings:
            color = 16776960  # Yellow
        else:
            color = 3066993  # Green
        
        embed = {
            "title": "🎯 ALPHA INTELLIGENCE - LIVE HEALTH",
            "color": color,
            "description": f"**Real-time system status** | Updated: {datetime.now().strftime('%H:%M:%S ET')}",
            "fields": fields,
            "footer": {"text": "Dynamic Health v1.0 | Auto-refreshed every cycle"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return embed

