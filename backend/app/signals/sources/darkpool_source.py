"""
Dark pool signal source — 5-day dp_position TREND + GEX Layer 2.

Signal logic:
    - Direction from dp_position 5d TREND (NOT from SV% threshold)
    - Velocity = continuous math, not tiered buckets
    - Divergence detection: DP improving while price falling = accumulation
    - GEX Layer 2: CBOE gamma regime modifies confidence
    - Option walls from AXLFI provide key_levels
    - Reasoning chain has min 6 sequential elements
    - Honesty labels: LIVE | CACHE_STALE | PAYWALL_FALLBACK
    - Persist every emitted signal into alerts_history.db

Author: Zo (no hardcoding, no tiered confidence, no fake data)
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time as dtime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _last_rth_close_date(now: Optional[datetime] = None) -> date:
    """Most recent US equity regular-session close date (16:00 America/New_York)."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        from backports.zoneinfo import ZoneInfo  # type: ignore

    et = ZoneInfo("America/New_York")
    now = now or datetime.now(et)
    if now.tzinfo is None:
        now = now.replace(tzinfo=et)
    else:
        now = now.astimezone(et)
    d = now.date()
    wd = d.weekday()  # Mon=0
    if wd == 5:  # Saturday → Friday
        d = d - timedelta(days=1)
    elif wd == 6:  # Sunday → Friday
        d = d - timedelta(days=2)
    elif now.time() < dtime(16, 0):
        d = d - timedelta(days=1)
        while d.weekday() >= 5:
            d = d - timedelta(days=1)
    return d


def _parse_as_of(raw: Any) -> Optional[date]:
    if raw is None:
        return None
    s = str(raw).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _classify_freshness(as_of: Optional[date], fetch_meta: Dict[str, Any]) -> str:
    """
    Honesty labels (never claim RTH fire from stale cache):
      PAYWALL_FALLBACK — HTTP 403 / Pro detail forced disk|repo|legacy
      CACHE_STALE — as_of_data < last RTH close (or non-live without paywall flag)
      LIVE — live HTTP 200 and as_of >= last RTH close
    """
    source = (fetch_meta or {}).get("source")
    paywall = bool((fetch_meta or {}).get("paywall"))
    last_close = _last_rth_close_date()
    as_of_stale = as_of is None or as_of < last_close

    # Paywall forced cache takes precedence even when as_of is current
    if paywall or (source in ("disk", "repo", "legacy") and (fetch_meta or {}).get("http_status") == 403):
        return "PAYWALL_FALLBACK"
    if as_of_stale:
        return "CACHE_STALE"
    if source in ("live", "browser") and not paywall:
        return "LIVE"
    return "CACHE_STALE"


def _persist_to_alerts_history(signal: dict) -> Tuple[bool, Optional[int], str]:
    """Write DarkPoolTrend signal into alerts_history.db. Returns (ok, row_id, reason)."""
    try:
        from live_monitoring.pipeline.components.alert_logger import AlertLogger

        logger_db = AlertLogger(db_path="data/alerts_history.db")
        freshness = signal.get("data_freshness", "UNKNOWN")
        as_of = signal.get("as_of_data", "?")
        title = (
            f"DarkPoolTrend {signal.get('action')} {signal.get('symbol')} "
            f"@ {signal.get('confidence')}% [{freshness}]"
        )
        description = (
            f"as_of_data={as_of} as_of_emit={signal.get('as_of_emit')} "
            f"age_hours={signal.get('age_hours')} source={signal.get('source')} "
            f"id={signal.get('id')}"
        )
        embed = {
            "title": title,
            "description": description,
            "fields": [
                {"name": "strategy", "value": "DarkPoolTrend"},
                {"name": "data_freshness", "value": str(freshness)},
                {"name": "as_of_data", "value": str(as_of)},
                {"name": "confidence", "value": str(signal.get("confidence"))},
                {"name": "action", "value": str(signal.get("action"))},
            ],
            "signal": {
                "id": signal.get("id"),
                "symbol": signal.get("symbol"),
                "action": signal.get("action"),
                "confidence": signal.get("confidence"),
                "data_freshness": freshness,
                "as_of_data": as_of,
            },
        }
        # Never claim "fired today" in content when CACHE_STALE / PAYWALL
        content = (
            f"persisted DarkPoolTrend {signal.get('symbol')} "
            f"freshness={freshness} as_of_data={as_of} (NOT an RTH fire stamp)"
        )
        row_id = logger_db.log_alert(
            alert_type="darkpool_trend",
            embed=embed,
            content=content,
            source="DarkPoolTrend",
            symbol=signal.get("symbol"),
        )
        if row_id is None:
            return False, None, "AlertLogger.log_alert returned None"
        return True, int(row_id), "written via AlertLogger"
    except Exception as exc:
        logger.warning("persist DarkPoolTrend to alerts_history failed: %s", exc)
        return False, None, f"persist exception: {exc}"


