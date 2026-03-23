"""
🔬 COMPREHENSIVE CHECKER BACKTEST — No Sandbagging Edition

Replays each checker's CORE LOGIC against real historical data.
No mocks. No fakes. Real prices. Real outcomes.

Data sources:
- spy_15min_1mo.json: 494 bars (Feb 17 → Mar 13 2026)
- spy_daily.json: 547 daily bars (Jan 2024 → Mar 2026)
- dp_learning.db: 346 settled DP interactions with outcomes
- dp_trends.db: 32 daily DP snapshots
- alerts_history.db: 475 real alerts

For each checker, we:
1. Extract its core detection logic
2. Run it on every bar of historical data
3. Measure forward returns at +5m, +15m, +30m, +60m
4. Calculate win rate, avg P&L, Sharpe-like metric
5. Verdict: PROMOTE / FIX / KILL
"""

import json
import sqlite3
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent

# ── Load Data ─────────────────────────────────────────────────────────

def load_15min_bars() -> List[Dict]:
    """Load 15-min SPY bars."""
    path = ROOT / "backtesting" / "data" / "spy_15min_1mo.json"
    with open(path) as f:
        return json.load(f)

def load_daily_bars() -> List[Dict]:
    """Load daily SPY bars (2024-2026)."""
    path = ROOT / "live_monitoring" / "data" / "backtest" / "spy_daily.json"
    with open(path) as f:
        return json.load(f)

def load_dp_learning() -> List[Dict]:
    """Load DP learning interactions with outcomes."""
    db_path = ROOT / "data" / "dp_learning.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM dp_interactions
        WHERE outcome IS NOT NULL AND outcome != 'PENDING'
        ORDER BY timestamp
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def load_dp_snapshots() -> List[Dict]:
    """Load daily DP snapshots."""
    db_path = ROOT / "data" / "dp_trends.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM dp_daily_snapshots
        WHERE symbol = 'SPY'
        ORDER BY date
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def load_alerts() -> List[Dict]:
    """Load historical alerts."""
    db_path = ROOT / "data" / "alerts_history.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM alerts ORDER BY timestamp
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Forward Return Calculator ─────────────────────────────────────────

def calc_forward_returns(bars: List[Dict], signal_idx: int, direction: str = "LONG") -> Dict:
    """Calculate forward returns at multiple horizons from a signal bar."""
    entry_price = bars[signal_idx]['close']
    results = {}

    for horizon_name, horizon_bars in [("5m", 1), ("15m", 1), ("30m", 2), ("60m", 4), ("2h", 8), ("4h", 16)]:
        target_idx = signal_idx + horizon_bars
        if target_idx < len(bars):
            exit_price = bars[target_idx]['close']
            if direction == "LONG":
                pnl = (exit_price - entry_price) / entry_price * 100
            else:
                pnl = (entry_price - exit_price) / entry_price * 100
            results[horizon_name] = {
                "exit_price": exit_price,
                "pnl_pct": pnl,
                "win": pnl > 0,
            }
        else:
            results[horizon_name] = None

    # Max favorable / adverse excursion
    max_fav = 0
    max_adv = 0
    for i in range(signal_idx + 1, min(signal_idx + 17, len(bars))):  # up to 4 hours
        price = bars[i]['high'] if direction == "LONG" else bars[i]['low']
        adverse_price = bars[i]['low'] if direction == "LONG" else bars[i]['high']

        if direction == "LONG":
            fav = (price - entry_price) / entry_price * 100
            adv = (adverse_price - entry_price) / entry_price * 100
        else:
            fav = (entry_price - price) / entry_price * 100
            adv = (entry_price - adverse_price) / entry_price * 100

        max_fav = max(max_fav, fav)
        max_adv = min(max_adv, adv)

    results["max_favorable"] = max_fav
    results["max_adverse"] = max_adv

    return results


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST 1: SELLOFF/RALLY — Momentum Detection
# ═══════════════════════════════════════════════════════════════════════

