"""
🔥 SQUEEZE SCANNER API ENDPOINTS

Fetch short squeeze candidates from the monitor.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from backend.app.core.dependencies import get_monitor_bridge
from backend.app.integrations.unified_monitor_bridge import MonitorBridge

logger = logging.getLogger(__name__)

router = APIRouter()


class SqueezeCandidateResponse(BaseModel):
    """Squeeze candidate response model"""
    symbol: str
    score: float = Field(..., description="Squeeze score (0-100)")
    
    # Component scores
    si_score: float
    borrow_fee_score: float
    ftd_score: float
    dp_support_score: float
    
    # Raw data
    short_interest_pct: float = Field(..., description="Short interest percentage")
    borrow_fee_pct: float = Field(..., description="Borrow fee percentage")
    ftd_spike_ratio: float = Field(..., description="FTD spike ratio")
    dp_buying_pressure: float = Field(..., description="DP buying pressure %")
    
    # Trade setup
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward_ratio: float
    
    # Context
    reasoning: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # DP context
    nearest_dp_support: Optional[float] = None
    nearest_dp_resistance: Optional[float] = None
    
    # Additional metrics
    days_to_cover: Optional[float] = None
    volume_ratio: Optional[float] = None
    price_change_5d: Optional[float] = None
    
    timestamp: str


class SqueezeScanResponse(BaseModel):
    """Squeeze scan response"""
    candidates: List[SqueezeCandidateResponse]
    count: int
    timestamp: str


@router.get("/squeeze/scan", response_model=SqueezeScanResponse)
async def scan_squeeze_candidates(
    min_score: float = Query(55.0, description="Minimum squeeze score (0-100)"),
    max_results: int = Query(20, le=50, description="Maximum number of results"),
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Scan for short squeeze candidates.
    
    Uses the OpportunityScanner to dynamically discover high short interest stocks
    and analyzes them for squeeze potential.
    """
    try:
        if not monitor_bridge or not monitor_bridge.monitor:
            logger.warning("Monitor not available - returning empty scan")
            return SqueezeScanResponse(
                candidates=[],
                count=0,
                timestamp=datetime.utcnow().isoformat()
            )
        
        monitor = monitor_bridge.monitor
        
        # Check if squeeze detector and opportunity scanner are available
        if not hasattr(monitor, 'squeeze_detector') or not monitor.squeeze_detector:
            logger.warning("SqueezeDetector not available - returning empty scan")
            return SqueezeScanResponse(
                candidates=[],
                count=0,
                timestamp=datetime.utcnow().isoformat()
            )
        
        if not hasattr(monitor, 'opportunity_scanner') or not monitor.opportunity_scanner:
            logger.warning("OpportunityScanner not available - returning empty scan")
            return SqueezeScanResponse(
                candidates=[],
                count=0,
                timestamp=datetime.utcnow().isoformat()
            )
        
        # Run the squeeze scan
        logger.info(f"🔥 Scanning for squeeze candidates (min_score={min_score})...")
        
        squeeze_opportunities = monitor.opportunity_scanner.scan_for_squeeze_candidates(
            monitor.squeeze_detector,
            min_score=min_score
        )
        
        # Convert to response format
        candidates = []
        for opp in squeeze_opportunities[:max_results]:
            # Get full squeeze signal for detailed data
            squeeze_signal = monitor.squeeze_detector.analyze(opp.symbol)
            
            if not squeeze_signal:
                continue
            
            # Get additional metrics (price change, volume ratio)
            try:
                import yfinance as yf
                ticker = yf.Ticker(opp.symbol)
                hist = ticker.history(period="5d")
                
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
                    price_5d_ago = float(hist['Close'].iloc[0])
                    price_change_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
                    
                    # Volume ratio (current vs average)
                    current_volume = float(hist['Volume'].iloc[-1])
                    avg_volume = float(hist['Volume'].mean())
                    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
                else:
                    price_change_5d = None
                    volume_ratio = None
            except Exception as e:
                logger.debug(f"Error fetching additional metrics for {opp.symbol}: {e}")
                price_change_5d = None
                volume_ratio = None
            
            # Get days to cover (if available)
            try:
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                api_key = monitor.dp_client.api_key if hasattr(monitor, 'dp_client') and monitor.dp_client else None
                if api_key:
                    client = UltimateChartExchangeClient(api_key, tier=3)
                    short_data = client.get_short_interest(opp.symbol)
                    if short_data and 'days_to_cover' in short_data:
                        days_to_cover = float(short_data['days_to_cover'])
                    else:
                        days_to_cover = None
                else:
                    days_to_cover = None
            except Exception as e:
                logger.debug(f"Error fetching days to cover for {opp.symbol}: {e}")
                days_to_cover = None
            
            candidates.append(SqueezeCandidateResponse(
                symbol=opp.symbol,
                score=squeeze_signal.score,
                si_score=squeeze_signal.si_score,
                borrow_fee_score=squeeze_signal.borrow_fee_score,
                ftd_score=squeeze_signal.ftd_score,
                dp_support_score=squeeze_signal.dp_support_score,
                short_interest_pct=squeeze_signal.short_interest_pct,
                borrow_fee_pct=squeeze_signal.borrow_fee_pct,
                ftd_spike_ratio=squeeze_signal.ftd_spike_ratio,
                dp_buying_pressure=squeeze_signal.dp_buying_pressure,
                entry_price=squeeze_signal.entry_price,
                stop_price=squeeze_signal.stop_price,
                target_price=squeeze_signal.target_price,
                risk_reward_ratio=squeeze_signal.risk_reward_ratio,
                reasoning=squeeze_signal.reasoning,
                warnings=squeeze_signal.warnings,
                nearest_dp_support=squeeze_signal.nearest_dp_support,
                nearest_dp_resistance=squeeze_signal.nearest_dp_resistance,
                days_to_cover=days_to_cover,
                volume_ratio=volume_ratio,
                price_change_5d=price_change_5d,
                timestamp=squeeze_signal.timestamp.isoformat() if squeeze_signal.timestamp else datetime.utcnow().isoformat()
            ))
        
        # Sort by score (highest first)
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        logger.info(f"✅ Found {len(candidates)} squeeze candidates")
        
        return SqueezeScanResponse(
            candidates=candidates,
            count=len(candidates),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"❌ Error scanning squeeze candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error scanning squeeze candidates: {str(e)}")


