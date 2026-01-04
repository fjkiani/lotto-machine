"""
📊 MARKET DATA API ENDPOINTS

Provides market quotes, context, and regime information.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from backtesting.simulation.market_context_detector import MarketContextDetector, MarketContext

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize detector
context_detector = MarketContextDetector()


class MarketContextResponse(BaseModel):
    """Market context response"""
    date: str
    spy_change_pct: float
    qqq_change_pct: float
    vix_level: float
    direction: str
    trend_strength: float
    news_sentiment: str
    key_headlines: List[str]
    regime: str
    favor_longs: bool
    favor_shorts: bool
    reduce_size: bool
    avoid_trading: bool
    reasoning: str
    timestamp: str


@router.get("/market/context")
async def get_market_context(date: Optional[str] = Query(None, description="Date (YYYY-MM-DD), defaults to today")):
    """
    Get current market context and regime.
    
    Returns:
    - Market direction (UP/DOWN/CHOP)
    - Trend strength (0-100)
    - Regime classification
    - Trading recommendations
    - News sentiment
    """
    try:
        context = context_detector.analyze_market(date)
        
        return MarketContextResponse(
            date=context.date,
            spy_change_pct=context.spy_change_pct,
            qqq_change_pct=context.qqq_change_pct,
            vix_level=context.vix_level,
            direction=context.direction,
            trend_strength=context.trend_strength,
            news_sentiment=context.news_sentiment,
            key_headlines=context.key_headlines,
            regime=context.regime,
            favor_longs=context.favor_longs,
            favor_shorts=context.favor_shorts,
            reduce_size=context.reduce_size,
            avoid_trading=context.avoid_trading,
            reasoning=context.reasoning,
            timestamp=datetime.utcnow().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error fetching market context: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching market context: {str(e)}")


@router.get("/market/{symbol}/quote")
async def get_market_quote(symbol: str):
    """
    Get real-time market quote for a symbol.
    """
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='1d', interval='1m')
        
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No data available for {symbol}")
        
        latest = hist.iloc[-1]
        current_price = float(latest['Close'])
        open_price = float(hist['Open'].iloc[0])
        change = current_price - open_price
        change_percent = (change / open_price) * 100
        
        return {
            "symbol": symbol,
            "price": current_price,
            "change": change,
            "change_percent": change_percent,
            "volume": int(latest['Volume']),
            "high": float(hist['High'].max()),
            "low": float(hist['Low'].min()),
            "open": open_price,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching market quote for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching market quote: {str(e)}")