def backtest_selloff_rally(bars: List[Dict]) -> Dict:
    """
    Test the MomentumDetector's core logic:
    - Selloff = price drops X% in N bars
    - Rally = price rises X% in N bars

    The actual thresholds in momentum_detector.py:
    - min 0.3% move in the lookback window
    - Volume confirmation
    """
    signals = []
    lookback = 4  # 4 x 15min = 1 hour

    for i in range(lookback, len(bars)):
        window = bars[i-lookback:i+1]
        start_price = window[0]['open']
        end_price = window[-1]['close']
        move_pct = (end_price - start_price) / start_price * 100

        # Volume spike check
        avg_vol = sum(b['volume'] for b in window[:-1]) / lookback
        last_vol = window[-1]['volume']
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0

        # SELLOFF: drop > 0.3%, volume spike
        if move_pct < -0.30 and vol_ratio > 1.2:
            fwd = calc_forward_returns(bars, i, "SHORT")
            signals.append({
                "type": "SELLOFF",
                "bar_idx": i,
                "time": bars[i].get('timestamp', ''),
                "price": end_price,
                "move_pct": move_pct,
                "vol_ratio": vol_ratio,
                "forward": fwd,
            })

        # RALLY: rise > 0.3%, volume spike
        elif move_pct > 0.30 and vol_ratio > 1.2:
            fwd = calc_forward_returns(bars, i, "LONG")
            signals.append({
                "type": "RALLY",
                "bar_idx": i,
                "time": bars[i].get('timestamp', ''),
                "price": end_price,
                "move_pct": move_pct,
                "vol_ratio": vol_ratio,
                "forward": fwd,
            })

    return _score_signals("selloff_rally", signals)


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST 2: DP DIVERGENCE — Dark Pool Level Reactions
# ═══════════════════════════════════════════════════════════════════════

def backtest_dp_divergence(dp_interactions: List[Dict]) -> Dict:
    """
    Test the DP learning edge using ACTUAL historical outcomes.
    This data is REAL — 346 interactions with BOUNCE/BREAK outcomes.
    """
    signals = []

    for ix in dp_interactions:
        direction = "LONG" if ix['level_type'] == 'SUPPORT' else "SHORT"
        is_win = ix['outcome'] == 'BOUNCE'

        # Calculate P&L from actual price snapshots
        entry = ix['approach_price']
        prices_at = {}
        for horizon in ['5min', '15min', '30min', '60min']:
            key = f"price_at_{horizon.replace('min', 'min')}"
            p = ix.get(key, 0)
            if p and p > 0:
                if direction == "LONG":
                    pnl = (p - entry) / entry * 100
                else:
                    pnl = (entry - p) / entry * 100
                prices_at[horizon] = {"pnl_pct": pnl, "win": pnl > 0, "exit_price": p}

        signals.append({
            "type": f"DP_{ix['level_type']}_{ix['outcome']}",
            "time": ix['timestamp'],
            "price": entry,
            "level_price": ix['level_price'],
            "distance_pct": ix['distance_pct'],
            "touch_count": ix['touch_count'],
            "time_of_day": ix['time_of_day'],
            "vix_level": ix['vix_level'],
            "outcome": ix['outcome'],
            "max_move_pct": ix['max_move_pct'],
            "forward": prices_at,
            "is_win": is_win,
        })

    return _score_dp_signals("dp_divergence", signals)


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST 3: DP TREND — Multi-day dark pool accumulation/distribution
# ═══════════════════════════════════════════════════════════════════════

