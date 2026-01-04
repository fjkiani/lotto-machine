"""
Gamma Tracker API Endpoints

Provides gamma exposure data, gamma flip levels, max pain, and P/C ratios.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from backend.app.core.dependencies import get_monitor_bridge
from backend.app.integrations.unified_monitor_bridge import MonitorBridge

logger = logging.getLogger(__name__)

router = APIRouter()


class GammaByStrike(BaseModel):
    """Gamma exposure by strike"""
    strike: float
    gamma_exposure: float
    call_oi: int
    put_oi: int


class GammaResponse(BaseModel):
    """Gamma exposure response"""
    symbol: str
    gamma_flip_level: Optional[float] = None
    current_regime: str = Field(..., description="POSITIVE or NEGATIVE")
    total_gex: float = Field(..., description="Total gamma exposure")
    max_pain: Optional[float] = None
    call_put_ratio: float = Field(..., description="Call/Put OI ratio")
    gamma_by_strike: Dict[str, float] = Field(default_factory=dict)
    current_price: float
    distance_to_flip: Optional[float] = None
    timestamp: datetime


@router.get("/gamma/{symbol}", response_model=GammaResponse)
async def get_gamma_data(
    symbol: str,
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Get gamma exposure data for a symbol.
    
    Returns gamma flip level, regime, max pain, P/C ratio, and gamma by strike.
    """
    try:
        # Get current price
        current_price = await _get_current_price(symbol, monitor_bridge)
        
        # Get gamma data from monitor
        gamma_data = await _fetch_gamma_data(symbol, monitor_bridge, current_price)
        
        # Calculate distance to gamma flip
        distance_to_flip = None
        if gamma_data.get('gamma_flip_level') and current_price:
            distance_to_flip = abs(gamma_data['gamma_flip_level'] - current_price)
        
        return GammaResponse(
            symbol=symbol.upper(),
            gamma_flip_level=gamma_data.get('gamma_flip_level'),
            current_regime=gamma_data.get('current_regime', 'POSITIVE'),
            total_gex=gamma_data.get('total_gex', 0.0),
            max_pain=gamma_data.get('max_pain'),
            call_put_ratio=gamma_data.get('call_put_ratio', 1.0),
            gamma_by_strike=gamma_data.get('gamma_by_strike', {}),
            current_price=current_price or 0.0,
            distance_to_flip=distance_to_flip,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error fetching gamma data for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch gamma data: {str(e)}")


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
    
    # Fallback: use yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='1d', interval='1m')
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
    except Exception as e:
        logger.warning(f"Could not fetch current price from yfinance for {symbol}: {e}")
    
    return None


async def _fetch_gamma_data(symbol: str, monitor_bridge: MonitorBridge, current_price: Optional[float]) -> Dict:
    """Fetch gamma data from monitor"""
    try:
        # Try to get from MonitorBridge
        if monitor_bridge:
            gamma_data = monitor_bridge.get_gamma_data(symbol)
            if gamma_data:
                return gamma_data
        
        # Try to get from monitor's gamma checker
        if monitor_bridge.monitor:
            gamma_checker = getattr(monitor_bridge.monitor, 'gamma_checker', None)
            if gamma_checker:
                # Get gamma data from checker
                context = await gamma_checker.check(symbol)
                if context:
                    return {
                        'gamma_flip_level': getattr(context, 'gamma_flip_level', None),
                        'current_regime': getattr(context, 'current_regime', 'POSITIVE'),
                        'total_gex': getattr(context, 'total_gex', 0.0),
                        'max_pain': getattr(context, 'max_pain', None),
                        'call_put_ratio': getattr(context, 'call_put_ratio', 1.0),
                        'gamma_by_strike': getattr(context, 'gamma_by_strike', {})
                    }
            
            # Try to get from gamma exposure module
            if hasattr(monitor_bridge.monitor, 'gamma_exposure_tracker'):
                tracker = monitor_bridge.monitor.gamma_exposure_tracker
                if tracker:
                    from datetime import datetime, timedelta
                    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    gamma_data = tracker.calculate_gamma_exposure(symbol, yesterday)
                    if gamma_data:
                        return {
                            'gamma_flip_level': gamma_data.get('gamma_flip_level'),
                            'current_regime': gamma_data.get('current_regime', 'POSITIVE'),
                            'total_gex': gamma_data.get('total_gex', 0.0),
                            'max_pain': None,  # Will be calculated separately
                            'call_put_ratio': 1.0,  # Will be calculated separately
                            'gamma_by_strike': gamma_data.get('gamma_by_strike', {})
                        }
        
        # Try to get from institutional engine
        from core.ultra_institutional_engine import UltraInstitutionalEngine
        import os
        api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
        if api_key:
            inst_engine = UltraInstitutionalEngine(api_key=api_key)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            context = inst_engine.build_institutional_context(symbol, yesterday)
            if context:
                # Extract gamma-related data from context
                max_pain = getattr(context, 'max_pain', None)
                put_call_ratio = getattr(context, 'put_call_ratio', 1.0)
                call_put_ratio = 1.0 / put_call_ratio if put_call_ratio > 0 else 1.0
                
                # Estimate gamma flip (simplified - would need options chain for accurate calculation)
                gamma_flip_level = None
                if current_price and max_pain:
                    # Simple estimate: gamma flip often near max pain
                    gamma_flip_level = max_pain
                
                return {
                    'gamma_flip_level': gamma_flip_level,
                    'current_regime': 'POSITIVE' if (current_price and gamma_flip_level and current_price > gamma_flip_level) else 'NEGATIVE',
                    'total_gex': 0.0,  # Would need options chain to calculate
                    'max_pain': max_pain,
                    'call_put_ratio': call_put_ratio,
                    'gamma_by_strike': {}
                }
    except Exception as e:
        logger.warning(f"Could not fetch gamma data from monitor for {symbol}: {e}")
    
    # Fallback: return mock data for development
    return _generate_mock_gamma_data(symbol, current_price)


def _generate_mock_gamma_data(symbol: str, current_price: Optional[float]) -> Dict:
    """Generate mock gamma data for development/testing"""
    base_price = current_price or (500.0 if symbol.upper() == 'SPY' else 400.0)
    
    # Mock gamma flip level (typically near current price)
    gamma_flip = base_price * 1.01  # 1% above current price
    
    # Mock regime (positive if price above flip, negative if below)
    regime = 'POSITIVE' if current_price and current_price > gamma_flip else 'NEGATIVE'
    
    # Mock max pain (typically near current price)
    max_pain = base_price * 0.99  # 1% below current price
    
    # Mock P/C ratio (typical range 0.7-1.3)
    call_put_ratio = 0.85
    
    # Mock gamma by strike (simplified)
    gamma_by_strike = {}
    for i in range(-5, 6):
        strike = base_price + (i * 5.0)
        gamma_by_strike[str(strike)] = 1000000.0 * (1.0 - abs(i) * 0.1)
    
    return {
        'gamma_flip_level': gamma_flip,
        'current_regime': regime,
        'total_gex': 50000000.0,  # Mock total GEX
        'max_pain': max_pain,
        'call_put_ratio': call_put_ratio,
        'gamma_by_strike': gamma_by_strike
    }

