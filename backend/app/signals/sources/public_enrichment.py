"""
PUBLIC (no Pro) AXLFI enrichment for HF signal pack path.

Uses StockgridClient methods from #16 — does NOT re-implement walls.
Darkpools are NEVER labeled LIVE here (Pro-only; fail-closed elsewhere).

Honesty:
  LIVE — HTTP 200 + non-empty payload + not paywall
  HARD_BLOCK / unavailable — non-200 or empty (never invent numbers)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _layer_from_meta(
    *,
    name: str,
    payload: Any,
    fetch_meta: Dict[str, Any],
    method: str,
    path_hint: str,
) -> Dict[str, Any]:
    """Classify a public layer from StockgridClient.last_fetch_meta only."""
    meta = dict(fetch_meta or {})
    http_status = meta.get("http_status")
    source = meta.get("source")
    paywall = bool(meta.get("paywall"))
    has_payload = payload is not None and payload != {} and payload != []

    live_ok = (
        http_status == 200
        and source in ("live", "browser")
        and has_payload
        and not paywall
    )
    if live_ok:
        status = "LIVE"
        freshness = "LIVE"
    elif http_status == 403 or paywall:
        # Public endpoints should not 403; if they do, treat as unavailable
        status = "HARD_BLOCK"
        freshness = "PAYWALL_FALLBACK"
    elif http_status is None and not has_payload:
        status = "HARD_BLOCK"
        freshness = "UNAVAILABLE"
    else:
        status = "HARD_BLOCK"
        freshness = "UNAVAILABLE"

    out: Dict[str, Any] = {
        "name": name,
        "method": method,
        "path": path_hint,
        "status": status,
        "freshness": freshness,
        "http_status": http_status,
        "source": source,
        "paywall": paywall,
        "live_ok": live_ok,
        "has_payload": has_payload,
    }
    # Tiny non-secret summary keys only — never invent DP series
    if isinstance(payload, dict) and live_ok:
        for key in ("ticker", "as_of", "as_of_date", "spot", "narrative", "count"):
            if key in payload and payload[key] is not None:
                out[key] = payload[key]
        if "option_walls" in payload and isinstance(payload["option_walls"], dict):
            dates = sorted(payload["option_walls"].keys())
            out["walls_expiries"] = len(dates)
            if dates:
                nearest = payload["option_walls"][dates[0]]
                out["call_wall"] = nearest.get("call_wall")
                out["put_wall"] = nearest.get("put_wall")
                out["poc"] = nearest.get("poc")
        rows = payload.get("rows") or payload.get("points") or payload.get("trades")
        if isinstance(rows, list):
            out["row_count"] = len(rows)
    return out


def fetch_public_enrichment(client, symbol: str = "SPY") -> Dict[str, Any]:
    """
    Probe PUBLIC AXLFI layers via existing StockgridClient methods.

    Methods called (PUBLIC, no Pro cookie required):
      - get_option_walls(symbol)           → /options/walls
      - get_short_interest_ticker(symbol)  → /short-interest/ticker
      - get_clusters_scan()                → /clusters/scan
      - get_market_update()                → /market/update  (market surface)

    Never probes /darkpools/* — those stay fail-closed in the Pro path.
    """
    layers: Dict[str, Dict[str, Any]] = {}

    # 1) Options walls LIVE (already shipped in #16 — reuse, do not re-add)
    walls_payload = None
    walls_meta: Dict[str, Any] = {}
    try:
        walls_payload = client.get_option_walls(symbol)
        walls_meta = dict(getattr(client, "last_fetch_meta", {}) or {})
    except Exception as exc:
        logger.warning("public walls probe failed: %s", exc)
        walls_meta = {"http_status": None, "source": None, "paywall": False}
    layers["options_walls"] = _layer_from_meta(
        name="options_walls",
        payload=walls_payload,
        fetch_meta=walls_meta,
        method="get_option_walls",
        path_hint="/options/walls",
    )

    # 2) Short interest LIVE
    si_payload = None
    si_meta: Dict[str, Any] = {}
    try:
        si_payload = client.get_short_interest_ticker(symbol)
        si_meta = dict(getattr(client, "last_fetch_meta", {}) or {})
    except Exception as exc:
        logger.warning("public short-interest probe failed: %s", exc)
        si_meta = {"http_status": None, "source": None, "paywall": False}
    layers["short_interest"] = _layer_from_meta(
        name="short_interest",
        payload=si_payload,
        fetch_meta=si_meta,
        method="get_short_interest_ticker",
        path_hint="/short-interest/ticker",
    )

    # 3) Market / clusters LIVE
    clusters_payload = None
    clusters_meta: Dict[str, Any] = {}
    try:
        clusters_payload = client.get_clusters_scan()
        clusters_meta = dict(getattr(client, "last_fetch_meta", {}) or {})
    except Exception as exc:
        logger.warning("public clusters probe failed: %s", exc)
        clusters_meta = {"http_status": None, "source": None, "paywall": False}
    layers["clusters"] = _layer_from_meta(
        name="clusters",
        payload=clusters_payload,
        fetch_meta=clusters_meta,
        method="get_clusters_scan",
        path_hint="/clusters/scan",
    )

    market_payload = None
    market_meta: Dict[str, Any] = {}
    try:
        market_payload = client.get_market_update()
        market_meta = dict(getattr(client, "last_fetch_meta", {}) or {})
    except Exception as exc:
        logger.warning("public market/update probe failed: %s", exc)
        market_meta = {"http_status": None, "source": None, "paywall": False}
    layers["market_update"] = _layer_from_meta(
        name="market_update",
        payload=market_payload,
        fetch_meta=market_meta,
        method="get_market_update",
        path_hint="/market/update",
    )

    live_layers = [k for k, v in layers.items() if v.get("live_ok")]
    return {
        "symbol": symbol.upper(),
        "layers": layers,
        "live_layer_names": live_layers,
        "public_live_count": len(live_layers),
        "public_live_ok": len(live_layers) > 0,
        "all_public_live": len(live_layers) == len(layers),
        # Explicit: darkpools are NOT part of public enrichment
        "darkpools_included": False,
    }


def darkpools_hard_block_layer(*, reason: str, http_status: Optional[int] = None) -> Dict[str, Any]:
    """Fail-closed darkpools layer — never LIVE without HTTP 200 Pro."""
    return {
        "name": "darkpools",
        "method": "get_ticker_detail_raw",
        "path": "/darkpools/ticker",
        "status": "HARD_BLOCK",
        "freshness": "PAYWALL_FALLBACK",
        "http_status": http_status,
        "live_ok": False,
        "reason": reason,
    }
