"""
Pivot Points API — Classic/Fib/Camarilla/Woodie + 200-EMA

GET /pivots/{symbol}  → all levels + confluence zones
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)
router = APIRouter()


class PivotLevel(BaseModel):
    label: str
    price: float
    set_name: str  # Classic, Fibonacci, Camarilla, Woodie, EMA
    level_type: str  # SUPPORT, RESISTANCE, PIVOT, MOVING_AVERAGE


class ConfluenceZone(BaseModel):
    avg_price: float
    level_count: int
    sets: List[str]
    levels: List[PivotLevel]


class PivotResponse(BaseModel):
    symbol: str
    prior_high: float
    prior_low: float
    prior_close: float
    ema_200: Optional[float]
    levels: List[PivotLevel]
    confluence_zones: List[ConfluenceZone]
    total_levels: int
    narrative: str


def _find_confluence(levels: List[dict], threshold: float = 1.5) -> List[ConfluenceZone]:
    """Find zones where 3+ levels from different formulas cluster within $threshold."""
    sorted_levels = sorted(levels, key=lambda x: x["price"])
    zones = []
    used = set()

    for i, l1 in enumerate(sorted_levels):
        if i in used:
            continue
        cluster = [l1]
        for j, l2 in enumerate(sorted_levels):
            if j != i and j not in used:
                if abs(l1["price"] - l2["price"]) <= threshold and l1["set"] != l2["set"]:
                    cluster.append(l2)
                    used.add(j)

        if len(cluster) >= 3:
            used.add(i)
            avg = sum(c["price"] for c in cluster) / len(cluster)
            sets = list(set(c["set"] for c in cluster))
            zones.append(ConfluenceZone(
                avg_price=round(avg, 2),
                level_count=len(cluster),
                sets=sets,
                levels=[PivotLevel(
                    label=c["label"],
                    price=round(c["price"], 2),
                    set_name=c["set"],
                    level_type=c["type"],
                ) for c in cluster],
            ))

    return zones


@router.get("/pivots/{symbol}", response_model=PivotResponse)
async def get_pivots(symbol: str):
    """Get pivot levels + confluence zones for a symbol."""
    try:
        from live_monitoring.enrichment.apis.pivot_calculator import PivotCalculator

        calc = PivotCalculator()
        result = calc.compute(symbol.upper())

        if not result:
            raise HTTPException(status_code=404, detail=f"No pivot data for {symbol}")

        flat = result.all_levels_flat()
        levels = [PivotLevel(
            label=l["label"],
            price=round(l["price"], 2),
            set_name=l["set"],
            level_type=l["type"],
        ) for l in flat]

        confluence = _find_confluence(flat)
        narrative = calc.get_narrative(symbol.upper())

        return PivotResponse(
            symbol=symbol.upper(),
            prior_high=round(result.prior_high, 2),
            prior_low=round(result.prior_low, 2),
            prior_close=round(result.prior_close, 2),
            ema_200=round(result.ema_200, 2) if result.ema_200 else None,
            levels=levels,
            confluence_zones=confluence,
            total_levels=len(levels),
            narrative=narrative,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pivot endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
