"""
🌐 WebSocket Manager for Real-Time Updates

Manages WebSocket connections and broadcasts alerts/signals to connected clients.
Integrates with AlertManager to intercept and broadcast all alerts.
"""

import json
import logging
import asyncio
from typing import Dict, Set, Optional, Any
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and channel subscriptions.
    
    Supports multiple channels:
    - /ws/unified - All alerts and signals
    - /ws/market/{symbol} - Price updates for specific symbol
    - /ws/signals - Trading signals only
    - /ws/agents/{agent_name} - Agent insights
    - /ws/narrative - Narrative Brain updates
    """
    
    def __init__(self):
        # Active connections by channel
        self.active_connections: Dict[str, Set[WebSocket]] = defaultdict(set)
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, channel: str = "unified"):
        """Accept WebSocket connection and add to channel"""
        await websocket.accept()
        self.active_connections[channel].add(websocket)
        self.connection_metadata[websocket] = {
            "channel": channel,
            "connected_at": datetime.now().isoformat(),
            "message_count": 0
        }
        logger.info(f"✅ WebSocket connected to channel '{channel}' (total: {len(self.active_connections[channel])})")
        
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.connection_metadata:
            channel = self.connection_metadata[websocket].get("channel", "unified")
            self.active_connections[channel].discard(websocket)
            del self.connection_metadata[websocket]
            logger.info(f"❌ WebSocket disconnected from channel '{channel}' (remaining: {len(self.active_connections[channel])})")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to a specific connection"""
        try:
            await websocket.send_json(message)
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["message_count"] += 1
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast_to_channel(self, message: dict, channel: str):
        """Broadcast message to all connections in a channel"""
        if channel not in self.active_connections:
            return
        
        disconnected = set()
        for websocket in self.active_connections[channel]:
            try:
                await websocket.send_json(message)
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["message_count"] += 1
            except Exception as e:
                logger.error(f"Error broadcasting to channel '{channel}': {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected connections
        for ws in disconnected:
            self.disconnect(ws)
    
    async def broadcast_unified(self, message: dict):
        """Broadcast to unified channel (all alerts)"""
        await self.broadcast_to_channel(message, "unified")
    
    async def broadcast_market(self, symbol: str, message: dict):
        """Broadcast to symbol-specific market channel"""
        await self.broadcast_to_channel(message, f"market_{symbol}")
    
    async def broadcast_signals(self, message: dict):
        """Broadcast to signals channel"""
        await self.broadcast_to_channel(message, "signals")
    
    async def broadcast_agent(self, agent_name: str, message: dict):
        """Broadcast to agent-specific channel"""
        await self.broadcast_to_channel(message, f"agent_{agent_name}")
    
    async def broadcast_narrative(self, message: dict):
        """Broadcast to narrative channel"""
        await self.broadcast_to_channel(message, "narrative")
    
    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "total_connections": sum(len(conns) for conns in self.active_connections.values()),
            "channels": {
                channel: len(conns) 
                for channel, conns in self.active_connections.items()
            },
            "connections": [
                {
                    "channel": meta.get("channel"),
                    "connected_at": meta.get("connected_at"),
                    "message_count": meta.get("message_count", 0)
                }
                for meta in self.connection_metadata.values()
            ]
        }


# Global connection manager instance
connection_manager = ConnectionManager()


class WebSocketPublisher:
    """
    Publishes alerts and signals to WebSocket channels.
    
    This class can be integrated with AlertManager to intercept
    alerts and broadcast them via WebSocket.
    """
    
    def __init__(self, connection_manager: ConnectionManager = None):
        self.connection_manager = connection_manager or globals()['connection_manager']
    
    async def publish_alert(
        self,
        embed: dict,
        content: str = None,
        alert_type: str = "general",
        source: str = "monitor",
        symbol: str = None
    ):
        """
        Publish alert to WebSocket channels.
        
        This method should be called from AlertManager.send_discord()
        to broadcast alerts via WebSocket.
        """
        message = {
            "type": "alert",
            "alert_type": alert_type,
            "source": source,
            "symbol": symbol,
            "content": content,
            "embed": embed,
            "timestamp": datetime.now().isoformat()
        }
        
        # Broadcast to unified channel (all alerts)
        await self.connection_manager.broadcast_unified(message)
        
        # Broadcast to signals channel if it's a signal
        if alert_type in ["signal", "synthesis", "narrative"]:
            await self.connection_manager.broadcast_signals(message)
        
        # Broadcast to symbol-specific market channel
        if symbol:
            await self.connection_manager.broadcast_market(symbol, message)
    
    async def publish_signal(self, signal: dict):
        """Publish trading signal"""
        message = {
            "type": "signal",
            "signal": signal,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.broadcast_signals(message)
        await self.connection_manager.broadcast_unified(message)
        
        if signal.get("symbol"):
            await self.connection_manager.broadcast_market(
                signal["symbol"], 
                message
            )
    
    async def publish_market_data(self, symbol: str, data: dict):
        """Publish market data update"""
        message = {
            "type": "market_data",
            "symbol": symbol,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.broadcast_market(symbol, message)
        await self.connection_manager.broadcast_unified(message)
    
    async def publish_agent_insight(self, agent_name: str, insight: dict):
        """Publish agent insight"""
        message = {
            "type": "agent_insight",
            "agent": agent_name,
            "insight": insight,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.broadcast_agent(agent_name, message)
        await self.connection_manager.broadcast_unified(message)
    
    async def publish_narrative(self, narrative: dict):
        """Publish narrative update"""
        message = {
            "type": "narrative",
            "narrative": narrative,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.connection_manager.broadcast_narrative(message)
        await self.connection_manager.broadcast_unified(message)


# Global WebSocket publisher instance
websocket_publisher = WebSocketPublisher(connection_manager)

