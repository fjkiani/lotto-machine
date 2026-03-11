"""
🌙 OVERNIGHT MANAGER

Handles all post-market and overnight monitoring:
- Overnight intelligence checks (every 2h when market closed)
- Overnight narrative generation (futures, crypto, Asia markets)
- Daily market recap (4:00-4:05 PM ET)

Extracted from unified_monitor.py for modularity.
"""

import logging
from datetime import datetime
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)


class OvernightManager:
    """Manages overnight checks, narratives, and daily recaps."""

    def __init__(
        self,
        send_discord: Callable,
        run_checker_with_health: Callable,
        trump_checker=None,
        news_intelligence_checker=None,
        gamma_tracker=None,
        symbols: List[str] = None,
        gamma_enabled: bool = False,
        squeeze_enabled: bool = False,
    ):
        self.send_discord = send_discord
        self.run_checker_with_health = run_checker_with_health
        self.trump_checker = trump_checker
        self.news_intelligence_checker = news_intelligence_checker
        self.gamma_tracker = gamma_tracker
        self.symbols = symbols or ['SPY', 'QQQ', 'IWM']
        self.gamma_enabled = gamma_enabled
        self.squeeze_enabled = squeeze_enabled
        self._last_recap_date = None

    # ═══════════════════════════════════════════════════════════════
    # OVERNIGHT CHECK
    # ═══════════════════════════════════════════════════════════════

    def run_overnight_check(self, now: datetime):
        """
        Run checks when market is CLOSED (post-market and overnight).
        Runs every 2 hours to keep service alive and monitor overnight developments.
        """
        import pytz
        et = pytz.timezone('America/New_York')
        now_et = now.astimezone(et) if now.tzinfo else pytz.UTC.localize(now).astimezone(et)

        logger.info("=" * 60)
        logger.info(f"🌙 OVERNIGHT CHECK | {now_et.strftime('%I:%M %p ET')}")
        logger.info("=" * 60)

        try:
            # 1. Check Trump news (can happen anytime)
            trump_alerts = []
            if self.trump_checker:
                trump_alerts = self.run_checker_with_health('trump_overnight', self.trump_checker.check)
                for alert in trump_alerts:
                    self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)

            # 2. Check news for major symbols
            if self.news_intelligence_checker:
                news_alerts = self.run_checker_with_health('news_overnight', self.news_intelligence_checker.check)
                for alert in news_alerts:
                    self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)

            # 3. Get overnight futures/crypto sentiment
            overnight_narrative = self._generate_overnight_narrative(now_et)

            if overnight_narrative:
                embed = {
                    "title": f"🌙 OVERNIGHT INTEL | {now_et.strftime('%I:%M %p ET')}",
                    "description": overnight_narrative,
                    "color": 0x3498db,
                    "fields": [
                        {
                            "name": "📊 Status",
                            "value": f"• Market: CLOSED\n• Next open: 9:30 AM ET\n• Trump alerts: {len(trump_alerts)}",
                            "inline": True
                        }
                    ],
                    "footer": {"text": "Alpha Intelligence | Overnight Watch"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.send_discord(embed, "", "overnight_intel", "overnight_monitor", "SPY,QQQ")

            logger.info(f"   ✅ Overnight check complete | Trump: {len(trump_alerts)} alerts")

        except Exception as e:
            logger.error(f"   ❌ Overnight check error: {e}")

    def _generate_overnight_narrative(self, now_et: datetime) -> str:
        """Generate a brief overnight market narrative."""
        try:
            import yfinance as yf

            spy = yf.Ticker('SPY')
            btc = yf.Ticker('BTC-USD')

            spy_info = spy.info
            btc_hist = btc.history(period='1d')

            parts = []

            if 'regularMarketPrice' in spy_info and 'previousClose' in spy_info:
                spy_close = spy_info.get('regularMarketPrice', 0)
                spy_prev = spy_info.get('previousClose', 0)
                if spy_prev > 0:
                    spy_change = ((spy_close - spy_prev) / spy_prev) * 100
                    direction = "📈" if spy_change > 0 else "📉" if spy_change < 0 else "➡️"
                    parts.append(f"{direction} SPY closed at ${spy_close:.2f} ({spy_change:+.2f}%)")

            if not btc_hist.empty:
                btc_price = btc_hist['Close'].iloc[-1]
                parts.append(f"₿ BTC at ${btc_price:,.0f}")

            hour = now_et.hour
            if hour < 6:
                parts.append("🌃 Asia markets active")
            elif hour < 12:
                parts.append("🌅 Pre-market prep time")
            elif hour < 17:
                parts.append("🌆 After-hours trading")
            else:
                parts.append("🌙 Overnight watch")

            return " | ".join(parts) if parts else "Market closed - monitoring overnight developments"

        except Exception as e:
            logger.debug(f"Overnight narrative error: {e}")
            return "Market closed - monitoring overnight developments"

    # ═══════════════════════════════════════════════════════════════
    # DAILY RECAP
    # ═══════════════════════════════════════════════════════════════

    def should_send_daily_recap(self, now: datetime) -> bool:
        """Check if we should send daily recap (4:00-4:05 PM ET on weekdays)."""
        try:
            import pytz
            et = pytz.timezone('America/New_York')
            now_et = now.astimezone(et) if now.tzinfo else pytz.UTC.localize(now).astimezone(et)

            if now_et.weekday() >= 5:
                return False

            if now_et.hour == 16 and now_et.minute < 5:
                if self._last_recap_date != now_et.date():
                    return True
            return False

        except Exception as e:
            logger.debug(f"Daily recap check error: {e}")
            return False

    def send_daily_recap(self):
        """📊 Send daily market recap to Discord."""
        try:
            import yfinance as yf
            import pytz

            et = pytz.timezone('America/New_York')
            now_et = datetime.now(et)

            logger.info("📊 Generating daily market recap...")

            spy = yf.Ticker('SPY')
            qqq = yf.Ticker('QQQ')
            vix = yf.Ticker('^VIX')

            spy_hist = spy.history(period='1d', interval='5m')
            qqq_hist = qqq.history(period='1d', interval='5m')
            vix_hist = vix.history(period='1d')

            if spy_hist.empty:
                logger.warning("   ⚠️ No SPY data for daily recap")
                return

            spy_open = float(spy_hist['Open'].iloc[0])
            spy_close = float(spy_hist['Close'].iloc[-1])
            spy_high = float(spy_hist['High'].max())
            spy_low = float(spy_hist['Low'].min())
            spy_change = ((spy_close - spy_open) / spy_open) * 100
            spy_range = ((spy_high - spy_low) / spy_open) * 100

            qqq_open = float(qqq_hist['Open'].iloc[0]) if not qqq_hist.empty else 0
            qqq_close = float(qqq_hist['Close'].iloc[-1]) if not qqq_hist.empty else 0
            qqq_change = ((qqq_close - qqq_open) / qqq_open) * 100 if qqq_open > 0 else 0

            vix_close = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 0

            if spy_change > 0.5:
                sentiment = "🟢 BULLISH"
                color = 0x00ff00
            elif spy_change < -0.5:
                sentiment = "🔴 BEARISH"
                color = 0xff0000
            else:
                sentiment = "⚪ NEUTRAL"
                color = 0x808080

            gamma_status = "❌ No signals"
            if self.gamma_enabled and self.gamma_tracker:
                for symbol in self.symbols:
                    signal = self.gamma_tracker.analyze(symbol)
                    if signal:
                        gamma_status = f"✅ {symbol}: {signal.direction} (Score {signal.score:.0f})"
                        break

            embed = {
                "title": f"📊 DAILY MARKET RECAP - {now_et.strftime('%B %d, %Y')}",
                "color": color,
                "description": f"**Market Sentiment:** {sentiment}",
                "fields": [
                    {"name": "📈 SPY", "value": f"Open: ${spy_open:.2f}\nClose: ${spy_close:.2f}\nChange: {spy_change:+.2f}%\nRange: {spy_range:.2f}%", "inline": True},
                    {"name": "📈 QQQ", "value": f"Open: ${qqq_open:.2f}\nClose: ${qqq_close:.2f}\nChange: {qqq_change:+.2f}%", "inline": True},
                    {"name": "😰 VIX", "value": f"{vix_close:.2f}", "inline": True},
                    {"name": "📊 Intraday", "value": f"High: ${spy_high:.2f}\nLow: ${spy_low:.2f}", "inline": True},
                    {"name": "🎲 Gamma Status", "value": gamma_status, "inline": True},
                    {"name": "🔥 Exploitation", "value": f"Squeeze: {'✅' if self.squeeze_enabled else '❌'}\nGamma: {'✅' if self.gamma_enabled else '❌'}", "inline": True},
                ],
                "footer": {"text": "Alpha Intelligence • Daily Recap"},
                "timestamp": datetime.utcnow().isoformat()
            }

            morning_drop = ((spy_low - spy_open) / spy_open) * 100
            if morning_drop < -0.5:
                embed["fields"].append({"name": "🔻 Key Event", "value": f"Morning selloff: {morning_drop:.2f}%\nLow: ${spy_low:.2f}", "inline": False})

            recovery = ((spy_close - spy_low) / spy_low) * 100
            if recovery > 0.3:
                embed["fields"].append({"name": "📈 Recovery", "value": f"+{recovery:.2f}% from lows", "inline": False})

            content = f"📊 **DAILY RECAP** | SPY {spy_change:+.2f}% | QQQ {qqq_change:+.2f}% | VIX {vix_close:.2f}"

            self.send_discord(embed, content=content, alert_type="daily_recap", source="daily_recap", symbol="SPY,QQQ")

            self._last_recap_date = now_et.date()
            logger.info(f"   📊 Daily recap sent! SPY {spy_change:+.2f}%")

        except Exception as e:
            logger.error(f"   ❌ Daily recap error: {e}")
