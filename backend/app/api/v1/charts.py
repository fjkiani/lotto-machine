"""
🪤 TRAP MATRIX CHART API

Thin API layer serving the orchestrator's current state.
Does NOT compute — reads the cached state from TrapMatrixOrchestrator.

Endpoints:
  GET /charts/{symbol}/matrix  → Full Trap Matrix state (levels, traps, conviction, staleness)
  GET /charts/{symbol}/ohlc    → yfinance OHLC candle data for chart base layer
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Lazy singleton orchestrator ──────────────────────────────────────────────

_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        try:
            from live_monitoring.enrichment.apis.trap_matrix_orchestrator import TrapMatrixOrchestrator
            _orchestrator = TrapMatrixOrchestrator()
            logger.info("🪤 TrapMatrixOrchestrator initialized")
        except Exception as e:
            logger.error(f"Failed to init TrapMatrixOrchestrator: {e}")
            raise HTTPException(status_code=503, detail=f"Orchestrator unavailable: {e}")
    return _orchestrator


# ── OHLC Cache (prevents yfinance spam on 30s polls) ─────────────────────────

_ohlc_cache: dict[tuple, dict] = {}  # (symbol, period, interval) -> {data, timestamp}

# Intraday periods change fast — shorter TTL
_INTRADAY_PERIODS = {"1d", "5d"}
_INTRADAY_TTL = 30   # 30s — match frontend poll
_DAILY_TTL = 120      # 2min — daily candles barely change mid-session


def _ohlc_cache_ttl(period: str) -> int:
    return _INTRADAY_TTL if period in _INTRADAY_PERIODS else _DAILY_TTL


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/charts/{symbol}/matrix")
async def get_trap_matrix(symbol: str):
    """
    Get the full Trap Matrix state for a symbol.

    Returns unified MarketState with:
    - Current price and timestamp
    - All levels: dark pool, GEX walls, gamma flip, max pain, pivots, MAs
    - Classified traps with conviction scores (1-5)
    - Market context: COT, VIX regime, gamma regime
    - Staleness tracking per data source
    - Rebuild decision from state diffing

    Each data layer uses its own cache TTL — this endpoint never blocks on stale data.
    """
    orch = _get_orchestrator()
    try:
        state = orch.get_current_state(symbol.upper())
        return state.to_dict()
    except Exception as e:
        logger.error(f"Error fetching trap matrix for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Trap matrix error: {str(e)}")


@router.get("/charts/{symbol}/ohlc")
async def get_ohlc(
    symbol: str,
    period: str = Query("3mo", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y"),
    interval: str = Query("1d", description="Interval: 1m, 5m, 15m, 1h, 1d, 1wk"),
):
    """
    Get OHLC candle data for TradingView chart base layer.

    Returns array of candles: [{time, open, high, low, close, volume}, ...]
    Cached per (symbol, period, interval) to prevent yfinance spam on polling.
    """
    cache_key = (symbol.upper(), period, interval)
    now = time.time()
    ttl = _ohlc_cache_ttl(period)

    # Return cached if fresh
    cached = _ohlc_cache.get(cache_key)
    if cached and (now - cached["timestamp"]) < ttl:
        return cached["data"]

    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol.upper())
        df = ticker.history(period=period, interval=interval)

        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

        # Format for lightweight-charts
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "time": int(idx.timestamp()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        result = {
            "symbol": symbol.upper(),
            "period": period,
            "interval": interval,
            "candles": candles,
            "count": len(candles),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Store in cache
        _ohlc_cache[cache_key] = {"data": result, "timestamp": now}

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching OHLC for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OHLC error: {str(e)}")
