"""Morningstar SAL passthrough (holdings and related)."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/morningstar", tags=["morningstar"])


@router.get("/sal/holdings/{fund_id}")
def get_sal_fund_holdings(
    fund_id: str,
    benchmark_id: str = Query("mstarorcat", description="SAL benchmarkId"),
    sal_version: str = Query("4.71.0", description="SAL component version (mstarpy uses 4.71.0)"),
    client_id: str = Query(
        "MDC",
        description="MDC matches mstarpy; try DOTCOM_EC if 400 with an older sal_version",
    ),
    premium_num: str = Query("100"),
    free_num: str = Query("25"),
) -> Dict[str, Any]:
    """
    Proxy to Morningstar api-global SAL fund holdings JSON.

    Example fund_id: FOUSA06WRH (American Funds Growth fund on morningstar.com pages).
    """
    try:
        from core.data.morningstar_sal_client import fetch_fund_holdings
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Morningstar client import failed: {e}")

    try:
        data = fetch_fund_holdings(
            fund_id,
            benchmark_id=benchmark_id,
            sal_version=sal_version,
            premium_num=premium_num,
            free_num=free_num,
            client_id=client_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        logger.warning("Morningstar SAL error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Morningstar SAL failure")
        raise HTTPException(status_code=502, detail=str(e))

    # Lightweight envelope so callers know source
    return {
        "source": "morningstar_sal",
        "fund_id": fund_id,
        "data": data,
    }
