"""
📋 MORNING BRIEF GENERATOR

Automated pre-market brief at 07:45 ET.
Composes REGIME / BIAS / GAMMA verdict, key levels, approved tickers,
blocked tickers, and Gate Health metric.

Output: morning_brief.json + morning_brief.txt + Discord webhook
"""

import json
import logging
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
BRIEF_JSON = DATA_DIR / "morning_brief.json"
BRIEF_TXT = DATA_DIR / "morning_brief.txt"
SIGNALS_TODAY = DATA_DIR / "gate_signals_today.json"


class MorningBriefGenerator:
    """
    Generates the daily trading brief.

    Invoked by the scheduler at 07:45 ET.
    Reads all available context and produces a structured brief.
    """

    def __init__(
        self,
        confluence_gate=None,
        regime_detector=None,
        gamma_tracker=None,
        outcome_tracker=None,
        send_discord=None,
    ):
        self.gate = confluence_gate
        self.regime_detector = regime_detector
        self.gamma_tracker = gamma_tracker
        self.outcome_tracker = outcome_tracker
        self.send_discord_fn = send_discord
        self._last_brief_date = None
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def should_generate(self, now: datetime) -> bool:
        """Check if we should generate the brief (07:45-08:00 ET weekdays)."""
        try:
            import pytz
            et = pytz.timezone('America/New_York')
            now_et = now.astimezone(et) if now.tzinfo else et.localize(now)
            if now_et.weekday() >= 5:
                return False
            if now_et.hour == 7 and 45 <= now_et.minute < 60:
                if self._last_brief_date != now_et.date():
                    return True
            return False
        except Exception:
            return False

    def generate(self, force: bool = False) -> Optional[Dict]:
        """
        Generate the morning brief. Returns the brief dict.

        Can be called manually with force=True for testing.
        """
        import pytz
        et = pytz.timezone('America/New_York')
        now_et = datetime.now(et)

        if not force and not self.should_generate(datetime.now()):
            return None

        logger.info("📋 Generating morning brief...")

        brief = {
            "date": now_et.strftime("%Y-%m-%d"),
            "generated_at": now_et.isoformat(),
            "verdict": self._build_verdict(),
            "key_levels": self._build_key_levels(),
            "approved_tickers": self._get_approved_tickers(),
            "blocked_tickers": self._get_blocked_tickers(),
            "gate_health": self._get_gate_health(),
            "gamma_status": self._get_gamma_status(),
        }

        # Write JSON
        with open(BRIEF_JSON, "w") as f:
            json.dump(brief, f, indent=2, default=str)

        # Write TXT (human-readable)
        txt = self._format_text(brief)
        with open(BRIEF_TXT, "w") as f:
            f.write(txt)

        # Send to Discord
        if self.send_discord_fn:
            self._send_to_discord(brief)

        self._last_brief_date = now_et.date()
        logger.info(f"   ✅ Morning brief generated — {BRIEF_JSON.name}")

        return brief

    # ─── VERDICT ──────────────────────────────────────────────────────

    def _build_verdict(self) -> Dict:
        """REGIME / BIAS / GAMMA one-liner."""
        regime = "UNKNOWN"
        bias = "UNKNOWN"

        if self.gate:
            bias = self.gate._synthesis_bias or "NO DATA"

        if self.regime_detector:
            try:
                import yfinance as yf
                spy = yf.Ticker("SPY")
                hist = spy.history(period="5d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    regime_result = self.regime_detector.detect(price)
                    regime = regime_result if isinstance(regime_result, str) else str(regime_result)
            except Exception as e:
                logger.debug(f"Verdict regime error: {e}")

        gamma = self._get_gamma_status()

        return {
            "regime": regime,
            "bias": bias,
            "gamma": gamma.get("status", "UNKNOWN"),
            "one_liner": f"REGIME: {regime} | BIAS: {bias} | GAMMA: {gamma.get('status', '?')}",
        }

    # ─── KEY LEVELS ──────────────────────────────────────────────────

    def _build_key_levels(self) -> Dict:
        """SPY/QQQ/IWM walls and key support/resistance."""
        levels = {}
        try:
            import yfinance as yf
            for sym in ["SPY", "QQQ", "IWM"]:
                t = yf.Ticker(sym)
                hist = t.history(period="5d")
                if not hist.empty:
                    close = float(hist["Close"].iloc[-1])
                    high_5d = float(hist["High"].max())
                    low_5d = float(hist["Low"].min())
                    levels[sym] = {
                        "close": round(close, 2),
                        "5d_high": round(high_5d, 2),
                        "5d_low": round(low_5d, 2),
                        "distance_from_low_pct": round(((close - low_5d) / low_5d) * 100, 2),
                    }
        except Exception as e:
            logger.debug(f"Key levels error: {e}")
        return levels

    # ─── APPROVED / BLOCKED TICKERS ───────────────────────────────────

    def _get_approved_tickers(self) -> List[Dict]:
        """Read today's gated signals that PASSED."""
        try:
            if SIGNALS_TODAY.exists():
                with open(SIGNALS_TODAY) as f:
                    signals = json.load(f)
                return [
                    {"ticker": s["ticker"], "direction": s["direction"],
                     "confidence": s.get("confidence", 0)}
                    for s in signals if not s.get("blocked")
                ][:5]
        except Exception:
            pass
        return []

    def _get_blocked_tickers(self) -> List[Dict]:
        """Read today's blocked signals."""
        blocked_file = DATA_DIR / "gate_blocked_today.json"
        try:
            if blocked_file.exists():
                with open(blocked_file) as f:
                    signals = json.load(f)
                return [
                    {"ticker": s["ticker"], "direction": s["direction"],
                     "reason": s.get("reason", "Blocked by gate")}
                    for s in signals
                ][:5]
        except Exception:
            pass
        return []

    # ─── GATE HEALTH ──────────────────────────────────────────────────

    def _get_gate_health(self) -> Dict:
        """Gate Health metric — non-negotiable field."""
        if self.outcome_tracker:
            health = self.outcome_tracker.get_health(n=20)
            return {
                "win_rate_last_20": health["win_rate_last_n"],
                "blocked_vs_allowed": health["blocked_vs_allowed"],
                "avg_R_last_20": health["avg_r_last_n"],
                "total_signals": health["total_signals"],
            }
        return {
            "win_rate_last_20": 0.0,
            "blocked_vs_allowed": "0 / 0",
            "avg_R_last_20": 0.0,
            "total_signals": 0,
        }

    # ─── GAMMA STATUS ────────────────────────────────────────────────

    def _get_gamma_status(self) -> Dict:
        """Get current gamma flip status."""
        if self.gamma_tracker:
            try:
                signal = self.gamma_tracker.analyze("SPY")
                if signal:
                    return {
                        "status": f"{signal.direction} (score {signal.score:.0f})",
                        "level": getattr(signal, "flip_level", None),
                    }
            except Exception:
                pass
        return {"status": "NO DATA", "level": None}

    # ─── TEXT FORMAT ──────────────────────────────────────────────────

    def _format_text(self, brief: Dict) -> str:
        """Human-readable brief."""
        lines = [
            "=" * 60,
            f"📋 MORNING BRIEF — {brief['date']}",
            f"Generated: {brief['generated_at']}",
            "=" * 60,
            "",
            f"🎯 VERDICT: {brief['verdict']['one_liner']}",
            "",
        ]

        # Key levels
        if brief.get("key_levels"):
            lines.append("📊 KEY LEVELS:")
            for sym, lvl in brief["key_levels"].items():
                lines.append(f"   {sym}: ${lvl['close']} (5d range: ${lvl['5d_low']}-${lvl['5d_high']})")
            lines.append("")

        # Approved
        if brief.get("approved_tickers"):
            lines.append("✅ APPROVED TICKERS:")
            for t in brief["approved_tickers"]:
                lines.append(f"   {t['ticker']} {t['direction']} ({t['confidence']:.0f}%)")
        else:
            lines.append("✅ APPROVED TICKERS: None yet")
        lines.append("")

        # Blocked
        if brief.get("blocked_tickers"):
            lines.append("⛔ BLOCKED:")
            for t in brief["blocked_tickers"]:
                lines.append(f"   {t['ticker']} {t['direction']} — {t['reason'][:50]}")
        lines.append("")

        # Gate Health
        gh = brief.get("gate_health", {})
        lines.extend([
            "📈 GATE HEALTH:",
            f"   Win Rate (last 20): {gh.get('win_rate_last_20', 0)}%",
            f"   Blocked / Allowed:  {gh.get('blocked_vs_allowed', '0 / 0')}",
            f"   Avg R (last 20):    {gh.get('avg_R_last_20', 0)}R",
            "",
            "=" * 60,
        ])

        return "\n".join(lines)

    # ─── DISCORD ──────────────────────────────────────────────────────

    def _send_to_discord(self, brief: Dict):
        """Send brief to Discord via the orchestrator's send_discord."""
        verdict = brief.get("verdict", {})
        gh = brief.get("gate_health", {})

        fields = [
            {"name": "🎯 Verdict", "value": verdict.get("one_liner", "N/A"), "inline": False},
        ]

        # Key levels
        levels_str = ""
        for sym, lvl in brief.get("key_levels", {}).items():
            levels_str += f"**{sym}**: ${lvl['close']} (range: ${lvl['5d_low']}-${lvl['5d_high']})\n"
        if levels_str:
            fields.append({"name": "📊 Key Levels", "value": levels_str, "inline": False})

        # Approved
        approved = brief.get("approved_tickers", [])
        if approved:
            appr_str = "\n".join(f"**{t['ticker']}** {t['direction']} ({t['confidence']:.0f}%)" for t in approved)
            fields.append({"name": "✅ Approved", "value": appr_str, "inline": True})

        # Blocked
        blocked = brief.get("blocked_tickers", [])
        if blocked:
            blk_str = "\n".join(f"**{t['ticker']}** {t['direction']}" for t in blocked)
            fields.append({"name": "⛔ Blocked", "value": blk_str, "inline": True})

        # Gate Health
        fields.append({
            "name": "📈 Gate Health",
            "value": (
                f"Win Rate: **{gh.get('win_rate_last_20', 0)}%**\n"
                f"Blocked/Allowed: **{gh.get('blocked_vs_allowed', '0/0')}**\n"
                f"Avg R: **{gh.get('avg_R_last_20', 0)}R**"
            ),
            "inline": False,
        })

        embed = {
            "title": f"📋 MORNING BRIEF — {brief['date']}",
            "color": 0x3498db,
            "fields": fields,
            "footer": {"text": "ConfluenceGate | Automated Brief"},
            "timestamp": datetime.utcnow().isoformat(),
        }

        content = f"📋 **MORNING BRIEF** | {verdict.get('one_liner', 'N/A')}"

        try:
            self.send_discord_fn(embed, content, "morning_brief", "morning_brief_generator", "SPY")
        except Exception as e:
            logger.error(f"❌ Brief Discord send failed: {e}")
