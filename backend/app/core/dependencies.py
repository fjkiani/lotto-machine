"""
FastAPI dependencies for agent endpoints
"""

import os
import logging
from typing import Optional
import redis

logger = logging.getLogger(__name__)

# Global instances
_monitor_bridge = None
_redis_client = None


def get_redis():
    """Get Redis client (singleton)"""
    global _redis_client
    
    if _redis_client is None:
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            try:
                _redis_client = redis.from_url(redis_url, decode_responses=True)
                logger.info("✅ Redis client connected")
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
                _redis_client = None
        else:
            logger.warning("No REDIS_URL found - agent memory disabled")
    
    return _redis_client


def get_monitor_bridge():
    """Get MonitorBridge instance (singleton)"""
    global _monitor_bridge
    
    if _monitor_bridge is None:
        from backend.app.integrations.unified_monitor_bridge import MonitorBridge
        _monitor_bridge = MonitorBridge()
        logger.info("✅ MonitorBridge created")
    
    return _monitor_bridge


def set_monitor_bridge(monitor):
    """Set the monitor instance in bridge (called from FastAPI startup)"""
    bridge = get_monitor_bridge()
    bridge.set_monitor(monitor)