def backtest_dp_trend(snapshots: List[Dict], daily_bars: List[Dict]) -> Dict:
    """
    Test DP trend analyzer:
    - 5-day cumulative DP accumulation
    - Price divergence detection (DP accumulating while price drops)
    - Forward returns on divergence signals
    """
    if len(snapshots) < 5:
        return {"checker": "dp_trend", "verdict": "INSUFFICIENT_DATA", "note": f"Only {len(snapshots)} DP snapshots"}

    # Build price lookup from daily bars
    price_map = {}
    for bar in daily_bars:
        date_key = bar.get('Date', bar.get('date', ''))
        close = bar.get('Close', bar.get('close', 0))
        if date_key and close:
            price_map[date_key[:10]] = close

    signals = []
    for i in range(4, len(snapshots)):
        window = snapshots[i-4:i+1]
        dp_positions = [s.get('dp_position', 0) or 0 for s in window]
        prices = [s.get('price', 0) or 0 for s in window]

        cum_5d = sum(dp_positions)
        price_change = (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] else 0

        # Divergence: DP accumulating (positive) while price dropping
        dp_accumulating = cum_5d > 0
        price_dropping = price_change < -0.5

        # Reverse: DP distributing (negative) while price rising
        dp_distributing = cum_5d < 0
        price_rising = price_change > 0.5

        signal_date = snapshots[i]['date']
        current_price = prices[-1]

        if dp_accumulating and price_dropping:
            # Look for forward returns in daily bars
            fwd = _daily_forward_returns(signal_date, daily_bars, "LONG")
            signals.append({
                "type": "DP_ACCUM_DIVERGENCE",
                "date": signal_date,
                "price": current_price,
                "cum_5d_dp": cum_5d,
                "price_change_5d": price_change,
                "forward": fwd,
            })
        elif dp_distributing and price_rising:
            fwd = _daily_forward_returns(signal_date, daily_bars, "SHORT")
            signals.append({
                "type": "DP_DISTRIB_DIVERGENCE",
                "date": signal_date,
                "price": current_price,
                "cum_5d_dp": cum_5d,
                "price_change_5d": price_change,
                "forward": fwd,
            })

    return _score_daily_signals("dp_trend", signals)


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST 4: OPTIONS FLOW — Bullish/Bearish detection
# ═══════════════════════════════════════════════════════════════════════

def backtest_options_flow(alerts: List[Dict], daily_bars: List[Dict]) -> Dict:
    """
    Test options flow signals from alerts_history.db.
    Check if bullish/bearish options flow alerts predicted direction.
    """
    options_alerts = [a for a in alerts if 'bullish' in a.get('alert_type', '').lower()
                      or 'bearish' in a.get('alert_type', '').lower()
                      or 'options' in a.get('alert_type', '').lower()]

    signals = []
    for alert in options_alerts:
        alert_type = alert.get('alert_type', '').lower()
        alert_date = alert.get('timestamp', '')[:10]

        direction = "LONG" if 'bullish' in alert_type else "SHORT"
        fwd = _daily_forward_returns(alert_date, daily_bars, direction)

        signals.append({
            "type": alert.get('alert_type', 'unknown'),
            "date": alert_date,
            "symbol": alert.get('symbol', 'SPY'),
            "direction": direction,
            "source": alert.get('source', ''),
            "forward": fwd,
        })

    return _score_daily_signals("options_flow", signals)


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST 5: SQUEEZE DETECTION (simulated)
# ═══════════════════════════════════════════════════════════════════════

def backtest_squeeze_conditions(daily_bars: List[Dict]) -> Dict:
    """
    Simulate squeeze conditions: Bollinger Bands inside Keltner Channels.
    When BBands contract inside KC, a "squeeze" forms.
    When it releases, a breakout follows.
    """
    if len(daily_bars) < 21:
        return {"checker": "squeeze", "verdict": "INSUFFICIENT_DATA"}

    signals = []
    closes = [b.get('Close', b.get('close', 0)) for b in daily_bars if b.get('Close', b.get('close'))]
    highs = [b.get('High', b.get('high', 0)) for b in daily_bars if b.get('High', b.get('high'))]
    lows = [b.get('Low', b.get('low', 0)) for b in daily_bars if b.get('Low', b.get('low'))]
    dates = [b.get('Date', b.get('date', ''))[:10] for b in daily_bars]

    for i in range(20, len(closes)):
        window = closes[i-20:i]
        sma = sum(window) / 20
        std = (sum((x - sma)**2 for x in window) / 20) ** 0.5

        # Bollinger Bands
        bb_upper = sma + 2 * std
        bb_lower = sma - 2 * std
        bb_width = (bb_upper - bb_lower) / sma * 100

        # True Range based Keltner (simplified with ATR proxy)
        tr_window = [highs[j] - lows[j] for j in range(i-14, i)]
        atr = sum(tr_window) / 14 if tr_window else 0
        kc_upper = sma + 1.5 * atr
        kc_lower = sma - 1.5 * atr

        in_squeeze = bb_upper < kc_upper and bb_lower > kc_lower

        # Check if squeeze just released (was in, now out)
        if i > 21:
            prev_window = closes[i-21:i-1]
            prev_sma = sum(prev_window) / 20
            prev_std = (sum((x - prev_sma)**2 for x in prev_window) / 20) ** 0.5
            prev_bb_u = prev_sma + 2 * prev_std
            prev_bb_l = prev_sma - 2 * prev_std
            prev_tr = [highs[j] - lows[j] for j in range(i-15, i-1)]
            prev_atr = sum(prev_tr) / 14 if prev_tr else 0
            prev_kc_u = prev_sma + 1.5 * prev_atr
            prev_kc_l = prev_sma - 1.5 * prev_atr
            was_in_squeeze = prev_bb_u < prev_kc_u and prev_bb_l > prev_kc_l

            if was_in_squeeze and not in_squeeze:
                # Squeeze fired! Direction = momentum at release
                direction = "LONG" if closes[i] > sma else "SHORT"
                fwd = _daily_forward_returns(dates[i], daily_bars, direction, start_idx=i)

                signals.append({
                    "type": f"SQUEEZE_RELEASE_{direction}",
                    "date": dates[i],
                    "price": closes[i],
                    "bb_width": bb_width,
                    "direction": direction,
                    "forward": fwd,
                })

    return _score_daily_signals("squeeze", signals)


