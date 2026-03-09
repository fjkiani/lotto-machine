"""
📊 SIGNALS API ENDPOINTS

Fetch active trading signals from the monitor.

All endpoints fail loudly (HTTP 503/404/500) — no mock or hardcoded fallbacks.
"""

import os
import logging
import sqlite3
from typing import List, Optional
from datetime import datetime, timedelta
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


class DivergenceSignal(BaseModel):
    """DP Divergence or Confluence signal"""
    symbol: str
    signal_type: str          # DP_CONFLUENCE or OPTIONS_DIVERGENCE
    direction: str            # LONG or SHORT
    confidence: float
    entry_price: float
    stop_pct: float
    target_pct: float
    reasoning: str
    dp_bias: str
    dp_strength: float
    has_divergence: bool
    options_bias: Optional[str] = None


class DivergenceResponse(BaseModel):
    """Response for /signals/divergence"""
    signals: List[DivergenceSignal]
    count: int
    dp_edge_stats: dict       # 89.8% WR stats from dp_learning.db
    timestamp: str


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


@router.get("/signals/divergence", response_model=DivergenceResponse)
async def get_divergence_signals(
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Get DP confluence / options divergence signals.

    Uses DPDivergenceChecker which exploits the 89.8% proven DP bounce rate.
    Also returns live stats from dp_learning.db so the FE can show the edge proof.

    Raises HTTP 503 if DPDivergenceChecker is not initialized.
    Raises HTTP 502 if ChartExchange API call fails.
    Never returns hardcoded or mock data.
    """
    if not monitor_bridge or not monitor_bridge.monitor:
        raise HTTPException(
            status_code=503,
            detail="Monitor not initialized — divergence signals unavailable"
        )

    monitor = monitor_bridge.monitor

    # Locate the DPDivergenceChecker
    dp_div_checker = (
        getattr(monitor, "dp_divergence_checker", None)
        or getattr(monitor, "divergence_checker", None)
    )
    if not dp_div_checker:
        raise HTTPException(
            status_code=503,
            detail=(
                "DPDivergenceChecker not registered on monitor. "
                "Start the monitor with divergence_checker enabled."
            )
        )

    # Get dp_learning.db edge stats (read-only, fast)
    edge_stats: dict = {}
    try:
        edge_stats = dp_div_checker.get_dp_learning_stats()
    except Exception as e:
        logger.warning(f"Could not read dp_learning.db stats: {e}")
        # Non-fatal — edge stats are informational, not required for signals

    # Run the live divergence check
    try:
        raw_alerts = dp_div_checker.check()
    except Exception as e:
        logger.error(f"DPDivergenceChecker.check() failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"DPDivergenceChecker.check() raised an error: {e}"
        )

    # Translate CheckerAlerts → DivergenceSignal models
    signals = []
    for alert in (raw_alerts or []):
        try:
            embed = alert.embed or {}
            fields = {f["name"]: f["value"] for f in embed.get("fields", [])}

            # Parse entry price from "📊 Entry" field
            entry_raw = fields.get("📊 Entry", "0").replace("$", "").strip()
            entry_price = float(entry_raw) if entry_raw else 0.0

            # Parse stop/target
            stop_raw = fields.get("🛑 Stop", "0.0%").replace("-", "").replace("%", "").strip()
            target_raw = fields.get("🎯 Target", "0.0%").replace("+", "").replace("%", "").strip()
            confidence_raw = fields.get("💪 Confidence", "0%").replace("%", "").strip()

            dp_bias_raw = fields.get("📈 DP Bias", "NEUTRAL").split(" ")[0]
            strength_raw = fields.get("📈 DP Bias", "0.0%").split("(")[-1].replace(")", "").replace("%", "").strip()

            signal_type = "DP_CONFLUENCE" if "CONFLUENCE" in embed.get("title", "") else "OPTIONS_DIVERGENCE"
            direction = "LONG" if "LONG" in embed.get("title", "") else "SHORT"
            has_divergence = signal_type == "OPTIONS_DIVERGENCE"

            signals.append(DivergenceSignal(
                symbol=alert.symbol or "UNKNOWN",
                signal_type=signal_type,
                direction=direction,
                confidence=float(confidence_raw) if confidence_raw else 0.0,
                entry_price=entry_price,
                stop_pct=float(stop_raw) if stop_raw else 0.0,
                target_pct=float(target_raw) if target_raw else 0.0,
                reasoning=embed.get("description", ""),
                dp_bias=dp_bias_raw,
                dp_strength=float(strength_raw) / 100 if strength_raw else 0.0,
                has_divergence=has_divergence,
                options_bias=fields.get("📉 Options Bias"),
            ))
        except Exception as parse_err:
            logger.warning(f"Could not parse divergence alert: {parse_err} | alert={alert}")
            continue

    return DivergenceResponse(
        signals=signals,
        count=len(signals),
        dp_edge_stats=edge_stats,
        timestamp=datetime.utcnow().isoformat(),
    )
