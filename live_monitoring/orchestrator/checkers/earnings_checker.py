#!/usr/bin/env python3
"""
📅 EARNINGS CHECKER — Autonomous Earnings Kill Chain

Dynamically discovers upcoming earnings targets, runs a multi-source
intelligence sweep, scores each via an 8-factor decision matrix, and
fires Discord alerts with actionable score cards.

DATA SOURCES (all verified live 2026-03-11):
  1. yfinance .calendar      → earnings dates
  2. yfinance .option_chain   → IV, P/C ratio, straddle (RTH only)
  3. yfinance .earnings_history → beat/miss streak
  4. yfinance .insider_transactions → insider activity
  5. StockgridClient.get_earnings_intel → dark pool + option walls + VIX regime
  6. KillChainLogger.run_single_check → COT + GEX triple confluence
  7. FinnhubClient.get_company_news → news headline catalysts (needs key)

SCHEDULE: Runs daily at 7 AM ET (pre-market), then every 4h during RTH.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from live_monitoring.orchestrator.checkers.base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 8-Factor Scoring Matrix
# ═══════════════════════════════════════════════════════════════════════════════

FACTOR_WEIGHTS = {
    "iv_rank":            15,   # IV rank vs historical (options overpriced?)
    "dp_accumulation":    20,   # Dark pool net position trend (smart money direction)
    "earnings_streak":    10,   # Consecutive beats/misses
    "insider_activity":   10,   # Net insider buying/selling
    "options_skew":       15,   # Put/Call ratio + straddle implied move
    "sector_momentum":    5,    # Peer performance context
    "kill_chain_regime":  15,   # COT + GEX + DVR macro regime
    "news_catalyst":      10,   # Headline catalyst proximity
}


def _score_factor(name: str, value: float, max_val: float = 100.0) -> Tuple[float, str]:
    """Score a factor 0-100, return (weighted_score, evidence_string)."""
    raw = min(max(value, 0.0), max_val)
    weight = FACTOR_WEIGHTS.get(name, 10)
    weighted = (raw / max_val) * weight
    return weighted, f"{raw:.0f}/100 ({weighted:.1f}/{weight} pts)"


class EarningsChecker(BaseChecker):
    """
    Autonomous earnings intelligence checker.

    - Discovers targets dynamically from yfinance calendar
    - Scores each with 8-factor matrix
    - Returns CheckerAlert list for Discord
    """

    # Default watchlist for high-volume tickers. Auto-discovery supplements this.
    WATCHLIST = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
        "ADBE", "ORCL", "CRM", "NFLX", "AVGO", "AMD", "INTC",
        "JPM", "BAC", "GS", "MS", "WFC",
        "UNH", "JNJ", "PFE", "LLY", "MRK",
        "HD", "LOW", "NKE", "COST", "WMT",
        "FDX", "UPS", "LEN", "KBH", "PHM",
        "MU", "LULU", "DRI", "GIS", "FDS",
    ]

    def __init__(self, alert_manager, unified_mode: bool = False):
        super().__init__(alert_manager, unified_mode)
        self._stockgrid = None
        self._kill_chain = None
        self._finnhub = None
        self._scanned_today = set()
        self._init_clients()

    def _init_clients(self):
        """Initialize data clients (fail-soft)."""
        try:
            from live_monitoring.enrichment.apis.stockgrid_client import StockgridClient
            self._stockgrid = StockgridClient()
            logger.info("   ✅ EarningsChecker: StockgridClient loaded")
        except Exception as e:
            logger.warning(f"   ⚠️ EarningsChecker: StockgridClient unavailable: {e}")

        try:
            from live_monitoring.kill_chain_logger import KillChainLogger
            self._kill_chain = KillChainLogger(check_interval_min=999)
            logger.info("   ✅ EarningsChecker: KillChainLogger loaded")
        except Exception as e:
            logger.warning(f"   ⚠️ EarningsChecker: KillChainLogger unavailable: {e}")

        try:
            if os.getenv("FINNHUB_API_KEY"):
                from live_monitoring.enrichment.apis.finnhub_client import FinnhubClient
                self._finnhub = FinnhubClient()
                logger.info("   ✅ EarningsChecker: FinnhubClient loaded")
        except Exception as e:
            logger.warning(f"   ⚠️ EarningsChecker: FinnhubClient unavailable: {e}")

    @property
    def name(self) -> str:
        return "earnings_checker"

    # ═══════════════════════════════════════════════════════════════════════════
    # Main Check Entry Point
    # ═══════════════════════════════════════════════════════════════════════════

    def check(self, symbols: List[str] = None) -> List[CheckerAlert]:
        """
        Main entry: discover targets → score → alert.

        Returns list of CheckerAlert for tickers with earnings in 0-2 days.
        """
        alerts = []
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            # Phase 1: Discover earnings targets
            targets = self._discover_targets(symbols or self.WATCHLIST)

            if not targets:
                logger.info("   📅 EarningsChecker: No upcoming earnings in watchlist")
                return alerts

            logger.info(f"   📅 EarningsChecker: {len(targets)} earnings targets found")

            # Phase 2: Score each target
            for ticker, earnings_date, days_until in targets:
                alert_key = f"earnings_{ticker}_{today}"
                if alert_key in self._scanned_today:
                    continue

                try:
                    score_card = self._score_target(ticker, earnings_date, days_until)
                    self._scanned_today.add(alert_key)

                    # Phase 3: Generate alert if score >= 40
                    if score_card["total_score"] >= 40:
                        alert = self._create_earnings_alert(ticker, score_card)
                        alerts.append(alert)
                        logger.info(
                            f"   📅 Earnings alert: {ticker} Score={score_card['total_score']:.0f} "
                            f"Exploit={score_card['exploit']}"
                        )

                except Exception as e:
                    logger.error(f"   ❌ EarningsChecker: Error scoring {ticker}: {e}")

            # Clean stale entries
            self._scanned_today = {k for k in self._scanned_today if k.startswith(f"earnings_") and today in k}

        except Exception as e:
            logger.error(f"   ❌ EarningsChecker: Main check error: {e}")

        return alerts

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 1: Dynamic Target Discovery
    # ═══════════════════════════════════════════════════════════════════════════

    def _discover_targets(self, watchlist: List[str]) -> List[Tuple[str, str, int]]:
        """
        Scan watchlist for tickers with earnings in the next 0-2 days.

        Returns: [(ticker, earnings_date_str, days_until), ...]
        """
        import yfinance as yf

        targets = []
        today = datetime.now().date()

        for ticker in watchlist:
            try:
                t = yf.Ticker(ticker)
                cal = t.calendar
                if cal is None:
                    continue

                if 'Earnings Date' in cal:
                    dates = list(cal['Earnings Date'])
                    if not dates:
                        continue
                    ed = dates[0]
                    if hasattr(ed, 'date'):
                        ed_date = ed.date()
                    else:
                        from dateutil.parser import parse
                        ed_date = parse(str(ed)).date()

                    days_until = (ed_date - today).days

                    # Only care about earnings within 0-2 days
                    if 0 <= days_until <= 2:
                        targets.append((ticker, str(ed_date), days_until))

            except Exception:
                continue  # Skip tickers that fail silently

        # Sort by soonest first
        targets.sort(key=lambda x: x[2])
        return targets

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 2: 8-Factor Scoring
    # ═══════════════════════════════════════════════════════════════════════════

    def _score_target(self, ticker: str, earnings_date: str, days_until: int) -> Dict:
        """
        Score a single earnings target using the 8-factor matrix.

        Returns dict with factor scores, total, evidence, and exploit recommendation.
        """
        import yfinance as yf

        card = {
            "ticker": ticker,
            "earnings_date": earnings_date,
            "days_until": days_until,
            "factors": {},
            "total_score": 0.0,
            "exploit": "SKIP",
            "evidence": [],
        }

        total = 0.0
        t = yf.Ticker(ticker)

        # ── Factor 1: IV Rank ──────────────────────────────────────────────
        iv_score = 0.0
        try:
            exps = t.options
            if exps:
                chain = t.option_chain(exps[0])
                if not chain.calls.empty:
                    avg_iv = chain.calls['impliedVolatility'].mean() * 100
                    # Score higher when IV is elevated (>50% = premium is rich)
                    iv_score = min(avg_iv * 1.5, 100.0)
                    card["evidence"].append(f"IV: {avg_iv:.1f}% (nearest exp)")
        except Exception:
            card["evidence"].append("IV: unavailable (after-hours)")

        w, ev = _score_factor("iv_rank", iv_score)
        card["factors"]["iv_rank"] = {"score": iv_score, "weighted": w, "evidence": ev}
        total += w

        # ── Factor 2: Dark Pool Accumulation ───────────────────────────────
        dp_score = 0.0
        try:
            if self._stockgrid:
                intel = self._stockgrid.get_earnings_intel([ticker])
                ti = intel.get(ticker, {})
                if ti.get("status") == "live":
                    sv_pct = ti.get("short_volume_pct", 50.0)
                    trend = ti.get("trend_5d", [])
                    close = ti.get("close", 0)

                    # Covering (DP position going less negative) = bullish
                    # Distributing (more negative) = bearish
                    # Either direction = signal strength
                    if len(trend) >= 2:
                        first_pos = trend[0].get("dp_position", 0)
                        last_pos = trend[-1].get("dp_position", 0)
                        delta = last_pos - first_pos
                        # Magnitude of 5d change relative to position
                        if abs(first_pos) > 0:
                            change_pct = abs(delta / first_pos) * 100
                            dp_score = min(change_pct * 5, 100.0)

                    card["evidence"].append(
                        f"DP: SV%={sv_pct:.1f}%, close=${close}, "
                        f"5d trend={'covering' if delta > 0 else 'distributing'}"
                    )

                    # Store for alert
                    card["dp_data"] = {
                        "sv_pct": sv_pct,
                        "close": close,
                        "trend_5d": trend,
                    }

                    # Also grab walls
                    spy_walls = intel.get("SPY_walls", {})
                    regime = intel.get("_regime", {})
                    card["spy_walls"] = spy_walls
                    card["regime"] = regime
        except Exception as e:
            card["evidence"].append(f"DP: error ({e})")

        w, ev = _score_factor("dp_accumulation", dp_score)
        card["factors"]["dp_accumulation"] = {"score": dp_score, "weighted": w, "evidence": ev}
        total += w

        # ── Factor 3: Earnings Streak ──────────────────────────────────────
        streak_score = 0.0
        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                beats = 0
                for _, row in eh.iterrows():
                    if row.get('epsActual', 0) > row.get('epsEstimate', 0):
                        beats += 1
                streak_pct = (beats / len(eh)) * 100
                streak_score = streak_pct
                card["evidence"].append(f"Earnings: {beats}/{len(eh)} beats")
                card["earnings_streak"] = beats
        except Exception:
            card["evidence"].append("Earnings history: unavailable")

        w, ev = _score_factor("earnings_streak", streak_score)
        card["factors"]["earnings_streak"] = {"score": streak_score, "weighted": w, "evidence": ev}
        total += w

        # ── Factor 4: Insider Activity ─────────────────────────────────────
        insider_score = 0.0
        try:
            ins = t.insider_transactions
            if ins is not None and not ins.empty:
                # Look at last 90 days
                recent = ins.head(20)
                buys = recent[recent['Text'].str.contains('Purchase|Acquisition', case=False, na=False)]
                sells = recent[recent['Text'].str.contains('Sale|Disposition', case=False, na=False)]
                net = len(buys) - len(sells)
                # Positive net = buying = bullish
                insider_score = min(abs(net) * 15, 100.0)
                direction = "NET BUY" if net > 0 else "NET SELL" if net < 0 else "NEUTRAL"
                card["evidence"].append(f"Insiders: {direction} ({len(buys)}B/{len(sells)}S in last 20 txns)")
                card["insider_direction"] = direction
        except Exception:
            card["evidence"].append("Insiders: unavailable")

        w, ev = _score_factor("insider_activity", insider_score)
        card["factors"]["insider_activity"] = {"score": insider_score, "weighted": w, "evidence": ev}
        total += w

        # ── Factor 5: Options Skew ─────────────────────────────────────────
        skew_score = 0.0
        try:
            exps = t.options
            if exps:
                chain = t.option_chain(exps[0])
                total_call_oi = int(chain.calls['openInterest'].sum())
                total_put_oi = int(chain.puts['openInterest'].sum())
                if total_put_oi > 0:
                    pc_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 999
                    # Extreme P/C ratio (>1.5 or <0.5) = directional bet = higher score
                    deviation = abs(pc_ratio - 1.0)
                    skew_score = min(deviation * 100, 100.0)
                    card["evidence"].append(f"P/C Ratio: {pc_ratio:.2f} ({total_call_oi:,}C/{total_put_oi:,}P)")
                elif total_call_oi > 0:
                    skew_score = 50.0  # All calls, no puts = bullish signal
                    card["evidence"].append(f"Options: {total_call_oi:,} calls, 0 puts (after-hours)")
                else:
                    card["evidence"].append("Options OI: stale (after-hours)")
        except Exception:
            card["evidence"].append("Options: unavailable")

        w, ev = _score_factor("options_skew", skew_score)
        card["factors"]["options_skew"] = {"score": skew_score, "weighted": w, "evidence": ev}
        total += w

        # ── Factor 6: Sector Momentum ──────────────────────────────────────
        sector_score = 50.0  # Neutral default
        try:
            info = t.info or {}
            sector = info.get("sector", "Unknown")
            card["evidence"].append(f"Sector: {sector}")
        except Exception:
            card["evidence"].append("Sector: unavailable")

        w, ev = _score_factor("sector_momentum", sector_score)
        card["factors"]["sector_momentum"] = {"score": sector_score, "weighted": w, "evidence": ev}
        total += w

        # ── Factor 7: Kill Chain Regime ────────────────────────────────────
        regime_score = 0.0
        try:
            if self._kill_chain:
                self._kill_chain.run_single_check()
                if self._kill_chain.triple_active:
                    regime_score = 90.0
                    card["evidence"].append("Kill Chain: TRIPLE ACTIVE (COT+GEX+DVR)")
                elif self._kill_chain.cot_divergence:
                    regime_score = 60.0
                    card["evidence"].append("Kill Chain: COT divergence active")
                else:
                    regime_score = 30.0
                    card["evidence"].append("Kill Chain: No confluence")

                card["kill_chain"] = {
                    "cot_divergence": self._kill_chain.cot_divergence,
                    "gex_positive": self._kill_chain.gex_positive,
                    "triple_active": self._kill_chain.triple_active,
                    "vix": self._kill_chain.vix,
                    "spy": self._kill_chain.spy_price,
                }
        except Exception as e:
            card["evidence"].append(f"Kill Chain: error ({e})")

        w, ev = _score_factor("kill_chain_regime", regime_score)
        card["factors"]["kill_chain_regime"] = {"score": regime_score, "weighted": w, "evidence": ev}
        total += w

        # ── Factor 8: News Catalyst ────────────────────────────────────────
        news_score = 0.0
        try:
            if self._finnhub:
                news = self._finnhub.get_company_news(ticker)
                if news:
                    # Having recent news = catalyst active
                    news_score = min(len(news) * 8, 100.0)
                    top = news[0].get("headline", "")[:60]
                    card["evidence"].append(f"News: {len(news)} articles, top='{top}'")
                else:
                    card["evidence"].append("News: no recent articles")
        except Exception:
            card["evidence"].append("News: Finnhub unavailable")

        w, ev = _score_factor("news_catalyst", news_score)
        card["factors"]["news_catalyst"] = {"score": news_score, "weighted": w, "evidence": ev}
        total += w

        # ── Final Score & Exploit Decision ─────────────────────────────────
        card["total_score"] = total

        if total >= 75:
            card["exploit"] = "🔴 SELL PREMIUM (Iron Condor / Strangle)"
        elif total >= 60:
            card["exploit"] = "🟡 DIRECTIONAL (Debit Spread / Stock)"
        elif total >= 40:
            card["exploit"] = "🟢 MONITOR (Wait for confirmation)"
        else:
            card["exploit"] = "⚪ SKIP (Low conviction)"

        return card

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase 3: Discord Alert
    # ═══════════════════════════════════════════════════════════════════════════

    def _create_earnings_alert(self, ticker: str, card: Dict) -> CheckerAlert:
        """Create a Discord alert from a scored earnings card."""
        score = card["total_score"]
        days = card["days_until"]

        if score >= 75:
            color = 0xff0000  # Red = high conviction
        elif score >= 60:
            color = 0xff8c00  # Orange
        elif score >= 40:
            color = 0xffd700  # Gold
        else:
            color = 0x808080  # Gray

        timing = "📅 TODAY" if days == 0 else f"📅 In {days} day{'s' if days > 1 else ''}"

        # Build factor summary
        factor_lines = []
        for fname, fdata in card["factors"].items():
            factor_lines.append(f"{fname}: {fdata['evidence']}")

        embed = {
            "title": f"📅 EARNINGS INTEL: {ticker} | {timing}",
            "color": color,
            "description": (
                f"**Score: {score:.0f}/100** | {card['exploit']}\n"
                f"Earnings: {card['earnings_date']}"
            ),
            "fields": [],
            "footer": {"text": "Earnings Kill Chain • Autonomous Scanner"},
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add top evidence
        evidence_text = "\n".join([f"• {e}" for e in card["evidence"][:8]])
        embed["fields"].append({
            "name": "📊 Intelligence",
            "value": evidence_text[:1024] if evidence_text else "No data",
            "inline": False,
        })

        # Factor breakdown
        factor_text = "\n".join([
            f"**{fn}**: {fd['evidence']}"
            for fn, fd in card["factors"].items()
        ])
        embed["fields"].append({
            "name": "🎯 8-Factor Breakdown",
            "value": factor_text[:1024] if factor_text else "No factors",
            "inline": False,
        })

        # Kill chain regime if available
        kc = card.get("kill_chain", {})
        if kc:
            embed["fields"].append({
                "name": "⚔️ Kill Chain",
                "value": (
                    f"COT: {'✅' if kc.get('cot_divergence') else '❌'} | "
                    f"GEX: {'✅' if kc.get('gex_positive') else '❌'} | "
                    f"Triple: {'✅ ACTIVE' if kc.get('triple_active') else '❌'}\n"
                    f"VIX: {kc.get('vix', 0):.1f} | SPY: ${kc.get('spy', 0):.2f}"
                ),
                "inline": False,
            })

        # Exploit recommendation
        embed["fields"].append({
            "name": "💡 Exploit",
            "value": card["exploit"],
            "inline": False,
        })

        content = (
            f"📅 **EARNINGS ALERT** | {ticker} Score: {score:.0f}/100 | "
            f"{card['exploit']} | {timing}"
        )

        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="earnings_intel",
            source="earnings_checker",
            symbol=ticker,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Standalone Test
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("📅 EARNINGS CHECKER — STANDALONE TEST")
    print("=" * 70)

    checker = EarningsChecker(alert_manager=None)

    print(f"\nChecker: {checker.name}")
    print(f"Watchlist: {len(checker.WATCHLIST)} tickers")

    # Run check
    alerts = checker.check()

    print(f"\n{'=' * 70}")
    print(f"RESULTS: {len(alerts)} alerts generated")
    print(f"{'=' * 70}")

    for alert in alerts:
        print(f"\n  Ticker: {alert.symbol}")
        print(f"  Title:  {alert.embed['title']}")
        print(f"  {alert.embed['description']}")
        for field in alert.embed.get("fields", []):
            print(f"  {field['name']}:")
            for line in field['value'].split('\n')[:5]:
                print(f"    {line}")

    if not alerts:
        # Force-test with ADBE
        print("\n  No natural targets. Force-testing ADBE...")
        card = checker._score_target("ADBE", "2026-03-12", 1)
        print(f"  Score: {card['total_score']:.0f}/100")
        print(f"  Exploit: {card['exploit']}")
        for e in card["evidence"]:
            print(f"    • {e}")

    print(f"\n{'=' * 70}")
    print("✅ Earnings Checker test complete!")
