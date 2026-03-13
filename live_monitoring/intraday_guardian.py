"""
🛡️ INTRADAY GUARDIAN

15-minute market-hours loop that checks whether the morning thesis is still valid.
Writes /tmp/intraday_snapshot.json — the single source of truth during 9:30–16:00 ET.

Reads:
  - SPY live price (yfinance)
  - SPY call/put wall (StockgridClient)
  - Morning brief verdict (/tmp/morning_briefs/{today}.json)
  - Gate outcomes (data/gate_outcomes.json)
  - Gate signals (data/gate_signals_today.json)

Writes:
  - /tmp/intraday_snapshot.json
"""

import json
import logging
import os
from datetime import datetime, date, time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SNAPSHOT_PATH = "/tmp/intraday_snapshot.json"
BRIEF_DIR = "/tmp/morning_briefs"
DATA_DIR = Path(__file__).resolve().parent / "orchestrator" / ".." / ".." / "data"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SIGNALS_TODAY = DATA_DIR / "gate_signals_today.json"
OUTCOMES_FILE = DATA_DIR / "gate_outcomes.json"


def _et_now():
    """Current time in US/Eastern."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("US/Eastern"))
    except ImportError:
        try:
            import pytz
            return datetime.now(pytz.timezone("US/Eastern"))
        except ImportError:
            from datetime import timedelta
            utc_now = datetime.utcnow()
            month = utc_now.month
            offset = 4 if 3 <= month <= 11 else 5
            return utc_now - timedelta(hours=offset)


class IntradayGuardian:
    """
    Market-hours watchdog. Detects when the morning thesis breaks.

    Usage:
        guardian = IntradayGuardian()
        snapshot = guardian.check()
        # snapshot['thesis_valid'] == False means STOP TRADING
    """

    def __init__(self):
        self._previous_thesis_valid: Optional[bool] = None
        self._wall_break_time: Optional[str] = None
        self._cached_walls: dict = {}

    def check(self) -> dict:
        """
        Run all intraday checks and write /tmp/intraday_snapshot.json.

        Returns the snapshot dict. Never crashes — returns safe defaults on any failure.
        """
        et = _et_now()
        now_str = et.isoformat()
        h, m = et.hour, et.minute

        # Check if market is open (9:30 - 16:00 ET, weekdays)
        market_open = (
            et.weekday() < 5
            and (
                (h == 9 and m >= 30)
                or (10 <= h <= 15)
                or (h == 16 and m == 0)
            )
        )

        # ── Defaults ──
        snapshot = {
            "timestamp": now_str,
            "market_open": market_open,
            "spy_price": 0.0,
            "spy_call_wall": 0.0,
            "spy_put_wall": 0.0,
            "spy_poc": 0.0,
            "spy_vs_wall": "unknown",
            "wall_status": "unknown",
            "wall_break_time": None,
            "volume_character": "unknown",
            "volume_ratio": 0.0,
            "thesis_valid": True,
            "thesis_invalidation_reason": None,
            "circuit_breaker_active": False,
            "circuit_breaker_reason": None,
            "consecutive_losses_today": 0,
            "signals_active": 0,
            "signals_invalidated": 0,
            "morning_verdict": None,
            "last_check": et.strftime("%H:%M:%S"),
        }

        if not market_open:
            # Market closed — return safe defaults, don't attempt yfinance
            snapshot["thesis_valid"] = True
            self._write_snapshot(snapshot)
            return snapshot

        # ── Step 1: SPY Price ──
        spy_price = self._get_spy_price()
        snapshot["spy_price"] = spy_price

        # ── Step 2-4: Option Walls ──
        call_wall, put_wall, poc = self._get_walls()
        snapshot["spy_call_wall"] = call_wall
        snapshot["spy_put_wall"] = put_wall
        snapshot["spy_poc"] = poc

        # ── Step 5: SPY vs Wall ──
        if spy_price > 0 and call_wall > 0:
            diff = spy_price - call_wall
            if diff > 0.5:
                snapshot["spy_vs_wall"] = "above"
                snapshot["wall_status"] = "defended"
            elif diff < -0.5:
                snapshot["spy_vs_wall"] = "below"
                snapshot["wall_status"] = "broken"
                if self._wall_break_time is None:
                    self._wall_break_time = et.strftime("%I:%M %p")
                snapshot["wall_break_time"] = self._wall_break_time
            else:
                snapshot["spy_vs_wall"] = "at"
                snapshot["wall_status"] = "testing"

        # ── Step 6: Volume Character ──
        vol_char, vol_ratio = self._get_volume_character()
        snapshot["volume_character"] = vol_char
        snapshot["volume_ratio"] = vol_ratio

        # ── Step 7: Read Morning Brief ──
        morning_verdict = self._get_morning_verdict()
        snapshot["morning_verdict"] = morning_verdict

        # ── Step 8: Thesis Logic ──
        thesis_valid = True
        thesis_reason = None

        if snapshot["wall_status"] == "broken" and spy_price > 0:
            thesis_valid = False
            thesis_reason = (
                f"SPY broke call wall ${call_wall:.0f} at {snapshot.get('wall_break_time', 'N/A')}"
            )

        if thesis_valid and put_wall > 0 and spy_price > 0 and spy_price < put_wall:
            thesis_valid = False
            thesis_reason = f"SPY ${spy_price:.2f} below put wall ${put_wall:.0f}"

        snapshot["thesis_valid"] = thesis_valid
        snapshot["thesis_invalidation_reason"] = thesis_reason

        # ── Step 9: Circuit Breaker ──
        cb_active, cb_reason, consec_losses = self._check_circuit_breaker()
        snapshot["circuit_breaker_active"] = cb_active
        snapshot["circuit_breaker_reason"] = cb_reason
        snapshot["consecutive_losses_today"] = consec_losses

        # If circuit breaker, also invalidate thesis
        if cb_active and thesis_valid:
            snapshot["thesis_valid"] = False
            snapshot["thesis_invalidation_reason"] = cb_reason

        # ── Step 10: Signal Counts + Invalidation ──
        active_count, invalidated_count = self._count_signals()
        snapshot["signals_active"] = active_count
        snapshot["signals_invalidated"] = invalidated_count

        # If thesis just flipped to invalid, invalidate all active signals
        if not snapshot["thesis_valid"] and self._previous_thesis_valid is not False:
            reason = snapshot["thesis_invalidation_reason"] or "Thesis invalidated"
            self._invalidate_signals(reason)
            # Recount after invalidation
            active_count, invalidated_count = self._count_signals()
            snapshot["signals_active"] = active_count
            snapshot["signals_invalidated"] = invalidated_count

        self._previous_thesis_valid = snapshot["thesis_valid"]

        # ── Write snapshot ──
        self._write_snapshot(snapshot)
        logger.info(
            f"🛡️ Guardian: thesis={'VALID' if snapshot['thesis_valid'] else 'INVALID'} "
            f"| SPY=${snapshot['spy_price']:.2f} | wall={snapshot['wall_status']} "
            f"| vol={snapshot['volume_character']}"
        )

        return snapshot

    # ── DATA SOURCES ──────────────────────────────────────────────────

    def _get_spy_price(self) -> float:
        """Fetch current SPY price from yfinance. Returns 0.0 on failure."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("SPY")
            hist = ticker.history(period="1d", interval="1m")
            if hist is not None and not hist.empty:
                return round(float(hist["Close"].iloc[-1]), 2)
        except Exception as e:
            logger.warning(f"yfinance SPY price fetch failed: {e}")
        return 0.0

    def _get_walls(self) -> tuple:
        """Fetch SPY call wall, put wall, POC from Stockgrid. Returns cached on failure."""
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            client = StockgridClient(cache_ttl=120)
            wall = client.get_option_walls_today("SPY")
            if wall:
                self._cached_walls = {
                    "call_wall": wall.call_wall,
                    "put_wall": wall.put_wall,
                    "poc": wall.poc,
                }
                return wall.call_wall, wall.put_wall, wall.poc
        except Exception as e:
            logger.warning(f"StockgridClient wall fetch failed: {e}")

        # Fallback to cached walls
        if self._cached_walls:
            return (
                self._cached_walls.get("call_wall", 0.0),
                self._cached_walls.get("put_wall", 0.0),
                self._cached_walls.get("poc", 0.0),
            )

        # Fallback to morning brief walls
        return self._get_walls_from_brief()

    def _get_walls_from_brief(self) -> tuple:
        """Extract walls from the morning brief cache."""
        try:
            today_str = date.today().isoformat()
            brief_path = os.path.join(BRIEF_DIR, f"{today_str}.json")
            if os.path.exists(brief_path):
                with open(brief_path) as f:
                    brief = json.load(f)
                levels = brief.get("key_levels", {}).get("SPY", {})
                return (
                    float(levels.get("call_wall", 0)),
                    float(levels.get("put_wall", 0)),
                    float(levels.get("poc", 0)),
                )
        except Exception as e:
            logger.debug(f"Brief wall fallback failed: {e}")
        return 0.0, 0.0, 0.0

    def _get_volume_character(self) -> tuple:
        """Compare today's volume vs 20-day average. Returns (character, ratio)."""
        try:
            import yfinance as yf
            ticker = yf.Ticker("SPY")

            # Today's volume
            today_hist = ticker.history(period="1d")
            if today_hist is None or today_hist.empty:
                return "unknown", 0.0
            today_vol = float(today_hist["Volume"].iloc[-1])

            # 20-day average volume
            hist_20d = ticker.history(period="21d")
            if hist_20d is None or len(hist_20d) < 2:
                return "unknown", 0.0
            avg_vol = float(hist_20d["Volume"].iloc[:-1].mean())

            if avg_vol <= 0:
                return "unknown", 0.0

            ratio = round(today_vol / avg_vol, 2)
            if ratio > 1.3:
                char = "accumulation"
            elif ratio < 0.7:
                char = "distribution"
            else:
                char = "neutral"

            return char, ratio
        except Exception as e:
            logger.warning(f"Volume character check failed: {e}")
            return "unknown", 0.0

    def _get_morning_verdict(self) -> Optional[str]:
        """Read today's morning brief verdict."""
        try:
            today_str = date.today().isoformat()
            brief_path = os.path.join(BRIEF_DIR, f"{today_str}.json")
            if os.path.exists(brief_path):
                with open(brief_path) as f:
                    brief = json.load(f)
                return brief.get("verdict") or brief.get("signal_intel", {}).get("verdict", {}).get("signal")
        except Exception as e:
            logger.debug(f"Morning brief read failed: {e}")
        return None

    # ── CIRCUIT BREAKER ───────────────────────────────────────────────

    def _check_circuit_breaker(self) -> tuple:
        """
        Check if 2+ consecutive losses today → circuit breaker active.
        Returns (active: bool, reason: str|None, consecutive_losses: int).
        """
        try:
            if not OUTCOMES_FILE.exists():
                return False, None, 0

            with open(OUTCOMES_FILE) as f:
                outcomes = json.load(f)

            if not isinstance(outcomes, list):
                return False, None, 0

            today_str = date.today().isoformat()
            today_outcomes = [
                o for o in outcomes
                if o.get("date") == today_str and not o.get("blocked")
            ]

            if len(today_outcomes) < 2:
                return False, None, 0

            # Count consecutive losses from the end
            consec = 0
            for o in reversed(today_outcomes):
                if o.get("result") == "LOSS":
                    consec += 1
                else:
                    break

            if consec >= 2:
                return True, f"Circuit breaker active — {consec} consecutive losses today", consec

            return False, None, consec
        except Exception as e:
            logger.warning(f"Circuit breaker check failed: {e}")
            return False, None, 0

    # ── SIGNAL INVALIDATION ───────────────────────────────────────────

    def _invalidate_signals(self, reason: str):
        """
        When thesis flips to invalid: mark all active signals as invalidated.
        Only runs ONCE per thesis flip (tracked by _previous_thesis_valid).
        """
        try:
            if not SIGNALS_TODAY.exists():
                return

            with open(SIGNALS_TODAY) as f:
                signals = json.load(f)

            if not isinstance(signals, list):
                return

            now_str = datetime.now().isoformat()
            changed = False
            for sig in signals:
                status = sig.get("status", "active")
                if status == "active":
                    sig["status"] = "invalidated"
                    sig["invalidation_reason"] = reason
                    sig["invalidated_at"] = now_str
                    changed = True

            if changed:
                with open(SIGNALS_TODAY, "w") as f:
                    json.dump(signals, f, indent=2, default=str)
                invalidated = sum(1 for s in signals if s.get("status") == "invalidated")
                logger.info(f"🛡️ Guardian: {invalidated} signals invalidated — {reason}")
        except Exception as e:
            logger.error(f"Signal invalidation failed: {e}")

    def _count_signals(self) -> tuple:
        """Count active vs invalidated signals. Returns (active, invalidated)."""
        try:
            if not SIGNALS_TODAY.exists():
                return 0, 0
            with open(SIGNALS_TODAY) as f:
                signals = json.load(f)
            if not isinstance(signals, list):
                return 0, 0
            active = sum(1 for s in signals if s.get("status", "active") == "active")
            invalidated = sum(1 for s in signals if s.get("status") == "invalidated")
            return active, invalidated
        except Exception:
            return 0, 0

    # ── OUTPUT ────────────────────────────────────────────────────────

    def _write_snapshot(self, snapshot: dict):
        """Write snapshot to /tmp/intraday_snapshot.json."""
        try:
            os.makedirs(os.path.dirname(SNAPSHOT_PATH) or "/tmp", exist_ok=True)
            with open(SNAPSHOT_PATH, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Snapshot write failed: {e}")
