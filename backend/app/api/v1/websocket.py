"""
🌐 WebSocket Endpoints for Real-Time Updates

Provides WebSocket endpoints for real-time market data, signals, and agent insights.
"""

import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from backend.app.core.websocket_manager import connection_manager, websocket_publisher

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/unified")
async def websocket_unified(websocket: WebSocket):
    """
    Unified WebSocket endpoint - receives all alerts and signals.
    
    Subscribe to all real-time updates:
    - Alerts from all checkers
    - Trading signals
    - Market data updates
    - Agent insights
    - Narrative updates
    """
    await connection_manager.connect(websocket, channel="unified")
    
    try:
        # Send welcome message
        await connection_manager.send_personal_message({
            "type": "welcome",
            "channel": "unified",
            "message": "Connected to Alpha Terminal unified stream",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }, websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle client messages (e.g., subscription changes)
                if message.get("type") == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": __import__("datetime").datetime.now().isoformat()
                    }, websocket)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("Client disconnected from unified stream")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)


@router.websocket("/ws/market/{symbol}")
async def websocket_market(websocket: WebSocket, symbol: str):
    """
    Symbol-specific market data WebSocket endpoint.
    
    Subscribe to real-time updates for a specific symbol:
    - Price updates
    - Volume updates
    - DP level alerts
    - Gamma updates
    """
    channel = f"market_{symbol.upper()}"
    await connection_manager.connect(websocket, channel=channel)
    
    try:
        await connection_manager.send_personal_message({
            "type": "welcome",
            "channel": channel,
            "symbol": symbol.upper(),
            "message": f"Connected to {symbol.upper()} market stream",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }, websocket)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": __import__("datetime").datetime.now().isoformat()
                    }, websocket)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info(f"Client disconnected from {symbol} market stream")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)


@router.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """
    Trading signals WebSocket endpoint.
    
    Subscribe to real-time trading signals:
    - Master signals (75%+ confidence)
    - High confidence signals (60-74%)
    - Signal updates (entry/exit)
    """
    await connection_manager.connect(websocket, channel="signals")
    
    try:
        await connection_manager.send_personal_message({
            "type": "welcome",
            "channel": "signals",
            "message": "Connected to signals stream",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }, websocket)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": __import__("datetime").datetime.now().isoformat()
                    }, websocket)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("Client disconnected from signals stream")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)


@router.websocket("/ws/agents/{agent_name}")
async def websocket_agent(websocket: WebSocket, agent_name: str):
    """
    Agent-specific WebSocket endpoint.
    
    Subscribe to real-time insights from a specific agent:
    - MarketAgent insights
    - SignalAgent insights
    - DarkPoolAgent insights
    - etc.
    """
    channel = f"agent_{agent_name.lower()}"
    await connection_manager.connect(websocket, channel=channel)
    
    try:
        await connection_manager.send_personal_message({
            "type": "welcome",
            "channel": channel,
            "agent": agent_name,
            "message": f"Connected to {agent_name} agent stream",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }, websocket)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": __import__("datetime").datetime.now().isoformat()
                    }, websocket)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info(f"Client disconnected from {agent_name} agent stream")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)


@router.websocket("/ws/narrative")
async def websocket_narrative(websocket: WebSocket):
    """
    Narrative Brain WebSocket endpoint.
    
    Subscribe to real-time narrative updates:
    - Market narrative synthesis
    - Narrative updates (every 5 minutes)
    - Narrative Q&A responses
    """
    await connection_manager.connect(websocket, channel="narrative")
    
    try:
        await connection_manager.send_personal_message({
            "type": "welcome",
            "channel": "narrative",
            "message": "Connected to Narrative Brain stream",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }, websocket)
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await connection_manager.send_personal_message({
                        "type": "pong",
                        "timestamp": __import__("datetime").datetime.now().isoformat()
                    }, websocket)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
        logger.info("Client disconnected from narrative stream")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        connection_manager.disconnect(websocket)


@router.get("/ws/stats")
async def websocket_stats():
    """Get WebSocket connection statistics"""
    return connection_manager.get_stats()

