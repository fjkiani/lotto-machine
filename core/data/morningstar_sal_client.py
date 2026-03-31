"""
Morningstar SAL (api-global) — fund portfolio holdings JSON.

Version / clientId matrix (holdings URL, verified with apikey header):
  - clientId=MDC + version=4.71.0 → 200 (matches mstarpy default_params).
  - clientId=DOTCOM_EC + version=4.71.0 → 200.
  - clientId=MDC + version=3.59.1 + full component params → often 400 "Invalid request".
  - clientId=DOTCOM_EC + version=3.59.1 + same full params → 200.

So "MDC is broken" was wrong: MDC works when SAL `version` matches the
contract (4.71.0). DOTCOM_EC is more forgiving paired with older SO snippets
(3.59.1).

Requires: MORNINGSTAR_API_KEY in the environment.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

SAL_HOLDINGS_TEMPLATE = (
    "https://api-global.morningstar.com/sal-service/v1/fund/portfolio/holding/v2/{fund_id}/data"
)


def get_morningstar_api_key() -> Optional[str]:
    k = (os.getenv("MORNINGSTAR_API_KEY") or "").strip()
    return k or None


def fetch_fund_holdings(
    fund_id: str,
    *,
    api_key: Optional[str] = None,
    benchmark_id: str = "mstarorcat",
    sal_version: str = "4.71.0",
    premium_num: str = "100",
    free_num: str = "25",
    client_id: str = "MDC",
    timeout: int = 45,
) -> Dict[str, Any]:
    """
    GET fund portfolio holdings (SAL JSON).

    Args:
        fund_id: Morningstar security id (e.g. FOUSA06WRH, F00000MUR2).
        api_key: Overrides MORNINGSTAR_API_KEY.
        client_id: MDC aligns with mstarpy; use DOTCOM_EC if you must pair with
            older `sal_version` (e.g. 3.59.1) and see 400 with MDC.
    """
    key = api_key or get_morningstar_api_key()
    if not key:
        raise ValueError("MORNINGSTAR_API_KEY is not set")

    url = SAL_HOLDINGS_TEMPLATE.format(fund_id=fund_id.strip())
    params = {
        "premiumNum": str(premium_num),
        "freeNum": str(free_num),
        "languageId": "en",
        "locale": "en",
        "clientId": client_id,
        "benchmarkId": benchmark_id,
        "component": "sal-components-mip-holdings",
        "version": sal_version,
    }
    headers = {
        "apikey": key,
        "User-Agent": "Mozilla/5.0 (compatible; AlphaTerminal/1.0)",
        "Accept": "application/json",
    }
    r = requests.get(url, headers=headers, params=params, timeout=timeout)
    if r.status_code == 401:
        try:
            err = r.json()
        except Exception:
            err = {"message": r.text}
        raise RuntimeError(f"SAL unauthorized: {err}")
    if r.status_code == 400:
        raise RuntimeError(f"SAL bad request (check fund_id / client_id / version): {r.text!r}")
    r.raise_for_status()
    return r.json()
