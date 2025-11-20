#!/usr/bin/env python3
"""
Core Signals Runner (Minimal, Live, DP-aware)
- Tickers: SPY, QQQ
- Source priority: Yahoo Direct (chart API) → yfinance (fallback)
- RTH only (09:30–16:00 ET) by default; can run short validation anytime
- Signals: composite breakout/reversal with DP filtering
- Output: CSV/JSON logs with timestamp, regime, decision; echo missed intervals

Notes:
- Designed for resilient live operation with graceful degradation.
- Uses Yahoo Direct chart API to seed rolling windows without RapidAPI.
"""

import asyncio
import csv
import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from zoneinfo import ZoneInfo

try:
    import yfinance as yf  # fallback only
except Exception:
    yf = None

# Optional DP-aware filter (best-effort)
try:
    from filters.dp_aware_signal_filter import DPAwareSignalFilter  # type: ignore
except Exception:
    DPAwareSignalFilter = None  # type: ignore


US_EASTERN = ZoneInfo("America/New_York")


@dataclass
class MarketPoint:
    timestamp: datetime
    price: float
    volume: int


class YahooDirectProvider:
    """Yahoo Direct chart API + quote scraping for robustness."""

    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        ]

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        }

    def get_intraday_series(self, ticker: str, interval: str = "1m", range_: str = "1d") -> List[MarketPoint]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_}"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return []
        r0 = result[0]
        ts_list = r0.get("timestamp", [])
        indicators = r0.get("indicators", {})
        quote = indicators.get("quote", [{}])[0]
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])
        points: List[MarketPoint] = []
        for i, ts in enumerate(ts_list):
            try:
                price = float(closes[i]) if closes[i] is not None else np.nan
                vol = int(volumes[i]) if volumes[i] is not None else 0
                if np.isnan(price):
                    continue
                dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone(US_EASTERN).replace(tzinfo=None)
                points.append(MarketPoint(timestamp=dt, price=price, volume=vol))
            except Exception:
                continue
        return points

    def get_last_quote(self, ticker: str) -> Optional[MarketPoint]:
        # Use chart API range=1d to get latest
        series = self.get_intraday_series(ticker, interval="1m", range_="1d")
        if not series:
            return None
        return series[-1]


