"""
FastAPI router for analog endpoints.
Mount with: app.include_router(analog.router.router, prefix="/api/v1")
"""
from __future__ import annotations

from fastapi import APIRouter

from analog.analog_scorer import score_analogs

router = APIRouter(prefix="/analog", tags=["analog"])


@router.get("/health")
async def analog_health():
    return {"status": "ok", "analog_scorer": "analog.analog_scorer.score_analogs"}


@router.get("/snapshot/live")
async def analog_snapshot_live_stub():
    """Placeholder — will proxy ground_truth/live_snapshot_2026.json or re-fetch FRED."""
    return {"detail": "stub — run scripts/ground_truth_mission3_nyx.py"}


@router.get("/score/manual-baseline")
async def analog_score_baseline():
    """MinMax + Euclidean vs VERIFIED_ANALOG_VECTORS; current from live_snapshot_2026.json."""
    r = score_analogs()
    return {
        "confidence": r.confidence,
        "closest_analog": r.primary_analog,
        "distances": r.distances,
        "regime_trajectory": r.regime_trajectory,
    }
