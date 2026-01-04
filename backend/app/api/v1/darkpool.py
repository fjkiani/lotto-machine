"""
Dark Pool Flow API Endpoints

Provides dark pool levels, summaries, and recent prints for frontend widgets.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from backend.app.core.dependencies import get_monitor_bridge
from backend.app.integrations.unified_monitor_bridge import MonitorBridge

logger = logging.getLogger(__name__)

router = APIRouter()


class DPLevel(BaseModel):
    """Dark Pool Level"""
    price: float
    volume: int
    level_type: str = Field(..., description="SUPPORT, RESISTANCE, or BATTLEGROUND")
    strength: float = Field(..., ge=0, le=100, description="Strength score 0-100")
    distance_from_price: Optional[float] = None


class DPPrint(BaseModel):
    """Dark Pool Print"""
    price: float
    volume: int
    side: str = Field(..., description="BUY or SELL")
    timestamp: datetime


class DPSummary(BaseModel):
    """Dark Pool Summary"""
    total_volume: int
    dp_percent: float = Field(..., ge=0, le=100, description="Dark pool percentage")
    buying_pressure: float = Field(..., ge=0, le=100, description="Buying pressure 0-100")
    nearest_support: Optional[DPLevel] = None
    nearest_resistance: Optional[DPLevel] = None
    battlegrounds: List[DPLevel] = Field(default_factory=list)


class DPLevelsResponse(BaseModel):
    """Dark Pool Levels Response"""
    symbol: str
    levels: List[DPLevel]
    current_price: float
    timestamp: datetime


class DPPrintsResponse(BaseModel):
    """Dark Pool Prints Response"""
    symbol: str
    prints: List[DPPrint]
    count: int
    timestamp: datetime


class DPSummaryResponse(BaseModel):
    """Dark Pool Summary Response"""
    symbol: str
    summary: DPSummary
    timestamp: datetime


@router.get("/darkpool/{symbol}/levels", response_model=DPLevelsResponse)
async def get_dp_levels(
    symbol: str,
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Get dark pool levels for a symbol.
    
    Returns support, resistance, and battleground levels with volumes.
    """
    try:
        # Get current price
        current_price = await _get_current_price(symbol, monitor_bridge)
        
        # Get dark pool levels from monitor
        levels = await _fetch_dp_levels(symbol, monitor_bridge)
        
        # Calculate distance from current price
        for level in levels:
            if level.get('price') and current_price:
                level['distance_from_price'] = abs(level['price'] - current_price)
        
        # Sort by volume (descending)
        levels_sorted = sorted(levels, key=lambda x: x.get('volume', 0), reverse=True)
        
        # Convert to DPLevel models
        dp_levels = [
            DPLevel(
                price=level['price'],
                volume=level['volume'],
                level_type=level.get('type', 'UNKNOWN'),
                strength=level.get('strength', 50.0),
                distance_from_price=level.get('distance_from_price')
            )
            for level in levels_sorted
            if level.get('price') and level.get('volume')
        ]
        
        return DPLevelsResponse(
            symbol=symbol.upper(),
            levels=dp_levels,
            current_price=current_price or 0.0,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error fetching DP levels for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch DP levels: {str(e)}")


@router.get("/darkpool/{symbol}/summary", response_model=DPSummaryResponse)
async def get_dp_summary(
    symbol: str,
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Get dark pool summary for a symbol.
    
    Returns aggregated statistics including total volume, DP%, buying pressure,
    and nearest support/resistance levels.
    """
    try:
        # Get levels
        levels_response = await get_dp_levels(symbol, monitor_bridge)
        levels = levels_response.levels
        current_price = levels_response.current_price
        
        # Get summary data from monitor
        summary_data = await _fetch_dp_summary(symbol, monitor_bridge)
        
        # Find nearest support and resistance
        nearest_support = None
        nearest_resistance = None
        battlegrounds = []
        
        for level in levels:
            if level.level_type == 'SUPPORT' and level.price < current_price:
                if nearest_support is None or level.price > nearest_support.price:
                    nearest_support = level
            elif level.level_type == 'RESISTANCE' and level.price > current_price:
                if nearest_resistance is None or level.price < nearest_resistance.price:
                    nearest_resistance = level
            elif level.level_type == 'BATTLEGROUND':
                battlegrounds.append(level)
        
        # Build summary
        summary = DPSummary(
            total_volume=summary_data.get('total_volume', sum(l.volume for l in levels)),
            dp_percent=summary_data.get('dp_percent', 0.0),
            buying_pressure=summary_data.get('buying_pressure', 50.0),
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            battlegrounds=battlegrounds[:5]  # Top 5 battlegrounds
        )
        
        return DPSummaryResponse(
            symbol=symbol.upper(),
            summary=summary,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error fetching DP summary for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch DP summary: {str(e)}")


@router.get("/darkpool/{symbol}/prints", response_model=DPPrintsResponse)
async def get_dp_prints(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Number of recent prints to return"),
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Get recent dark pool prints for a symbol.
    
    Returns the most recent dark pool trades (prints).
    """
    try:
        # Get prints from monitor
        prints = await _fetch_dp_prints(symbol, monitor_bridge, limit)
        
        # Convert to DPPrint models
        dp_prints = [
            DPPrint(
                price=print_data['price'],
                volume=print_data['volume'],
                side=print_data.get('side', 'BUY'),
                timestamp=datetime.fromisoformat(print_data['timestamp'].replace('Z', '+00:00'))
                if isinstance(print_data.get('timestamp'), str)
                else print_data.get('timestamp', datetime.now())
            )
            for print_data in prints
            if print_data.get('price') and print_data.get('volume')
        ]
        
        # Sort by timestamp (most recent first)
        dp_prints.sort(key=lambda x: x.timestamp, reverse=True)
        
        return DPPrintsResponse(
            symbol=symbol.upper(),
            prints=dp_prints[:limit],
            count=len(dp_prints),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error fetching DP prints for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch DP prints: {str(e)}")


# Helper functions

async def _get_current_price(symbol: str, monitor_bridge: MonitorBridge) -> Optional[float]:
    """Get current price for symbol"""
    try:
        if monitor_bridge.monitor:
            # Try to get from monitor's data fetcher
            data = await monitor_bridge.monitor.data_fetcher.fetch_quote(symbol)
            if data and hasattr(data, 'price'):
                return float(data.price)
            elif isinstance(data, dict) and 'price' in data:
                return float(data['price'])
    except Exception as e:
        logger.warning(f"Could not fetch current price for {symbol}: {e}")
    
    # Fallback: return None (frontend can handle)
    return None


async def _fetch_dp_levels(symbol: str, monitor_bridge: MonitorBridge) -> List[dict]:
    """Fetch dark pool levels from monitor"""
    try:
        if monitor_bridge.monitor:
            # Try to get from dark pool checker
            dp_checker = getattr(monitor_bridge.monitor, 'dark_pool_checker', None)
            if dp_checker:
                # Get levels from checker
                context = await dp_checker.check(symbol)
                if context and hasattr(context, 'dp_levels'):
                    levels = context.dp_levels
                    return [
                        {
                            'price': level.price if hasattr(level, 'price') else level.get('price'),
                            'volume': level.volume if hasattr(level, 'volume') else level.get('volume', 0),
                            'type': level.type if hasattr(level, 'type') else level.get('type', 'UNKNOWN'),
                            'strength': level.strength if hasattr(level, 'strength') else level.get('strength', 50.0)
                        }
                        for level in levels
                    ]
    except Exception as e:
        logger.warning(f"Could not fetch DP levels from monitor for {symbol}: {e}")
    
    # Fallback: return mock data for development
    return _generate_mock_dp_levels(symbol)


async def _fetch_dp_summary(symbol: str, monitor_bridge: MonitorBridge) -> dict:
    """Fetch dark pool summary from monitor"""
    try:
        if monitor_bridge.monitor:
            # Try to get from dark pool checker
            dp_checker = getattr(monitor_bridge.monitor, 'dark_pool_checker', None)
            if dp_checker:
                context = await dp_checker.check(symbol)
                if context:
                    return {
                        'total_volume': getattr(context, 'total_dp_volume', 0),
                        'dp_percent': getattr(context, 'dp_percent', 0.0),
                        'buying_pressure': getattr(context, 'buying_pressure', 50.0)
                    }
    except Exception as e:
        logger.warning(f"Could not fetch DP summary from monitor for {symbol}: {e}")
    
    # Fallback: return mock data
    return {
        'total_volume': 1000000,
        'dp_percent': 45.0,
        'buying_pressure': 60.0
    }


async def _fetch_dp_prints(symbol: str, monitor_bridge: MonitorBridge, limit: int) -> List[dict]:
    """Fetch dark pool prints from monitor"""
    try:
        if monitor_bridge.monitor:
            # Try to get from dark pool checker
            dp_checker = getattr(monitor_bridge.monitor, 'dark_pool_checker', None)
            if dp_checker:
                context = await dp_checker.check(symbol)
                if context and hasattr(context, 'recent_prints'):
                    prints = context.recent_prints
                    return [
                        {
                            'price': p.price if hasattr(p, 'price') else p.get('price'),
                            'volume': p.volume if hasattr(p, 'volume') else p.get('volume', 0),
                            'side': p.side if hasattr(p, 'side') else p.get('side', 'BUY'),
                            'timestamp': p.timestamp if hasattr(p, 'timestamp') else p.get('timestamp', datetime.now())
                        }
                        for p in prints[:limit]
                    ]
    except Exception as e:
        logger.warning(f"Could not fetch DP prints from monitor for {symbol}: {e}")
    
    # Fallback: return mock data
    return _generate_mock_dp_prints(symbol, limit)


def _generate_mock_dp_levels(symbol: str) -> List[dict]:
    """Generate mock DP levels for development/testing"""
    base_price = 500.0 if symbol.upper() == 'SPY' else 400.0
    
    return [
        {'price': base_price - 5.0, 'volume': 2500000, 'type': 'SUPPORT', 'strength': 85.0},
        {'price': base_price - 2.5, 'volume': 1500000, 'type': 'SUPPORT', 'strength': 70.0},
        {'price': base_price, 'volume': 5000000, 'type': 'BATTLEGROUND', 'strength': 90.0},
        {'price': base_price + 2.5, 'volume': 1800000, 'type': 'RESISTANCE', 'strength': 75.0},
        {'price': base_price + 5.0, 'volume': 3000000, 'type': 'RESISTANCE', 'strength': 80.0},
    ]


def _generate_mock_dp_prints(symbol: str, limit: int) -> List[dict]:
    """Generate mock DP prints for development/testing"""
    base_price = 500.0 if symbol.upper() == 'SPY' else 400.0
    prints = []
    
    for i in range(limit):
        prints.append({
            'price': base_price + (i * 0.5) - (limit * 0.25),
            'volume': 100000 + (i * 50000),
            'side': 'BUY' if i % 2 == 0 else 'SELL',
            'timestamp': datetime.now() - timedelta(minutes=limit - i)
        })
    
    return prints

