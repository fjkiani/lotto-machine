#!/usr/bin/env python3
"""
📡 Signal Intelligence Engine — Automates the manager's tactical questions.

One call returns:
  1. SPY position vs call wall (when did it cross, grinding up or down?)
  2. QQQ/SPY short vol trend (rising = loading, falling = done)
  3. Bull signal tickers DP profile (SV%, position, bias)
  4. Intraday volume profile (sustained = accumulation, dried = distribution)
  5. Close defense check (last 15 min vol + price vs wall)
  6. Monday verdict

Author: Zo (Alpha's AI)
"""

import logging
from datetime import datetime, date
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class SignalIntelEngine:
    """Generates complete signal intelligence report in one call."""

    def __init__(self):
        self._cache = {}

    def generate_report(self, call_wall: float = None) -> Dict[str, Any]:
        """Full tactical intelligence report. One call, all answers."""
        import yfinance as yf
        import numpy as np

        report = {
            "timestamp": datetime.now().isoformat(),
            "date": date.today().isoformat(),
        }

        # ── Get option walls from Stockgrid ──────────────────────────
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            client = StockgridClient(cache_ttl=120)
        except Exception as e:
            logger.error(f"StockgridClient init failed: {e}")
            client = None

        walls = {}
        if client:
            for sym in ["SPY", "QQQ", "IWM"]:
                try:
                    w = client.get_option_walls_today(sym)
                    if w:
                        walls[sym] = {
                            "call_wall": w.call_wall,
                            "put_wall": w.put_wall,
                            "poc": w.poc,
                        }
                except Exception:
                    pass

        spy_call_wall = call_wall or walls.get("SPY", {}).get("call_wall", 0)
        report["walls"] = walls
        report["spy_call_wall"] = spy_call_wall

        # ── Q1: SPY vs Call Wall — Intraday Timeline ─────────────────
        try:
            spy_ticker = yf.Ticker("SPY")
            intraday_5m = spy_ticker.history(period="1d", interval="5m")
            intraday_1m = spy_ticker.history(period="1d", interval="1m")

            if len(intraday_5m) > 0 and spy_call_wall > 0:
                opens_above = intraday_5m["Close"].iloc[0] > spy_call_wall
                current = intraday_5m["Close"].iloc[-1]
                delta = current - spy_call_wall

                # Find cross events
                crosses = []
                for i in range(1, len(intraday_5m)):
                    prev = intraday_5m["Close"].iloc[i - 1]
                    curr = intraday_5m["Close"].iloc[i]
                    ts = intraday_5m.index[i].strftime("%H:%M")
                    if prev <= spy_call_wall < curr:
                        crosses.append({"time": ts, "direction": "ABOVE", "from": round(float(prev), 2), "to": round(float(curr), 2)})
                    elif prev >= spy_call_wall > curr:
                        crosses.append({"time": ts, "direction": "BELOW", "from": round(float(prev), 2), "to": round(float(curr), 2)})

                # Session high/low vs wall
                session_high = float(intraday_5m["High"].max())
                session_low = float(intraday_5m["Low"].min())

                # Trend: grinding up or down from open?
                open_delta = float(intraday_5m["Close"].iloc[0]) - spy_call_wall
                close_delta = float(current) - spy_call_wall
                if open_delta > close_delta + 1:
                    wall_trend = "GRINDING_DOWN_TOWARD_WALL"
                elif close_delta > open_delta + 1:
                    wall_trend = "BREAKING_AWAY_FROM_WALL"
                else:
                    wall_trend = "HOLDING_NEAR_WALL"

                report["spy_vs_wall"] = {
                    "opened_above": opens_above,
                    "current_price": round(float(current), 2),
                    "delta_from_wall": round(float(delta), 2),
                    "open_price": round(float(intraday_5m["Close"].iloc[0]), 2),
                    "session_high": round(session_high, 2),
                    "session_low": round(session_low, 2),
                    "crosses": crosses,
                    "cross_count": len(crosses),
                    "trend": wall_trend,
                    "read": (
                        "Opened above wall, grinding down toward it" if opens_above and wall_trend == "GRINDING_DOWN_TOWARD_WALL"
                        else "Opened above wall, holding" if opens_above
                        else "Crossed above during session" if any(c["direction"] == "ABOVE" for c in crosses)
                        else "Below wall all session"
                    ),
                }
        except Exception as e:
            report["spy_vs_wall"] = {"error": str(e)}

        # ── Q2: QQQ + SPY Short Vol Trend ────────────────────────────
        try:
            if client:
                for sym in ["QQQ", "SPY"]:
                    raw = client.get_ticker_detail_raw(sym, window=10)
                    if raw:
                        sv_raw = raw.get("individual_short_volume_table", {})
                        items = sv_raw.get("data", []) if isinstance(sv_raw, dict) else sv_raw if isinstance(sv_raw, list) else []
                        sorted_items = sorted(items, key=lambda x: x.get("date", ""))

                        trend_data = []
                        prev_sv = None
                        for row in sorted_items[-5:]:
                            sv = float(row.get("short_volume_pct", row.get("short_volume%", 0)) or 0)
                            if sv <= 1.0:
                                sv *= 100
                            change = round(sv - prev_sv, 1) if prev_sv is not None else None
                            trend_data.append({
                                "date": row.get("date", "?"),
                                "sv_pct": round(sv, 1),
                                "change": change,
                                "short_volume": int(row.get("short_volume", 0) or 0),
                            })
                            prev_sv = sv

                        if len(trend_data) >= 2:
                            latest = trend_data[-1]["sv_pct"]
                            prev = trend_data[-2]["sv_pct"]
                            if latest > prev + 1:
                                direction = "RISING"
                                read = "absorption ACCELERATING — institutions still loading"
                            elif latest < prev - 1:
                                direction = "FALLING"
                                read = "institutions DONE loading — positions built"
                            else:
                                direction = "FLAT"
                                read = "steady state, no change in institutional behavior"
                        else:
                            direction = "UNKNOWN"
                            read = "insufficient data"

                        report[f"{sym.lower()}_sv_trend"] = {
                            "direction": direction,
                            "latest": trend_data[-1] if trend_data else None,
                            "trend": trend_data,
                            "read": read,
                        }
        except Exception as e:
            report["sv_trend_error"] = str(e)

        # ── Q3: Bull Signal Tickers DP Profile ───────────────────────
        try:
            if client:
                # Get current bull signals from signal differ
                bull_tickers = []
                try:
                    from live_monitoring.enrichment.apis.axlfi_signal_differ import AXLFISignalDiffer
                    sd = AXLFISignalDiffer()
                    latest = sd.get_latest()
                    bull_tickers = latest.get("bullish", [])
                except Exception:
                    bull_tickers = ["AMAT", "LRCX", "MU", "ODFL", "STX", "WDC"]  # fallback

                ticker_intel = {}
                for t in bull_tickers[:10]:
                    try:
                        dp = client.get_ticker_latest(t)
                        if dp:
                            sv = dp.short_volume_pct
                            if sv > 55:
                                bias = "HEAVY_SHORT_VOL"
                            elif sv > 50:
                                bias = "ELEVATED"
                            elif sv > 45:
                                bias = "NEUTRAL"
                            else:
                                bias = "LOW_SHORT_VOL_BULLISH"

                            ticker_intel[t] = {
                                "sv_pct": round(sv, 1),
                                "dp_position_dollars": dp.dp_position_dollars,
                                "bias": bias,
                                "date": dp.date,
                            }
                    except Exception:
                        pass

                report["bull_signals"] = {
                    "tickers": bull_tickers,
                    "count": len(bull_tickers),
                    "intel": ticker_intel,
                    "note": "AXLFI does not provide individual stock option walls — DP flow only",
                }
        except Exception as e:
            report["bull_signals"] = {"error": str(e)}

        # ── Q4: Volume Profile — Sustained or Dried Up ───────────────
        try:
            if len(intraday_5m) > 0:
                vols = intraday_5m["Volume"].values
                closes = intraday_5m["Close"].values

                total_vol = int(sum(vols))
                first_hour_bars = min(12, len(vols))
                first_hour_vol = int(sum(vols[:first_hour_bars]))
                rest_vol = int(sum(vols[first_hour_bars:]))
                ratio = first_hour_vol / rest_vol if rest_vol > 0 else 999

                # 30-min buckets
                buckets = []
                times = [idx.strftime("%H:%M") for idx in intraday_5m.index]
                bucket_map = {}
                for i, t in enumerate(times):
                    h = int(t[:2])
                    m = int(t[3:5])
                    key = f"{h:02d}:{(m // 30) * 30:02d}"
                    if key not in bucket_map:
                        bucket_map[key] = {"vol": 0, "count": 0}
                    bucket_map[key]["vol"] += int(vols[i])
                    bucket_map[key]["count"] += 1

                for k in sorted(bucket_map.keys()):
                    pct = bucket_map[k]["vol"] / total_vol * 100 if total_vol > 0 else 0
                    buckets.append({"period": k, "volume": bucket_map[k]["vol"], "pct_total": round(pct, 1)})

                if ratio > 1.5:
                    pattern = "DISTRIBUTION"
                    read = "Volume dried up — front-loaded, distribution pattern"
                elif ratio > 1.0:
                    pattern = "FRONT_LOADED"
                    read = "Moderate decay, watch for late squeeze"
                else:
                    pattern = "ACCUMULATION"
                    read = "Sustained volume — accumulation, not distribution"

                report["volume_profile"] = {
                    "total": total_vol,
                    "first_hour": first_hour_vol,
                    "first_hour_pct": round(first_hour_vol / total_vol * 100, 1) if total_vol > 0 else 0,
                    "rest_of_day": rest_vol,
                    "front_back_ratio": round(ratio, 2),
                    "pattern": pattern,
                    "read": read,
                    "buckets": buckets,
                }
        except Exception as e:
            report["volume_profile"] = {"error": str(e)}

        # ── Q5: Close Defense (last 15 min) ──────────────────────────
        try:
            if len(intraday_1m) > 0 and spy_call_wall > 0:
                last15 = intraday_1m.tail(15)
                close_vol = int(last15["Volume"].sum())
                avg_15m_vol = int(intraday_1m["Volume"].rolling(15).sum().mean())
                vol_ratio = close_vol / avg_15m_vol if avg_15m_vol > 0 else 0

                below_wall = any(last15["Close"] < spy_call_wall)
                min_price = float(last15["Close"].min())
                max_price = float(last15["Close"].max())
                close_price = float(last15["Close"].iloc[-1])

                # Last bar volume (most important)
                last_bar_vol = int(intraday_1m["Volume"].iloc[-1])

                if not below_wall and vol_ratio > 1.3:
                    defense = "DEFENDED"
                    read = "Wall defended with heavy volume. Next session opens as BUY above wall."
                elif below_wall:
                    defense = "BREACHED"
                    read = "Wall breached during close. Next session opens as TRAP — watch for gap down."
                elif vol_ratio < 0.7:
                    defense = "ABANDONED"
                    read = "Volume dried up near wall. No institutional conviction. COIN FLIP."
                else:
                    defense = "HELD"
                    read = "Wall held but volume normal. Cautious optimism."

                report["close_defense"] = {
                    "wall": spy_call_wall,
                    "close_price": round(close_price, 2),
                    "delta": round(close_price - spy_call_wall, 2),
                    "below_wall_during_close": below_wall,
                    "close_15m_volume": close_vol,
                    "avg_15m_volume": avg_15m_vol,
                    "vol_ratio": round(vol_ratio, 2),
                    "last_bar_volume": last_bar_vol,
                    "min_price": round(min_price, 2),
                    "max_price": round(max_price, 2),
                    "defense": defense,
                    "read": read,
                }
        except Exception as e:
            report["close_defense"] = {"error": str(e)}

        # ── VERDICT ──────────────────────────────────────────────────
        try:
            signals = []
            # Wall defense
            cd = report.get("close_defense", {})
            if cd.get("defense") == "DEFENDED":
                signals.append(("BULLISH", "Wall defended with heavy close volume"))
            elif cd.get("defense") == "BREACHED":
                signals.append(("BEARISH", "Wall breached during close"))

            # Volume profile
            vp = report.get("volume_profile", {})
            if vp.get("pattern") == "ACCUMULATION":
                signals.append(("BULLISH", "Sustained volume = accumulation"))
            elif vp.get("pattern") == "DISTRIBUTION":
                signals.append(("BEARISH", "Volume dried up = distribution"))

            # SV trend
            qqq = report.get("qqq_sv_trend", {})
            if qqq.get("direction") == "RISING":
                signals.append(("BULLISH", "QQQ absorption accelerating"))
            elif qqq.get("direction") == "FALLING":
                signals.append(("CAUTION", "QQQ institutions done loading"))

            # Wall position
            svw = report.get("spy_vs_wall", {})
            if svw.get("trend") == "GRINDING_DOWN_TOWARD_WALL":
                signals.append(("CAUTION", "SPY grinding down toward call wall"))
            elif svw.get("trend") == "BREAKING_AWAY_FROM_WALL":
                signals.append(("BULLISH", "SPY breaking away from call wall"))

            bullish = sum(1 for s in signals if s[0] == "BULLISH")
            bearish = sum(1 for s in signals if s[0] == "BEARISH")
            caution = sum(1 for s in signals if s[0] == "CAUTION")

            if bullish >= 3:
                verdict = "STRONG_BUY"
            elif bullish >= 2 and bearish == 0:
                verdict = "BUY"
            elif bearish >= 2:
                verdict = "SELL"
            elif caution >= 2:
                verdict = "CAUTION"
            else:
                verdict = "NEUTRAL"

            report["verdict"] = {
                "signal": verdict,
                "bullish_count": bullish,
                "bearish_count": bearish,
                "caution_count": caution,
                "signals": [{"bias": s[0], "reason": s[1]} for s in signals],
            }
        except Exception as e:
            report["verdict"] = {"error": str(e)}

        return report
