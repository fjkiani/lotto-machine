"""
Gamma Tracker API Endpoints

Provides gamma exposure data, gamma flip levels, max pain, and P/C ratios.

Data source: GEXCalculator (CBOE free delayed options API — no auth, no key).
NO MOCK FALLBACKS — if data is unavailable the endpoint raises HTTP 503.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared GEX calculator instance (lazy init)
# ---------------------------------------------------------------------------

_gex_calc = None


def _get_gex_calculator():
    """Get or create GEXCalculator singleton."""
    global _gex_calc
    if _gex_calc is None:
        try:
            from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
            _gex_calc = GEXCalculator(cache_ttl=300)
        except ImportError as e:
            raise HTTPException(
                status_code=503,
                detail=f"GEXCalculator import failed: {e}"
            )
    return _gex_calc


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GammaWallResponse(BaseModel):
    """A strike with significant gamma exposure."""
    strike: float
    gex: float
    open_interest: int = 0
    signal: str = Field(..., description="SUPPORT or RESISTANCE")


class GammaResponse(BaseModel):
    """Gamma exposure response"""
    symbol: str
    gamma_flip_level: Optional[float] = None
    current_regime: str = Field(..., description="POSITIVE or NEGATIVE")
    total_gex: float = Field(..., description="Total gamma exposure")
    max_pain: Optional[float] = None
    call_put_ratio: float = Field(..., description="Call/Put OI ratio")
    gamma_walls: List[GammaWallResponse] = Field(default_factory=list)
    negative_zones: List[GammaWallResponse] = Field(default_factory=list)
    current_price: float
    distance_to_flip: Optional[float] = None
    total_contracts: int = 0
    total_calls: int = 0
    total_puts: int = 0
    source: str = "cboe"
    timestamp: datetime


# ---------------------------------------------------------------------------
# Routes — powered by GEXCalculator (CBOE free API)
# ---------------------------------------------------------------------------

@router.get("/gamma/{symbol}", response_model=GammaResponse)
async def get_gamma_data(symbol: str):
    """
    Get gamma exposure data for a symbol from CBOE options.

    Returns gamma flip level, regime, max pain, gamma walls, negative zones.
    Raises HTTP 503 if CBOE data is unavailable.
    Never returns mock/hardcoded data.
    """
    symbol = symbol.upper()
    calc = _get_gex_calculator()

    # Map common equity symbols to CBOE format
    # GEXCalculator already handles SPX/NDX/RUT with underscore prefix
    try:
        result = calc.compute_gex(symbol)
    except Exception as e:
        logger.error(f"GEX compute failed for {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"CBOE GEX computation error: {e}")

    if not result.spot_price:
        raise HTTPException(
            status_code=404,
            detail=f"No options data available for {symbol} from CBOE"
        )

    # Calculate distance to gamma flip
    distance_to_flip = None
    if result.gamma_flip and result.spot_price:
        distance_to_flip = round(abs(result.gamma_flip - result.spot_price), 2)

    # Call/Put ratio from contract counts
    call_put_ratio = round(result.total_calls / max(result.total_puts, 1), 2)

    # Convert dataclass walls to response models
    walls = [
        GammaWallResponse(
            strike=w.strike,
            gex=w.gex,
            open_interest=w.open_interest,
            signal=w.signal or "SUPPORT",
        )
        for w in result.gamma_walls
    ]

    neg_zones = [
        GammaWallResponse(
            strike=z.strike,
            gex=z.gex,
            open_interest=z.open_interest,
            signal=z.signal or "RESISTANCE",
        )
        for z in result.negative_zones
    ]

    return GammaResponse(
        symbol=symbol,
        gamma_flip_level=result.gamma_flip if result.gamma_flip else None,
        current_regime=result.gamma_regime or "POSITIVE",
        total_gex=result.total_gex,
        max_pain=result.max_pain if result.max_pain else None,
        call_put_ratio=call_put_ratio,
        gamma_walls=walls,
        negative_zones=neg_zones,
        current_price=result.spot_price,
        distance_to_flip=distance_to_flip,
        total_contracts=result.total_contracts,
        total_calls=result.total_calls,
        total_puts=result.total_puts,
        source=result.source,
        timestamp=datetime.now(),
    )
