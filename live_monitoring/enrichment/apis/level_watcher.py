"""
⚔️ LEVEL WATCHER — The Activation Layer

60-second daemon that monitors SPY price vs DP levels.
When price is within 0.5% of a known level, classifies the pattern context
(touch count, time of day, volume regime) and routes through ConfluenceGate.

On gate pass → Discord alert + gate_signals_today.json entry.

Constraints (per manager):
  1. Hydrate _touch_counts from dp_learning.db on startup
  2. Single background daemon thread, 60s sleep, auto-continue on errors
  3. Pass /tmp/intraday_snapshot.json into every gate.should_fire()
  4. Discord alert + gate_signals_today.json on gate pass
"""

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # → ai-hedge-fund-main/
DB_PATH = PROJECT_ROOT / "data" / "dp_learning.db"
SNAPSHOT_PATH = "/tmp/intraday_snapshot.json"
SIGNALS_PATH = PROJECT_ROOT / "data" / "gate_signals_today.json"
API_BASE = os.getenv("API_BASE", "http://localhost:8000/api/v1")

# ─── Config ───────────────────────────────────────────────────────────────
POLL_INTERVAL = 60          # seconds
PROXIMITY_THRESHOLD = 0.5   # percent
SYMBOLS = ["SPY"]           # watchlist


