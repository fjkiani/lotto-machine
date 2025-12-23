"""
🏰 MOAT CHART API ENDPOINTS

Generate 12-layer intelligence charts using the MOAT Chart Engine.
"""

import os
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
import yfinance as yf

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

router = APIRouter()

# Try to import MOAT Chart Engine
try:
    from src.streamlit_app.moat_chart_engine import MOATChartEngine
    MOAT_ENGINE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"MOAT Chart Engine not available: {e}")
    MOAT_ENGINE_AVAILABLE = False
    MOATChartEngine = None


@router.get("/charts/moat/{symbol}")
async def get_moat_chart(
    symbol: str,
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    timeframe: str = Query("1d", description="Timeframe: 1d, 5d, 1mo"),
    interval: str = Query("1m", description="Interval: 1m, 5m, 15m, 1h, 1d")
):
    """Generate MOAT chart with all 12 intelligence layers."""
    if not MOAT_ENGINE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="MOAT Chart Engine not available. Check backend logs for import errors."
        )
    
    try:
        api_key = os.getenv('CHARTEXCHANGE_API_KEY')
        if not api_key:
            logger.warning("CHARTEXCHANGE_API_KEY not set - chart will have limited functionality")
        
        engine = MOATChartEngine(api_key=api_key)
        
        # Get candlestick data
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=timeframe, interval=interval)
        
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No price data available for {symbol}"
            )
        
        # Ensure proper column names
        df.columns = [col.lower() for col in df.columns]
        current_price = float(df['close'].iloc[-1])
        date = date or datetime.now().strftime('%Y-%m-%d')
        
        # Gather intelligence
        logger.info(f"Gathering intelligence for {symbol} on {date}")
        intelligence = engine.gather_all_intelligence(
            ticker=symbol,
            date=date,
            current_price=current_price,
        )
        
        # Create MOAT chart
        logger.info(f"Creating MOAT chart for {symbol}")
        fig = engine.create_moat_chart(
            ticker=symbol,
            candlestick_data=df,
            intelligence=intelligence,
        )
        
        chart_json = fig.to_json()
        
        return {
            "symbol": symbol,
            "date": date,
            "chart": chart_json,
            "intelligence": {
                "dp_levels_count": len(intelligence.dp_levels),
                "gamma_flip_level": intelligence.gamma_flip_level,
                "max_pain": intelligence.max_pain,
                "regime": intelligence.regime,
                "reddit_sentiment": intelligence.reddit_sentiment,
                "signals_count": len(intelligence.signals),
            },
            "current_price": current_price,
            "timestamp": datetime.utcnow().isoformat(),
            "layers": {
                "price_action": True,
                "dark_pool": len(intelligence.dp_levels) > 0,
                "gamma": intelligence.gamma_flip_level is not None,
                "squeeze": len(intelligence.squeeze_zones) > 0,
                "signals": len(intelligence.signals) > 0,
                "institutional_context": intelligence.buying_pressure is not None,
                "regime": intelligence.regime is not None,
                "volume_profile": intelligence.volume_profile_data is not None,
                "reddit_sentiment": intelligence.reddit_sentiment != 'NEUTRAL',
                "options_flow": len(intelligence.options_flow_zones) > 0,
                "news_events": len(intelligence.upcoming_events) > 0,
                "historical_learning": len(intelligence.dp_bounce_rates) > 0,
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating MOAT chart for {symbol}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating chart: {str(e)}"
        )