class CoreSignalsRunner:
    def __init__(self, tickers: List[str], logs_dir: str = "logs", require_rth: bool = True):
        self.tickers = tickers
        self.logs_dir = logs_dir
        os.makedirs(self.logs_dir, exist_ok=True)
        self.csv_path = os.path.join(self.logs_dir, "core_signals.csv")
        self.jsonl_path = os.path.join(self.logs_dir, "core_signals.jsonl")

        self.provider = YahooDirectProvider()
        self.dp_filter = DPAwareSignalFilter() if DPAwareSignalFilter else None
        self.require_rth = require_rth

        # Rolling storage per ticker
        self.price_history: Dict[str, List[MarketPoint]] = {t: [] for t in self.tickers}

        # Detection thresholds
        self.breakout_threshold = 0.006  # 0.6% above resistance
        self.reversal_threshold = 0.006  # 0.6% below support
        self.volume_spike_mult = 1.8
        self.min_points = 20  # require window to stabilize

        # CSV header
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "ticker", "regime", "signal_type", "price", "level", "strength",
                    "volume", "volume_spike", "dp_confirmed", "reason"
                ])

    def _is_rth_now(self) -> bool:
        now_et = datetime.now(US_EASTERN)
        if now_et.weekday() >= 5:
            return False
        rth_start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        rth_end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return rth_start <= now_et <= rth_end

    def _append_history(self, ticker: str, points: List[MarketPoint]) -> None:
        if not points:
            return
        hist = self.price_history[ticker]
        hist.extend(points)
        # Deduplicate by timestamp and keep last 300 points
        seen = {}
        for p in hist:
            seen[p.timestamp] = p
        hist_new = list(sorted(seen.values(), key=lambda x: x.timestamp))
        self.price_history[ticker] = hist_new[-300:]

    def _compute_regime(self, ticker: str) -> Dict[str, Any]:
        hist = self.price_history[ticker]
        if len(hist) < 10:
            return {"regime": "UNKNOWN", "confidence": 0.0, "reasoning": "Insufficient data"}
        
        closes = np.array([p.price for p in hist[-20:]], dtype=float)
        vols = np.array([p.volume for p in hist[-20:]], dtype=float)
        
        # trend slope normalized
        x = np.arange(len(closes))
        try:
            slope = np.polyfit(x, closes, 1)[0]
            trend_strength = float(slope / np.mean(closes)) if np.mean(closes) else 0.0
        except Exception:
            trend_strength = 0.0
        
        # volatility
        rets = np.diff(closes) / closes[:-1] if len(closes) > 1 else np.array([0.0])
        vol = float(np.std(rets))
        
        # momentum
        momentum = float((closes[-1] - closes[0]) / closes[0]) if closes[0] else 0.0
        
        # volume regime
        vol_ratio = float(np.mean(vols[-5:]) / (np.mean(vols[-10:-5]) + 1e-9)) if len(vols) >= 10 else 1.0
        
        # decide regime
        regime = "CHOP"
        confidence = 0.5
        reasoning_parts = []
        
        if trend_strength > 0.002 and momentum > 0.003:
            regime = "UPTREND"
            confidence += 0.2
            reasoning_parts.append(f"Trend: {trend_strength:.4f}")
        elif trend_strength < -0.002 and momentum < -0.003:
            regime = "DOWNTREND"
            confidence += 0.2
            reasoning_parts.append(f"Trend: {trend_strength:.4f}")
        
        if vol > 0.02:
            confidence += 0.1
            reasoning_parts.append(f"Vol: {vol:.4f}")
        
        if vol_ratio > 1.5:
            confidence += 0.1
            reasoning_parts.append(f"VolRatio: {vol_ratio:.2f}")
        
        if not reasoning_parts:
            reasoning_parts.append("No strong signals")
        
        return {
            "regime": regime,
            "confidence": min(1.0, confidence),
            "trend_strength": trend_strength,
            "volatility": vol,
            "momentum": momentum,
            "volume_ratio": vol_ratio,
            "reasoning": ", ".join(reasoning_parts),
            "data_points": len(hist)
        }

    def _detect_levels(self, prices: List[float]) -> Dict[str, List[float]]:
        supports: List[float] = []
        resistances: List[float] = []
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i - 1] and prices[i] < prices[i + 1]:
                supports.append(prices[i])
            if prices[i] > prices[i - 1] and prices[i] > prices[i + 1]:
                resistances.append(prices[i])
        return {
            "supports": list(sorted(supports))[:3],
            "resistances": list(sorted(resistances, reverse=True))[:3],
        }

    async def _dp_confirm(self, ticker: str, kind: str) -> bool:
        if not self.dp_filter:
            print(f"⚠️  DP FILTER WARNING: No DP filter available for {ticker} {kind}")
            return False
        try:
            signals = await self.dp_filter.filter_signals_with_dp_confirmation(ticker)
            if not signals:
                print(f"⚠️  DP FILTER WARNING: No DP signals returned for {ticker} {kind}")
                return False
            if kind == "BREAKOUT":
                confirmed = any(getattr(s, "dp_confirmation", False) and getattr(s, "breakout_confirmed", False) for s in signals)
                if confirmed:
                    print(f"✅ DP CONFIRMED: {ticker} {kind} - DP structure agrees")
                else:
                    print(f"❌ DP REJECTED: {ticker} {kind} - DP structure disagrees")
                return confirmed
            confirmed = any(getattr(s, "dp_confirmation", False) and getattr(s, "mean_reversion_confirmed", False) for s in signals)
            if confirmed:
                print(f"✅ DP CONFIRMED: {ticker} {kind} - DP structure agrees")
            else:
                print(f"❌ DP REJECTED: {ticker} {kind} - DP structure disagrees")
            return confirmed
        except Exception as e:
            print(f"⚠️  DP FILTER ERROR: {ticker} {kind} - {e}")
            return False

    def _log_decision(self, row: Dict[str, Any]) -> None:
        # CSV
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                row.get("timestamp"), row.get("ticker"), row.get("regime"), row.get("signal_type"),
                row.get("price"), row.get("level"), row.get("strength"), row.get("volume"),
                row.get("volume_spike"), row.get("dp_confirmed"), row.get("reason"),
            ])
        # JSONL
        with open(self.jsonl_path, "a") as f:
            f.write(json.dumps(row) + "\n")

    async def run_once(self, custom_timestamp: Optional[datetime] = None) -> None:
        now = (custom_timestamp or datetime.now()).replace(microsecond=0)
        if self.require_rth and not self._is_rth_now():
            # echo missed interval
            for t in self.tickers:
                self._log_decision({
                    "timestamp": now.isoformat(),
                    "ticker": t,
                    "regime": "OUT_OF_RTH",
                    "signal_type": "NONE",
                    "price": None,
                    "level": None,
                    "strength": None,
                    "volume": None,
                    "volume_spike": None,
                    "dp_confirmed": None,
                    "reason": "Missed interval (outside RTH)",
                })
            return

        for ticker in self.tickers:
            try:
                # In replay mode, we already have historical data loaded
                # Just use the existing history for analysis
                hist = self.price_history[ticker]
                if len(hist) < self.min_points:
                    self._log_decision({
                        "timestamp": now.isoformat(),
                        "ticker": ticker,
                        "regime": "WARMING_UP",
                        "signal_type": "NONE",
                        "price": hist[-1].price if hist else None,
                        "level": None,
                        "strength": None,
                        "volume": hist[-1].volume if hist else None,
                        "volume_spike": None,
                        "dp_confirmed": None,
                        "reason": f"Insufficient history ({len(hist)}/{self.min_points})",
                    })
                    continue

                # Compute regime with detailed analysis
                regime_info = self._compute_regime(ticker)
                regime = regime_info["regime"]
                
                # Print real-time rolling calculations
                print(f"\n🔍 {now.strftime('%H:%M:%S')} - {ticker}:")
                print(f"   Price: ${hist[-1].price:.2f}")
                print(f"   Volume: {hist[-1].volume:,}")
                print(f"   Regime: {regime} (confidence: {regime_info['confidence']:.2f})")
                print(f"   Trend Strength: {regime_info['trend_strength']:.4f}")
                print(f"   Volatility: {regime_info['volatility']:.4f}")
                print(f"   Momentum: {regime_info['momentum']:.4f}")
                print(f"   Volume Ratio: {regime_info['volume_ratio']:.2f}")
                print(f"   Data Points: {regime_info['data_points']}")
                print(f"   Reasoning: {regime_info['reasoning']}")

                # Prepare arrays
                closes = [p.price for p in hist[-40:]]
                vols = [p.volume for p in hist[-40:]]
                levels = self._detect_levels(closes)
                price = closes[-1]
                volume = vols[-1]
                avg_vol = float(np.mean(vols[-10:])) if len(vols) >= 10 else volume
                volume_spike = volume > avg_vol * self.volume_spike_mult

                # Check breakout
                actionable_logged = False
                for resistance in levels["resistances"]:
                    if price > resistance * (1.0 + self.breakout_threshold):
                        strength = (price - resistance) / resistance
                        dp_ok = await self._dp_confirm(ticker, "BREAKOUT")
                        row = {
                            "timestamp": now.isoformat(),
                            "ticker": ticker,
                            "regime": regime,
                            "signal_type": "BREAKOUT" if dp_ok else "CANDIDATE_BREAKOUT",
                            "price": price,
                            "level": resistance,
                            "strength": strength,
                            "volume": volume,
                            "volume_spike": volume_spike,
                            "dp_confirmed": dp_ok,
                            "reason": f"Price > resistance*(1+thr); thr={self.breakout_threshold}",
                        }
                        self._log_decision(row)
                        actionable_logged = actionable_logged or dp_ok
                        break

                # Check reversal if no breakout logged
                if not actionable_logged:
                    for support in levels["supports"]:
                        if price < support * (1.0 - self.reversal_threshold):
                            strength = (support - price) / support
                            dp_ok = await self._dp_confirm(ticker, "REVERSAL")
                            row = {
                                "timestamp": now.isoformat(),
                                "ticker": ticker,
                                "regime": regime,
                                "signal_type": "REVERSAL" if dp_ok else "CANDIDATE_REVERSAL",
                                "price": price,
                                "level": support,
                                "strength": strength,
                                "volume": volume,
                                "volume_spike": volume_spike,
                                "dp_confirmed": dp_ok,
                                "reason": f"Price < support*(1-thr); thr={self.reversal_threshold}",
                            }
                            self._log_decision(row)
                            actionable_logged = True
                            break

                # Log NO_SIGNAL heartbeat if no actionable signal
                if not actionable_logged:
                    self._log_decision({
                        "timestamp": now.isoformat(),
                        "ticker": ticker,
                        "regime": regime,
                        "signal_type": "NO_SIGNAL",
                        "price": price,
                        "level": None,
                        "strength": None,
                        "volume": volume,
                        "volume_spike": volume_spike,
                        "dp_confirmed": None,
                        "reason": f"No breakout/reversal detected. Resistance: {levels['resistances'][:2]}, Support: {levels['supports'][:2]}",
                    })

            except Exception as e:
                print(f"❌ ERROR processing {ticker}: {e}")
                self._log_decision({
                    "timestamp": now.isoformat(),
                    "ticker": ticker,
                    "regime": "ERROR",
                    "signal_type": "NONE",
                    "price": None,
                    "level": None,
                    "strength": None,
                    "volume": None,
                    "volume_spike": None,
                    "dp_confirmed": None,
                    "reason": f"Fetch/process error: {e}",
                })


