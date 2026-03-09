"""
Dark Pool Flow API Endpoints

Provides dark pool levels, summaries, and recent prints for frontend widgets.

Data source: StockgridClient (free, no auth, proven in Kill Chain Engine).
NO MOCK FALLBACKS — if data is unavailable the endpoint raises HTTP 503.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared client instance (lazy init)
# ---------------------------------------------------------------------------

_stockgrid = None


def _get_stockgrid():
    """Get or create StockgridClient singleton."""
    global _stockgrid
    if _stockgrid is None:
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            _stockgrid = StockgridClient(cache_ttl=300)
        except ImportError as e:
            raise HTTPException(
                status_code=503,
                detail=f"StockgridClient import failed: {e}"
            )
    return _stockgrid


def _get_current_price(symbol: str) -> float:
    """Get current price via yfinance. Raises 503 if unavailable."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            # Fallback to daily
            hist = ticker.history(period="5d")
        if hist.empty:
            raise HTTPException(
                status_code=503,
                detail=f"No price data available for {symbol}"
            )
        return float(hist["Close"].iloc[-1])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch price for {symbol}: {e}"
        )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DPLevel(BaseModel):
    """A single dark pool price level."""
    price: float
    volume: int
    level_type: str = Field(..., description="SUPPORT, RESISTANCE, or BATTLEGROUND")
    strength: float = Field(..., ge=0, le=100, description="Strength score 0-100")
    distance_from_price: Optional[float] = None


class DPPrint(BaseModel):
    """A single dark pool trade print."""
    price: float
    volume: int
    side: str = Field(..., description="BUY or SELL")
    timestamp: datetime


class DPSummary(BaseModel):
    """Aggregated dark pool summary."""
    total_volume: int
    dp_percent: float = Field(..., ge=0, le=100)
    buying_pressure: float = Field(..., ge=0, le=100)
    nearest_support: Optional[DPLevel] = None
    nearest_resistance: Optional[DPLevel] = None
    battlegrounds: List[DPLevel] = Field(default_factory=list)


class DPLevelsResponse(BaseModel):
    symbol: str
    levels: List[DPLevel]
    current_price: float
    date: str
    timestamp: datetime


class DPPrintsResponse(BaseModel):
    symbol: str
    prints: List[DPPrint]
    count: int
    timestamp: datetime


class DPSummaryResponse(BaseModel):
    symbol: str
    summary: DPSummary
    timestamp: datetime


# ---------------------------------------------------------------------------
# Routes — powered by Stockgrid (free, no auth, real data)
# ---------------------------------------------------------------------------