@router.get("/squeeze/{symbol}", response_model=SqueezeCandidateResponse)
async def get_squeeze_analysis(
    symbol: str,
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge)
):
    """
    Get detailed squeeze analysis for a specific symbol.
    """
    try:
        if not monitor_bridge or not monitor_bridge.monitor:
            raise HTTPException(status_code=503, detail="Monitor not available")
        
        monitor = monitor_bridge.monitor
        
        if not hasattr(monitor, 'squeeze_detector') or not monitor.squeeze_detector:
            raise HTTPException(status_code=503, detail="SqueezeDetector not available")
        
        # Analyze the symbol
        squeeze_signal = monitor.squeeze_detector.analyze(symbol.upper())
        
        if not squeeze_signal:
            raise HTTPException(status_code=404, detail=f"No squeeze signal found for {symbol}")
        
        # Get additional metrics
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol.upper())
            hist = ticker.history(period="5d")
            
            if not hist.empty:
                current_price = float(hist['Close'].iloc[-1])
                price_5d_ago = float(hist['Close'].iloc[0])
                price_change_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
                
                current_volume = float(hist['Volume'].iloc[-1])
                avg_volume = float(hist['Volume'].mean())
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            else:
                price_change_5d = None
                volume_ratio = None
        except Exception as e:
            logger.debug(f"Error fetching additional metrics: {e}")
            price_change_5d = None
            volume_ratio = None
        
        # Get days to cover
        try:
            api_key = monitor.dp_client.api_key if hasattr(monitor, 'dp_client') and monitor.dp_client else None
            if api_key:
                from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
                client = UltimateChartExchangeClient(api_key, tier=3)
                short_data = client.get_short_interest(symbol.upper())
                if short_data and 'days_to_cover' in short_data:
                    days_to_cover = float(short_data['days_to_cover'])
                else:
                    days_to_cover = None
            else:
                days_to_cover = None
        except Exception as e:
            logger.debug(f"Error fetching days to cover: {e}")
            days_to_cover = None
        
        return SqueezeCandidateResponse(
            symbol=symbol.upper(),
            score=squeeze_signal.score,
            si_score=squeeze_signal.si_score,
            borrow_fee_score=squeeze_signal.borrow_fee_score,
            ftd_score=squeeze_signal.ftd_score,
            dp_support_score=squeeze_signal.dp_support_score,
            short_interest_pct=squeeze_signal.short_interest_pct,
            borrow_fee_pct=squeeze_signal.borrow_fee_pct,
            ftd_spike_ratio=squeeze_signal.ftd_spike_ratio,
            dp_buying_pressure=squeeze_signal.dp_buying_pressure,
            entry_price=squeeze_signal.entry_price,
            stop_price=squeeze_signal.stop_price,
            target_price=squeeze_signal.target_price,
            risk_reward_ratio=squeeze_signal.risk_reward_ratio,
            reasoning=squeeze_signal.reasoning,
            warnings=squeeze_signal.warnings,
            nearest_dp_support=squeeze_signal.nearest_dp_support,
            nearest_dp_resistance=squeeze_signal.nearest_dp_resistance,
            days_to_cover=days_to_cover,
            volume_ratio=volume_ratio,
            price_change_5d=price_change_5d,
            timestamp=squeeze_signal.timestamp.isoformat() if squeeze_signal.timestamp else datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting squeeze analysis for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing {symbol}: {str(e)}")

