"""
🛡️ GUARDIAN REPLAY ENGINE v2

Replays the Intraday Guardian logic against historical 15-minute SPY bars.
Uses REAL wall data from every source on disk:
  ── GEX archive (call_wall, put_wall from CBOE data)
  ── DP level CSVs (top-volume level = institutional wall)
  ── CX DP levels (Stockgrid raw export, 1161 rows)
  ── Stockgrid live API (today's walls)
  ── AXLFI dark pool position data
  ── Prior-day close based estimation only as LAST resort

Data sourced from:
    - backtesting/data/spy_15min_1mo.json (494 bars, 19 days, yfinance)
    - data/external/cboe_gex/gex_archive.jsonl (call/put walls)
    - data/historical_test/dark_pool/SPY_*_levels.csv (DP levels)
    - data/cx_dark_pool_levels_nyse-spy_*.csv (Stockgrid raw)
    - Stockgrid live API (current walls)
    - cache/alpha_vantage/SPY_1min_full_20251121.json (21K bars)
    - backtesting/reports/backtest_*.json (trade data)
    - data/gate_backtest_week1.json (gate signals)
"""

import json
import csv
import os
import sys
import glob
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "backtesting" / "data"
REPORTS = BASE / "backtesting" / "reports"


# ═══════════════════════════════════════════════════════════
# DATA LOADERS
# ═══════════════════════════════════════════════════════════

def load_15min_bars():
    """Load SPY 15-min bars from yfinance cache."""
    path = DATA / "spy_15min_1mo.json"
    if not path.exists():
        logger.error(f"Missing: {path}")
        return []
    with open(path) as f:
        return json.load(f)


def load_alpha_vantage_bars():
    """Load SPY 1-min bars from Alpha Vantage cache — covers Nov 20-21, 2025."""
    path = BASE / "cache" / "alpha_vantage" / "SPY_1min_full_20251121.json"
    if not path.exists():
        return {}
    with open(path) as f:
        raw = json.load(f)
    ts_key = "Time Series (1min)"
    if ts_key not in raw:
        return {}
    bars_by_date = defaultdict(list)
    for ts_str, vals in raw[ts_key].items():
        bar_date = ts_str[:10]
        bars_by_date[bar_date].append({
            "timestamp": ts_str,
            "open": float(vals["1. open"]),
            "high": float(vals["2. high"]),
            "low": float(vals["3. low"]),
            "close": float(vals["4. close"]),
            "volume": int(vals["5. volume"]),
        })
    # Sort each day's bars by timestamp
    for d in bars_by_date:
        bars_by_date[d].sort(key=lambda b: b["timestamp"])
    return dict(bars_by_date)


