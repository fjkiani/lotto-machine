"""
🩺 SYSTEM HEALTH API ENDPOINTS

Provides health status for all checkers in the system.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from live_monitoring.orchestrator.checker_health import CheckerHealthRegistry, CheckerStatus, CheckerHealth

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize health registry
health_registry = CheckerHealthRegistry()


class CheckerHealthResponse(BaseModel):
    """Health response for a single checker"""
    name: str
    display_name: str
    emoji: str
    status: str
    last_run: Optional[str]
    last_success: Optional[str]
    last_error: Optional[str]
    alerts_today: int
    alerts_24h: int
    win_rate_7d: Optional[float]
    total_trades_7d: int
    expected_interval: int
    run_conditions: str
    time_since_last_run: Optional[str]


class HealthSummaryResponse(BaseModel):
    """Overall health summary"""
    total_checkers: int
    healthy: int
    warning: int
    error: int
    disabled: int
    not_applicable: int
    checkers: List[CheckerHealthResponse]
    timestamp: str


@router.get("/health/checkers")
async def get_checker_health():
    """
    Get health status for all checkers.
    
    Returns detailed health information including:
    - Status (healthy/warning/error/disabled)
    - Last run time
    - Alerts generated
    - Win rates (7-day)
    """
    try:
        # Get health summary from registry
        health_summary = health_registry.get_health_summary()
        
        # Convert to API response format
        checkers = []
        status_counts = {
            'healthy': 0,
            'warning': 0,
            'error': 0,
            'disabled': 0,
            'n/a': 0
        }
        
        for checker_name, health in health_summary.items():
            # Calculate time since last run
            time_since = None
            if health.last_run:
                delta = datetime.now() - health.last_run
                if delta.total_seconds() < 60:
                    time_since = f"{int(delta.total_seconds())}s ago"
                elif delta.total_seconds() < 3600:
                    time_since = f"{int(delta.total_seconds() / 60)}m ago"
                else:
                    time_since = f"{int(delta.total_seconds() / 3600)}h ago"
            elif health.status == CheckerStatus.NOT_APPLICABLE:
                time_since = "N/A"
            else:
                time_since = "Never"
            
            # Count by status
            status_key = health.status.value
            if status_key in status_counts:
                status_counts[status_key] += 1
            
            checkers.append(CheckerHealthResponse(
                name=health.name,
                display_name=health.display_name,
                emoji=health.emoji,
                status=health.status.value,
                last_run=health.last_run.isoformat() if health.last_run else None,
                last_success=health.last_success.isoformat() if health.last_success else None,
                last_error=health.last_error,
                alerts_today=health.alerts_today,
                alerts_24h=health.alerts_24h,
                win_rate_7d=health.win_rate_7d,
                total_trades_7d=health.total_trades_7d,
                expected_interval=health.expected_interval,
                run_conditions=health.run_conditions,
                time_since_last_run=time_since
            ))
        
        return HealthSummaryResponse(
            total_checkers=len(checkers),
            healthy=status_counts['healthy'],
            warning=status_counts['warning'],
            error=status_counts['error'],
            disabled=status_counts['disabled'],
            not_applicable=status_counts['n/a'],
            checkers=checkers,
            timestamp=datetime.utcnow().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error fetching checker health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching checker health: {str(e)}")


@router.get("/health/checkers/{checker_name}")
async def get_single_checker_health(checker_name: str):
    """
    Get health status for a single checker.
    """
    try:
        health_summary = health_registry.get_health_summary()
        
        if checker_name not in health_summary:
            raise HTTPException(status_code=404, detail=f"Checker '{checker_name}' not found")
        
        health = health_summary[checker_name]
        
        # Calculate time since last run
        time_since = None
        if health.last_run:
            delta = datetime.now() - health.last_run
            if delta.total_seconds() < 60:
                time_since = f"{int(delta.total_seconds())}s ago"
            elif delta.total_seconds() < 3600:
                time_since = f"{int(delta.total_seconds() / 60)}m ago"
            else:
                time_since = f"{int(delta.total_seconds() / 3600)}h ago"
        elif health.status == CheckerStatus.NOT_APPLICABLE:
            time_since = "N/A"
        else:
            time_since = "Never"
        
        return CheckerHealthResponse(
            name=health.name,
            display_name=health.display_name,
            emoji=health.emoji,
            status=health.status.value,
            last_run=health.last_run.isoformat() if health.last_run else None,
            last_success=health.last_success.isoformat() if health.last_success else None,
            last_error=health.last_error,
            alerts_today=health.alerts_today,
            alerts_24h=health.alerts_24h,
            win_rate_7d=health.win_rate_7d,
            total_trades_7d=health.total_trades_7d,
            expected_interval=health.expected_interval,
            run_conditions=health.run_conditions,
            time_since_last_run=time_since
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching checker health for {checker_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching checker health: {str(e)}")


@router.get("/health/summary")
async def get_health_summary():
    """
    Get a quick health summary (for dashboard header).
    """
    try:
        health_summary = health_registry.get_health_summary()
        
        status_counts = {
            'healthy': 0,
            'warning': 0,
            'error': 0,
            'disabled': 0,
            'n/a': 0
        }
        
        for health in health_summary.values():
            status_key = health.status.value
            if status_key in status_counts:
                status_counts[status_key] += 1
        
        return {
            "total": len(health_summary),
            "healthy": status_counts['healthy'],
            "warning": status_counts['warning'],
            "error": status_counts['error'],
            "disabled": status_counts['disabled'],
            "not_applicable": status_counts['n/a'],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching health summary: {e}", exc_info=True)
        return {
            "total": 0,
            "healthy": 0,
            "warning": 0,
            "error": 0,
            "disabled": 0,
            "not_applicable": 0,
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/health/history")
async def get_health_history(days: int = 7):
    """
    Get historical health data from alerts_history.db and checker_health.db.
    Returns recent alerts and checker run counts for cross-session intelligence.
    """
    import sqlite3
    from pathlib import Path
    
    result = {"alerts": [], "checker_runs": [], "timestamp": datetime.utcnow().isoformat()}
    
    try:
        alerts_path = Path("data/alerts_history.db")
        if not alerts_path.exists():
            try:
                from core.utils.persistent_storage import get_database_path
                alerts_path = get_database_path("alerts_history.db")
            except Exception:
                pass
        
        if alerts_path.exists():
            conn = sqlite3.connect(str(alerts_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 50"
            ).fetchall()
            result["alerts"] = [dict(r) for r in rows]
            conn.close()
    except Exception as e:
        logger.warning(f"Could not read alerts_history: {e}")
    
    try:
        checker_path = Path("data/checker_health.db")
        if not checker_path.exists():
            try:
                from core.utils.persistent_storage import get_database_path
                checker_path = get_database_path("checker_health.db")
            except Exception:
                pass
        
        if checker_path.exists():
            conn = sqlite3.connect(str(checker_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT checker_name, COUNT(*) as run_count, MAX(run_time) as last_run "
                "FROM checker_runs GROUP BY checker_name ORDER BY last_run DESC"
            ).fetchall()
            result["checker_runs"] = [dict(r) for r in rows]
            conn.close()
    except Exception as e:
        logger.warning(f"Could not read checker_health: {e}")
    
    return result


@router.get("/health/win-rates")
async def get_win_rates():
    """
    Get per-checker win rates over 7 days.
    
    Primary source: checker_win_rates table.
    Fallback: computes dark_pool win rate from dp_learning.db (89.8% WR proven).
    """
    import sqlite3
    from pathlib import Path
    
    win_rates = []
    
    # Try checker_win_rates table first
    try:
        checker_path = Path("data/checker_health.db")
        if checker_path.exists():
            conn = sqlite3.connect(str(checker_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT checker_name, date, win_rate, total_trades, total_pnl_pct "
                "FROM checker_win_rates ORDER BY date DESC LIMIT 100"
            ).fetchall()
            win_rates = [dict(r) for r in rows]
            conn.close()
    except Exception as e:
        logger.warning(f"Could not read checker_win_rates: {e}")
    
    # Fallback: compute from dp_learning.db if no win_rates recorded
    dp_stats = None
    try:
        dp_path = Path("data/dp_learning.db")
        if dp_path.exists():
            conn = sqlite3.connect(str(dp_path))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT outcome, COUNT(*) FROM dp_interactions
                WHERE outcome IS NOT NULL GROUP BY outcome
            """)
            outcomes = dict(cursor.fetchall())
            bounces = outcomes.get('BOUNCE', 0)
            breaks = outcomes.get('BREAK', 0) + outcomes.get('BREAKDOWN', 0)
            total = bounces + breaks
            
            dp_stats = {
                "checker_name": "dark_pool",
                "win_rate": round(bounces / total * 100, 1) if total > 0 else 0,
                "total_trades": total,
                "bounces": bounces,
                "breaks": breaks,
                "source": "dp_learning.db (computed)"
            }
            conn.close()
    except Exception as e:
        logger.warning(f"Could not compute DP win rate: {e}")
    
    return {
        "win_rates": win_rates,
        "dp_learning_stats": dp_stats,
        "has_data": len(win_rates) > 0 or dp_stats is not None,
        "timestamp": datetime.utcnow().isoformat()
    }


