"""
Legacy / alias routes: /api/llm/* and /api/snapshots — backed by canonical SQLite.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/llm/analyze")
async def llm_analyze(body: Dict[str, Any]):
    from backend.app.api.v1.oracle import OracleRequest, oracle_analyze

    req = OracleRequest.model_validate(body)
    return await oracle_analyze(req)


@router.get("/llm/trend")
def llm_trend():
    from backend.app.signals.canonical_state import get_trend_summary

    return get_trend_summary(n=5)


@router.get("/snapshots")
def api_snapshots(
    limit: int = Query(20, ge=1, le=200),
    since: Optional[str] = Query(None, description="ISO datetime lower bound"),
    symbol: Optional[str] = Query(None),
):
    from backend.app.signals.canonical_state import list_snapshots

    return list_snapshots(limit=limit, since=since, symbol=symbol)