def _public_layer_summary(
    public_enrichment: Dict[str, Any], layer_name: str
) -> Dict[str, Any]:
    """Compact honesty summary for a PUBLIC layer (no invented numbers)."""
    layer = ((public_enrichment or {}).get("layers") or {}).get(layer_name) or {}
    return {
        "status": layer.get("status"),
        "freshness": layer.get("freshness"),
        "http_status": layer.get("http_status"),
        "live_ok": bool(layer.get("live_ok")),
        "method": layer.get("method"),
        "path": layer.get("path"),
        "row_count": layer.get("row_count"),
        "as_of": layer.get("as_of") or layer.get("as_of_date"),
    }


def _leaderboard_single_name(client) -> Optional[str]:
    """Pick first non-index ticker from leaderboard (live or cache)."""
    try:
        rows = client.get_top_positions(limit=20) or []
    except Exception as exc:
        logger.warning("leaderboard single-name lookup failed: %s", exc)
        return None
    indexish = {"SPY", "QQQ", "IWM", "DIA", "VOO", "IVV", "SPX", "NDX"}
    for p in rows:
        t = getattr(p, "ticker", None) or (p.get("ticker") if isinstance(p, dict) else None)
        if t and str(t).upper() not in indexish:
            return str(t).upper()
    return None


def fetch_darkpool_universe(regime_tier: int = 1) -> List[dict]:
    """
    Sellable-universe attempt: SPY + QQQ + 1 single-name from leaderboard.
    Missing tickers are omitted (caller records HARD BLOCK reasons).

    When SPY itself is PAYWALL_FALLBACK, skip QQQ/single-name probes — they
    share the same Pro gate and only burn the /signals parallel budget.
    """
    out: List[dict] = []
    spy_sigs = fetch_darkpool_signals(symbol="SPY", regime_tier=regime_tier)
    out.extend(spy_sigs)

    spy_fresh = (spy_sigs[0].get("data_freshness") if spy_sigs else None)
    if spy_fresh == "PAYWALL_FALLBACK":
        logger.warning(
            "universe HARD BLOCK QQQ + single-name: SPY DarkPoolTrend is "
            "PAYWALL_FALLBACK (AXLFI Pro required for /darkpools/ticker)"
        )
        return out

    for sym in ("QQQ",):
        out.extend(fetch_darkpool_signals(symbol=sym, regime_tier=regime_tier))

    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

        client = StockgridClient(cache_ttl=300)
        single = _leaderboard_single_name(client)
        if single and single not in ("SPY", "QQQ"):
            out.extend(fetch_darkpool_signals(symbol=single, regime_tier=regime_tier))
    except Exception as exc:
        logger.warning("universe leaderboard probe failed: %s", exc)

    return out


