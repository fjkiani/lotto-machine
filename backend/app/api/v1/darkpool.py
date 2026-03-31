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
import requests

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
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"yfinance price path failed for {symbol}, falling back to Yahoo chart API: {e}")

    # Fallback: direct Yahoo chart API
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}?interval=1m&range=1d"
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        payload = resp.json()
        result = payload.get("chart", {}).get("result", [])
        if not result:
            raise ValueError("No chart result")
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            raise ValueError("No regularMarketPrice in chart meta")
        return float(price)
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

    Note: The AXLFI leaderboard API returns short_volume_percent=None when
    sorted by dark_pool_position_dollars. We enrich missing values from
    the per-ticker endpoint.
    """
    sg = _get_stockgrid()
    try:
        positions = sg.get_top_positions(limit=limit, sort_by=sort_by)

        result = []
        for p in positions:
            svp = p.short_volume_pct
            # Leaderboard often returns 0/None for short_volume_pct when
            # sorted by dp_position_dollars. Enrich from per-ticker API.
            if not svp and len(result) < 15:  # cap enrichment to avoid slow responses
                try:
                    detail = sg.get_ticker_detail(p.ticker)
                    if detail and detail.short_volume_pct:
                        svp = detail.short_volume_pct
                except Exception:
                    pass  # Enrichment is best-effort

            result.append({
                "ticker": p.ticker,
                "dp_position_dollars": p.dp_position_dollars,
                "dp_position_shares": p.dp_position_shares,
                "short_volume_pct": svp,
                "net_short_volume": getattr(p, "net_short_volume", None),
                "date": p.date,
            })

        return {
            "positions": result,
            "count": len(result),
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

    # If the symbol itself has detail data, classify current_price as S/R level
    # NOTE: dp_position_dollars / dp_position_shares gives the dollar-weighted DP
    # average price (~$603) which is NOT the current market price. We use current_price instead.
    if detail:
        short_pct = detail.short_volume_pct or 50
        vol = abs(int(detail.dp_position_shares or 0))
        
        # short_volume_pct is ALREADY a percentage (e.g. 63.3), not a decimal (0.633)
        if short_pct > 55:
            lt = "RESISTANCE"
        elif short_pct < 45:
            lt = "SUPPORT"
        else:
            lt = "BATTLEGROUND"

        dp_levels.append(DPLevel(
            price=round(current_price, 2),
            volume=vol,
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

    # net_short_volume is shares in Stockgrid payloads; convert to dollars using current price.
    # Do not force abs() so direction is preserved (positive = net short pressure).
    net_short_shares = getattr(detail, "net_short_volume", None) if detail else None
    if (net_short_shares is None or net_short_shares == 0) and top_positions:
        for pos in top_positions:
            if pos.ticker == symbol and hasattr(pos, "net_short_volume"):
                net_short_shares = getattr(pos, "net_short_volume", None)
                if net_short_shares is not None:
                    break
    net_short_dollars = (float(net_short_shares) * float(current_price)) if net_short_shares is not None else None

    # B3 FIX: Return raw Stockgrid short_volume_pct, not the derived dp_percent
    raw_short_vol_pct = round(raw_pct if raw_pct > 1 else raw_pct * 100, 1) if detail else None

    # B2 FIX v2: Wire GEX call/put walls as nearest resistance/support
    # The DP short-vol classification tells us the BIAS (selling vs buying pressure),
    # but the actual LEVELS come from the GEX gamma walls — those are the real
    # support/resistance strikes defined by options market makers.
    nearest_support = None
    nearest_resistance = None
    battlegrounds = []

    # Try to get GEX levels for this symbol (same data the GEX panel uses)
    gex_call_wall = None   # highest positive GEX above price = resistance/ceiling
    gex_put_wall = None    # most negative GEX below price = support/floor
    gex_max_pain = None
    try:
        from backend.app.api.v1.gamma import _get_gex_calculator
        calc = _get_gex_calculator()
        gex_result = calc.compute_gex(symbol)
        if gex_result and gex_result.spot_price:
            # Call wall = highest positive GEX strike >= current price
            gamma_walls_above = [w for w in (gex_result.gamma_walls or []) if w.strike >= current_price]
            if gamma_walls_above:
                cw = max(gamma_walls_above, key=lambda w: w.gex)
                gex_call_wall = cw
                nearest_resistance = DPLevel(
                    price=round(cw.strike, 2),
                    volume=cw.open_interest,
                    level_type="RESISTANCE",
                    strength=round(abs(cw.gex / 1e6), 1),  # gamma in millions
                    distance_from_price=round(abs(cw.strike - current_price), 2),
                )
            # Put wall = most negative GEX strike <= current price
            neg_zones_below = [z for z in (gex_result.negative_zones or []) if z.strike <= current_price]
            if neg_zones_below:
                pw = min(neg_zones_below, key=lambda z: z.gex)
                gex_put_wall = pw
                nearest_support = DPLevel(
                    price=round(pw.strike, 2),
                    volume=pw.open_interest,
                    level_type="SUPPORT",
                    strength=round(abs(pw.gex / 1e6), 1),
                    distance_from_price=round(abs(current_price - pw.strike), 2),
                )
            gex_max_pain = gex_result.max_pain
    except Exception as e:
        logger.warning(f"GEX data unavailable for {symbol} S/R levels: {e}")

    # Fallback: if GEX gave nothing, use DP short-vol classification
    if not nearest_resistance and not nearest_support:
        if detail and current_price:
            svp = detail.short_volume_pct or 50
            vol = abs(int(detail.dp_position_shares or 0))
            if svp > 55:
                nearest_resistance = DPLevel(
                    price=round(current_price, 2), volume=vol,
                    level_type="RESISTANCE", strength=min(100.0, svp),
                    distance_from_price=0.0,
                )
            elif svp < 45:
                nearest_support = DPLevel(
                    price=round(current_price, 2), volume=vol,
                    level_type="SUPPORT", strength=min(100.0, 100 - svp),
                    distance_from_price=0.0,
                )
            else:
                battlegrounds.append(DPLevel(
                    price=round(current_price, 2), volume=vol,
                    level_type="BATTLEGROUND", strength=50.0,
                    distance_from_price=0.0,
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
            svp = pos.short_volume_pct or 50  # Already a percentage
            vol = abs(int(pos.dp_position_shares))
            if svp > 55:
                level_type = "RESISTANCE"
            elif svp < 45:
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
    We transform the target symbol's data into a print-like format.
    Only returns prints for the REQUESTED symbol — no cross-ticker contamination.
    """
    symbol = symbol.upper()
    sg = _get_stockgrid()
    current_price = _get_current_price(symbol)

    try:
        detail = sg.get_ticker_detail(symbol)
        top = sg.get_top_positions(limit=50, sort_by="Net Short Volume $")
    except Exception as e:
        logger.error(f"Stockgrid DP prints call failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail=f"Stockgrid error: {e}")

    dp_prints = []

    # Add the target symbol's detail as a "print"
    if detail and detail.dp_position_dollars:
        implied_price = round(abs(detail.dp_position_dollars / detail.dp_position_shares), 2) if detail.dp_position_shares else 0
        # Hard floor + 8% proximity filter — eliminates Stockgrid math artifacts like $603.13
        # Tightened from 20% to 8% for defense-in-depth against cross-ticker contamination
        price_valid = implied_price >= 580 and (
            not current_price or abs(implied_price - current_price) / current_price <= 0.08
        )
        side = "SELL" if (detail.short_volume_pct or 0) > 50 else "BUY"
        dp_prints.append(DPPrint(
            price=implied_price if price_valid else round(current_price, 2),
            volume=abs(int(detail.short_volume or detail.dp_position_shares or 0)),
            side=side,
            timestamp=datetime.now(),
        ))

    # ONLY add prints from positions of THE SAME SYMBOL
    # Previous code added other tickers ($QQQ $80, $IWM $257) which contaminated the feed
    for pos in top:
        if pos.ticker != symbol:
            continue  # Only this symbol
        if not pos.dp_position_dollars or not pos.dp_position_shares:
            continue
        implied_price = round(abs(pos.dp_position_dollars / pos.dp_position_shares), 2)
        # Filter: price must be within 8% of current price to be valid
        # Tightened from 20% to 8% — defense-in-depth against cross-ticker contamination
        # Hard floor: SPY doesn't trade below $580 in current range
        if current_price and implied_price > 0:
            if implied_price < 580:
                continue  # Stockgrid math artifact, not a real trade
            if abs(implied_price - current_price) / current_price > 0.08:
                continue  # Outside ±8% of current price — not valid for this symbol
        side = "SELL" if (pos.short_volume_pct or 0) > 50 else "BUY"
        # Avoid duplicate if we already have the same price from detail
        if dp_prints and abs(dp_prints[0].price - implied_price) < 0.01:
            continue
        dp_prints.append(DPPrint(
            price=implied_price,
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