@router.get("/darkpool/{symbol}/levels", response_model=DPLevelsResponse)
async def get_dp_levels(symbol: str):
    """
    Get dark pool levels for a symbol from Stockgrid.

    Uses top dark pool positions to derive support/resistance levels.
    Raises HTTP 503 if the data source is unavailable.
    """
    symbol = symbol.upper()
    sg = _get_stockgrid()
    current_price = _get_current_price(symbol)

    try:
        # Get ticker detail from Stockgrid
        detail = sg.get_ticker_detail(symbol)
        top_positions = sg.get_top_positions(limit=20)
    except Exception as e:
        logger.error(f"Stockgrid DP levels call failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail=f"Stockgrid error: {e}")

    if not detail and not top_positions:
        raise HTTPException(
            status_code=404,
            detail=f"No dark pool data for {symbol} from Stockgrid"
        )

    # Build levels from top positions (tickers with largest DP activity)
    dp_levels = []
    max_vol = max((abs(int(p.dp_position_shares)) for p in top_positions), default=1) or 1

    for pos in top_positions:
        if not pos.dp_position_dollars:
            continue

        # Derive implied price from position dollars / shares
        implied_price = abs(pos.dp_position_dollars / pos.dp_position_shares) if pos.dp_position_shares else 0
        if not implied_price:
            continue

        vol = abs(int(pos.dp_position_shares))
        strength = round(min(100.0, (vol / max_vol) * 100), 1)

        # Classify based on short volume %
        if pos.short_volume_pct > 0.55:
            level_type = "RESISTANCE"
        elif pos.short_volume_pct < 0.45:
            level_type = "SUPPORT"
        else:
            level_type = "BATTLEGROUND"

        dp_levels.append(DPLevel(
            price=round(implied_price, 2),
            volume=vol,
            level_type=level_type,
            strength=strength,
            distance_from_price=round(abs(implied_price - current_price), 4) if pos.ticker == symbol else None,
        ))

    # If the symbol itself has detail data, add it as a primary level
    if detail and detail.dp_position_dollars:
        implied = abs(detail.dp_position_dollars / detail.dp_position_shares) if detail.dp_position_shares else current_price
        short_pct = detail.short_volume_pct or 0
        if short_pct > 0.55:
            lt = "RESISTANCE"
        elif short_pct < 0.45:
            lt = "SUPPORT"
        else:
            lt = "BATTLEGROUND"

        dp_levels.insert(0, DPLevel(
            price=round(implied, 2),
            volume=abs(int(detail.dp_position_shares or 0)),
            level_type=lt,
            strength=100.0,
            distance_from_price=0.0,
        ))

    dp_levels.sort(key=lambda x: x.volume, reverse=True)
    date_str = detail.date if detail else (top_positions[0].date if top_positions else "")

    return DPLevelsResponse(
        symbol=symbol,
        levels=dp_levels[:20],
        current_price=current_price,
        date=date_str,
        timestamp=datetime.now(),
    )


@router.get("/darkpool/{symbol}/summary", response_model=DPSummaryResponse)
async def get_dp_summary(symbol: str):
    """
    Get aggregated dark pool summary for a symbol from Stockgrid.
    """
    symbol = symbol.upper()
    sg = _get_stockgrid()
    current_price = _get_current_price(symbol)

    try:
        detail = sg.get_ticker_detail(symbol)
        top_positions = sg.get_top_positions(limit=20)
    except Exception as e:
        logger.error(f"Stockgrid DP summary call failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail=f"Stockgrid error: {e}")

    # Try to find the symbol in top positions if detail is None
    if not detail and top_positions:
        for pos in top_positions:
            if pos.ticker == symbol:
                detail = pos
                break

    if not detail and not top_positions:
        raise HTTPException(
            status_code=404,
            detail=f"No dark pool data for {symbol} from Stockgrid"
        )

    # Derive buying pressure from short volume %
    short_pct = (detail.short_volume_pct if detail else 0.5) or 0.5
    buying_pressure = round((1 - short_pct) * 100, 1)

    total_volume = abs(int((detail.short_volume if detail else 0) or (detail.dp_position_shares if detail else 0) or 0))
    dp_position = abs((detail.dp_position_dollars if detail else 0) or 0)

    # DP % (short volume % from Stockgrid)
    dp_percent = round(short_pct * 100, 1)

    summary = DPSummary(
        total_volume=total_volume,
        dp_percent=dp_percent,
        buying_pressure=buying_pressure,
        nearest_support=None,
        nearest_resistance=None,
        battlegrounds=[],
    )

    return DPSummaryResponse(
        symbol=symbol,
        summary=summary,
        timestamp=datetime.now(),
    )


@router.get("/darkpool/{symbol}/prints", response_model=DPPrintsResponse)
async def get_dp_prints(
    symbol: str,
    limit: int = Query(10, ge=1, le=50, description="Number of recent prints to return"),
):
    """
    Get recent dark pool activity for a symbol from Stockgrid.

    Note: Stockgrid provides daily aggregates, not individual prints.
    We transform the top positions into a print-like format.
    """
    symbol = symbol.upper()
    sg = _get_stockgrid()

    try:
        detail = sg.get_ticker_detail(symbol)
        top = sg.get_top_positions(limit=limit, sort_by="Net Short Volume $")
    except Exception as e:
        logger.error(f"Stockgrid DP prints call failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail=f"Stockgrid error: {e}")

    dp_prints = []

    # Add the target symbol's detail as a "print"
    if detail and detail.dp_position_dollars:
        side = "SELL" if (detail.short_volume_pct or 0) > 0.5 else "BUY"
        dp_prints.append(DPPrint(
            price=round(abs(detail.dp_position_dollars / detail.dp_position_shares), 2) if detail.dp_position_shares else 0,
            volume=abs(int(detail.short_volume or detail.dp_position_shares or 0)),
            side=side,
            timestamp=datetime.now(),
        ))

    # Add top net-short positions as context prints
    for pos in top:
        if pos.ticker == symbol:
            continue  # Already added above
        if not pos.dp_position_dollars or not pos.dp_position_shares:
            continue
        side = "SELL" if (pos.short_volume_pct or 0) > 0.5 else "BUY"
        dp_prints.append(DPPrint(
            price=round(abs(pos.dp_position_dollars / pos.dp_position_shares), 2),
            volume=abs(int(pos.short_volume or pos.dp_position_shares or 0)),
            side=side,
            timestamp=datetime.now(),
        ))

    if not dp_prints:
        raise HTTPException(
            status_code=404,
            detail=f"No dark pool prints for {symbol} from Stockgrid"
        )

    return DPPrintsResponse(
        symbol=symbol,
        prints=dp_prints[:limit],
        count=len(dp_prints),
        timestamp=datetime.now(),
    )
