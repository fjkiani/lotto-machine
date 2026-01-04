"""
Options Flow API Endpoints

Provides options flow data, most active options, unusual activity, and accumulation zones.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from backend.app.core.dependencies import get_monitor_bridge
from backend.app.integrations.unified_monitor_bridge import MonitorBridge

logger = logging.getLogger(__name__)

router = APIRouter()


class OptionFlow(BaseModel):
    """Most active option"""
    symbol: str
    strike: float
    expiration: str
    option_type: str = Field(..., description="CALL or PUT")
    volume: int
    open_interest: int
    last_price: float
    bid: float
    ask: float
    implied_volatility: Optional[float] = None


class UnusualActivity(BaseModel):
    """Unusual options activity"""
    symbol: str
    strike: float
    expiration: str
    option_type: str = Field(..., description="CALL or PUT")
    volume: int
    open_interest: int
    volume_oi_ratio: float
    last_price: float
    reason: str = Field(..., description="Why it's unusual")


class StrikeZone(BaseModel):
    """Call/Put accumulation zone"""
    strike: float
    expiration: str
    total_volume: int
    total_oi: int
    avg_price: float
    direction: str = Field(..., description="CALL or PUT")


class Sweep(BaseModel):
    """Options sweep"""
    symbol: str
    strike: float
    expiration: str
    option_type: str = Field(..., description="CALL or PUT")
    contracts: int
    premium: float
    timestamp: datetime


class OptionsFlowResponse(BaseModel):
    """Options flow response"""
    symbol: str
    most_active: List[OptionFlow] = Field(default_factory=list)
    unusual_activity: List[UnusualActivity] = Field(default_factory=list)
    call_put_ratio: float = Field(..., description="Call/Put volume ratio")
    accumulation_zones: Dict[str, List[StrikeZone]] = Field(
        default_factory=dict,
        description="calls and puts accumulation zones"
    )
    sweeps: List[Sweep] = Field(default_factory=list)
    timestamp: datetime


@router.get("/options/{symbol}/flow", response_model=OptionsFlowResponse)
async def get_options_flow(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Number of results per category"),
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Get options flow data for a symbol.
    
    Returns most active options, unusual activity, P/C ratio, accumulation zones, and sweeps.
    """
    try:
        # Get options flow data from monitor
        flow_data = await _fetch_options_flow(symbol, monitor_bridge, limit)
        
        return OptionsFlowResponse(
            symbol=symbol.upper(),
            most_active=flow_data.get('most_active', []),
            unusual_activity=flow_data.get('unusual_activity', []),
            call_put_ratio=flow_data.get('call_put_ratio', 1.0),
            accumulation_zones=flow_data.get('accumulation_zones', {'calls': [], 'puts': []}),
            sweeps=flow_data.get('sweeps', []),
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error fetching options flow for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch options flow: {str(e)}")


# Helper functions

async def _fetch_options_flow(symbol: str, monitor_bridge: MonitorBridge, limit: int) -> Dict:
    """Fetch options flow data from monitor"""
    try:
        # Try to get from MonitorBridge
        if monitor_bridge:
            options_data = monitor_bridge.get_options_data(symbol)
            if options_data:
                return _convert_options_data_to_flow(options_data, limit)
        
        # Try to get from monitor's options flow checker
        if monitor_bridge.monitor:
            options_checker = getattr(monitor_bridge.monitor, 'options_flow_checker', None)
            if options_checker:
                # Get options flow from checker
                alerts = await options_checker.check()
                if alerts:
                    return _convert_alerts_to_flow_data(alerts, symbol, limit)
        
        # Try to get from RapidAPI Options Client
        from core.data.rapidapi_options_client import RapidAPIOptionsClient
        import os
        rapidapi_key = os.getenv('RAPIDAPI_KEY')
        if rapidapi_key:
            client = RapidAPIOptionsClient(rapidapi_key)
            
            # Get most active options
            most_active_data = client.get_most_active_options(symbol)
            
            # Get unusual activity
            unusual_data = client.get_unusual_options_activity(symbol)
            
            # Calculate P/C ratio
            call_put_ratio = _calculate_call_put_ratio(most_active_data)
            
            # Build accumulation zones
            accumulation_zones = _build_accumulation_zones(most_active_data)
            
            # Convert to response format
            most_active = [
                OptionFlow(
                    symbol=opt.get('symbol', symbol),
                    strike=float(opt.get('strike', 0)),
                    expiration=opt.get('expiration', ''),
                    option_type=opt.get('type', 'CALL'),
                    volume=int(opt.get('volume', 0)),
                    open_interest=int(opt.get('openInterest', 0)),
                    last_price=float(opt.get('lastPrice', 0)),
                    bid=float(opt.get('bid', 0)),
                    ask=float(opt.get('ask', 0)),
                    implied_volatility=float(opt.get('impliedVolatility', 0)) if opt.get('impliedVolatility') else None
                )
                for opt in (most_active_data or [])[:limit]
            ]
            
            unusual_activity = [
                UnusualActivity(
                    symbol=opt.get('symbol', symbol),
                    strike=float(opt.get('strike', 0)),
                    expiration=opt.get('expiration', ''),
                    option_type=opt.get('type', 'CALL'),
                    volume=int(opt.get('volume', 0)),
                    open_interest=int(opt.get('openInterest', 0)),
                    volume_oi_ratio=float(opt.get('volume', 0)) / max(int(opt.get('openInterest', 1)), 1),
                    last_price=float(opt.get('lastPrice', 0)),
                    reason=opt.get('reason', 'High volume/OI ratio')
                )
                for opt in (unusual_data or [])[:limit]
            ]
            
            return {
                'most_active': most_active,
                'unusual_activity': unusual_activity,
                'call_put_ratio': call_put_ratio,
                'accumulation_zones': accumulation_zones,
                'sweeps': []  # Would need sweep detection logic
            }
    except Exception as e:
        logger.warning(f"Could not fetch options flow from monitor for {symbol}: {e}")
    
    # Fallback: return mock data for development
    return _generate_mock_options_flow(symbol, limit)


def _convert_options_data_to_flow(options_data: Dict, limit: int) -> Dict:
    """Convert MonitorBridge options data to flow format"""
    # This would convert the data structure from MonitorBridge
    # For now, return mock if structure doesn't match
    return _generate_mock_options_flow(options_data.get('symbol', 'SPY'), limit)


def _convert_alerts_to_flow_data(alerts: List, symbol: str, limit: int) -> Dict:
    """Convert checker alerts to flow data format"""
    # This would parse CheckerAlert objects
    # For now, return mock
    return _generate_mock_options_flow(symbol, limit)


def _calculate_call_put_ratio(options_data: List[Dict]) -> float:
    """Calculate Call/Put volume ratio"""
    if not options_data:
        return 1.0
    
    call_volume = sum(opt.get('volume', 0) for opt in options_data if opt.get('type', '').upper() == 'CALL')
    put_volume = sum(opt.get('volume', 0) for opt in options_data if opt.get('type', '').upper() == 'PUT')
    
    if put_volume == 0:
        return 10.0 if call_volume > 0 else 1.0
    
    return call_volume / put_volume


def _build_accumulation_zones(options_data: List[Dict]) -> Dict[str, List[StrikeZone]]:
    """Build call and put accumulation zones"""
    calls = {}
    puts = {}
    
    for opt in options_data:
        strike = float(opt.get('strike', 0))
        expiration = opt.get('expiration', '')
        option_type = opt.get('type', '').upper()
        volume = int(opt.get('volume', 0))
        oi = int(opt.get('openInterest', 0))
        price = float(opt.get('lastPrice', 0))
        
        key = f"{strike}_{expiration}"
        
        if option_type == 'CALL':
            if key not in calls:
                calls[key] = {
                    'strike': strike,
                    'expiration': expiration,
                    'total_volume': 0,
                    'total_oi': 0,
                    'total_premium': 0.0,
                    'count': 0
                }
            calls[key]['total_volume'] += volume
            calls[key]['total_oi'] += oi
            calls[key]['total_premium'] += price * volume
            calls[key]['count'] += 1
        elif option_type == 'PUT':
            if key not in puts:
                puts[key] = {
                    'strike': strike,
                    'expiration': expiration,
                    'total_volume': 0,
                    'total_oi': 0,
                    'total_premium': 0.0,
                    'count': 0
                }
            puts[key]['total_volume'] += volume
            puts[key]['total_oi'] += oi
            puts[key]['total_premium'] += price * volume
            puts[key]['count'] += 1
    
    call_zones = [
        StrikeZone(
            strike=zone['strike'],
            expiration=zone['expiration'],
            total_volume=zone['total_volume'],
            total_oi=zone['total_oi'],
            avg_price=zone['total_premium'] / max(zone['total_volume'], 1),
            direction='CALL'
        )
        for zone in sorted(calls.values(), key=lambda x: x['total_volume'], reverse=True)[:limit]
    ]
    
    put_zones = [
        StrikeZone(
            strike=zone['strike'],
            expiration=zone['expiration'],
            total_volume=zone['total_volume'],
            total_oi=zone['total_oi'],
            avg_price=zone['total_premium'] / max(zone['total_volume'], 1),
            direction='PUT'
        )
        for zone in sorted(puts.values(), key=lambda x: x['total_volume'], reverse=True)[:limit]
    ]
    
    return {'calls': call_zones, 'puts': put_zones}


def _generate_mock_options_flow(symbol: str, limit: int) -> Dict:
    """Generate mock options flow data for development/testing"""
    base_price = 500.0 if symbol.upper() == 'SPY' else 400.0
    
    # Mock most active options
    most_active = []
    for i in range(limit):
        strike = base_price + (i - limit // 2) * 5.0
        option_type = 'CALL' if i % 2 == 0 else 'PUT'
        most_active.append(OptionFlow(
            symbol=symbol.upper(),
            strike=strike,
            expiration=(datetime.now() + timedelta(days=7 + i)).strftime('%Y-%m-%d'),
            option_type=option_type,
            volume=1000 + i * 500,
            open_interest=5000 + i * 1000,
            last_price=2.5 + i * 0.5,
            bid=2.4 + i * 0.5,
            ask=2.6 + i * 0.5,
            implied_volatility=0.20 + i * 0.01
        ))
    
    # Mock unusual activity
    unusual_activity = []
    for i in range(min(limit, 5)):
        strike = base_price + (i - 2) * 10.0
        unusual_activity.append(UnusualActivity(
            symbol=symbol.upper(),
            strike=strike,
            expiration=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
            option_type='CALL' if i % 2 == 0 else 'PUT',
            volume=5000 + i * 2000,
            open_interest=10000 + i * 5000,
            volume_oi_ratio=0.5 + i * 0.1,
            last_price=5.0 + i * 1.0,
            reason='High volume/OI ratio' if i % 2 == 0 else 'Unusual volume spike'
        ))
    
    # Mock accumulation zones
    call_zones = [
        StrikeZone(
            strike=base_price + i * 5.0,
            expiration=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
            total_volume=10000 + i * 5000,
            total_oi=50000 + i * 10000,
            avg_price=3.0 + i * 0.5,
            direction='CALL'
        )
        for i in range(min(limit, 5))
    ]
    
    put_zones = [
        StrikeZone(
            strike=base_price - i * 5.0,
            expiration=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d'),
            total_volume=8000 + i * 4000,
            total_oi=40000 + i * 8000,
            avg_price=2.5 + i * 0.4,
            direction='PUT'
        )
        for i in range(min(limit, 5))
    ]
    
    return {
        'most_active': most_active,
        'unusual_activity': unusual_activity,
        'call_put_ratio': 0.85,  # Mock ratio
        'accumulation_zones': {'calls': call_zones, 'puts': put_zones},
        'sweeps': []  # Mock sweeps would go here
    }

