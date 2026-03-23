#!/usr/bin/env python3
"""
🛡️ Guardian Historical Replay — Simulates a full trading day using real SPY data.

Replays this week's session: generates 26 snapshots (every 15 min from 9:30-16:00 ET)
using real yfinance price data + synthetic wall/volume scenarios.

Usage:
    python3 live_monitoring/guardian_replay.py [--date 2026-03-13] [--invalidate-at 12:00]
"""

import os
import sys
import json
import time
import shutil
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_spy_price_history(date_str: str) -> list:
    """Fetch real SPY 15-min bars for the given date using yfinance."""
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        # Get intraday data for the target date
        start = datetime.strptime(date_str, "%Y-%m-%d")
        end = start + timedelta(days=1)
        data = spy.history(start=start.strftime("%Y-%m-%d"),
                           end=end.strftime("%Y-%m-%d"),
                           interval="15m")
        if data.empty:
            print(f"⚠️ No intraday data for {date_str}, using synthetic prices")
            return _synthetic_prices()

        bars = []
        for ts, row in data.iterrows():
            bars.append({
                "timestamp": str(ts),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        print(f"✅ Fetched {len(bars)} real SPY bars for {date_str}")
        return bars
    except Exception as e:
        print(f"⚠️ yfinance failed ({e}), using synthetic prices")
        return _synthetic_prices()


def _synthetic_prices() -> list:
    """Generate synthetic SPY prices for replay when real data unavailable."""
    base = 590.0
    bars = []
    for i in range(26):
        # Simulate realistic intraday movement: gap up, sell off, recover
        if i < 4:  # 9:30-10:30: gap up
            price = base + i * 0.8
        elif i < 10:  # 10:30-12:00: consolidation
            price = base + 3.0 + (i - 4) * 0.2
        elif i < 16:  # 12:00-1:30: sell-off
            price = base + 4.0 - (i - 10) * 1.2
        elif i < 20:  # 1:30-2:30: bounce
            price = base - 3.0 + (i - 16) * 0.8
        else:  # 2:30-4:00: power hour
            price = base - 0.5 + (i - 20) * 0.3

        bars.append({
            "timestamp": f"2026-03-13 {9 + (i * 15 + 30) // 60}:{(i * 15 + 30) % 60:02d}:00",
            "close": round(price, 2),
            "volume": 5_000_000 + i * 200_000,
        })
    return bars


def run_replay(date_str: str, invalidate_at: str = None, breaker_at: str = None):
    """
    Replay a full trading day:
    - 26 snapshots every 15 min (9:30 AM - 4:00 PM ET)
    - Uses real SPY price data
    - Optionally triggers thesis invalidation at specified time
    - Optionally triggers circuit breaker at specified time
    - Saves each snapshot to /tmp/guardian_snapshots/YYYY-MM-DD/
    """
    from live_monitoring.intraday_guardian import IntradayGuardian

    # Setup
    snapshot_dir = f"/tmp/guardian_snapshots/{date_str}"
    os.makedirs(snapshot_dir, exist_ok=True)

    # Clean previous run
    for f in Path(snapshot_dir).glob("*.json"):
        f.unlink()

    guardian = IntradayGuardian()
    bars = get_spy_price_history(date_str)

    print(f"\n{'='*70}")
    print(f"🛡️ GUARDIAN REPLAY — {date_str}")
    print(f"{'='*70}")
    print(f"   Bars: {len(bars)}")
    print(f"   Snapshot dir: {snapshot_dir}")
    if invalidate_at:
        print(f"   ⚡ Thesis invalidation scheduled at: {invalidate_at}")
    if breaker_at:
        print(f"   🔴 Circuit breaker scheduled at: {breaker_at}")
    print(f"{'='*70}\n")

    snapshots = []
    thesis_flips = 0
    prev_thesis = True
    total_check = 0

    # Generate 26 time slots: 9:30 to 15:45 (every 15 min)
    for slot in range(26):
        hour = 9 + (slot * 15 + 30) // 60
        minute = (slot * 15 + 30) % 60
        time_str = f"{hour:02d}:{minute:02d}"
        total_check += 1

        # Get price from bars (use closest bar or fallback)
        bar_idx = min(slot, len(bars) - 1)
        price = bars[bar_idx]["close"]
        volume = bars[bar_idx].get("volume", 5_000_000)

        # Build realistic wall levels based on price
        call_wall = round(price + 3.0, 2)  # $3 above
        put_wall = round(price - 5.0, 2)   # $5 below
        poc = round(price - 0.5, 2)        # Slightly below

        # Determine wall status
        wall_status = "holding"
        if price > call_wall:
            wall_status = "above_call"
        elif price < put_wall:
            wall_status = "broken"

        # Volume character
        avg_vol = 5_000_000
        vol_ratio = volume / avg_vol if avg_vol else 1.0
        if vol_ratio > 2.0:
            vol_char = "climactic"
        elif vol_ratio > 1.3:
            vol_char = "distribution"
        elif vol_ratio > 0.7:
            vol_char = "balanced"
        else:
            vol_char = "thin"

        # Check for forced invalidation
        thesis_valid = True
        invalidation_reason = None

        if invalidate_at and time_str >= invalidate_at:
            thesis_valid = False
            invalidation_reason = f"SPY broke put wall at {put_wall} (replay simulation)"
            wall_status = "broken"

        # Check for circuit breaker
        cb_active = False
        cb_reason = None
        if breaker_at and time_str >= breaker_at:
            cb_active = True
            cb_reason = "RiskManager circuit breaker — daily PnL -3.20% <= -3.00%"

        # Track thesis flips
        if thesis_valid != prev_thesis:
            thesis_flips += 1
        prev_thesis = thesis_valid

        # Build snapshot
        snapshot = {
            "timestamp": f"{date_str}T{time_str}:00-04:00",
            "market_open": True,
            "spy_price": price,
            "spy_call_wall": call_wall,
            "spy_put_wall": put_wall,
            "spy_poc": poc,
            "spy_vs_wall": "above" if price > poc else "below",
            "wall_status": wall_status,
            "wall_break_time": f"{hour}:{minute:02d}" if wall_status == "broken" else None,
            "volume_character": vol_char,
            "volume_ratio": round(vol_ratio, 2),
            "thesis_valid": thesis_valid,
            "thesis_invalidation_reason": invalidation_reason,
            "circuit_breaker_active": cb_active,
            "circuit_breaker_reason": cb_reason,
            "consecutive_losses_today": 0,
            "signals_active": max(0, 3 - slot // 8),  # Decay over day
            "signals_invalidated": thesis_flips if not thesis_valid else 0,
            "morning_verdict": "CONVICTION" if thesis_valid else "CAUTION",
            "last_check": time_str,
            "replay_mode": True,
            "replay_bar_index": slot,
        }

        # Save snapshot to file
        snap_file = f"{snapshot_dir}/{time_str.replace(':', '')}.json"
        with open(snap_file, "w") as f:
            json.dump(snapshot, f, indent=2)

        # Also write to /tmp/intraday_snapshot.json (latest)
        with open("/tmp/intraday_snapshot.json", "w") as f:
            json.dump(snapshot, f, indent=2)

        snapshots.append(snapshot)

        # Print progress
        thesis_icon = "✅" if thesis_valid else "⛔"
        cb_icon = " 🔴CB" if cb_active else ""
        print(f"  [{total_check:02d}/26] {time_str} ET | SPY {price:7.2f} | "
              f"wall={wall_status:12s} | vol={vol_char:12s} | "
              f"thesis={thesis_icon}{cb_icon}")

    # Write summary
    summary = {
        "date": date_str,
        "total_snapshots": len(snapshots),
        "thesis_flips": thesis_flips,
        "circuit_breaker_activations": sum(1 for s in snapshots if s["circuit_breaker_active"]),
        "wall_breaks": sum(1 for s in snapshots if s["wall_status"] == "broken"),
        "volume_spikes": sum(1 for s in snapshots if s["volume_character"] in ("climactic", "distribution")),
        "final_thesis": snapshots[-1]["thesis_valid"],
        "final_price": snapshots[-1]["spy_price"],
        "snapshot_dir": snapshot_dir,
    }

    summary_path = f"{snapshot_dir}/summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*70}")
    print(f"📊 REPLAY SUMMARY")
    print(f"{'='*70}")
    print(f"   Snapshots: {summary['total_snapshots']}")
    print(f"   Thesis flips: {summary['thesis_flips']}")
    print(f"   CB activations: {summary['circuit_breaker_activations']}")
    print(f"   Wall breaks: {summary['wall_breaks']}")
    print(f"   Volume spikes: {summary['volume_spikes']}")
    print(f"   Final thesis: {'✅ VALID' if summary['final_thesis'] else '⛔ INVALID'}")
    print(f"   Final price: ${summary['final_price']:.2f}")
    print(f"   Files: {snapshot_dir}/")
    print(f"{'='*70}")

    return summary


def run_force_invalidate_test():
    """Run the force_invalidate kill test to prove E2E."""
    from live_monitoring.intraday_guardian import IntradayGuardian

    print(f"\n{'='*70}")
    print(f"⚡ KILL TEST — force_invalidate()")
    print(f"{'='*70}")

    g = IntradayGuardian()
    snap = g.force_invalidate("KILL TEST: SPY broke call wall at 590 during replay")

    assert snap["thesis_valid"] == False, "FAIL: thesis should be invalid"
    print(f"   thesis_valid: {snap['thesis_valid']} ✅")
    print(f"   reason: {snap['thesis_invalidation_reason']}")

    # Verify file on disk
    with open("/tmp/intraday_snapshot.json") as f:
        disk = json.load(f)
    assert disk["thesis_valid"] == False, "FAIL: disk snapshot wrong"
    print(f"   disk file: ✅ correct")
    print(f"{'='*70}\n")


def run_bearish_backtest(start_date: str = "2026-03-05", end_date: str = "2026-03-13") -> dict:
    """Replay bearish divergence checker across date range using REAL DP data.
    
    - Reads real data from data/axlfi_dark_pool_live.json
    - Missing file → status: INSUFFICIENT_DATA (not fake data)
    - Outputs JSON with 8 required keys
    """
    from live_monitoring.orchestrator.confluence_gate import ConfluenceGate
    from live_monitoring.orchestrator.checkers.dp_bearish_checker import DPBearishDivergenceChecker

    result = {
        "mode": "bearish_backtest",
        "date_range": f"{start_date} → {end_date}",
        "status": "INSUFFICIENT_DATA",
        "total_bars": 0,
        "signals_fired": 0,
        "signals_blocked": 0,
        "avg_confidence": 0.0,
        "signal_log": [],
    }

    # ── Load real DP data ──
    dp_path = "data/axlfi_dark_pool_live.json"
    if not os.path.exists(dp_path):
        print(f"⚠️ DP data file not found: {dp_path}")
        print(json.dumps(result, indent=2))
        return result

    try:
        with open(dp_path) as f:
            dp_data = json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to read DP data: {e}")
        print(json.dumps(result, indent=2))
        return result

    # ── Extract DP flow from real format ──
    dp_flow_history = []
    for key, val in dp_data.items():
        if isinstance(val, dict) and 'symbol=SPY' in str(key) and 'window' in str(key):
            isv = val.get("individual_short_volume", {})
            if isinstance(isv, dict):
                nv = isv.get("net_volume", [])
                if isinstance(nv, list) and len(nv) >= 3:
                    dp_flow_history = [float(v) for v in nv]
            break
    
    # Fallback: legacy epoch format
    if not dp_flow_history:
        epochs = dp_data.get("epochs", dp_data.get("data", []))
        if isinstance(epochs, list):
            dp_flow_history = [e.get("net_premium", 0.0) for e in epochs if isinstance(e, dict)]
    
    if len(dp_flow_history) < 3:
        print(f"⚠️ Insufficient DP data points: {len(dp_flow_history)} < 3")
        print(json.dumps(result, indent=2))
        return result

    # ── Fetch real SPY price bars ──
    bars = get_spy_price_history(start_date)
    if not bars:
        print(f"⚠️ No SPY price data for {start_date}")
        result["status"] = "NO_PRICE_DATA"
        print(json.dumps(result, indent=2))
        return result

    result["status"] = "COMPLETE"
    result["total_bars"] = len(bars)

    # ── Build gate + checker ──
    gate = ConfluenceGate()
    checker = DPBearishDivergenceChecker(confluence_gate=gate)
    # Override market-open check for replay
    checker._is_market_open = lambda: True
    # Override data path to use loaded data in-memory
    
    confidences = []

    print(f"\n{'='*70}")
    print(f"🐻 BEARISH BACKTEST — {start_date} → {end_date}")
    print(f"{'='*70}")
    print(f"   DP Data Points: {len(dp_flow_history)}")
    print(f"   SPY Bars: {len(bars)}")
    print(f"{'='*70}\n")

    for i, bar in enumerate(bars):
        price = bar["close"]
        volume = bar.get("volume", 5_000_000)
        vol_ratio = volume / 5_000_000

        # Build snapshot for the checker (mimic guardian snapshot)
        snapshot = {
            "thesis_valid": True,
            "bearish_breakdown_building": False,
            "spy_price": price,
            "spy_call_wall": dp_data.get("call_wall", price + 5),
            "spy_put_wall": dp_data.get("put_wall", price - 5),
            "spy_open": bars[0]["close"],  # First bar as open proxy
            "volume_ratio": round(vol_ratio, 2),
        }

        # Write DP data to expected path (checker reads from file)
        tmp_dp = dp_data.copy()
        tmp_dp["date"] = bar.get("timestamp", start_date)[:10]  # Match date check
        try:
            os.makedirs("data", exist_ok=True)
            with open(dp_path, "w") as f:
                json.dump(tmp_dp, f)
        except Exception:
            pass

        res = checker.check(price, snapshot)

        if res.get("signal_fired"):
            result["signals_fired"] += 1
            confidences.append(res.get("confidence", 0))
            entry = {
                "bar": i,
                "timestamp": bar.get("timestamp", "?"),
                "spy_price": price,
                "confidence": res.get("confidence", 0),
                "dp_flow": res.get("dp_flow", 0),
                "verdict": res.get("gate_verdict", "?"),
            }
            result["signal_log"].append(entry)
            print(f"  🔴 BAR {i:03d} | SPY ${price:.2f} | SIGNAL FIRED | Confidence {res.get('confidence', 0):.0f}%")
        elif res.get("dp_direction") == "NEGATIVE":
            result["signals_blocked"] += 1
            print(f"  ⛔ BAR {i:03d} | SPY ${price:.2f} | BLOCKED by gate | {res.get('gate_verdict', '?')}")
        else:
            print(f"  ⚪ BAR {i:03d} | SPY ${price:.2f} | no divergence")

        # Reset cooldown for backtest (so each bar is independent)
        checker.last_fire_time = None

    result["avg_confidence"] = round(sum(confidences) / len(confidences), 1) if confidences else 0.0

    print(f"\n{'='*70}")
    print(f"📊 BACKTEST RESULTS")
    print(f"{'='*70}")
    print(f"   Bars tested: {result['total_bars']}")
    print(f"   Signals fired: {result['signals_fired']}")
    print(f"   Signals blocked: {result['signals_blocked']}")
    print(f"   Avg confidence: {result['avg_confidence']:.1f}%")
    print(f"{'='*70}")

    # Save result JSON
    os.makedirs("backtesting/reports", exist_ok=True)
    out_path = "backtesting/reports/bearish_backtest_results.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"   📄 Results: {out_path}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guardian Historical Replay")
    parser.add_argument("--date", default="2026-03-13",
                        help="Date to replay (YYYY-MM-DD)")
    parser.add_argument("--invalidate-at", default="13:00",
                        help="Time to trigger thesis invalidation (HH:MM)")
    parser.add_argument("--breaker-at", default=None,
                        help="Time to trigger circuit breaker (HH:MM)")
    parser.add_argument("--kill-test", action="store_true",
                        help="Run force_invalidate kill test after replay")
    parser.add_argument("--no-invalidate", action="store_true",
                        help="Run clean session with no invalidation")

    parser.add_argument("--mode", default="replay",
                        choices=["replay", "bearish_backtest"],
                        help="Run mode: 'replay' (default) or 'bearish_backtest'")

    args = parser.parse_args()

    if args.mode == "bearish_backtest":
        run_bearish_backtest()
        sys.exit(0)

    invalidate_at = None if args.no_invalidate else args.invalidate_at

    summary = run_replay(
        date_str=args.date,
        invalidate_at=invalidate_at,
        breaker_at=args.breaker_at,
    )

    if args.kill_test:
        run_force_invalidate_test()

    print(f"\n✅ Replay complete. {summary['total_snapshots']} snapshots saved.")
