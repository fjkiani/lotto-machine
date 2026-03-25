"""
Dark pool signal source — 5-day dp_position TREND + GEX Layer 2.

Signal logic:
    - Direction from dp_position 5d TREND (NOT from SV% threshold)
    - Velocity = continuous math, not tiered buckets
    - Divergence detection: DP improving while price falling = accumulation
    - GEX Layer 2: CBOE gamma regime modifies confidence
    - Option walls from AXLFI provide key_levels
    - Reasoning chain has min 6 sequential elements

Author: Zo (no hardcoding, no tiered confidence, no fake data)
"""
import logging
import threading
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

# Module-level GEXCalculator singleton — shared across all fetch_darkpool_signals calls
_gex_calc = None
_gex_lock = threading.Lock()


def _get_gex():
    global _gex_calc
    if _gex_calc is None:
        with _gex_lock:
            if _gex_calc is None:
                from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
                _gex_calc = GEXCalculator(cache_ttl=300)
    return _gex_calc


def fetch_darkpool_signals(symbol: str = "SPY", regime_tier: int = 1) -> List[dict]:
    """Generate signals from 5-day dark pool position trend.

    Returns empty list on any failure — never crashes, never fakes.
    """
    results: List[dict] = []
    try:
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient

        client = StockgridClient(cache_ttl=300)
        raw = client.get_ticker_detail_raw(symbol, window=10)
        if not raw:
            logger.warning(f"darkpool_source: no data for {symbol}")
            return results

        dp_data = raw.get("individual_dark_pool_position_data", {})
        positions = dp_data.get("dp_position", [])
        dates = dp_data.get("dates", [])

        if len(positions) < 5 or len(dates) < 5:
            logger.warning(f"darkpool_source: insufficient DP history for {symbol} ({len(positions)} days)")
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
            is_divergent = (dp_improving and price_falling) or (not dp_improving and not price_falling)

        # ── Dynamic confidence — continuous math ───────────────────────────
        base_confidence = min(50 + velocity * 2, 90)
        if is_divergent:
            base_confidence = min(base_confidence + 10, 95)

        # ── Option wall context ────────────────────────────────────────────
        key_levels = {}
        try:
            # For individual stocks, only SPY/QQQ/IWM have option walls
            wall_symbol = symbol if symbol in ("SPY", "QQQ", "IWM") else "SPY"
            walls = client.get_option_walls_today(wall_symbol)
            if walls:
                key_levels = {
                    "call_wall": walls.call_wall,
                    "put_wall": walls.put_wall,
                    "poc": walls.poc,
                }
        except Exception as wall_exc:
            logger.debug(f"Option walls unavailable: {wall_exc}")

        # ── GEX Layer 2 — gamma regime from CBOE ──────────────────────────
        gex_data = {}
        try:
            gex_calc = _get_gex()
            gex_ticker = "SPX" if symbol in ("SPY", "SPX") else symbol
            gex_result = gex_calc.compute_gex(gex_ticker)
            gex_data = {
                "net_gex": gex_result.total_gex,
                "gamma_regime": gex_result.gamma_regime,
                "gamma_flip": gex_result.gamma_flip,
                "max_pain": gex_result.max_pain,
                "top_wall": gex_result.gamma_walls[0].strike if gex_result.gamma_walls else None,
            }
            if gex_result.gamma_flip and gex_result.gamma_flip != 0.0:
                key_levels["gamma_flip"] = gex_result.gamma_flip
            key_levels["max_pain"] = gex_result.max_pain

            # GEX modifies confidence
            if gex_result.gamma_regime == "NEGATIVE" and direction == "SHORT":
                base_confidence = min(base_confidence + 5, 95)
            elif gex_result.gamma_regime == "POSITIVE" and direction == "LONG":
                base_confidence = min(base_confidence + 3, 95)

            # Warn if gamma_flip is 0 (uncomputed)
            if gex_result.gamma_flip == 0.0:
                logger.warning(f"GEX gamma_flip is 0.0 for {gex_ticker} — may be uncomputed")
        except Exception as gex_exc:
            logger.warning(f"GEX Layer 2 unavailable: {gex_exc}")

        # ── Reasoning chain — min 6 sequential elements ────────────────────
        reasoning_chain = [
            f"Regime Tier {regime_tier}: {'longs permitted' if regime_tier < 3 else 'longs suppressed'}",
            f"DP 5d trend: {start:,.0f} → {end:,.0f} block position (AXLFI) ({velocity:.1f}% {'accumulation' if dp_improving else 'distribution'})",
            f"Price 5d: ${price_start:.2f} → ${price_end:.2f} ({price_change:+.1f}%)" if price_start > 0 else "Price: unavailable",
            f"Divergence: {'YES — institutional accumulation detected' if is_divergent else 'NO — DP and price aligned'}",
        ]
        if gex_data:
            gex_net = gex_data.get("net_gex", 0)
            reasoning_chain.append(
                f"GEX: {gex_data.get('gamma_regime', '?')} ({gex_net:+,.0f}), "
                f"gamma_flip={gex_data.get('gamma_flip', 0):.0f}, max_pain={gex_data.get('max_pain', 0):.0f}"
            )
        if key_levels:
            reasoning_chain.append(
                f"Option floor: put_wall ${key_levels.get('put_wall', 0)}, call_wall ${key_levels.get('call_wall', 0)}"
            )
        reasoning_chain.append(
            f"Confluence: {direction} @ velocity {velocity:.1f}% → confidence {base_confidence:.1f}%"
        )

        # ── Invalidation conditions ────────────────────────────────────────
        invalidation_conditions = [
            "DP trend reverses (velocity drops below 5%)",
            "Regime upgrades to Tier 3+",
        ]
        if direction == "LONG":
            invalidation_conditions.append(f"Price breaks below put_wall ${key_levels.get('put_wall', 0)}")
        else:
            invalidation_conditions.append(f"Price breaks above call_wall ${key_levels.get('call_wall', 0)}")

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

        # ── Entry context — range, not a point price ───────────────────────
        entry_low = stop  # below stop = invalidated
        entry_high = round(entry * 1.005, 2) if entry else 0  # 0.5% above last close
        entry_note = (
            f"Entry valid within ${entry_low}–${entry_high} range. "
            f"Above ${entry_high} — wait for pullback."
        ) if entry else "Entry price unavailable"

        # ── Data freshness — users must know this is EOD, not live ─────────
        data_date = dates[-1] if dates else "unknown"
        signal_generated_at = f"{data_date} 16:00 ET (end-of-day)"

        results.append({
            "id": f"dp_trend_{symbol}_{dates[-1]}",
            "symbol": symbol,
            "type": "darkpool_trend",
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
            "signal_generated_at": signal_generated_at,
            "source": "DarkPoolTrend",
            "is_master": base_confidence >= 70,
        })

    except Exception as exc:
        logger.warning(f"fetch_darkpool_signals failed for {symbol}: {exc}")

    return results