def load_all_wall_data():
    """
    Extract wall levels from EVERY source on disk.
    Returns dict: { "YYYY-MM-DD": {"call_wall": X, "put_wall": Y, "source": "..."} }
    """
    walls = {}

    # ── Source 1: GEX archive (most reliable — CBOE data) ──
    gex_path = BASE / "data" / "external" / "cboe_gex" / "gex_archive.jsonl"
    if gex_path.exists():
        with open(gex_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                walls[d["date"]] = {
                    "call_wall": d.get("call_wall", 0),
                    "put_wall": d.get("put_wall", 0),
                    "gamma_flip": d.get("gamma_flip", 0),
                    "source": "GEX_archive",
                }

    # ── Source 2: GEX history JSONs ──
    gex_hist = BASE / "data" / "external" / "cboe_gex" / "history"
    if gex_hist.exists():
        for f in gex_hist.glob("gex_*.json"):
            try:
                d = json.load(open(f))
                dt = d.get("date", "")
                if dt and dt not in walls:
                    walls[dt] = {
                        "call_wall": d.get("call_wall", 0),
                        "put_wall": d.get("put_wall", 0),
                        "gamma_flip": d.get("gamma_flip", 0),
                        "source": "GEX_history",
                    }
            except Exception:
                pass

    # ── Source 3: DP level CSVs (top-volume level = institutional wall) ──
    dp_dir = BASE / "data" / "historical_test" / "dark_pool"
    if dp_dir.exists():
        for f in dp_dir.glob("SPY_*_levels.csv"):
            try:
                date_str = f.stem.split("_")[1]  # SPY_2025-10-14_levels
                with open(f) as fh:
                    reader = csv.DictReader(fh)
                    rows = sorted(list(reader), key=lambda r: -float(r.get("volume", 0)))
                if rows and date_str not in walls:
                    top = float(rows[0]["level"])
                    # Call wall = max of top 3 levels, put wall = min of top 3 levels
                    top3 = [float(r["level"]) for r in rows[:3]]
                    walls[date_str] = {
                        "call_wall": max(top3),
                        "put_wall": min(top3),
                        "source": "DP_levels_csv",
                    }
            except Exception as e:
                logger.debug(f"DP CSV parse error {f}: {e}")

    # ── Source 4: CX Stockgrid raw DP levels CSVs ──
    for f in (BASE / "data").glob("cx_dark_pool_levels_*.csv"):
        try:
            # filename: cx_dark_pool_levels_nyse-spy_2025-10-16_17607558648217.csv
            parts = f.stem.split("_")
            date_str = parts[5]  # 2025-10-16
            with open(f) as fh:
                reader = csv.DictReader(fh)
                rows = sorted(list(reader), key=lambda r: -float(r.get("volume", 0)))
            if rows and date_str not in walls:
                top5 = [float(r["level"]) for r in rows[:5]]
                walls[date_str] = {
                    "call_wall": max(top5),
                    "put_wall": min(top5),
                    "source": "CX_stockgrid_csv",
                }
        except Exception as e:
            logger.debug(f"CX CSV parse error {f}: {e}")

    # ── Source 5: Stockgrid live API (today's walls) ──
    try:
        sys.path.insert(0, str(BASE))
        from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
        client = StockgridClient()
        walls_today = client.get_option_walls_today("SPY")
        if walls_today:
            today_str = date.today().isoformat()
            walls[today_str] = {
                "call_wall": walls_today.call_wall,
                "put_wall": walls_today.put_wall,
                "poc": walls_today.poc,
                "source": "Stockgrid_live",
            }
            logger.info(f"Stockgrid live: call={walls_today.call_wall}, put={walls_today.put_wall}")
    except Exception as e:
        logger.warning(f"Stockgrid live failed: {e}")

    return walls


def estimate_walls_from_price(day_bars, prior_close=None):
    """
    Smart estimation: use the PRIOR day's close as the anchor.
    In real markets, call wall tends to be 1-2% above prior close,
    put wall tends to be 1-2% below.
    This is much better than day_high+2 / day_low-2 which always triggers.
    """
    if not day_bars:
        return {}, "no_data"

    open_price = day_bars[0]["open"]
    anchor = prior_close if prior_close else open_price

    # Call wall: ~1.5% above anchor (round to $1)
    call_wall = round(anchor * 1.015, 0)
    # Put wall: ~1.5% below anchor (round to $1)
    put_wall = round(anchor * 0.985, 0)

    return {
        "call_wall": call_wall,
        "put_wall": put_wall,
        "source": "estimated_from_prior_close",
    }, "estimated"


def load_backtest_trades():
    """Load historical trades from ALL backtest reports and gate data."""
    all_trades = []

    for report_name in sorted(REPORTS.glob("backtest_*.json")):
        try:
            with open(report_name) as f:
                data = json.load(f)
            daily = data.get("daily_breakdown", [])
            for day in daily:
                day_date = day.get("date", "")
                for trade in day.get("trades", []):
                    trade["date"] = day_date
                    trade["market_direction"] = day.get("market_direction", "UNKNOWN")
                    trade["vix"] = day.get("vix", 0)
                    trade["source"] = report_name.name
                    all_trades.append(trade)
        except Exception:
            pass

    # Gate backtest week 1 signals
    gate_path = BASE / "data" / "gate_backtest_week1.json"
    if gate_path.exists():
        with open(gate_path) as f:
            gate_data = json.load(f)
        for sig in gate_data.get("signals", []):
            sig["source"] = "gate_backtest_week1"
            sig["date"] = sig.get("timestamp", "")[:10]
            all_trades.append(sig)

    return all_trades


def load_replay_signals():
    """Load minute-by-minute signal replay CSVs."""
    signals = {}
    replay_dir = BASE / "logs" / "replay"
    if not replay_dir.exists():
        return signals
    for f in replay_dir.glob("lotto_signals_*.csv"):
        try:
            with open(f) as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            if not rows:
                continue
            # Extract date from filename: lotto_signals_SPY_2025-11-20.csv
            parts = f.stem.split("_")
            date_str = parts[-1]  # 2025-11-20
            ticker = parts[2] if len(parts) > 2 else "SPY"
            key = f"{ticker}_{date_str}"
            signals[key] = rows
        except Exception:
            pass
    return signals


def get_historical_kill_chain_batch(all_dates):
    """
    Computes Kill Chain state (layers active) for a list of historical dates.
    Uses yfinance for GEX/DVR and cot_reports for COT divergence.
    """
    if not all_dates:
        return {}
        
    logger.info("🔪 Computing historical Kill Chain states...")
    import yfinance as yf
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    
    kc_history = {}
    
    start_dt = datetime.strptime(all_dates[0], "%Y-%m-%d") - timedelta(days=45)
    end_dt = datetime.strptime(all_dates[-1], "%Y-%m-%d") + timedelta(days=2)
    
    # Download time series once
    import warnings
    warnings.filterwarnings('ignore')
    spy = yf.download('SPY', start=start_dt, end=end_dt, progress=False)
    vix = yf.download('^VIX', start=start_dt, end=end_dt, progress=False)
    vix3m = yf.download('^VIX3M', start=start_dt, end=end_dt, progress=False)
    
    def flat(s):
        if hasattr(s, 'columns'): return s.iloc[:, 0]
        return s
        
    try:
        spy_c = flat(spy['Close'])
        spy_v = flat(spy['Volume'])
        vix_c = flat(vix['Close'])
        vix3m_c = flat(vix3m['Close'])
        
        df = pd.DataFrame({
            'close': spy_c, 'volume': spy_v,
            'vix': vix_c, 'vix3m': vix3m_c,
        }).dropna()
        
        df['ret'] = df['close'].pct_change()
        df['is_down'] = (df['ret'] < 0).astype(float)
        df['down_vol'] = (df['volume'] * df['is_down']).rolling(10).sum()
        df['total_vol'] = df['volume'].rolling(10).sum()
        df['dvr'] = df['down_vol'] / df['total_vol']
    except Exception as e:
        logger.warning(f"Failed to compute historical DVR/GEX: {e}")
        df = pd.DataFrame()
        
    # Download COT once per year
    cot_data_by_year = {}
    
    for date_str in all_dates:
        gex_positive = False
        dp_selling = False
        cot_divergence = False
        
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # 1. GEX and DVR
        if not df.empty:
            df_slice = df[df.index <= pd.to_datetime(date_str)]
            if len(df_slice) > 0:
                latest = df_slice.iloc[-1]
                vix_val = float(latest['vix'])
                vix3m_val = float(latest['vix3m'])
                vix_ratio = vix_val / vix3m_val if vix3m_val > 0 else 1.0
                gex_positive = vix_ratio < 1.0
                
                dvr_val = float(latest['dvr'])
                dp_selling = dvr_val > 0.55
                
        # 2. COT
        year = target_dt.year
        if year not in cot_data_by_year:
            try:
                from cot_reports import cot_year
                cot_df = cot_year(year, cot_report_type='legacy_fut')
                if cot_df is not None and len(cot_df) > 0:
                    sp = cot_df[cot_df['Market and Exchange Names'].str.contains('E-MINI S&P 500', case=False, na=False)].copy()
                    if len(sp) > 0:
                        sp['date'] = pd.to_datetime(sp['As of Date in Form YYYY-MM-DD'])
                        cot_data_by_year[year] = sp
            except Exception as e:
                logger.debug(f"COT pull loop error for {year}: {e}")
                cot_data_by_year[year] = pd.DataFrame()
                
        cot_df = cot_data_by_year.get(year, pd.DataFrame())
        if not cot_df.empty:
            sp_slice = cot_df[cot_df['date'] <= pd.to_datetime(date_str)] if 'date' in cot_df.columns else pd.DataFrame()
            if len(sp_slice) > 0:
                sp_slice = sp_slice.sort_values('date')
                latest_cot = sp_slice.iloc[-1]
                specs_long = float(pd.to_numeric(latest_cot['Noncommercial Positions-Long (All)'], errors='coerce') or 0)
                specs_short = float(pd.to_numeric(latest_cot['Noncommercial Positions-Short (All)'], errors='coerce') or 0)
                comm_long = float(pd.to_numeric(latest_cot['Commercial Positions-Long (All)'], errors='coerce') or 0)
                comm_short = float(pd.to_numeric(latest_cot['Commercial Positions-Short (All)'], errors='coerce') or 0)
                
                cot_specs_net = specs_long - specs_short
                cot_comm_net = comm_long - comm_short
                cot_divergence = (cot_specs_net < 0) and (cot_comm_net > 0)
                
        active_layers = sum([cot_divergence, gex_positive, dp_selling])
        
        kc_history[date_str] = {
            "cot_divergence": cot_divergence,
            "gex_positive": gex_positive,
            "dp_selling": dp_selling,
            "active_layers": active_layers
        }
        
    return kc_history


# ═══════════════════════════════════════════════════════════
# GUARDIAN SIMULATION
# ═══════════════════════════════════════════════════════════

def simulate_guardian_for_day(day_bars, call_wall, put_wall):
    """
    Simulate Guardian thesis checks on a single day's 15-min bars.
    Returns list of check results.
    """
    checks = []
    thesis_valid = True
    thesis_reason = None
    wall_break_time = None
    recovery_count = 0

    for bar in day_bars:
        ts = bar["timestamp"]
        close = bar["close"]
        high = bar["high"]
        low = bar["low"]

        # Thesis check: SPY broke call wall downward by > $0.50
        if call_wall > 0 and close < call_wall - 0.5:
            if thesis_valid:
                wall_break_time = ts
            thesis_valid = False
            thesis_reason = f"SPY ${close:.2f} < call_wall ${call_wall:.0f} by ${call_wall - close:.2f}"
        elif put_wall > 0 and close < put_wall:
            if thesis_valid:
                wall_break_time = ts
            thesis_valid = False
            thesis_reason = f"SPY ${close:.2f} below put_wall ${put_wall:.0f}"
        else:
            if not thesis_valid:
                recovery_count += 1
            thesis_valid = True
            thesis_reason = None

        checks.append({
            "timestamp": ts,
            "spy_price": close,
            "thesis_valid": thesis_valid,
            "thesis_reason": thesis_reason,
        })

    return checks, wall_break_time, recovery_count


# ═══════════════════════════════════════════════════════════
# MAIN REPLAY
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("🛡️ GUARDIAN REPLAY ENGINE v2 — Starting")
    logger.info("Parsing ALL historical data from disk...\n")

    # ── Load 15-min bars ──
    bars_15m = load_15min_bars()
    logger.info(f"📊 15-min bars: {len(bars_15m)}")

    # ── Load Alpha Vantage 1-min bars ──
    av_bars = load_alpha_vantage_bars()
    logger.info(f"📊 Alpha Vantage 1-min days: {len(av_bars)} ({sum(len(v) for v in av_bars.values())} bars)")

    # ── Load ALL wall data ──
    walls = load_all_wall_data()
    logger.info(f"🧱 Wall data loaded: {len(walls)} days")
    for dt, w in sorted(walls.items()):
        logger.info(f"   {dt}: call={w['call_wall']} put={w['put_wall']} ({w['source']})")

    # ── Load trades ──
    trades = load_backtest_trades()
    logger.info(f"📈 Historical trades loaded: {len(trades)}")

    # ── Load replay signals ──
    replay_sigs = load_replay_signals()
    logger.info(f"🔁 Replay signal sets loaded: {len(replay_sigs)}")
    for k, v in replay_sigs.items():
        logger.info(f"   {k}: {len(v)} signals")

    # ── Group 15-min bars by date ──
    bars_by_date = defaultdict(list)
    for bar in bars_15m:
        bars_by_date[bar["timestamp"][:10]].append(bar)

    # ── Add Alpha Vantage days (resample 1-min to 15-min) ──
    for av_date, av_day_bars in av_bars.items():
        if av_date in bars_by_date:
            continue  # Already have 15-min data
        # Resample: group by 15-min windows
        resampled = []
        window = []
        for bar in av_day_bars:
            window.append(bar)
            if len(window) >= 15:
                resampled.append({
                    "timestamp": window[0]["timestamp"],
                    "open": window[0]["open"],
                    "high": max(b["high"] for b in window),
                    "low": min(b["low"] for b in window),
                    "close": window[-1]["close"],
                    "volume": sum(b["volume"] for b in window),
                })
                window = []
        if window:
            resampled.append({
                "timestamp": window[0]["timestamp"],
                "open": window[0]["open"],
                "high": max(b["high"] for b in window),
                "low": min(b["low"] for b in window),
                "close": window[-1]["close"],
                "volume": sum(b["volume"] for b in window),
            })
        bars_by_date[av_date] = resampled

    all_dates = sorted(bars_by_date.keys())
    logger.info(f"\n📅 Total trading days: {len(all_dates)} ({all_dates[0]} → {all_dates[-1]})")

    # ── Pre-compute Kill Chain historically ──
    kc_history = get_historical_kill_chain_batch(all_dates)

    # ═══════════════════════════════════
    # RUN SIMULATION
    # ═══════════════════════════════════
    logger.info(f"\n{'='*70}")
    logger.info("REPLAYING GUARDIAN ACROSS ALL DAYS")
    logger.info(f"{'='*70}\n")

    daily_results = []
    prior_close = None

    for day_str in all_dates:
        day_bars = bars_by_date[day_str]
        if not day_bars:
            continue

        # Get walls — try REAL data first, estimate as last resort
        if day_str in walls:
            call_wall = walls[day_str]["call_wall"]
            put_wall = walls[day_str]["put_wall"]
            wall_source = walls[day_str]["source"]
        else:
            est, wall_source = estimate_walls_from_price(day_bars, prior_close)
            call_wall = est.get("call_wall", 0)
            put_wall = est.get("put_wall", 0)

        # Filter to market hours only (9:30-16:00 ET)
        market_bars = []
        for bar in day_bars:
            ts = bar["timestamp"]
            # Extract hour — handle both timezone-aware and naive timestamps
            if "T" in ts:
                hour_str = ts[11:13]
            else:
                hour_str = ts.split(" ")[1][:2] if " " in ts else "00"
            try:
                hour = int(hour_str)
                # Accept bars from 9-20 (UTC) or 9-16 (ET) — be permissive
                if 4 <= hour <= 20:
                    market_bars.append(bar)
            except ValueError:
                market_bars.append(bar)

        if not market_bars:
            market_bars = day_bars  # Fallback: use all bars

        checks, wall_break_time, recoveries = simulate_guardian_for_day(
            market_bars, call_wall, put_wall
        )

        bars_invalid = sum(1 for c in checks if not c["thesis_valid"])
        open_price = market_bars[0]["open"]
        close_price = market_bars[-1]["close"]
        day_change = (close_price - open_price) / open_price * 100

        result = {
            "date": day_str,
            "call_wall": call_wall,
            "put_wall": put_wall,
            "wall_source": wall_source,
            "bars_total": len(checks),
            "bars_thesis_invalid": bars_invalid,
            "pct_bars_invalid": round(bars_invalid / len(checks) * 100, 1) if checks else 0,
            "thesis_flip_time": wall_break_time,
            "recoveries": recoveries,
            "day_open": round(open_price, 2),
            "day_close": round(close_price, 2),
            "day_change_pct": round(day_change, 2),
        }
        daily_results.append(result)

        status = "🔴 INVALID" if wall_break_time else "🟢 VALID"
        pct_inv = f"{result['pct_bars_invalid']}%" if wall_break_time else "0%"
        logger.info(
            f"  {day_str}: {status} ({pct_inv} bars) | "
            f"SPY {open_price:.2f}→{close_price:.2f} ({day_change:+.2f}%) | "
            f"walls={call_wall:.0f}/{put_wall:.0f} ({wall_source})"
            f"{f' | recovered {recoveries}x' if recoveries else ''}"
        )

        prior_close = close_price

    # ═══════════════════════════════════
    # CROSS-REFERENCE WITH TRADES
    # ═══════════════════════════════════
    logger.info(f"\n{'='*70}")
    logger.info("CROSS-REFERENCING WITH HISTORICAL TRADES")
    logger.info(f"{'='*70}\n")

    trades_would_block = 0
    trades_would_pass = 0
    blocked_pnl = []
    passed_pnl = []
    blocked_trades_detail = []
    passed_trades_detail = []

    for trade in trades:
        trade_date = trade.get("date", "")[:10]
        if trade_date not in bars_by_date:
            continue

        day_result = next((d for d in daily_results if d["date"] == trade_date), None)
        if not day_result:
            continue

        # Extract PnL from various field names
        pnl = (
            trade.get("pnl_pct")
            or trade.get("pnl")
            or trade.get("return_pct")
            or trade.get("profit_loss_pct")
            or 0
        )
        pnl = float(pnl) if pnl else 0

        ticker = trade.get("ticker", trade.get("symbol", "?"))
        direction = trade.get("direction", trade.get("action", "?"))
        
        # Calculate sizing multiplier
        multiplier = 1.0  # default
        if day_result["thesis_flip_time"]:
            multiplier = 0.0
        else:
            kc_state = kc_history.get(trade_date, {"active_layers": 0})
            active_layers = kc_state["active_layers"]
            if active_layers == 0:
                multiplier = 0.5
            elif active_layers in [1, 2]:
                multiplier = 1.0
            elif active_layers == 3:
                multiplier = 3.0
                
        dynamic_pnl = pnl * multiplier

        if day_result["thesis_flip_time"]:
            trades_would_block += 1
            blocked_pnl.append(pnl)
            blocked_trades_detail.append({
                "date": trade_date,
                "ticker": ticker,
                "direction": direction,
                "flat_pnl": pnl,
                "dynamic_pnl": dynamic_pnl,
                "sizing_multiplier": multiplier,
                "was_loser": pnl < 0,
                "wall_break_time": day_result["thesis_flip_time"],
            })
        else:
            trades_would_pass += 1
            passed_pnl.append(pnl)
            passed_trades_detail.append({
                "date": trade_date,
                "ticker": ticker,
                "direction": direction,
                "flat_pnl": pnl,
                "dynamic_pnl": dynamic_pnl,
                "sizing_multiplier": multiplier,
            })

    # ═══════════════════════════════════
    # COMPUTE METRICS
    # ═══════════════════════════════════
    avg_blocked_pnl = sum(blocked_pnl) / len(blocked_pnl) if blocked_pnl else 0
    avg_passed_pnl = sum(passed_pnl) / len(passed_pnl) if passed_pnl else 0
    true_blocks = sum(1 for p in blocked_pnl if p < 0)
    false_blocks = sum(1 for p in blocked_pnl if p >= 0)
    precision = (true_blocks / len(blocked_pnl) * 100) if blocked_pnl else 0
    pnl_saved = sum(abs(p) for p in blocked_pnl if p < 0)
    
    total_flat_pnl = sum(blocked_pnl) + sum(passed_pnl)
    total_dynamic_pnl = sum([t["dynamic_pnl"] for t in passed_trades_detail]) + sum([t["dynamic_pnl"] for t in blocked_trades_detail])
    dynamic_outperformance = total_dynamic_pnl - total_flat_pnl

    # Days summary
    days_valid = sum(1 for d in daily_results if not d["thesis_flip_time"])
    days_invalid = sum(1 for d in daily_results if d["thesis_flip_time"])

    # PnL on valid vs invalid days
    valid_day_changes = [d["day_change_pct"] for d in daily_results if not d["thesis_flip_time"]]
    invalid_day_changes = [d["day_change_pct"] for d in daily_results if d["thesis_flip_time"]]
    avg_valid_day = sum(valid_day_changes) / len(valid_day_changes) if valid_day_changes else 0
    avg_invalid_day = sum(invalid_day_changes) / len(invalid_day_changes) if invalid_day_changes else 0

    results = {
        "replay_period": {
            "start": all_dates[0],
            "end": all_dates[-1],
            "trading_days": len(all_dates),
            "total_bars": sum(len(bars_by_date[d]) for d in all_dates),
            "data_sources": {
                "yfinance_15min": len(bars_15m),
                "alpha_vantage_1min_resampled": sum(len(v) for v in av_bars.values()),
                "wall_sources": {src: sum(1 for w in walls.values() if w["source"] == src) for src in set(w["source"] for w in walls.values())},
            },
        },
        "guardian_summary": {
            "days_thesis_valid_all_day": days_valid,
            "days_thesis_invalidated": days_invalid,
            "avg_spy_change_valid_days": round(avg_valid_day, 2),
            "avg_spy_change_invalid_days": round(avg_invalid_day, 2),
        },
        "trade_impact": {
            "total_trades_analyzed": len(blocked_pnl) + len(passed_pnl),
            "trades_guardian_would_block": trades_would_block,
            "trades_guardian_would_pass": trades_would_pass,
            "blocked_trade_avg_pnl": round(avg_blocked_pnl, 4),
            "passed_trade_avg_pnl": round(avg_passed_pnl, 4),
            "total_flat_pnl": round(total_flat_pnl, 4),
            "total_dynamic_pnl": round(total_dynamic_pnl, 4),
            "dynamic_strategy_alpha": round(dynamic_outperformance, 4),
            "true_blocks_losers_caught": true_blocks,
            "false_blocks_winners_missed": false_blocks,
            "precision_pct": round(precision, 1),
            "total_pnl_saved": round(pnl_saved, 4),
        },
        "blocked_trades_detail": blocked_trades_detail,
        "passed_trades_detail": passed_trades_detail,
        "daily_detail": daily_results,
    }

    # ── Save ──
    out_path = REPORTS / "guardian_replay_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # ═══════════════════════════════════
    # PRINT REPORT
    # ═══════════════════════════════════
    logger.info(f"\n{'='*70}")
    logger.info(f"🛡️  GUARDIAN REPLAY RESULTS")
    logger.info(f"{'='*70}")
    logger.info(f"Period:  {all_dates[0]} → {all_dates[-1]} ({len(all_dates)} trading days)")
    logger.info(f"Bars:    {results['replay_period']['total_bars']}")
    logger.info(f"")
    logger.info(f"── THESIS DAYS ──")
    logger.info(f"  🟢 Valid all day:  {days_valid} days (avg SPY change: {avg_valid_day:+.2f}%)")
    logger.info(f"  🔴 Invalidated:    {days_invalid} days (avg SPY change: {avg_invalid_day:+.2f}%)")
    logger.info(f"")
    logger.info(f"── TRADE IMPACT ──")
    logger.info(f"  Trades analyzed:   {results['trade_impact']['total_trades_analyzed']}")
    logger.info(f"  Would BLOCK:       {trades_would_block} (avg PnL: {avg_blocked_pnl:+.4f})")
    logger.info(f"  Would PASS:        {trades_would_pass} (avg PnL: {avg_passed_pnl:+.4f})")
    logger.info(f"  True blocks:       {true_blocks} losers caught")
    logger.info(f"  False blocks:      {false_blocks} winners missed")
    logger.info(f"  PRECISION:         {precision:.1f}%")
    logger.info(f"  PNL SAVED:         {pnl_saved:.4f}")
    logger.info(f"")
    logger.info(f"── SIZING PERFORMANCE (Conviction Engine) ──")
    logger.info(f"  Total Flat PnL:    {total_flat_pnl:+.4f}")
    logger.info(f"  Total Dynamic PnL: {total_dynamic_pnl:+.4f}")
    logger.info(f"  DYNAMIC ALPHA:     ⭐️ {dynamic_outperformance:+.4f} ⭐️")
    logger.info(f"")

    # Print blocked trades
    if blocked_trades_detail:
        logger.info(f"── BLOCKED TRADES DETAIL ──")
        for t in blocked_trades_detail[:15]:
            emoji = "❌" if t["was_loser"] else "⚠️"
            logger.info(f"  {emoji} {t['date']} {t['ticker']} {t['direction']} flat={t['flat_pnl']:+.4f} -> dyn={t['dynamic_pnl']:+.4f} (0x)")

    if passed_trades_detail:
        logger.info(f"\n── PASSED TRADES DETAIL ──")
        for t in passed_trades_detail[:15]:
            emoji = "✅" if t["flat_pnl"] > 0 else "❌"
            sz_str = f"({t['sizing_multiplier']}x)"
            if t['sizing_multiplier'] >= 3.0: sz_str = "🔥 " + sz_str
            logger.info(f"  {emoji} {t['date']} {t['ticker']} {t['direction']} flat={t['flat_pnl']:+.4f} -> dyn={t['dynamic_pnl']:+.4f} {sz_str}")

    logger.info(f"\nSaved to: {out_path}")

    # ── Acceptance checks ──
    logger.info(f"\n{'='*70}")
    logger.info("ACCEPTANCE TESTS")
    logger.info(f"{'='*70}")

    all_pass = True
    if blocked_pnl:
        if avg_blocked_pnl < 0:
            logger.info(f"✅ blocked_trade_avg_pnl = {avg_blocked_pnl:+.4f} (NEGATIVE = guardian blocks losers)")
        else:
            logger.error(f"❌ blocked_trade_avg_pnl = {avg_blocked_pnl:+.4f} (POSITIVE = blocking winners!)")
            all_pass = False

        if precision > 60:
            logger.info(f"✅ precision = {precision:.1f}% > 60%")
        else:
            logger.warning(f"⚠️  precision = {precision:.1f}% < 60% — threshold may need tuning")
            all_pass = False
    else:
        logger.warning("⚠️  No trades matched replay days — cannot compute trade impact")
        all_pass = False

    if days_valid > 0:
        logger.info(f"✅ {days_valid} valid days found — not all days flagged (estimation is reasonable)")
    else:
        logger.warning(f"⚠️  0 valid days — all days flagged as invalid")

    if avg_valid_day > avg_invalid_day:
        logger.info(f"✅ Valid days outperform invalid days ({avg_valid_day:+.2f}% vs {avg_invalid_day:+.2f}%)")
    elif days_valid > 0:
        logger.warning(f"⚠️  Invalid days outperform valid days ({avg_invalid_day:+.2f}% vs {avg_valid_day:+.2f}%)")

    return results


if __name__ == "__main__":
    main()
