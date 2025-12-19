"""
🔗 Alert Manager → WebSocket Bridge

Integrates AlertManager with WebSocket publisher to broadcast
all alerts in real-time to connected clients.

Usage:
    # In AlertManager.send_discord(), add:
    from backend.app.integrations.alert_websocket_bridge import publish_alert_to_websocket
    await publish_alert_to_websocket(embed, content, alert_type, source, symbol)
"""

import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_websocket_publisher = None


def _get_websocket_publisher():
    """Get WebSocket publisher instance (lazy import)"""
    global _websocket_publisher
    if _websocket_publisher is None:
        try:
            from backend.app.core.websocket_manager import websocket_publisher
            _websocket_publisher = websocket_publisher
        except ImportError:
            logger.warning("WebSocket publisher not available - alerts will not be broadcast")
            return None
    return _websocket_publisher


async def publish_alert_to_websocket(
    embed: dict,
    content: str = None,
    alert_type: str = "general",
    source: str = "monitor",
    symbol: str = None
):
    """
    Publish alert to WebSocket channels.
    
    This function should be called from AlertManager.send_discord()
    to broadcast alerts via WebSocket.
    
    Args:
        embed: Discord embed dict
        content: Alert content string
        alert_type: Type of alert (e.g., "signal", "synthesis", "dark_pool")
        source: Source of alert (e.g., "monitor", "checker_name")
        symbol: Symbol if applicable (e.g., "SPY", "QQQ")
    """
    publisher = _get_websocket_publisher()
    if publisher is None:
        return
    
    try:
        await publisher.publish_alert(
            embed=embed,
            content=content,
            alert_type=alert_type,
            source=source,
            symbol=symbol
        )
    except Exception as e:
        logger.error(f"Error publishing alert to WebSocket: {e}", exc_info=True)


def publish_alert_to_websocket_sync(
    embed: dict,
    content: str = None,
    alert_type: str = "general",
    source: str = "monitor",
    symbol: str = None
):
    """
    Synchronous wrapper for publish_alert_to_websocket.
    
    Use this if you're calling from a synchronous context (like AlertManager).
    """
    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule as task
            asyncio.create_task(publish_alert_to_websocket(
                embed, content, alert_type, source, symbol
            ))
        else:
            # If loop is not running, run it
            loop.run_until_complete(publish_alert_to_websocket(
                embed, content, alert_type, source, symbol
            ))
    except RuntimeError:
        # No event loop, create new one
        try:
            asyncio.run(publish_alert_to_websocket(
                embed, content, alert_type, source, symbol
            ))
        except Exception as e:
            logger.error(f"Error in sync WebSocket publish: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error in sync WebSocket publish: {e}", exc_info=True)

