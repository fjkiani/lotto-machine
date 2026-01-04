"""
🩺 SYSTEM HEALTH API ENDPOINTS

Provides health status for all checkers in the system.
"""

import logging
from typing import Dict, List
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
    last_run: str | None
    last_success: str | None
    last_error: str | None
    alerts_today: int
    alerts_24h: int
    win_rate_7d: float | None
    total_trades_7d: int
    expected_interval: int
    run_conditions: str
    time_since_last_run: str | None


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
            'not_applicable': 0
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
            not_applicable=status_counts['not_applicable'],
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
            'not_applicable': 0
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
            "not_applicable": status_counts['not_applicable'],
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