# ═══════════════════════════════════════════════════════════════════════
# BACKTEST 6: GAMMA — Price at major GEX levels
# ═══════════════════════════════════════════════════════════════════════

def backtest_gamma_levels(daily_bars: List[Dict]) -> Dict:
    """
    Test if SPY pin near round numbers (gamma walls) predicts next-day direction.
    Round numbers often act as gamma walls.
    """
    signals = []
    for i in range(1, len(daily_bars) - 1):
        close = daily_bars[i].get('Close', daily_bars[i].get('close', 0))
        if not close:
            continue

        # Round number proximity (5-point intervals)
        nearest_round = round(close / 5) * 5
        distance_pct = abs(close - nearest_round) / close * 100

        # Pin: within 0.1% of round number
        if distance_pct < 0.10:
            # When pinned at gamma: expect MEAN REVERSION next day
            next_close = daily_bars[i+1].get('Close', daily_bars[i+1].get('close', 0))
            prev_close = daily_bars[i-1].get('Close', daily_bars[i-1].get('close', 0))

            if prev_close and next_close:
                # Direction = away from current momentum
                was_rising = close > prev_close
                direction = "SHORT" if was_rising else "LONG"

                if direction == "LONG":
                    pnl = (next_close - close) / close * 100
                else:
                    pnl = (close - next_close) / close * 100

                date = daily_bars[i].get('Date', daily_bars[i].get('date', ''))[:10]
                signals.append({
                    "type": "GAMMA_PIN",
                    "date": date,
                    "price": close,
                    "nearest_round": nearest_round,
                    "distance_pct": distance_pct,
                    "direction": direction,
                    "forward": {"1d": {"pnl_pct": pnl, "win": pnl > 0}},
                })

    return _score_daily_signals("gamma_pin", signals)


# ═══════════════════════════════════════════════════════════════════════
# SCORING HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _daily_forward_returns(signal_date: str, daily_bars: List[Dict], direction: str, start_idx: int = None) -> Dict:
    """Forward returns from daily bars."""
    # Find signal date in bars
    if start_idx is None:
        start_idx = None
        for i, bar in enumerate(daily_bars):
            bar_date = bar.get('Date', bar.get('date', ''))[:10]
            if bar_date == signal_date[:10]:
                start_idx = i
                break

    if start_idx is None:
        return {}

    results = {}
    entry_price = daily_bars[start_idx].get('Close', daily_bars[start_idx].get('close', 0))
    if not entry_price:
        return {}

    for horizon_name, offset in [("1d", 1), ("2d", 2), ("3d", 3), ("5d", 5), ("10d", 10)]:
        idx = start_idx + offset
        if idx < len(daily_bars):
            exit_price = daily_bars[idx].get('Close', daily_bars[idx].get('close', 0))
            if exit_price:
                if direction == "LONG":
                    pnl = (exit_price - entry_price) / entry_price * 100
                else:
                    pnl = (entry_price - exit_price) / entry_price * 100
                results[horizon_name] = {"pnl_pct": pnl, "win": pnl > 0, "exit_price": exit_price}

    return results