class LevelWatcher:
    """
    Background daemon that watches SPY price vs DP levels.
    When price approaches a level, classifies the pattern and routes
    through ConfluenceGate.
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Touch count state — hydrated from DB, updated in-memory
        self._touch_counts: Dict[str, int] = {}

        # Gate + alert infra
        self._gate = None
        self._alert_manager = None
        self._engine = None

        # Track today's signals to avoid duplicate alerts
        self._today_signals: List[dict] = []

    # ══════════════════════════════════════════════════════════════════════
    # CONSTRAINT 1: Hydrate _touch_counts from dp_learning.db on startup
    # ══════════════════════════════════════════════════════════════════════
    def _hydrate_touch_counts(self):
        """
        Read dp_learning.db and populate _touch_counts with the maximum
        touch_count per (symbol, level_price) pair. This ensures Touch 3
        stays Touch 3 after a restart.
        """
        if not DB_PATH.exists():
            logger.warning(f"⚠️ dp_learning.db not found at {DB_PATH}")
            return

        try:
            conn = sqlite3.connect(str(DB_PATH))
            rows = conn.execute(
                "SELECT symbol, ROUND(level_price, 2) as lp, MAX(touch_count) as tc "
                "FROM dp_interactions "
                "GROUP BY symbol, ROUND(level_price, 2)"
            ).fetchall()
            conn.close()

            for symbol, level_price, touch_count in rows:
                key = f"{symbol}_{float(level_price):.2f}"
                self._touch_counts[key] = touch_count or 1

            logger.info(f"✅ Hydrated {len(self._touch_counts)} touch counts from DB")
            # Log top 5 by count
            top5 = sorted(self._touch_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            for key, count in top5:
                logger.info(f"   {key}: {count} touches")

        except Exception as e:
            logger.error(f"❌ Touch count hydration failed: {e}")

    def _get_touch_count(self, symbol: str, level_price: float) -> int:
        """Get current touch count for a level (from hydrated state)."""
        key = f"{symbol}_{level_price:.2f}"
        return self._touch_counts.get(key, 0) + 1  # Next touch

    # ══════════════════════════════════════════════════════════════════════
    # Data fetching (from live API)
    # ══════════════════════════════════════════════════════════════════════
    def _fetch_json(self, path: str) -> Optional[dict]:
        """Fetch JSON from local API."""
        import requests
        try:
            resp = requests.get(f"{API_BASE}{path}", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.debug(f"⚠️ Fetch {path} failed: {e}")
            return None

    def _get_current_price(self, symbol: str) -> Optional[float]:
        data = self._fetch_json(f"/charts/{symbol}/matrix")
        return data.get("current_price") if data else None

    def _get_dp_levels(self, symbol: str) -> List[dict]:
        data = self._fetch_json(f"/darkpool/{symbol}/levels")
        if data:
            return data.get("levels", [])
        return []

    def _get_patterns(self) -> Dict[str, float]:
        """Fetch pattern bounce rates: {pattern_name: bounce_rate}."""
        data = self._fetch_json("/dp/patterns")
        if data:
            return {p["pattern_name"]: p["bounce_rate"]
                    for p in data.get("patterns", [])}
        return {}

    def _get_prediction(self, symbol: str) -> Optional[dict]:
        """Get ML prediction for symbol."""
        return self._fetch_json(f"/dp/prediction/{symbol}")

    # ══════════════════════════════════════════════════════════════════════
    # CONSTRAINT 3: Load intraday_snapshot.json for gate
    # ══════════════════════════════════════════════════════════════════════
    def _load_snapshot(self) -> dict:
        """Load /tmp/intraday_snapshot.json for ConfluenceGate."""
        if os.path.exists(SNAPSHOT_PATH):
            try:
                with open(SNAPSHOT_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"⚠️ Snapshot read failed: {e}")
        return {}

    # ══════════════════════════════════════════════════════════════════════
    # Pattern classification
    # ══════════════════════════════════════════════════════════════════════
    def _classify_context(self, symbol: str, level: dict,
                          current_price: float, patterns: Dict[str, float]) -> dict:
        """
        Classify the current approach context against the pattern table.

        Returns:
            {
                "level_price": 660.0,
                "level_type": "SUPPORT",
                "distance_pct": 0.35,
                "touch_count": 1,
                "time_of_day": "MIDDAY",
                "matching_patterns": [("touch_1", 97.9), ("midday", 94.1), ...],
                "compound_confidence": 94.5,
                "signal_direction": "LONG"
            }
        """
        level_price = level["price"]
        level_type = level.get("level_type", "SUPPORT")
        distance_pct = abs(current_price - level_price) / level_price * 100

        # Touch count (from hydrated DB state)
        touch_count = self._get_touch_count(symbol, level_price)

        # Time of day classification
        hour = datetime.now().hour
        if 9 <= hour < 11:
            tod = "morning"
        elif 11 <= hour < 14:
            tod = "midday"
        else:
            tod = "afternoon"

        # Pattern matching
        matching = []

        # Touch count pattern
        if touch_count == 1 and "touch_1" in patterns:
            matching.append(("touch_1", patterns["touch_1"]))
        elif touch_count == 2 and "touch_2" in patterns:
            matching.append(("touch_2", patterns["touch_2"]))
        elif touch_count >= 3 and "touch_3_plus" in patterns:
            matching.append(("touch_3_plus", patterns["touch_3_plus"]))

        # Time of day pattern
        if tod in patterns:
            matching.append((tod, patterns[tod]))

        # Level type pattern
        lt_key = level_type.lower()
        if lt_key in patterns:
            matching.append((lt_key, patterns[lt_key]))

        # Volume patterns (if available from summary)
        if "vol_2m_plus" in patterns:
            vol = level.get("volume", 0)
            if vol >= 2_000_000:
                matching.append(("vol_2m_plus", patterns["vol_2m_plus"]))

        # Signal direction: support → LONG, resistance → SHORT
        signal_direction = "LONG" if level_type == "SUPPORT" else "SHORT"

        # Compound confidence: weighted average of matching patterns
        if matching:
            compound = sum(rate for _, rate in matching) / len(matching)
        else:
            compound = 50.0  # No pattern match — neutral

        return {
            "symbol": symbol,
            "level_price": level_price,
            "level_type": level_type,
            "distance_pct": round(distance_pct, 3),
            "touch_count": touch_count,
            "time_of_day": tod,
            "matching_patterns": matching,
            "compound_confidence": round(compound, 1),
            "signal_direction": signal_direction,
            "current_price": current_price,
        }

    # ══════════════════════════════════════════════════════════════════════
    # Gate + Alert (Constraints 3 & 4)
    # ══════════════════════════════════════════════════════════════════════
    def _run_gate(self, ctx: dict) -> Optional[dict]:
        """
        Pass the classified context through ConfluenceGate.
        Loads intraday_snapshot.json for every call.
        """
        try:
            if not self._gate:
                from live_monitoring.orchestrator.confluence_gate import ConfluenceGate
                self._gate = ConfluenceGate()

            snapshot = self._load_snapshot()

            result = self._gate.should_fire(
                signal_direction=ctx["signal_direction"],
                symbol=ctx["symbol"],
                raw_confidence=ctx["compound_confidence"],
                current_price=ctx["current_price"],
                snapshot=snapshot,
            )

            return {
                "blocked": result.blocked,
                "reason": result.reason,
                "adjusted_confidence": result.adjusted_confidence,
                "gates_passed": result.gates_passed,
                "gates_failed": result.gates_failed,
                "regime": result.regime,
                "bias": result.bias,
                "sizing_multiplier": result.sizing_multiplier,
            }
        except Exception as e:
            logger.error(f"❌ Gate check failed: {e}")
            return None

    def _compute_trade_levels(self, ctx: dict) -> dict:
        """Compute entry, stop, target, R:R from context.

        Target = nearest GEX call wall (LONG) or put wall (SHORT).
        Falls back to 2R if walls unavailable from snapshot.
        """
        level = ctx["level_price"]
        snapshot = self._load_snapshot()

        if ctx["signal_direction"] == "LONG":
            entry = round(level + 0.50, 2)
            stop = round(level - 3.00, 2)
            risk = entry - stop

            # Target: nearest call wall above entry from GEX
            call_wall = snapshot.get("spy_call_wall")
            if call_wall and float(call_wall) > entry:
                target = round(float(call_wall), 2)
            else:
                target = round(entry + risk * 2, 2)  # 2R fallback
        else:  # SHORT
            entry = round(level - 0.50, 2)
            stop = round(level + 3.00, 2)
            risk = stop - entry

            # Target: nearest put wall below entry from GEX
            put_wall = snapshot.get("spy_put_wall")
            if put_wall and float(put_wall) < entry:
                target = round(float(put_wall), 2)
            else:
                target = round(entry - risk * 2, 2)  # 2R fallback

        reward = abs(entry - target)
        rr = round(reward / risk, 1) if risk > 0 else 0

        return {
            "entry": entry,
            "stop": stop,
            "target": target,
            "rr": rr,
        }

    # ══════════════════════════════════════════════════════════════════════
    # CONSTRAINT 4: Discord alert + gate_signals_today.json
    # ══════════════════════════════════════════════════════════════════════
    def _send_alert(self, ctx: dict, gate_result: dict, trade: dict):
        """Send Discord alert and write to gate_signals_today.json."""

        # ── Discord embed ──
        patterns_str = ", ".join(
            f"{p} ({r:.1f}%)" for p, r in ctx["matching_patterns"]
        )
        embed = {
            "title": f"⚔️ LEVEL WATCHER: {ctx['signal_direction']} {ctx['symbol']}",
            "description": (
                f"**{ctx['symbol']}** approaching **${ctx['level_price']:.2f}** "
                f"{ctx['level_type']} level\n\n"
                f"**Pattern Match:** {patterns_str}\n"
                f"**Bounce Probability:** {ctx['compound_confidence']:.1f}%\n"
                f"**Touch Count:** {ctx['touch_count']} | "
                f"**Time:** {ctx['time_of_day'].upper()}\n\n"
                f"**Entry:** ${trade['entry']:.2f}\n"
                f"**Stop:** ${trade['stop']:.2f}\n"
                f"**Target:** ${trade['target']:.2f}\n"
                f"**R:R:** {trade['rr']:.1f}:1\n\n"
                f"Gate: {gate_result['reason']}\n"
                f"Sizing: {gate_result['sizing_multiplier']}x"
            ),
            "color": 0x00FF88 if ctx["signal_direction"] == "LONG" else 0xFF3366,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "LevelWatcher | ConfluenceGate"},
        }

        try:
            if not self._alert_manager:
                from live_monitoring.orchestrator.alert_manager import AlertManager
                self._alert_manager = AlertManager()

            self._alert_manager.send_discord(
                embed=embed,
                alert_type="LEVEL_WATCHER_SIGNAL",
                source="level_watcher",
                symbol=ctx["symbol"],
            )
            logger.info(f"📤 Discord alert sent: {ctx['signal_direction']} {ctx['symbol']} @ ${ctx['level_price']:.2f}")
        except Exception as e:
            logger.error(f"❌ Discord alert failed: {e}")

        # ── gate_signals_today.json ──
        signal_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "date": str(date.today()),
            "symbol": ctx["symbol"],
            "direction": ctx["signal_direction"],
            "level_price": ctx["level_price"],
            "level_type": ctx["level_type"],
            "current_price": ctx["current_price"],
            "distance_pct": ctx["distance_pct"],
            "touch_count": ctx["touch_count"],
            "time_of_day": ctx["time_of_day"],
            "patterns": ctx["matching_patterns"],
            "compound_confidence": ctx["compound_confidence"],
            "entry": trade["entry"],
            "stop": trade["stop"],
            "target": trade["target"],
            "rr": trade["rr"],
            "gate_result": gate_result["reason"],
            "regime": gate_result["regime"],
            "bias": gate_result["bias"],
            "sizing": gate_result["sizing_multiplier"],
            "status": "active",
        }

        self._today_signals.append(signal_entry)
        self._write_signals_file()

        logger.info(
            f"📝 Signal written to gate_signals_today.json: "
            f"{ctx['signal_direction']} {ctx['symbol']} "
            f"@ ${ctx['level_price']:.2f} (confidence {ctx['compound_confidence']:.1f}%)"
        )

    def _write_signals_file(self):
        """Write today's signals to gate_signals_today.json."""
        try:
            SIGNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(SIGNALS_PATH, "w") as f:
                json.dump({
                    "date": str(date.today()),
                    "signals": self._today_signals,
                    "count": len(self._today_signals),
                }, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"❌ Failed to write signals file: {e}")

    def _signal_already_fired(self, symbol: str, level_price: float) -> bool:
        """Check if we already fired a signal for this level today."""
        for sig in self._today_signals:
            if (sig["symbol"] == symbol
                    and abs(sig["level_price"] - level_price) < 0.50
                    and sig["date"] == str(date.today())):
                return True
        return False

    # ══════════════════════════════════════════════════════════════════════
    # CONSTRAINT 2: Single background daemon thread, 60s sleep
    # ══════════════════════════════════════════════════════════════════════
    def _poll_once(self):
        """Single poll iteration: check all symbols vs all levels."""
        patterns = self._get_patterns()
        if not patterns:
            logger.debug("⚠️ No patterns available, skipping cycle")
            return

        for symbol in SYMBOLS:
            try:
                price = self._get_current_price(symbol)
                if not price:
                    logger.debug(f"⚠️ No price for {symbol}")
                    continue

                levels = self._get_dp_levels(symbol)
                if not levels:
                    logger.debug(f"⚠️ No DP levels for {symbol}")
                    continue

                # Check each level for proximity
                for level in levels:
                    level_price = level.get("price", 0)
                    if level_price <= 0:
                        continue

                    distance_pct = abs(price - level_price) / level_price * 100
                    if distance_pct > PROXIMITY_THRESHOLD:
                        continue

                    # Within 0.5% — classify and evaluate
                    logger.info(
                        f"🎯 {symbol} @ ${price:.2f} within {distance_pct:.2f}% "
                        f"of ${level_price:.2f} {level.get('level_type', '?')}"
                    )

                    # Skip if already fired today
                    if self._signal_already_fired(symbol, level_price):
                        logger.info(f"   ⏭️ Signal already fired for ${level_price:.2f} today")
                        continue

                    # Classify context
                    ctx = self._classify_context(symbol, level, price, patterns)
                    logger.info(
                        f"   📊 Touch {ctx['touch_count']} | {ctx['time_of_day']} | "
                        f"{len(ctx['matching_patterns'])} patterns | "
                        f"confidence {ctx['compound_confidence']:.1f}%"
                    )

                    # Run through gate (with snapshot per constraint 3)
                    gate_result = self._run_gate(ctx)
                    if not gate_result:
                        logger.warning("   ⚠️ Gate check returned None")
                        continue

                    if gate_result["blocked"]:
                        logger.info(f"   ⛔ BLOCKED: {gate_result['reason']}")
                        continue

                    # Gate passed — compute trade levels and alert
                    trade = self._compute_trade_levels(ctx)
                    logger.info(
                        f"   ✅ GATE PASS: Entry ${trade['entry']:.2f}, "
                        f"Stop ${trade['stop']:.2f}, Target ${trade['target']:.2f}, "
                        f"R:R {trade['rr']:.1f}:1"
                    )

                    self._send_alert(ctx, gate_result, trade)

            except Exception as e:
                logger.error(f"❌ Poll error for {symbol}: {e}")
                import traceback
                logger.debug(traceback.format_exc())

    def _daemon_loop(self):
        """Main daemon loop — runs every POLL_INTERVAL seconds."""
        logger.info("🚀 Level Watcher daemon started")
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as e:
                logger.error(f"❌ Poll cycle error (continuing): {e}")
                import traceback
                logger.debug(traceback.format_exc())

            self._stop_event.wait(POLL_INTERVAL)
        logger.info("🛑 Level Watcher daemon stopped")

    def start(self):
        """Start the level watcher daemon."""
        if self._thread and self._thread.is_alive():
            logger.warning("⚠️ Level Watcher already running")
            return

        # CONSTRAINT 1: Hydrate touch counts BEFORE polling starts
        self._hydrate_touch_counts()

        # Load any existing signals for today
        self._load_existing_signals()

        # CONSTRAINT 2: Single background daemon thread
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._daemon_loop,
            name="LevelWatcher",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"✅ Level Watcher started (poll={POLL_INTERVAL}s, threshold={PROXIMITY_THRESHOLD}%)")

    def stop(self):
        """Stop the daemon."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("🛑 Level Watcher stopped")

    def _load_existing_signals(self):
        """Load existing signals from gate_signals_today.json."""
        if SIGNALS_PATH.exists():
            try:
                with open(SIGNALS_PATH) as f:
                    data = json.load(f)
                if data.get("date") == str(date.today()):
                    self._today_signals = data.get("signals", [])
                    logger.info(f"📋 Loaded {len(self._today_signals)} existing signals for today")
                else:
                    logger.info("📋 Stale signals file (different date), starting fresh")
            except Exception as e:
                logger.debug(f"⚠️ Failed to load existing signals: {e}")

    def status(self) -> dict:
        """Get current watcher status."""
        return {
            "running": self._thread.is_alive() if self._thread else False,
            "touch_counts_loaded": len(self._touch_counts),
            "today_signals": len(self._today_signals),
            "symbols": SYMBOLS,
            "poll_interval": POLL_INTERVAL,
            "threshold": PROXIMITY_THRESHOLD,
        }


# ─── CLI entry point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    watcher = LevelWatcher()

    if "--test" in sys.argv:
        # Test mode: hydrate + single poll + exit
        print("=== TEST MODE ===")
        watcher._hydrate_touch_counts()
        print(f"\nTouch counts loaded: {len(watcher._touch_counts)}")
        top5 = sorted(watcher._touch_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for k, v in top5:
            print(f"  {k}: {v} touches")

        print("\n--- Running single poll ---")
        watcher._poll_once()

        print(f"\n--- Status ---")
        print(json.dumps(watcher.status(), indent=2))
    else:
        # Daemon mode: run until Ctrl+C
        watcher.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()
