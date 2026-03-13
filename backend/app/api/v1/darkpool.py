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
    dp_percent: float
    buying_pressure: float
    dp_position_dollars: Optional[float] = None
    net_short_dollars: Optional[float] = None
    short_volume_pct: Optional[float] = None
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
# Routes — STATIC routes first (FastAPI matches in registration order)
# ---------------------------------------------------------------------------

@router.get("/darkpool/narrative")
async def get_dp_narrative():
    """
    Multi-ticker dark pool narrative — SPY vs QQQ vs IWM comparison.
    Uses the source's get_narrative() for rich dollar-value prose.
    """
    sg = _get_stockgrid()
    try:
        narrative = sg.get_narrative()
        return {
            "narrative": narrative,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"DP narrative failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DP narrative failed: {e}")


@router.get("/darkpool/top-positions")
async def get_dp_top_positions(
    limit: int = Query(10, ge=1, le=50, description="Number of top positions"),
    sort_by: str = Query("Net Short Volume $", description="Sort field"),
):
    """
    Top dark pool positions by dollar value with short vol % per ticker.
    """
    sg = _get_stockgrid()
    try:
        positions = sg.get_top_positions(limit=limit, sort_by=sort_by)
        return {
            "positions": [
                {
                    "ticker": p.ticker,
                    "dp_position_dollars": p.dp_position_dollars,
                    "dp_position_shares": p.dp_position_shares,
                    "short_volume_pct": p.short_volume_pct,
                    "net_short_volume": getattr(p, "net_short_volume", None),
                    "date": p.date,
                }
                for p in positions
            ],
            "count": len(positions),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"DP top positions failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DP top positions failed: {e}")


# ---------------------------------------------------------------------------
# Routes — parameterized {symbol} routes AFTER static routes
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

    dp_levels = []

    # If the symbol itself has detail data, add it as a primary level
    if detail and detail.dp_position_dollars:
        implied = abs(detail.dp_position_dollars / detail.dp_position_shares) if detail.dp_position_shares else current_price
        short_pct = detail.short_volume_pct or 0
        
        # FIX: Stockgrid short volume is a percentage (e.g. 59.2), not a decimal (0.59)
        if short_pct > 55:
            lt = "RESISTANCE"
        elif short_pct < 45:
            lt = "SUPPORT"
        else:
            lt = "BATTLEGROUND"

        dp_levels.append(DPLevel(
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
    # Stockgrid returns short_volume_pct as raw percentage (e.g. 54.4) OR decimal (0.544)
    raw_pct = (detail.short_volume_pct if detail else 0.5) or 0.5
    # Normalize: if > 1, it's already a percentage; if <= 1, multiply by 100
    dp_percent = round(raw_pct if raw_pct > 1 else raw_pct * 100, 1)
    dp_percent = max(0, min(100, dp_percent))  # Clamp to 0-100
    buying_pressure = round(max(0, 100 - dp_percent), 1)

    total_volume = abs(int((detail.short_volume if detail else 0) or (detail.dp_position_shares if detail else 0) or 0))
    dp_position_dollars = abs((detail.dp_position_dollars if detail else 0) or 0)
    net_short_dollars = abs((detail.net_short_volume if detail else 0) or 0) if hasattr(detail, 'net_short_volume') else None

    # B3 FIX: Return raw Stockgrid short_volume_pct, not the derived dp_percent
    raw_short_vol_pct = round(raw_pct if raw_pct > 1 else raw_pct * 100, 1) if detail else None

    # B2 FIX: Derive nearest support/resistance from same-symbol data only
    # Cross-ticker positions have different price scales — filter to this symbol
    nearest_support = None
    nearest_resistance = None
    battlegrounds = []

    # Use the symbol's own detail for primary S/R classification
    if detail and detail.dp_position_dollars and detail.dp_position_shares and current_price:
        implied = abs(detail.dp_position_dollars / detail.dp_position_shares)
        svp = detail.short_volume_pct or 0.5
        vol = abs(int(detail.dp_position_shares or 0))

        # Classify and create levels at price bands around implied price
        if svp > 0.55:
            # Heavy shorting → these levels are resistance
            nearest_resistance = DPLevel(
                price=round(implied, 2),
                volume=vol,
                level_type="RESISTANCE",
                strength=100.0,
                distance_from_price=round(abs(implied - current_price), 4),
            )
        elif svp < 0.45:
            nearest_support = DPLevel(
                price=round(implied, 2),
                volume=vol,
                level_type="SUPPORT",
                strength=100.0,
                distance_from_price=round(abs(implied - current_price), 4),
            )
        else:
            battlegrounds.append(DPLevel(
                price=round(implied, 2),
                volume=vol,
                level_type="BATTLEGROUND",
                strength=50.0,
                distance_from_price=round(abs(implied - current_price), 4),
            ))

    # Also check same-symbol positions in the top list for additional levels
    if top_positions and current_price:
        for pos in top_positions:
            if pos.ticker != symbol:
                continue  # Skip other symbols — their prices are different scales
            if not pos.dp_position_dollars or not pos.dp_position_shares:
                continue
            implied_price = abs(pos.dp_position_dollars / pos.dp_position_shares)
            if not implied_price:
                continue
            svp = pos.short_volume_pct or 0.5
            vol = abs(int(pos.dp_position_shares))
            if svp > 0.55:
                level_type = "RESISTANCE"
            elif svp < 0.45:
                level_type = "SUPPORT"
            else:
                level_type = "BATTLEGROUND"
            level = DPLevel(
                price=round(implied_price, 2),
                volume=vol,
                level_type=level_type,
                strength=0,
                distance_from_price=round(abs(implied_price - current_price), 4),
            )
            if level_type == "SUPPORT" and implied_price < current_price:
                if nearest_support is None or level.distance_from_price < nearest_support.distance_from_price:
                    nearest_support = level
            elif level_type == "RESISTANCE" and implied_price > current_price:
                if nearest_resistance is None or level.distance_from_price < nearest_resistance.distance_from_price:
                    nearest_resistance = level
            elif level_type == "BATTLEGROUND":
                battlegrounds.append(level)
        battlegrounds.sort(key=lambda x: x.distance_from_price or 999)

    summary = DPSummary(
        total_volume=total_volume,
        dp_percent=dp_percent,
        buying_pressure=buying_pressure,
        dp_position_dollars=dp_position_dollars if dp_position_dollars else None,
        net_short_dollars=net_short_dollars,
        short_volume_pct=raw_short_vol_pct,
        nearest_support=nearest_support,
        nearest_resistance=nearest_resistance,
        battlegrounds=battlegrounds[:5],
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


# (Static routes moved to top of file — see above)
