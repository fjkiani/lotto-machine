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


# High-SI watchlist — curated, covers classic and current squeeze setups
_SQUEEZE_WATCHLIST = [
    'GME', 'AMC', 'BB', 'NOK',
    'LCID', 'RIVN', 'NIO', 'WKHS', 'PLUG', 'FCEL',
    'MARA', 'RIOT', 'HUT', 'BITF', 'COIN', 'MSTR',
    'SAVA', 'PLTR', 'SOFI', 'UPST', 'AFRM', 'CVNA', 'BYND', 'SPCE',
]


def _score_squeeze_yfinance(symbol: str) -> Optional[SqueezeCandidateResponse]:
    """
    Score a squeeze candidate using yfinance (no paid API).
    Scoring (0-100): SI 40pts + borrow-proxy 30pts + volume 20pts + momentum 10pts
    """
    import yfinance as yf
    try:
        t = yf.Ticker(symbol)
        info = t.info
        si_pct = float(info.get('shortPercentOfFloat') or 0) * 100
        short_ratio = float(info.get('shortRatio') or 0)
        current_price = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
        if current_price <= 0 or si_pct <= 0:
            return None

        si_score = min((si_pct / 30) * 40, 40)
        borrow_fee_score = min(short_ratio * 2, 30)

        hist = t.history(period='5d')
        if hist.empty:
            return None
        cur = float(hist['Close'].iloc[-1])
        ago = float(hist['Close'].iloc[0])
        price_change_5d = ((cur - ago) / ago) * 100 if ago > 0 else 0.0
        vol_cur = float(hist['Volume'].iloc[-1])
        vol_avg = float(hist['Volume'].mean())
        volume_ratio = vol_cur / vol_avg if vol_avg > 0 else 1.0
        volume_score = min((volume_ratio - 1.0) * 10, 20) if volume_ratio > 1.0 else 0.0
        momentum_score = min(max(price_change_5d, 0) * 0.5, 10)
        total_score = si_score + borrow_fee_score + volume_score + momentum_score

        atr_proxy = (float(hist['High'].max()) - float(hist['Low'].min())) / 5
        entry = cur
        stop = round(entry - atr_proxy, 2)
        target = round(entry + atr_proxy * 3, 2)
        rr = 3.0 if atr_proxy > 0 else 0.0

        reasoning, warnings = [], []
        if si_pct >= 20:
            reasoning.append(f'High short interest: {si_pct:.1f}% of float')
        if short_ratio >= 5:
            reasoning.append(f'Hard-to-borrow proxy: {short_ratio:.1f}d to cover')
        if volume_ratio >= 1.5:
            reasoning.append(f'Volume surge: {volume_ratio:.1f}x average')
        if price_change_5d > 5:
            reasoning.append(f'5D momentum: +{price_change_5d:.1f}% — shorts under pressure')
        if si_pct < 15:
            warnings.append('SI% below 15% — weaker squeeze setup')
        if short_ratio < 3:
            warnings.append('Low days-to-cover — borrow not constrained')

        return SqueezeCandidateResponse(
            symbol=symbol,
            score=round(total_score, 1),
            si_score=round(si_score, 1),
            borrow_fee_score=round(borrow_fee_score, 1),
            ftd_score=0.0,
            dp_support_score=0.0,
            short_interest_pct=round(si_pct, 2),
            borrow_fee_pct=round(short_ratio * 2, 2),
            ftd_spike_ratio=1.0,
            dp_buying_pressure=0.0,
            entry_price=round(entry, 2),
            stop_price=stop,
            target_price=target,
            risk_reward_ratio=round(rr, 2),
            reasoning=reasoning,
            warnings=warnings,
            nearest_dp_support=None,
            nearest_dp_resistance=None,
            days_to_cover=round(short_ratio, 1) if short_ratio > 0 else None,
            volume_ratio=round(volume_ratio, 2),
            price_change_5d=round(price_change_5d, 2),
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.debug(f'Error scoring {symbol}: {e}')
        return None


@router.get('/squeeze/scan', response_model=SqueezeScanResponse)
async def scan_squeeze_candidates(
    min_score: float = Query(40.0, description='Minimum squeeze score (0-100)'),
    max_results: int = Query(20, le=50, description='Maximum number of results'),
):
    """
    Scan for short squeeze candidates using yfinance (no paid API required).
    Scores the curated watchlist on SI%, days-to-cover, volume surge, and 5D momentum.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    logger.info(f'🔥 Scanning {len(_SQUEEZE_WATCHLIST)} watchlist stocks (min_score={min_score})...')
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = await asyncio.gather(
            *[loop.run_in_executor(ex, _score_squeeze_yfinance, sym) for sym in _SQUEEZE_WATCHLIST],
            return_exceptions=True
        )
    candidates = [r for r in results if isinstance(r, SqueezeCandidateResponse) and r.score >= min_score]
    candidates.sort(key=lambda x: x.score, reverse=True)
    candidates = candidates[:max_results]
    logger.info(f'✅ Found {len(candidates)} squeeze candidates')
    return SqueezeScanResponse(candidates=candidates, count=len(candidates), timestamp=datetime.utcnow().isoformat())


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