async def main() -> None:
    print("🔥 CORE SIGNALS RUNNER - REPLAY MODE (TODAY'S RTH)")
    print("=" * 80)
    
    # Focus on SPY/QQQ for today's session
    tickers = ["SPY", "QQQ"]
    runner = CoreSignalsRunner(tickers=tickers, require_rth=False)  # Disable RTH check for replay

    # Get today's date
    today = datetime.now(US_EASTERN).date()
    print(f"📅 Replaying RTH session for {today}")
    
    # Seed initial history with today's data
    print("🌱 Loading today's historical data...")
    for t in tickers:
        try:
            # Get full day's data
            seed = runner.provider.get_intraday_series(t, interval="1m", range_="1d")
            if seed:
                # Filter to RTH only (09:30-16:00 ET)
                rth_data = []
                for point in seed:
                    if 9 <= point.timestamp.hour <= 16:
                        if point.timestamp.hour == 9 and point.timestamp.minute < 30:
                            continue
                        if point.timestamp.hour == 16 and point.timestamp.minute > 0:
                            continue
                        rth_data.append(point)
                
                runner._append_history(t, rth_data)
                print(f"   ✅ {t}: {len(rth_data)} RTH points loaded ({len(seed)} total)")
            else:
                print(f"   ❌ {t}: No data available")
        except Exception as e:
            print(f"   ❌ {t}: Failed to load - {e}")

    # Replay the historical data minute by minute
    print(f"\n🚀 Starting replay for {tickers}...")
    print("   Processing each minute with full signal detection")
    print("   Generating complete heartbeat log for today's RTH")
    print("   Press Ctrl+C to stop\n")

    # Process each minute of today's RTH data
    cycle_count = 0
    total_minutes = 0
    
    # Get the earliest start time across all tickers
    all_timestamps = []
    for ticker in tickers:
        hist = runner.price_history[ticker]
        if hist:
            all_timestamps.extend([p.timestamp for p in hist])
    
    if not all_timestamps:
        print("❌ No historical data available for replay")
        return
    
    # Sort all timestamps and process minute by minute
    all_timestamps = sorted(set(all_timestamps))
    print(f"📊 Processing {len(all_timestamps)} unique minutes across all tickers...")
    
    # Create a new runner for replay that simulates minute-by-minute processing
    replay_runner = CoreSignalsRunner(tickers=tickers, require_rth=False)
    
    for i, timestamp in enumerate(all_timestamps):
        cycle_count += 1
        total_minutes += 1
        
        try:
            print(f"\n{'='*60}")
            print(f"🔄 CYCLE {cycle_count} - {timestamp.strftime('%H:%M:%S')} ET")
            print(f"{'='*60}")
            
            # For each ticker, add data up to this timestamp
            for ticker in tickers:
                hist = runner.price_history[ticker]
                if hist:
                    # Add all data points up to and including this timestamp
                    points_up_to_now = [p for p in hist if p.timestamp <= timestamp]
                    replay_runner._append_history(ticker, points_up_to_now)
            
            # Run detection for this historical timestamp
            await replay_runner.run_once(custom_timestamp=timestamp)
            
            # Small delay to see output
            await asyncio.sleep(0.05)
            
        except Exception as e:
            print(f"❌ Error processing at {timestamp}: {e}")

    print(f"\n\n✅ REPLAY COMPLETE!")
    print(f"   Total minutes processed: {total_minutes}")
    print(f"   Total cycles: {cycle_count}")
    print(f"   Logs written to: {runner.csv_path} and {runner.jsonl_path}")
    print(f"   Review logs for today's complete RTH market action!")
    
    # Show summary of what was logged
    try:
        with open(runner.csv_path, 'r') as f:
            lines = f.readlines()
            print(f"\n📋 LOG SUMMARY:")
            print(f"   Total log entries: {len(lines) - 1}")  # -1 for header
            
            # Count signal types
            signal_counts = {}
            for line in lines[1:]:  # Skip header
                parts = line.strip().split(',')
                if len(parts) >= 4:
                    signal_type = parts[3]
                    signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
            for signal_type, count in signal_counts.items():
                print(f"   {signal_type}: {count}")
                
    except Exception as e:
        print(f"   Could not read log summary: {e}")


if __name__ == "__main__":
    asyncio.run(main())


