"""
📊 GATE OUTCOME TRACKER

Closed-loop accountability for the ConfluenceGate.

1. Logs every signal that passes or is blocked by the gate
2. After market close, settles outcomes (entry vs close price → P&L in R)
3. Computes Gate Health metric: win rate, blocked/allowed, avg R
"""

import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SIGNALS_TODAY = DATA_DIR / "gate_signals_today.json"
BLOCKED_TODAY = DATA_DIR / "gate_blocked_today.json"
OUTCOMES_FILE = DATA_DIR / "gate_outcomes.json"
ARCHIVE_DIR = DATA_DIR / "gate_signals_archive"


class GateOutcomeTracker:
    """
    Tracks gate signals and outcomes for closed-loop accountability.

    Flow:
        1. log_signal()       — called by ConfluenceGate when should_fire returns
        2. settle_day()       — called at 16:05 ET by scheduler
        3. get_health(n=20)   — called by API/UI anytime
    """

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    # ─── SIGNAL LOGGING ──────────────────────────────────────────────

    def log_signal(
        self,
        ticker: str,
        direction: str,
        entry_price: float,
        confidence: float,
        blocked: bool,
        reason: str = "",
        regime: str = "",
        bias: str = "",
        source: str = "",
    ):
        """
        Log a signal intent (passed or blocked).
        Called by ConfluenceGate.should_fire() on every invocation.
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "direction": direction,
            "entry_price": round(entry_price, 2) if entry_price else 0,
            "confidence": round(confidence, 2),
            "blocked": blocked,
            "status": "blocked" if blocked else "active",
            "reason": reason,
            "regime": regime,
            "bias": bias,
            "source": source,
        }

        target = BLOCKED_TODAY if blocked else SIGNALS_TODAY

        try:
            existing = self._read_json(target)
            existing.append(record)
            self._write_json(target, existing)
            status = "BLOCKED" if blocked else "ALLOWED"
            logger.info(f"📝 Gate log: {status} {ticker} {direction} @ ${entry_price:.2f}")
        except Exception as e:
            logger.error(f"❌ Gate signal log failed: {e}")

    # ─── POST-MARKET SETTLEMENT ───────────────────────────────────────

    def settle_day(self, target_date: str = None, stop_pct: float = 1.0):
        """
        Settle today's signals: fetch close prices, calculate P&L in R.

        Args:
            target_date: Date string 'YYYY-MM-DD' (defaults to today)
            stop_pct: Default stop loss percentage for R calculation (1.0 = 1%)
        """
        import yfinance as yf

        target_date = target_date or date.today().isoformat()
        logger.info(f"📊 Settling gate signals for {target_date}")

        # Read today's allowed signals
        allowed = self._read_json(SIGNALS_TODAY)
        blocked = self._read_json(BLOCKED_TODAY)

        if not allowed and not blocked:
            logger.info("   No signals to settle today")
            return

        # Fetch close prices for allowed signals
        outcomes = self._read_json(OUTCOMES_FILE)
        tickers = set(s["ticker"] for s in allowed)

        close_prices = {}
        for ticker in tickers:
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1d")
                if not hist.empty:
                    close_prices[ticker] = float(hist["Close"].iloc[-1])
            except Exception as e:
                logger.warning(f"   ⚠️ Could not fetch close for {ticker}: {e}")

        # Calculate outcomes for allowed signals
        for signal in allowed:
            ticker = signal["ticker"]
            entry = signal["entry_price"]
            close = close_prices.get(ticker, entry)
            direction = signal["direction"].upper()

            # P&L calculation
            if direction == "LONG":
                pnl_pct = ((close - entry) / entry) * 100
            else:
                pnl_pct = ((entry - close) / entry) * 100

            # R-multiple: pnl / stop distance
            stop_distance = entry * (stop_pct / 100)
            pnl_r = round(pnl_pct / stop_pct, 2) if stop_pct > 0 else 0

            outcome = {
                "date": target_date,
                "timestamp": signal["timestamp"],
                "ticker": ticker,
                "direction": direction,
                "entry_price": entry,
                "close_price": round(close, 2),
                "pnl_pct": round(pnl_pct, 2),
                "pnl_r": pnl_r,
                "result": "WIN" if pnl_r > 0 else "LOSS" if pnl_r < 0 else "NEUTRAL",
                "blocked": False,
                "confidence": signal.get("confidence", 0),
                "regime": signal.get("regime", ""),
                "bias": signal.get("bias", ""),
            }
            outcomes.append(outcome)

        # Also log blocked signals (they don't have outcomes, but count toward the ratio)
        for signal in blocked:
            outcome = {
                "date": target_date,
                "timestamp": signal["timestamp"],
                "ticker": signal["ticker"],
                "direction": signal["direction"],
                "entry_price": signal.get("entry_price", 0),
                "close_price": 0,
                "pnl_pct": 0,
                "pnl_r": 0,
                "result": "BLOCKED",
                "blocked": True,
                "confidence": signal.get("confidence", 0),
                "regime": signal.get("regime", ""),
                "bias": signal.get("bias", ""),
            }
            outcomes.append(outcome)

        # Write outcomes
        self._write_json(OUTCOMES_FILE, outcomes)
        logger.info(f"   ✅ Settled {len(allowed)} allowed + {len(blocked)} blocked signals")

        # Archive today's signals
        archive_file = ARCHIVE_DIR / f"{target_date}.json"
        self._write_json(archive_file, {"allowed": allowed, "blocked": blocked})

        # Reset today's files
        self._write_json(SIGNALS_TODAY, [])
        self._write_json(BLOCKED_TODAY, [])

        logger.info(f"   📁 Archived to {archive_file.name}, reset today's logs")

    # ─── GATE HEALTH METRIC ──────────────────────────────────────────

    def get_health(self, n: int = 20) -> Dict:
        """
        Compute Gate Health from the last N outcomes.

        Returns:
            {
                "win_rate_last_n": float,
                "blocked_vs_allowed": "X / Y",
                "avg_r_last_n": float,
                "total_signals": int,
                "blocked_count": int,
                "allowed_count": int,
                "wins": int,
                "losses": int,
                "current_streak": str,
                "n": int,
            }
        """
        outcomes = self._read_json(OUTCOMES_FILE)
        recent = outcomes[-n:] if len(outcomes) > n else outcomes

        blocked = [o for o in recent if o.get("blocked")]
        allowed = [o for o in recent if not o.get("blocked")]
        wins = [o for o in allowed if o.get("result") == "WIN"]
        losses = [o for o in allowed if o.get("result") == "LOSS"]

        win_rate = (len(wins) / len(allowed) * 100) if allowed else 0.0
        avg_r = (sum(o.get("pnl_r", 0) for o in allowed) / len(allowed)) if allowed else 0.0

        # Calculate streak
        streak = ""
        if allowed:
            streak_type = allowed[-1].get("result", "")
            streak_count = 0
            for o in reversed(allowed):
                if o.get("result") == streak_type:
                    streak_count += 1
                else:
                    break
            streak = f"{streak_count}{streak_type[0]}" if streak_type else ""

        return {
            "win_rate_last_n": round(win_rate, 1),
            "blocked_vs_allowed": f"{len(blocked)} / {len(allowed)}",
            "avg_r_last_n": round(avg_r, 2),
            "total_signals": len(recent),
            "blocked_count": len(blocked),
            "allowed_count": len(allowed),
            "wins": len(wins),
            "losses": len(losses),
            "current_streak": streak,
            "n": n,
        }

    # ─── CIRCUIT BREAKER ──────────────────────────────────────────────

    def is_circuit_breaker_active(self) -> tuple:
        """Check if circuit breaker is active (consecutive losses OR RiskManager PnL limit)."""
        # ── Source 1: Consecutive losses (gate outcomes) ──
        outcomes = self._read_json(OUTCOMES_FILE)
        today = date.today().isoformat()
        today_outcomes = [o for o in outcomes if o.get("date") == today and not o.get("blocked")]
        if len(today_outcomes) >= 2:
            last_two = today_outcomes[-2:]
            if all(o.get("result") == "LOSS" for o in last_two):
                return True, "Circuit breaker — 2 consecutive losses today"

        # ── Source 2: RiskManager PnL circuit breaker (persisted state file) ──
        try:
            import os as _os
            _cb_path = "/tmp/risk_manager_circuit_breaker.json"
            if _os.path.exists(_cb_path):
                with open(_cb_path) as _f:
                    _cb_state = json.load(_f)
                if _cb_state.get("triggered"):
                    pnl = _cb_state.get("daily_pnl_pct", 0)
                    limit = _cb_state.get("limit_pct", -0.03)
                    return True, f"RiskManager circuit breaker — daily PnL {pnl:.2%} <= {limit:.2%}"
        except Exception:
            pass  # File missing or corrupt — no penalty

        return False, None

    # ─── HELPERS ──────────────────────────────────────────────────────

    @staticmethod
    def _read_json(path: Path) -> list:
        try:
            if path.exists() and path.stat().st_size > 0:
                with open(path) as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except (json.JSONDecodeError, Exception):
            pass
        return []

    @staticmethod
    def _write_json(path: Path, data):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
