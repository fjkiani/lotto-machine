"""
PUBLIC (no Pro) AXLFI enrichment for HF signal pack path.

Uses StockgridClient methods from #16/#20 — does NOT re-implement walls.
Darkpools are NEVER labeled LIVE here (Pro-only; fail-closed elsewhere).
Insiders are Pro fail-closed — never counted as public LIVE.

Honesty:
  LIVE — HTTP 200 + non-empty payload + not paywall (PUBLIC endpoints only)
  HARD_BLOCK / PAYWALL_FALLBACK — non-200, empty, or Pro-gated (never invent numbers)
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _layer_from_meta(
    *,
    name: str,
    payload: Any,
    fetch_meta: Dict[str, Any],
    method: str,
    path_hint: str,
    allow_live: bool = True,
) -> Dict[str, Any]:
    """Classify a layer from StockgridClient.last_fetch_meta only."""
    meta = dict(fetch_meta or {})
    http_status = meta.get("http_status")
    source = meta.get("source")
    paywall = bool(meta.get("paywall"))
    has_payload = payload is not None and payload != {} and payload != []

    live_ok = (
        allow_live
        and http_status == 200
        and source in ("live", "browser")
        and has_payload
        and not paywall
    )
    if live_ok:
        status = "LIVE"
        freshness = "LIVE"
    elif http_status == 403 or paywall:
        status = "HARD_BLOCK"
        freshness = "PAYWALL_FALLBACK"
    elif not allow_live and http_status == 200 and has_payload and not paywall:
        # Pro-gated success — honest HTTP, never public LIVE
        status = "PRO_GATED"
        freshness = "LIVE"
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
        "pro_gated": not allow_live,
    }
    # Tiny non-secret summary keys only — never invent DP series
    if isinstance(payload, dict) and (live_ok or (not allow_live and has_payload)):
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
        rows = (
            payload.get("rows")
            or payload.get("points")
            or payload.get("trades")
            or payload.get("fails")
            or payload.get("signals")
            or payload.get("contracts")
            or payload.get("events")
        )
        if isinstance(rows, list):
            out["row_count"] = len(rows)
    return out


def _probe(
    client,
    *,
    name: str,
    method_name: str,
    path_hint: str,
    call: Callable[[], Any],
    allow_live: bool = True,
) -> Tuple[str, Dict[str, Any]]:
    payload = None
    meta: Dict[str, Any] = {}
    try:
        payload = call()
        meta = dict(getattr(client, "last_fetch_meta", {}) or {})
    except Exception as exc:
        logger.warning("public %s probe failed: %s", name, exc)
        meta = {"http_status": None, "source": None, "paywall": False}
    layer = _layer_from_meta(
        name=name,
        payload=payload,
        fetch_meta=meta,
        method=method_name,
        path_hint=path_hint,
        allow_live=allow_live,
    )
    return name, layer


def fetch_public_enrichment(client, symbol: str = "SPY") -> Dict[str, Any]:
    """
    Probe PUBLIC AXLFI layers via existing StockgridClient methods.

    PUBLIC (LIVE on HTTP 200):
      - get_option_walls(symbol)                  → /options/walls
      - get_short_interest_ticker(symbol)         → /short-interest/ticker
      - get_clusters_scan()                       → /clusters/scan
      - get_market_update()                       → /market/update
      - get_institutions_ticker(symbol)           → /institutions/ticker  (#20)
      - get_events_overview()                     → /events/overview     (#20)
      - get_breadth_signals()                     → /breadth/signals     (#20)
      - get_contracts_ticker(symbol)              → /contracts/ticker    (#20)
      - get_short_interest_fails_ticker(symbol)   → /short-interest/fails/ticker (#20)

    PRO fail-closed (never public LIVE):
      - get_insiders_ticker(symbol)               → /insiders/ticker

    Never probes /darkpools/* — those stay fail-closed in the Pro path.
    """
    sym = (symbol or "SPY").upper()
    layers: Dict[str, Dict[str, Any]] = {}
    fail_closed_layers: Dict[str, Dict[str, Any]] = {}

    public_probes = [
        (
            "options_walls",
            "get_option_walls",
            "/options/walls",
            lambda: client.get_option_walls(sym),
        ),
        (
            "short_interest",
            "get_short_interest_ticker",
            "/short-interest/ticker",
            lambda: client.get_short_interest_ticker(sym),
        ),
        (
            "clusters",
            "get_clusters_scan",
            "/clusters/scan",
            lambda: client.get_clusters_scan(),
        ),
        (
            "market_update",
            "get_market_update",
            "/market/update",
            lambda: client.get_market_update(),
        ),
        # #20 PUBLIC fold
        (
            "institutions",
            "get_institutions_ticker",
            "/institutions/ticker",
            lambda: client.get_institutions_ticker(sym),
        ),
        (
            "events",
            "get_events_overview",
            "/events/overview",
            lambda: client.get_events_overview(),
        ),
        (
            "breadth",
            "get_breadth_signals",
            "/breadth/signals",
            lambda: client.get_breadth_signals(),
        ),
        (
            "contracts",
            "get_contracts_ticker",
            "/contracts/ticker",
            lambda: client.get_contracts_ticker(sym),
        ),
        (
            "short_interest_fails",
            "get_short_interest_fails_ticker",
            "/short-interest/fails/ticker",
            lambda: client.get_short_interest_fails_ticker(sym),
        ),
    ]

    for name, method_name, path_hint, call in public_probes:
        key, layer = _probe(
            client,
            name=name,
            method_name=method_name,
            path_hint=path_hint,
            call=call,
            allow_live=True,
        )
        layers[key] = layer

    # Insiders — Pro fail-closed; never counted as public LIVE
    _, insiders_layer = _probe(
        client,
        name="insiders",
        method_name="get_insiders_ticker",
        path_hint="/insiders/ticker",
        call=lambda: client.get_insiders_ticker(sym),
        allow_live=False,
    )
    fail_closed_layers["insiders"] = insiders_layer

    live_layers = [k for k, v in layers.items() if v.get("live_ok")]
    return {
        "symbol": sym,
        "layers": layers,
        "fail_closed_layers": fail_closed_layers,
        "live_layer_names": live_layers,
        "public_live_count": len(live_layers),
        "public_live_ok": len(live_layers) > 0,
        "all_public_live": len(live_layers) == len(layers),
        # Explicit: darkpools are NOT part of public enrichment
        "darkpools_included": False,
        "insiders_public_live": False,
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
        "pro_gated": True,
    }
