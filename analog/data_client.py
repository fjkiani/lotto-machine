"""
FRED observations client (httpx). No scoring — fetch-only for analog pipeline.

Note: FRED series SP500 (daily) has a short observation history on FRED (starts ~2016-04-01).
Do not assume SP500 exists for 1970s/1990s windows — use a longer-history series (e.g.
SPASTT01USM661N) for equity calibration when building analogs.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx

FRED_OBSERVATIONS = "https://api.stlouisfed.org/fred/series/observations"


class FredObservationsClient:
    def __init__(self, api_key: str | None = None, timeout: float = 120.0):
        self.api_key = (api_key or os.environ.get("FRED_API_KEY", "")).strip()
        if not self.api_key:
            raise ValueError("FRED_API_KEY missing")
        self._timeout = timeout

    def observations(
        self,
        series_id: str,
        *,
        limit: int | None = None,
        sort_order: str = "desc",
        observation_start: str | None = None,
        observation_end: str | None = None,
        file_type: str = "json",
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": file_type,
            "sort_order": sort_order,
        }
        if limit is not None:
            params["limit"] = str(limit)
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end
        url = f"{FRED_OBSERVATIONS}?{urlencode(params)}"
        with httpx.Client(timeout=self._timeout) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.json()