def fetch_darkpool_signals(symbol: str = "SPY", regime_tier: int = 1) -> List[dict]:
    """Generate signals from 5-day dark pool position trend.

    Returns empty list on any failure — never crashes, never fakes.
    """
    results: List[dict] = []
    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

        client = StockgridClient(cache_ttl=300)
        raw = client.get_ticker_detail_raw(symbol, window=10)
        fetch_meta = dict(getattr(client, "last_fetch_meta", {}) or {})
        if not raw:
            logger.warning(
                "darkpool_source: no data for %s (meta=%s)", symbol, fetch_meta
            )
            return results

        dp_data = raw.get("individual_dark_pool_position_data", {})
        positions = dp_data.get("dp_position", [])
        dates = dp_data.get("dates", [])

        if len(positions) < 5 or len(dates) < 5:
            logger.warning(
                "darkpool_source: insufficient DP history for %s (%s days)",
                symbol,
                len(positions),
            )
            return results

        # ── 5-day trend (the REAL signal) ──────────────────────────────────
        trend_5d = positions[-5:]
        start, end = trend_5d[0], trend_5d[-1]

        dp_improving = end > start
        direction = "LONG" if dp_improving else "SHORT"

        # VELOCITY — continuous, not tiered
        velocity = abs((end - start) / abs(start)) * 100 if start != 0 else 0

        # ── Price divergence detection ─────────────────────────────────────
        price_data = raw.get("prices", {})
        prices = price_data.get("prices", [])  # AXLFI key is "prices" not "close"
        price_start = 0.0
        price_end = 0.0
        price_change = 0.0
        is_divergent = False

        if prices and len(prices) >= 5:
            price_start = float(prices[-5])
            price_end = float(prices[-1])
            if price_start > 0:
                price_change = ((price_end - price_start) / price_start) * 100
            price_falling = price_end < price_start
            is_divergent = (dp_improving and price_falling) or (
                not dp_improving and not price_falling
            )

        # ── Dynamic confidence — continuous math ───────────────────────────
        base_confidence = min(50 + velocity * 2, 90)
        if is_divergent:
            base_confidence = min(base_confidence + 10, 95)

        # ── PUBLIC enrichment (walls + SI + clusters) — no Pro required ───
        # Walls already shipped in #16 via get_option_walls_today; do not re-add.
        # Short-interest + clusters labeled LIVE only on HTTP 200.
        key_levels: Dict[str, Any] = {}
        walls_meta: Dict[str, Any] = {}
        public_enrichment: Dict[str, Any] = {}
        try:
            from backend.app.signals.sources.public_enrichment import (
                fetch_public_enrichment,
            )

            enrich_sym = symbol if symbol in ("SPY", "QQQ", "IWM") else "SPY"
            public_enrichment = fetch_public_enrichment(client, enrich_sym)
            walls_layer = (public_enrichment.get("layers") or {}).get(
                "options_walls"
            ) or {}
            if walls_layer.get("live_ok"):
                key_levels = {
                    "call_wall": walls_layer.get("call_wall"),
                    "put_wall": walls_layer.get("put_wall"),
                    "poc": walls_layer.get("poc"),
                    "walls_as_of": walls_layer.get("as_of")
                    or walls_layer.get("as_of_date"),
                    "walls_fetch": walls_layer.get("source"),
                    "walls_http_status": walls_layer.get("http_status"),
                    "walls_freshness": "LIVE",
                }
                walls_meta = {
                    "http_status": walls_layer.get("http_status"),
                    "source": walls_layer.get("source"),
                    "paywall": False,
                }
            else:
                # Fallback: existing #16 today helper (still public, not Pro)
                try:
                    walls = client.get_option_walls_today(enrich_sym)
                    walls_meta = dict(getattr(client, "last_fetch_meta", {}) or {})
                    if walls:
                        key_levels = {
                            "call_wall": walls.call_wall,
                            "put_wall": walls.put_wall,
                            "poc": walls.poc,
                            "walls_as_of": getattr(walls, "date", None),
                            "walls_fetch": walls_meta.get("source"),
                            "walls_http_status": walls_meta.get("http_status"),
                            "walls_freshness": (
                                "LIVE"
                                if walls_meta.get("http_status") == 200
                                and walls_meta.get("source") in ("live", "browser")
                                else "UNAVAILABLE"
                            ),
                        }
                except Exception as wall_exc:
                    logger.debug("Option walls fallback unavailable: %s", wall_exc)
        except Exception as enrich_exc:
            logger.debug("public enrichment unavailable: %s", enrich_exc)
            try:
                wall_symbol = symbol if symbol in ("SPY", "QQQ", "IWM") else "SPY"
                walls = client.get_option_walls_today(wall_symbol)
                walls_meta = dict(getattr(client, "last_fetch_meta", {}) or {})
                if walls:
                    key_levels = {
                        "call_wall": walls.call_wall,
                        "put_wall": walls.put_wall,
                        "poc": walls.poc,
                        "walls_as_of": getattr(walls, "date", None),
                        "walls_fetch": walls_meta.get("source"),
                    }
            except Exception as wall_exc:
                logger.debug(f"Option walls unavailable: {wall_exc}")

        # ── GEX Layer 2 — prefer last compute_kill_chain snapshot (stamped) else live canonical
        gex_data: Dict[str, Any] = {}
        try:
            from backend.app.signals.canonical_state import get_stamped_gex_for_symbol
            from backend.app.utils.gex_canonical import canonical_gex_as_dict

            gex_symbol = symbol if symbol in ("SPY", "QQQ", "IWM") else "SPY"
            gex_data = get_stamped_gex_for_symbol(gex_symbol, max_age_sec=600) or canonical_gex_as_dict(
                gex_symbol
            )
            gf = gex_data.get("gamma_flip")
            mp = gex_data.get("max_pain")
            if gf and gf != 0.0:
                key_levels["gamma_flip"] = gf
            key_levels["max_pain"] = mp

            regime = gex_data.get("gamma_regime") or ""
            if regime == "NEGATIVE" and direction == "SHORT":
                base_confidence = min(base_confidence + 5, 95)
            elif regime == "POSITIVE" and direction == "LONG":
                base_confidence = min(base_confidence + 3, 95)

            if gf == 0.0:
                logger.warning("GEX gamma_flip is 0.0 for %s — may be uncomputed", gex_symbol)
        except Exception as gex_exc:
            logger.warning(f"GEX Layer 2 unavailable: {gex_exc}")

        # ── Inputs for sellable pack ───────────────────────────────────────
        summary = raw.get("summary") or {}
        latest = raw.get("latest") or {}
        sv_rows = (raw.get("individual_short_volume_table") or {}).get("data") or []
        last_sv = sv_rows[-1] if sv_rows else {}
        dp_pct = float(
            summary.get("short_pct")
            or latest.get("short_volume_pct")
            or last_sv.get("short_volume_pct")
            or 0
        )
        position_notional = float(
            summary.get("position_usd")
            or latest.get("dp_position_dollars")
            or (positions[-1] if positions else 0)
            or 0
        )
        # buy/sell proxy from net vs short — honest, not invented consensus
        net_vol = float(last_sv.get("net_short_volume") or summary.get("net_volume") or 0)
        short_vol = float(last_sv.get("short_volume") or 0)
        total_vol = float(last_sv.get("total_volume") or 0)
        buy_vol = max(total_vol - short_vol, 0.0)
        buy_sell_ratio = round(buy_vol / short_vol, 3) if short_vol > 0 else None

        # Top battlegrounds: nearest wall levels as institutional magnets (honest proxy)
        battlegrounds = []
        for name, px in (
            ("call_wall", key_levels.get("call_wall")),
            ("put_wall", key_levels.get("put_wall")),
            ("poc", key_levels.get("poc")),
        ):
            if px:
                battlegrounds.append({"name": name, "price": px})

        # ── Freshness ──────────────────────────────────────────────────────
        as_of_raw = raw.get("as_of_date") or dates[-1]
        as_of_date = _parse_as_of(as_of_raw)
        as_of_emit = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        age_hours = None
        if as_of_date:
            # Age from end of as_of session (16:00 ET) to emit time
            try:
                from zoneinfo import ZoneInfo

                et = ZoneInfo("America/New_York")
                as_of_close = datetime.combine(as_of_date, dtime(16, 0), tzinfo=et)
                age_hours = round(
                    (datetime.now(et) - as_of_close).total_seconds() / 3600.0, 2
                )
            except Exception:
                age_hours = None
        data_freshness = _classify_freshness(as_of_date, fetch_meta)

        # ── Reasoning chain — min 6 sequential elements ────────────────────
        reasoning_chain = [
            f"Regime Tier {regime_tier}: {'longs permitted' if regime_tier < 3 else 'longs suppressed'}",
            f"DP 5d trend: {start:,.0f} → {end:,.0f} block position (AXLFI) ({velocity:.1f}% {'accumulation' if dp_improving else 'distribution'})",
            f"Price 5d: ${price_start:.2f} → ${price_end:.2f} ({price_change:+.1f}%)"
            if price_start > 0
            else "Price: unavailable",
            f"Divergence: {'YES — institutional accumulation detected' if is_divergent else 'NO — DP and price aligned'}",
            f"Freshness: {data_freshness} (as_of_data={as_of_raw}, fetch={fetch_meta.get('source')}, http={fetch_meta.get('http_status')})",
        ]
        if gex_data:
            gex_net = gex_data.get("net_gex") or 0
            gf = gex_data.get("gamma_flip")
            mp = gex_data.get("max_pain")
            gf_s = f"{float(gf):.0f}" if gf is not None else "—"
            mp_s = f"{float(mp):.0f}" if mp is not None else "—"
            reasoning_chain.append(
                f"GEX: {gex_data.get('gamma_regime', '?')} ({gex_net:+,.0f}), "
                f"gamma_flip={gf_s}, max_pain={mp_s}"
            )
        if key_levels:
            reasoning_chain.append(
                f"Option floor: put_wall ${key_levels.get('put_wall', 0)}, call_wall ${key_levels.get('call_wall', 0)}"
            )
        reasoning_chain.append(
            f"Confluence: {direction} @ velocity {velocity:.1f}% → confidence {base_confidence:.1f}%"
        )

        # ── Invalidation conditions (falsifiable next RTH) ─────────────────
        invalidation_conditions = [
            "DP trend reverses (velocity drops below 5%) on next T+1 FINRA/AXLFI print",
            "Regime upgrades to Tier 3+",
            f"Live Pro darkpools as_of advances and 5d trend flips vs {direction}",
        ]
        if direction == "LONG":
            invalidation_conditions.append(
                f"Price breaks below put_wall ${key_levels.get('put_wall', 0)} in next RTH session"
            )
        else:
            invalidation_conditions.append(
                f"Price breaks above call_wall ${key_levels.get('call_wall', 0)} in next RTH session"
            )

        # ── Dynamic entry / stop / target ──────────────────────────────────
        entry = price_end if price_end > 0 else 0
        if direction == "LONG":
            stop = round(entry * 0.993, 2) if entry else 0
            target = round(entry * 1.015, 2) if entry else 0
        else:
            stop = round(entry * 1.007, 2) if entry else 0
            target = round(entry * 0.985, 2) if entry else 0

        risk = abs(entry - stop) if entry else 0
        reward = abs(target - entry) if entry else 0
        rr = round(reward / risk, 1) if risk > 0 else 0

        entry_low = stop
        entry_high = round(entry * 1.005, 2) if entry else 0
        entry_note = (
            f"Entry valid within ${entry_low}–${entry_high} range. "
            f"Above ${entry_high} — wait for pullback. "
            f"NOT an RTH fire — data_freshness={data_freshness}."
        ) if entry else "Entry price unavailable"

        signal = {
            "id": f"dp_trend_{symbol}_{dates[-1]}",
            "symbol": symbol,
            "type": "darkpool_trend",
            "strategy": "DarkPoolTrend",
            "action": direction,
            "confidence": round(base_confidence, 1),
            "entry_price": round(entry, 2),
            "entry_note": entry_note,
            "stop_price": stop,
            "target_price": target,
            "risk_reward": rr,
            "reasoning": reasoning_chain,
            "reasoning_chain": reasoning_chain,
            "invalidation_conditions": invalidation_conditions,
            "dp_trend_velocity": round(velocity, 1),
            "key_levels": key_levels,
            "gex": gex_data,
            "warnings": [],
            "timestamp": datetime.now().isoformat(),
            "signal_generated_at": f"{as_of_raw} EOD (NOT RTH fire)",
            "as_of_data": str(as_of_raw),
            "as_of_emit": as_of_emit,
            "age_hours": age_hours,
            "data_freshness": data_freshness,
            "fetch_meta": fetch_meta,
            "inputs": {
                "dp_pct": dp_pct,
                "position_notional": position_notional,
                "battlegrounds": battlegrounds[:3],
                "buy_sell_ratio": buy_sell_ratio,
                "net_short_volume": net_vol,
                "walls_summary": {
                    "call_wall": key_levels.get("call_wall"),
                    "put_wall": key_levels.get("put_wall"),
                    "poc": key_levels.get("poc"),
                    "walls_as_of": key_levels.get("walls_as_of"),
                    "walls_fetch": key_levels.get("walls_fetch"),
                    "walls_freshness": key_levels.get("walls_freshness"),
                    "walls_http_status": key_levels.get("walls_http_status"),
                },
                "short_interest_summary": _public_layer_summary(
                    public_enrichment, "short_interest"
                ),
                "clusters_summary": _public_layer_summary(
                    public_enrichment, "clusters"
                ),
                "market_update_summary": _public_layer_summary(
                    public_enrichment, "market_update"
                ),
            },
            "public_enrichment": public_enrichment,
            "source": "DarkPoolTrend",
            "is_master": base_confidence >= 70,
            "persisted": False,
            "alerts_history_row_id": None,
            "persist_reason": None,
        }

        if data_freshness != "LIVE":
            signal["warnings"].append(
                f"DATA {data_freshness}: as_of_data={as_of_raw} — NOT a fresh RTH fire"
            )
            # Honesty: never claim darkpools LIVE when freshness is PAYWALL/CACHE
            if data_freshness == "PAYWALL_FALLBACK":
                signal["warnings"].append(
                    "DARKPOOLS HARD_BLOCK / PAYWALL_FALLBACK — Pro cookie + "
                    "HTTP 200 required; public walls/SI/clusters may still be LIVE"
                )

        ok, row_id, reason = _persist_to_alerts_history(signal)
        signal["persisted"] = ok
        signal["alerts_history_row_id"] = row_id
        signal["persist_reason"] = reason

        results.append(signal)

    except Exception as exc:
        logger.warning(f"fetch_darkpool_signals failed for {symbol}: {exc}")

    return results
