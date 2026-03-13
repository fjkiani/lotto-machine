"""
🐺 AXLFI Intelligence Router
Exposes ALL StockgridClient methods as API endpoints.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/axlfi", tags=["axlfi"])

# Lazy singleton
_client = None

def _get_client():
    global _client
    if _client is None:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        _client = StockgridClient(cache_ttl=300)
    return _client


# ── Dashboard Master Feed ────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard():
    """588KB master feed: index_returns, movers, signal_symbols, spy_history, strategy_metrics, tactical_allocation."""
    try:
        data = _get_client().get_dashboard()
        if not data:
            raise HTTPException(503, "AXLFI dashboard unavailable")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(500, str(e))


@router.get("/signals")
async def get_signals():
    """Active AXLFI signal symbols — bullish/bearish dark pool accumulation alerts."""
    try:
        signals = _get_client().get_signal_symbols()
        return {"signals": signals, "count": len(signals), "as_of": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Signals error: {e}")
        raise HTTPException(500, str(e))


@router.get("/regime")
async def get_regime():
    """Market regime / VIX climax tier (Tier 1-4)."""
    try:
        regime = _get_client().get_volatility_regime()
        return {"regime": regime, "as_of": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Regime error: {e}")
        raise HTTPException(500, str(e))


@router.get("/movers")
async def get_movers():
    """Today's market movers: sector leaders, price gainers/losers, volume spikes."""
    try:
        data = _get_client().get_movers()
        if not data:
            raise HTTPException(503, "AXLFI movers unavailable")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Movers error: {e}")
        raise HTTPException(500, str(e))


# ── Option Walls ─────────────────────────────────────────────────────────

@router.get("/option-walls/{symbol}")
async def get_option_walls(symbol: str):
    """Full option wall data for SPY/QQQ/IWM — includes strike-level OI and wall evolution."""
    symbol = symbol.upper()
    if symbol not in ("SPY", "QQQ", "IWM"):
        raise HTTPException(400, "Only SPY, QQQ, IWM supported")
    try:
        data = _get_client().get_option_walls(symbol)
        if not data:
            raise HTTPException(503, f"Option walls unavailable for {symbol}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Option walls error: {e}")
        raise HTTPException(500, str(e))


@router.get("/option-walls/{symbol}/today")
async def get_option_walls_today(symbol: str):
    """Today's call wall, put wall, and POC for a symbol."""
    symbol = symbol.upper()
    if symbol not in ("SPY", "QQQ", "IWM"):
        raise HTTPException(400, "Only SPY, QQQ, IWM supported")
    try:
        wall = _get_client().get_option_walls_today(symbol)
        if not wall:
            raise HTTPException(503, f"Today's walls unavailable for {symbol}")
        return {
            "symbol": symbol,
            "date": wall.date,
            "call_wall": wall.call_wall,
            "call_wall_2": wall.call_wall_2,
            "call_wall_3": wall.call_wall_3,
            "put_wall": wall.put_wall,
            "put_wall_2": wall.put_wall_2,
            "put_wall_3": wall.put_wall_3,
            "poc": wall.poc,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Option walls today error: {e}")
        raise HTTPException(500, str(e))


# ── Market Snapshot ──────────────────────────────────────────────────────

@router.get("/snapshot")
async def get_snapshot():
    """Quick SPY/QQQ/IWM prices without yfinance latency."""
    try:
        data = _get_client().get_market_snapshot()
        if not data:
            raise HTTPException(503, "Market snapshot unavailable")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        raise HTTPException(500, str(e))


# ── Clusters ─────────────────────────────────────────────────────────────

@router.get("/clusters")
async def get_clusters(universe: str = Query("sp500", enum=["sp500", "nasdaq100", "all"])):
    """Stock cluster universe with 1d/2d/5d/10d/20d forward returns."""
    try:
        data = _get_client().get_clusters()
        if not data:
            raise HTTPException(503, "Cluster data unavailable")
        subset = data.get(universe, {})
        items = subset.get("data", []) if isinstance(subset, dict) else subset
        return {
            "universe": universe,
            "count": len(items),
            "data": items,
            "as_of": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clusters error: {e}")
        raise HTTPException(500, str(e))


# ── Symbol Info ──────────────────────────────────────────────────────────

@router.get("/info/{symbol}")
async def get_info(symbol: str):
    """Ticker metadata: price, 52W range, sector, industry, volatility."""
    try:
        data = _get_client().get_symbol_info(symbol.upper())
        if not data:
            raise HTTPException(503, f"Symbol info unavailable for {symbol}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Symbol info error: {e}")
        raise HTTPException(500, str(e))


# ── Ticker Detail ────────────────────────────────────────────────────────

@router.get("/detail/{symbol}")
async def get_detail(symbol: str, window: int = Query(30, ge=5, le=252)):
    """Full dark pool + short volume history for a ticker."""
    try:
        data = _get_client().get_ticker_detail_raw(symbol.upper(), window=window)
        if not data:
            raise HTTPException(503, f"Detail unavailable for {symbol}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detail error: {e}")
        raise HTTPException(500, str(e))


# ── Earnings Kill Chain ──────────────────────────────────────────────────

@router.get("/earnings-intel")
async def get_earnings_intel(tickers: str = Query(..., description="Comma-separated tickers")):
    """Combined DP + option walls + signals intelligence for earnings targets."""
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if not ticker_list:
            raise HTTPException(400, "No tickers provided")
        if len(ticker_list) > 10:
            raise HTTPException(400, "Max 10 tickers per request")
        data = _get_client().get_earnings_intel(ticker_list)
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Earnings intel error: {e}")
        raise HTTPException(500, str(e))
