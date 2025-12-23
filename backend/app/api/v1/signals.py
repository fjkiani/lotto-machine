"""
📊 SIGNALS API ENDPOINTS

Fetch active trading signals from the monitor.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from backend.app.core.dependencies import get_monitor_bridge
from backend.app.integrations.unified_monitor_bridge import MonitorBridge

logger = logging.getLogger(__name__)

router = APIRouter()


class SignalResponse(BaseModel):
    """Signal response model"""
    id: str
    symbol: str
    type: str
    action: str
    confidence: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    reasoning: List[str]
    warnings: List[str]
    timestamp: str
    source: str
    is_master: bool
    position_size_pct: Optional[float] = None
    position_size_dollars: Optional[float] = None


@router.get("/signals")
async def get_signals(
    master_only: bool = Query(False, description="Only return master signals (75%+ confidence)"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """Get all active signals."""
    try:
        if not monitor_bridge or not monitor_bridge.monitor:
            return {
                "signals": [],
                "count": 0,
                "master_count": 0,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        monitor = monitor_bridge.monitor
        signals = []
        
        if hasattr(monitor, 'get_active_signals'):
            raw_signals = monitor.get_active_signals()
        elif hasattr(monitor, 'signal_generator') and hasattr(monitor.signal_generator, 'get_recent_signals'):
            raw_signals = monitor.signal_generator.get_recent_signals()
        else:
            logger.warning("Monitor does not expose signals directly")
            raw_signals = []
        
        for signal in raw_signals:
            if symbol and signal.symbol != symbol:
                continue
            if signal_type and signal.signal_type.value != signal_type:
                continue
            if master_only and not signal.is_master_signal:
                continue
            
            signals.append(SignalResponse(
                id=f"{signal.symbol}_{signal.signal_type.value}_{signal.timestamp.isoformat()}",
                symbol=signal.symbol,
                type=signal.signal_type.value,
                action=signal.action.value,
                confidence=signal.confidence * 100,
                entry_price=signal.entry_price,
                stop_price=signal.stop_price,
                target_price=signal.target_price,
                risk_reward=signal.risk_reward_ratio,
                reasoning=signal.supporting_factors,
                warnings=signal.warnings,
                timestamp=signal.timestamp.isoformat(),
                source="SignalGenerator",
                is_master=signal.is_master_signal,
                position_size_pct=signal.position_size_pct,
                position_size_dollars=signal.position_size_dollars,
            ))
        
        signals.sort(key=lambda x: x.confidence, reverse=True)
        master_count = sum(1 for s in signals if s.is_master)
        
        return {
            "signals": [s.dict() for s in signals],
            "count": len(signals),
            "master_count": master_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching signals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching signals: {str(e)}")


@router.get("/signals/master")
async def get_master_signals(
    symbol: Optional[str] = Query(None),
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """Get only master signals (75%+ confidence)"""
    return await get_signals(master_only=True, symbol=symbol, monitor_bridge=monitor_bridge)
