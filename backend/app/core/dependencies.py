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


def get_savage_agents_service():
    """Get NarrativeBrainAgent with all specialized agents (singleton)"""
    from backend.app.services.savage_agents import (
        MarketAgent, SignalAgent, DarkPoolAgent,
        GammaAgent, SqueezeAgent, OptionsAgent, RedditAgent, MacroAgent,
        NarrativeBrainAgent
    )
    
    redis_client = get_redis()
    
    # Initialize all specialized agents
    market_agent = MarketAgent(redis_client=redis_client)
    signal_agent = SignalAgent(redis_client=redis_client)
    dark_pool_agent = DarkPoolAgent(redis_client=redis_client)
    gamma_agent = GammaAgent(redis_client=redis_client)
    squeeze_agent = SqueezeAgent(redis_client=redis_client)
    options_agent = OptionsAgent(redis_client=redis_client)
    reddit_agent = RedditAgent(redis_client=redis_client)
    macro_agent = MacroAgent(redis_client=redis_client)
    
    # Create NarrativeBrainAgent with all agents
    narrative_brain = NarrativeBrainAgent(
        agents=[
            market_agent,
            signal_agent,
            dark_pool_agent,
            gamma_agent,
            squeeze_agent,
            options_agent,
            reddit_agent,
            macro_agent,
        ],
        redis_client=redis_client
    )
    
    return narrative_brain

