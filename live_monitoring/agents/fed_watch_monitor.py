#!/usr/bin/env python3
"""
🏦 FED WATCH MONITOR — Modular Rate Probability Tracker

Thin facade over FedWatchEngine (fedwatch_diy.py).
All rate data comes from live Fed Funds Futures (ZQ) via yfinance.

No hardcoded rates. No dead scrapers. No stale fallbacks.

Usage:
    from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
    monitor = FedWatchMonitor()
    status = monitor.get_current_status()
    monitor.print_fed_dashboard(status)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class FOMCMeeting:
    """FOMC meeting info."""
    date: datetime
    is_next: bool = False
    days_until: int = 0


@dataclass
class RateProbability:
    """Probability for a specific rate outcome."""
    rate_bps: int       # Rate in basis points (e.g., 425 = 4.25%)
    probability: float  # 0-100%
    change_bps: int = 0 # Change from current rate


@dataclass
class FedWatchStatus:
    """Complete Fed Watch status.
    
    All defaults are placeholders — overwritten by live FedWatchEngine data.
    If you see "UNKNOWN" or 0 values in production, the engine failed.
    """
    timestamp: datetime = field(default_factory=datetime.now)

    # Current rate — set dynamically from ZQ front-month futures
    current_rate_bps: int = 0
    current_rate_range: str = "UNKNOWN"

    # Next meeting — set dynamically from FOMC_2026 schedule
    next_meeting: Optional[FOMCMeeting] = None

    # Probabilities for next meeting
    probabilities: List[RateProbability] = field(default_factory=list)

    # Summary probabilities
    prob_cut: float = 0.0
    prob_hold: float = 0.0
    prob_hike: float = 0.0

    # Most likely outcome
    most_likely_outcome: str = "UNKNOWN"
    most_likely_probability: float = 0.0

    # Change tracking (vs previous check)
    prob_cut_change: float = 0.0
    prob_hold_change: float = 0.0
    prob_hike_change: float = 0.0

    # Market implications
    market_bias: str = "NEUTRAL"
    affected_sectors: List[str] = field(default_factory=list)

    # NEW: Full rate path from FedWatchEngine
    rate_path: List[Dict] = field(default_factory=list)
    source: str = "none"
    summary: str = ""


# ============================================================================
# FED WATCH FETCHER — Delegates to FedWatchEngine
# ============================================================================

class FedWatchFetcher:
    """
    Fetches Fed rate probabilities.
    
    Single source: FedWatchEngine (fedwatch_diy.py)
    — Derives probabilities from live ZQ futures via yfinance
    — Uses CME day-weighted formula for per-meeting calculation
    — Falls back to Diffbot scraping if configured
    
    No dead CME/Investing.com/Perplexity scrapers. No hardcoded fallbacks.
    """

    def __init__(self):
        self.last_status: Optional[FedWatchStatus] = None
        self.cache_time: Optional[datetime] = None
        self.cache_duration = timedelta(minutes=5)
        self._engine = None

    def _get_engine(self):
        """Lazy-init FedWatchEngine to avoid circular imports."""
        if self._engine is None:
            try:
                from live_monitoring.enrichment.apis.fedwatch_diy import FedWatchEngine
                self._engine = FedWatchEngine()
                logger.info("🏦 FedWatchFetcher → FedWatchEngine connected")
            except Exception as e:
                logger.error(f"FedWatchEngine import failed: {e}")
        return self._engine

    def get_status(self, force_refresh: bool = False) -> FedWatchStatus:
        """Get current Fed Watch status from live futures data."""
        # Check cache
        if not force_refresh and self.cache_time:
            if datetime.now() - self.cache_time < self.cache_duration:
                if self.last_status:
                    return self.last_status

        status = FedWatchStatus()

        engine = self._get_engine()
        if engine is None:
            logger.error("🏦 No FedWatchEngine available — returning empty status")
            return self._finalize_status(status)

        try:
            data = engine.get_probabilities(force_refresh=force_refresh)

            if not data or 'error' in data:
                logger.warning(f"🏦 FedWatchEngine returned error: {data}")
                return self._finalize_status(status)

            # ── Map next meeting probabilities ──
            next_mtg = data.get('next_meeting', {})
            if next_mtg:
                status.prob_cut = next_mtg.get('p_cut_25', 0)
                status.prob_hold = next_mtg.get('p_hold', 0)
                status.prob_hike = next_mtg.get('p_hike_25', 0)

                # Dynamic FOMC date
                try:
                    mtg_date = datetime.strptime(next_mtg['date'], '%Y-%m-%d')
                    status.next_meeting = FOMCMeeting(
                        date=mtg_date,
                        is_next=True,
                        days_until=next_mtg.get('days_away', (mtg_date - datetime.now()).days)
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(f"Could not parse meeting date: {e}")

            # ── Dynamic current rate from front-month futures ──
            current_range = data.get('current_range', [])
            if current_range and len(current_range) == 2:
                lo, hi = current_range
                status.current_rate_bps = int(hi * 100)  # Upper bound in bps
                status.current_rate_range = f"{lo:.2f}%-{hi:.2f}%"
            elif 'current_rate' in data:
                rate = data['current_rate']
                status.current_rate_bps = int(rate * 100)
                status.current_rate_range = f"{rate:.2f}%"

            # ── Full rate path (all future meetings) ──
            status.rate_path = data.get('rate_path', [])
            status.source = data.get('engine_source', 'unknown')
            status.summary = data.get('summary', '')

            logger.info(
                f"🏦 FedWatch LIVE: Cut={status.prob_cut:.1f}% | "
                f"Hold={status.prob_hold:.1f}% | Hike={status.prob_hike:.1f}% "
                f"| Rate={status.current_rate_range} | Source={status.source}"
            )

        except Exception as e:
            logger.error(f"FedWatchEngine fetch failed: {e}", exc_info=True)

        return self._finalize_status(status)

    def _finalize_status(self, status: FedWatchStatus) -> FedWatchStatus:
        """Normalize, determine outcome, bias, and cache."""
        # Normalize to 100%
        total = status.prob_cut + status.prob_hold + status.prob_hike
        if total > 0:
            status.prob_cut = (status.prob_cut / total) * 100
            status.prob_hold = (status.prob_hold / total) * 100
            status.prob_hike = (status.prob_hike / total) * 100

        # Determine most likely outcome
        probs = {
            "CUT": status.prob_cut,
            "HOLD": status.prob_hold,
            "HIKE": status.prob_hike,
        }
        status.most_likely_outcome = max(probs, key=probs.get)
        status.most_likely_probability = probs[status.most_likely_outcome]

        # Calculate changes from last check
        if self.last_status:
            status.prob_cut_change = status.prob_cut - self.last_status.prob_cut
            status.prob_hold_change = status.prob_hold - self.last_status.prob_hold
            status.prob_hike_change = status.prob_hike - self.last_status.prob_hike

        # Determine market bias (with stagflation scenario)
        if status.prob_cut > 60:
            status.market_bias = "BULLISH"
            status.affected_sectors = ["Tech (QQQ)", "Real Estate (XLRE)", "Utilities (XLU)", "Small Caps (IWM)"]
        elif status.prob_hike > 30:
            status.market_bias = "BEARISH"
            status.affected_sectors = ["Banks (XLF)", "Value (IVE)", "Cash-heavy companies"]
        elif status.prob_cut > 40 and status.prob_hike > 15:
            # Stagflation scenario — market split between cut and hike
            status.market_bias = "STAGFLATION_RISK"
            status.affected_sectors = ["Gold (GLD)", "Commodities (DBC)", "TIPS (TIP)", "Defensive (XLP)"]
        else:
            status.market_bias = "NEUTRAL"
            status.affected_sectors = ["Monitor for changes"]

        # Cache
        self.last_status = status
        self.cache_time = datetime.now()

        return status


# ============================================================================
# FED WATCH MONITOR — Alert & Analysis Layer
# ============================================================================

class FedWatchMonitor:
    """
    Rate probability monitor — tracks changes and alerts on significant shifts.
    
    Uses FedWatchFetcher (→ FedWatchEngine → ZQ futures) for data.
    """

    def __init__(self, alert_threshold: float = 5.0):
        """
        Args:
            alert_threshold: Minimum % change to trigger alert (default 5%)
        """
        self.fetcher = FedWatchFetcher()
        self.alert_threshold = alert_threshold
        self.previous_status: Optional[FedWatchStatus] = None
        self.alerts_sent: List[Dict] = []

        logger.info(f"🏦 FedWatchMonitor initialized (threshold={self.alert_threshold}%)")

    def get_current_status(self, force_refresh: bool = False) -> FedWatchStatus:
        """Get current Fed Watch status."""
        return self.fetcher.get_status(force_refresh=force_refresh)

    # Alias for backward compat
    get_current_probabilities = get_current_status

    def check_for_changes(self) -> Optional[Dict]:
        """Check for significant changes in rate probabilities.
        
        Returns change info if significant, None otherwise.
        """
        current = self.get_current_status(force_refresh=True)

        if not self.previous_status:
            self.previous_status = current
            return None

        changes = []
        for prob_type, attr, change_attr in [
            ('CUT', 'prob_cut', 'prob_cut_change'),
            ('HOLD', 'prob_hold', 'prob_hold_change'),
            ('HIKE', 'prob_hike', 'prob_hike_change'),
        ]:
            change = getattr(current, change_attr, 0)
            if abs(change) >= self.alert_threshold:
                changes.append({
                    'type': prob_type,
                    'direction': "↑" if change > 0 else "↓",
                    'change': change,
                    'new_value': getattr(current, attr),
                })

        self.previous_status = current

        if changes:
            return {
                'timestamp': datetime.now(),
                'changes': changes,
                'current_status': current,
            }
        return None

    def get_market_implications(self, status: FedWatchStatus) -> Dict:
        """Get market implications of current rate expectations.
        
        Uses the live rate path to provide dynamic analysis, not just
        prob_cut > 60% thresholds.
        """
        # ── Determine cumulative rate path ──
        cumul_bps = 0
        if status.rate_path:
            last_meeting = status.rate_path[-1] if status.rate_path else {}
            cumul_bps = last_meeting.get('cumulative_bps', 0)

        implications = {
            'bias': status.market_bias,
            'summary': '',
            'trades': [],
            'sectors': {},
            'cumulative_cuts_bps': cumul_bps,
        }

        if status.market_bias == "STAGFLATION_RISK":
            implications['summary'] = (
                f"STAGFLATION RISK — Cut {status.prob_cut:.0f}% vs Hike {status.prob_hike:.0f}%. "
                f"Market split on direction. Cumul: {cumul_bps:+.0f}bp through EOY."
            )
            implications['trades'] = [
                {"action": "LONG", "symbol": "GLD", "reason": "Gold thrives in stagflation"},
                {"action": "LONG", "symbol": "TIP", "reason": "TIPS protect against inflation"},
                {"action": "HEDGE", "symbol": "VIX calls", "reason": "Elevated uncertainty"},
                {"action": "REDUCE", "symbol": "QQQ", "reason": "Growth vulnerable to rate confusion"},
            ]
            implications['sectors'] = {
                'winners': ["Gold", "Commodities", "TIPS", "Staples"],
                'losers': ["Growth Tech", "Real Estate", "Discretionary"],
            }

        elif status.prob_cut > 60:
            implications['summary'] = (
                f"HIGH CUT PROBABILITY ({status.prob_cut:.0f}%) — BULLISH for risk assets. "
                f"Market pricing {abs(cumul_bps):.0f}bp of cuts through EOY."
            )
            implications['trades'] = [
                {"action": "LONG", "symbol": "QQQ", "reason": "Tech benefits from lower rates"},
                {"action": "LONG", "symbol": "XLRE", "reason": "Real estate loves lower rates"},
                {"action": "LONG", "symbol": "IWM", "reason": "Small caps benefit from cheaper borrowing"},
                {"action": "LONG", "symbol": "TLT", "reason": "Bond prices rise when rates fall"},
            ]
            implications['sectors'] = {
                'winners': ["Tech", "Real Estate", "Utilities", "Small Caps", "Growth"],
                'losers': ["Banks (NIM compression)", "Insurance"],
            }

        elif status.prob_hike > 30:
            implications['summary'] = (
                f"RATE HIKE RISK ELEVATED ({status.prob_hike:.0f}%) — BEARISH for risk assets."
            )
            implications['trades'] = [
                {"action": "LONG", "symbol": "XLF", "reason": "Banks benefit from higher rates"},
                {"action": "SHORT", "symbol": "TLT", "reason": "Bond prices fall when rates rise"},
                {"action": "REDUCE", "symbol": "QQQ", "reason": "Growth stocks hurt by higher rates"},
            ]
            implications['sectors'] = {
                'winners': ["Banks", "Insurance", "Value stocks"],
                'losers': ["Tech", "Real Estate", "Utilities", "Growth stocks"],
            }

        else:
            implications['summary'] = (
                f"RATE PATH UNCERTAIN — Hold {status.prob_hold:.0f}%. "
                f"Cumul: {cumul_bps:+.0f}bp through EOY. Wait for clarity."
            )
            implications['trades'] = [
                {"action": "WATCH", "symbol": "SPY", "reason": "Wait for clarity on rate path"},
                {"action": "HEDGE", "symbol": "VIX calls", "reason": "Protect against volatility"},
            ]
            implications['sectors'] = {
                'winners': ["Defensive sectors", "Dividend payers"],
                'losers': ["Rate-sensitive sectors until clarity"],
            }

        return implications

    def print_fed_dashboard(self, status: Optional[FedWatchStatus] = None):
        """Print formatted Fed Watch dashboard."""
        if status is None:
            status = self.get_current_status()

        implications = self.get_market_implications(status)

        print("\n" + "=" * 70)
        print("🏦 FED WATCH MONITOR")
        print(f"   Source: {status.source} | Updated: {status.timestamp:%Y-%m-%d %H:%M}")
        print("=" * 70)

        # Current rate
        print(f"\n  📊 CURRENT RATE: {status.current_rate_range}")

        # Next meeting
        if status.next_meeting:
            print(f"  📅 NEXT FOMC: {status.next_meeting.date:%B %d, %Y} ({status.next_meeting.days_until} days)")

        # Probability bars
        print(f"\n  📈 NEXT MEETING PROBABILITIES:")
        for label, prob, change_val in [
            ("CUT", status.prob_cut, status.prob_cut_change),
            ("HOLD", status.prob_hold, status.prob_hold_change),
            ("HIKE", status.prob_hike, status.prob_hike_change),
        ]:
            bar = "█" * int(prob / 5) + "░" * (20 - int(prob / 5))
            change_str = f" ({change_val:+.1f}%)" if change_val != 0 else ""
            print(f"     {label:4s}: [{bar}] {prob:.1f}%{change_str}")

        # Most likely outcome
        emoji_map = {"CUT": "📉", "HOLD": "➡️", "HIKE": "📈", "UNKNOWN": "❓"}
        print(f"\n  🎯 MOST LIKELY: {emoji_map.get(status.most_likely_outcome, '❓')} "
              f"{status.most_likely_outcome} ({status.most_likely_probability:.1f}%)")

        # Full rate path
        if status.rate_path:
            print(f"\n  📊 RATE PATH (all meetings):")
            for m in status.rate_path:
                print(f"     {m.get('label', '?'):12s} ({m.get('days_away', '?'):3d}d): "
                      f"Hold {m.get('p_hold', 0):5.1f}% | Cut {m.get('p_cut_25', 0):5.1f}% | "
                      f"Cumul: {m.get('cumulative_bps', 0):+.0f}bp")

        # Market bias
        bias_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡",
                      "STAGFLATION_RISK": "🟠"}.get(status.market_bias, "❓")
        print(f"\n  {bias_emoji} BIAS: {status.market_bias}")
        print(f"     {implications['summary']}")

        # Trade ideas
        if implications['trades']:
            print(f"\n  💰 TRADE IDEAS:")
            action_emoji = {"LONG": "🟢", "SHORT": "🔴", "WATCH": "👀",
                           "REDUCE": "⚠️", "HEDGE": "🛡️"}
            for t in implications['trades']:
                print(f"     {action_emoji.get(t['action'], '❓')} {t['action']} {t['symbol']}: {t['reason']}")

        print("\n" + "=" * 70)

    def format_discord_alert(self, change_info: Dict) -> Dict:
        """Format a change alert for Discord embed."""
        status = change_info['current_status']
        changes = change_info['changes']

        max_change = max(abs(c['change']) for c in changes)
        if max_change >= 15:
            color = 15548997  # Red
            title = "🚨 MAJOR FED WATCH SHIFT"
        elif max_change >= 10:
            color = 16776960  # Yellow
            title = "⚠️ SIGNIFICANT FED WATCH CHANGE"
        else:
            color = 3447003   # Blue
            title = "📊 Fed Watch Update"

        change_lines = []
        for c in changes:
            emoji = "📈" if c['direction'] == "↑" else "📉"
            change_lines.append(f"{emoji} {c['type']}: {c['new_value']:.1f}% ({c['change']:+.1f}%)")

        implications = self.get_market_implications(status)

        fields = [
            {"name": "Changes", "value": "\n".join(change_lines), "inline": False},
            {"name": "Probabilities", "value": (
                f"Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | "
                f"Hike: {status.prob_hike:.1f}%"
            ), "inline": False},
            {"name": "Most Likely", "value": (
                f"{status.most_likely_outcome} ({status.most_likely_probability:.1f}%)"
            ), "inline": True},
            {"name": "Bias", "value": status.market_bias, "inline": True},
        ]

        if status.next_meeting:
            fields.append({
                "name": "Next FOMC",
                "value": f"{status.next_meeting.date:%b %d} ({status.next_meeting.days_until}d)",
                "inline": True,
            })

        fields.append({"name": "Implication", "value": implications['summary'], "inline": False})

        if implications['trades']:
            trade_lines = [f"{t['action']} {t['symbol']}" for t in implications['trades'][:3]]
            fields.append({"name": "Trade Ideas", "value": " | ".join(trade_lines), "inline": False})

        return {
            "title": title,
            "color": color,
            "fields": fields,
            "footer": {"text": f"Fed Watch Monitor | Source: {status.source}"},
            "timestamp": datetime.utcnow().isoformat(),
        }


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Demo the Fed Watch Monitor."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    monitor = FedWatchMonitor()
    status = monitor.get_current_status()
    monitor.print_fed_dashboard(status)


if __name__ == "__main__":
    main()