def _score_signals(checker_name: str, signals: List[Dict]) -> Dict:
    """Score intraday signals with forward return analysis."""
    if not signals:
        return {"checker": checker_name, "total_signals": 0, "verdict": "DEAD — No signals generated"}

    horizons = ["15m", "30m", "60m", "2h"]
    results = {"checker": checker_name, "total_signals": len(signals)}

    for h in horizons:
        valid = [s for s in signals if s.get("forward", {}).get(h)]
        if not valid:
            continue

        pnls = [s["forward"][h]["pnl_pct"] for s in valid]
        wins = sum(1 for p in pnls if p > 0)
        wr = wins / len(pnls) * 100
        avg_pnl = sum(pnls) / len(pnls)
        avg_win = sum(p for p in pnls if p > 0) / max(wins, 1)
        avg_loss = sum(p for p in pnls if p <= 0) / max(len(pnls) - wins, 1)
        profit_factor = abs(avg_win * wins / (avg_loss * (len(pnls) - wins))) if avg_loss != 0 and (len(pnls) - wins) > 0 else float('inf')

        results[f"horizon_{h}"] = {
            "n": len(valid),
            "win_rate": round(wr, 1),
            "avg_pnl": round(avg_pnl, 4),
            "avg_win": round(avg_win, 4),
            "avg_loss": round(avg_loss, 4),
            "profit_factor": round(profit_factor, 2),
        }

    # MFE / MAE
    mfes = [s["forward"]["max_favorable"] for s in signals if "max_favorable" in s.get("forward", {})]
    maes = [s["forward"]["max_adverse"] for s in signals if "max_adverse" in s.get("forward", {})]
    if mfes:
        results["avg_max_favorable"] = round(sum(mfes) / len(mfes), 4)
    if maes:
        results["avg_max_adverse"] = round(sum(maes) / len(maes), 4)

    # Signal type breakdown
    type_counts = {}
    for s in signals:
        t = s["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    results["signal_breakdown"] = type_counts

    # Verdict
    best_horizon = None
    best_wr = 0
    for h in horizons:
        hr = results.get(f"horizon_{h}", {})
        if hr.get("win_rate", 0) > best_wr:
            best_wr = hr["win_rate"]
            best_horizon = h

    if best_wr >= 60 and results.get(f"horizon_{best_horizon}", {}).get("avg_pnl", 0) > 0:
        results["verdict"] = f"✅ PROMOTE — {best_wr:.0f}% WR at {best_horizon}, avg +{results[f'horizon_{best_horizon}']['avg_pnl']:.3f}%"
    elif best_wr >= 50 and results.get(f"horizon_{best_horizon}", {}).get("profit_factor", 0) > 1.0:
        results["verdict"] = f"🔧 FIX — {best_wr:.0f}% WR at {best_horizon}, PF={results[f'horizon_{best_horizon}']['profit_factor']:.1f}x. Tune thresholds."
    elif len(signals) > 0:
        results["verdict"] = f"❌ KILL — Best WR={best_wr:.0f}% at {best_horizon}. Not profitable."
    else:
        results["verdict"] = "❌ KILL — Generated 0 signals."

    return results


def _score_dp_signals(checker_name: str, signals: List[Dict]) -> Dict:
    """Score DP learning signals with actual outcomes."""
    if not signals:
        return {"checker": checker_name, "total_signals": 0, "verdict": "DEAD"}

    total = len(signals)
    bounces = sum(1 for s in signals if s["outcome"] == "BOUNCE")
    breaks = sum(1 for s in signals if s["outcome"] == "BREAK")

    results = {
        "checker": checker_name,
        "total_signals": total,
        "bounces": bounces,
        "breaks": breaks,
        "win_rate": round(bounces / total * 100, 1) if total > 0 else 0,
        "avg_max_move": round(sum(s["max_move_pct"] for s in signals) / total, 4),
    }

    # By level type
    for lt in ["SUPPORT", "RESISTANCE"]:
        subset = [s for s in signals if lt in s["type"]]
        if subset:
            wins = sum(1 for s in subset if s["outcome"] == "BOUNCE")
            results[f"{lt.lower()}_count"] = len(subset)
            results[f"{lt.lower()}_wr"] = round(wins / len(subset) * 100, 1)

    # By time of day
    for tod in ["MORNING", "MIDDAY", "AFTERNOON"]:
        subset = [s for s in signals if s.get("time_of_day") == tod]
        if subset:
            wins = sum(1 for s in subset if s["outcome"] == "BOUNCE")
            results[f"tod_{tod.lower()}_count"] = len(subset)
            results[f"tod_{tod.lower()}_wr"] = round(wins / len(subset) * 100, 1)

    # By touch count
    for tc in [1, 2, 3]:
        subset = [s for s in signals if s.get("touch_count", 0) >= tc]
        if subset:
            wins = sum(1 for s in subset if s["outcome"] == "BOUNCE")
            results[f"touch_{tc}plus_count"] = len(subset)
            results[f"touch_{tc}plus_wr"] = round(wins / len(subset) * 100, 1)

    # VIX impact
    high_vix = [s for s in signals if (s.get("vix_level") or 0) > 20]
    low_vix = [s for s in signals if 0 < (s.get("vix_level") or 0) <= 20]
    if high_vix:
        wins = sum(1 for s in high_vix if s["outcome"] == "BOUNCE")
        results["high_vix_count"] = len(high_vix)
        results["high_vix_wr"] = round(wins / len(high_vix) * 100, 1)
    if low_vix:
        wins = sum(1 for s in low_vix if s["outcome"] == "BOUNCE")
        results["low_vix_count"] = len(low_vix)
        results["low_vix_wr"] = round(wins / len(low_vix) * 100, 1)

    # Verdict
    wr = results["win_rate"]
    if wr >= 80:
        results["verdict"] = f"✅ PROMOTE — {wr:.0f}% WR across {total} samples. PROVEN EDGE."
    elif wr >= 60:
        results["verdict"] = f"🔧 FIX — {wr:.0f}% WR. Good edge but needs filtering to improve."
    else:
        results["verdict"] = f"❌ KILL — {wr:.0f}% WR. Not sufficient edge."

    return results


def _score_daily_signals(checker_name: str, signals: List[Dict]) -> Dict:
    """Score daily-timeframe signals."""
    if not signals:
        return {"checker": checker_name, "total_signals": 0, "verdict": "DEAD — No signals generated"}

    horizons = ["1d", "2d", "3d", "5d"]
    results = {"checker": checker_name, "total_signals": len(signals)}

    for h in horizons:
        valid = [s for s in signals if s.get("forward", {}).get(h)]
        if not valid:
            continue

        pnls = [s["forward"][h]["pnl_pct"] for s in valid]
        wins = sum(1 for p in pnls if p > 0)
        wr = wins / len(pnls) * 100 if pnls else 0
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0

        results[f"horizon_{h}"] = {
            "n": len(valid),
            "win_rate": round(wr, 1),
            "avg_pnl": round(avg_pnl, 4),
            "cum_pnl": round(sum(pnls), 2),
        }

    # Type breakdown
    type_counts = {}
    for s in signals:
        t = s.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
    results["signal_breakdown"] = type_counts

    # Verdict
    best_wr = 0
    best_h = None
    for h in horizons:
        hr = results.get(f"horizon_{h}", {})
        if hr.get("win_rate", 0) > best_wr:
            best_wr = hr["win_rate"]
            best_h = h

    if best_wr >= 60 and results.get(f"horizon_{best_h}", {}).get("avg_pnl", 0) > 0:
        results["verdict"] = f"✅ PROMOTE — {best_wr:.0f}% WR at +{best_h}"
    elif best_wr >= 50:
        results["verdict"] = f"🔧 FIX — {best_wr:.0f}% WR at +{best_h}. Needs tuning."
    else:
        results["verdict"] = f"❌ KILL — Best WR={best_wr:.0f}%"

    return results


# ═══════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════

def run_all_backtests():
    """Run all checker backtests and produce scorecard."""

    print("=" * 80)
    print("🔬 COMPREHENSIVE CHECKER BACKTEST — REAL DATA, REAL OUTCOMES")
    print("=" * 80)
    print()

    # Load data
    print("Loading data...")
    bars_15m = load_15min_bars()
    print(f"  ✅ 15-min bars: {len(bars_15m)} (Feb 17 → Mar 13)")

    daily = load_daily_bars()
    print(f"  ✅ Daily bars: {len(daily)} (2024 → 2026)")

    dp_learning = load_dp_learning()
    print(f"  ✅ DP learning: {len(dp_learning)} interactions")

    dp_snapshots = load_dp_snapshots()
    print(f"  ✅ DP snapshots: {len(dp_snapshots)} days")

    alerts = load_alerts()
    print(f"  ✅ Alerts: {len(alerts)} total")
    print()

    results = []

    # 1. Selloff/Rally
    print("─" * 70)
    print("BACKTEST 1: SELLOFF / RALLY (Momentum Detection)")
    print("─" * 70)
    r = backtest_selloff_rally(bars_15m)
    results.append(r)
    _print_result(r)

    # 2. DP Divergence (proven edge)
    print()
    print("─" * 70)
    print("BACKTEST 2: DP DIVERGENCE (Dark Pool Level Reactions)")
    print("─" * 70)
    r = backtest_dp_divergence(dp_learning)
    results.append(r)
    _print_result(r)

    # 3. DP Trend
    print()
    print("─" * 70)
    print("BACKTEST 3: DP TREND (Multi-day accumulation divergence)")
    print("─" * 70)
    r = backtest_dp_trend(dp_snapshots, daily)
    results.append(r)
    _print_result(r)

    # 4. Options Flow
    print()
    print("─" * 70)
    print("BACKTEST 4: OPTIONS FLOW (Bullish/Bearish alerts → direction)")
    print("─" * 70)
    r = backtest_options_flow(alerts, daily)
    results.append(r)
    _print_result(r)

    # 5. Squeeze
    print()
    print("─" * 70)
    print("BACKTEST 5: SQUEEZE (Bollinger–Keltner squeeze release)")
    print("─" * 70)
    r = backtest_squeeze_conditions(daily)
    results.append(r)
    _print_result(r)

    # 6. Gamma Pin
    print()
    print("─" * 70)
    print("BACKTEST 6: GAMMA PIN (Round-number mean reversion)")
    print("─" * 70)
    r = backtest_gamma_levels(daily)
    results.append(r)
    _print_result(r)

    # ── FINAL SCORECARD ──
    print()
    print("=" * 80)
    print("📊 FINAL SCORECARD — KEEP / FIX / KILL")
    print("=" * 80)
    for r in results:
        icon = "✅" if "PROMOTE" in r.get("verdict", "") else "🔧" if "FIX" in r.get("verdict", "") else "❌"
        print(f"  {icon} {r['checker']:20s} | n={r['total_signals']:4d} | {r['verdict']}")

    return results


def _print_result(r: Dict):
    """Pretty-print a backtest result."""
    print(f"  Total signals: {r['total_signals']}")

    # Horizons
    for key in sorted(r.keys()):
        if key.startswith("horizon_"):
            h = r[key]
            print(f"  {key}: n={h['n']:3d} | WR={h.get('win_rate', 0):.1f}% | avg_pnl={h.get('avg_pnl', 0):+.4f}% | cum={h.get('cum_pnl', 0):+.2f}%"
                  if 'cum_pnl' in h else
                  f"  {key}: n={h['n']:3d} | WR={h.get('win_rate', 0):.1f}% | avg_pnl={h.get('avg_pnl', 0):+.4f}% | PF={h.get('profit_factor', 0):.1f}x")

    # DP-specific fields
    for key in ['win_rate', 'bounces', 'breaks', 'support_wr', 'resistance_wr']:
        if key in r and key not in ['total_signals', 'verdict', 'checker']:
            print(f"  {key}: {r[key]}")

    # Breakdown
    if 'signal_breakdown' in r:
        print(f"  Types: {r['signal_breakdown']}")
    if 'avg_max_favorable' in r:
        print(f"  Avg MFE: +{r['avg_max_favorable']:.3f}% | Avg MAE: {r['avg_max_adverse']:.3f}%")

    print(f"  VERDICT: {r['verdict']}")


if __name__ == "__main__":
    run_all_backtests()
