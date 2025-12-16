"""
Daily Recap Checker - Generates daily market recap at market close.

Extracted from unified_monitor.py for modularity.

This checker sends a comprehensive daily market recap at 4:00 PM ET
on weekdays, summarizing SPY/QQQ performance, VIX, and key events.
"""

import logging
from datetime import datetime
from typing import List, Optional

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class DailyRecapChecker(BaseChecker):
    """
    Generates and sends daily market recap.
    
    Responsibilities:
    - Check if it's time to send recap (4:00-4:05 PM ET on weekdays)
    - Fetch market data (SPY, QQQ, VIX)
    - Calculate metrics (change, range, sentiment)
    - Generate comprehensive recap embed
    - Track last sent date to avoid duplicates
    """
    
    def __init__(
        self,
        alert_manager,
        gamma_tracker=None,
        symbols=None,
        squeeze_enabled=False,
        gamma_enabled=False,
        unified_mode=False
    ):
        """
        Initialize Daily Recap checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            gamma_tracker: GammaTracker instance (optional, for gamma status)
            symbols: List of symbols to check (e.g., ['SPY', 'QQQ'])
            squeeze_enabled: Whether squeeze detection is enabled
            gamma_enabled: Whether gamma tracking is enabled
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        self.gamma_tracker = gamma_tracker
        self.symbols = symbols or []
        self.squeeze_enabled = squeeze_enabled
        self.gamma_enabled = gamma_enabled
        
        # State management
        self._last_recap_date = None
    
    def should_send(self, now: datetime) -> bool:
        """
        Check if we should send daily recap (4:00-4:05 PM ET on weekdays).
        
        Args:
            now: Current datetime
            
        Returns:
            True if recap should be sent, False otherwise
        """
        try:
            import pytz
            et = pytz.timezone('America/New_York')
            now_et = now.astimezone(et) if now.tzinfo else et.localize(now)
            
            # Only weekdays
            if now_et.weekday() >= 5:
                return False
            
            # Between 4:00 PM and 4:05 PM ET
            if now_et.hour == 16 and now_et.minute < 5:
                # Check if we already sent today
                today = now_et.date()
                if self._last_recap_date != today:
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"Daily recap check error: {e}")
            return False
    
    def check(self, now: Optional[datetime] = None) -> List[CheckerAlert]:
        """
        Check if it's time to send daily recap and generate it.
        
        Args:
            now: Current datetime (defaults to datetime.now())
            
        Returns:
            List of CheckerAlert objects (empty if not time to send)
        """
        if now is None:
            now = datetime.now()
        
        if not self.should_send(now):
            return []
        
        try:
            import yfinance as yf
            import pytz
            
            et = pytz.timezone('America/New_York')
            now_et = datetime.now(et)
            
            logger.info("📊 Generating daily market recap...")
            
            # Get market data
            spy = yf.Ticker('SPY')
            qqq = yf.Ticker('QQQ')
            vix = yf.Ticker('^VIX')
            
            spy_hist = spy.history(period='1d', interval='5m')
            qqq_hist = qqq.history(period='1d', interval='5m')
            vix_hist = vix.history(period='1d')
            
            if spy_hist.empty:
                logger.warning("   ⚠️ No SPY data for daily recap")
                return []
            
            # Calculate metrics
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
            
            # Determine market sentiment
            if spy_change > 0.5:
                sentiment = "🟢 BULLISH"
                color = 0x00ff00
            elif spy_change < -0.5:
                sentiment = "🔴 BEARISH"
                color = 0xff0000
            else:
                sentiment = "⚪ NEUTRAL"
                color = 0x808080
            
            # Get gamma signal status
            gamma_status = "❌ No signals"
            if self.gamma_enabled and self.gamma_tracker:
                for symbol in self.symbols:
                    signal = self.gamma_tracker.analyze(symbol)
                    if signal:
                        gamma_status = f"✅ {symbol}: {signal.direction} (Score {signal.score:.0f})"
                        break
            
            # Build embed
            embed = {
                "title": f"📊 DAILY MARKET RECAP - {now_et.strftime('%B %d, %Y')}",
                "color": color,
                "description": f"**Market Sentiment:** {sentiment}",
                "fields": [
                    {
                        "name": "📈 SPY",
                        "value": f"Open: ${spy_open:.2f}\nClose: ${spy_close:.2f}\nChange: {spy_change:+.2f}%\nRange: {spy_range:.2f}%",
                        "inline": True
                    },
                    {
                        "name": "📈 QQQ",
                        "value": f"Open: ${qqq_open:.2f}\nClose: ${qqq_close:.2f}\nChange: {qqq_change:+.2f}%",
                        "inline": True
                    },
                    {
                        "name": "😰 VIX",
                        "value": f"{vix_close:.2f}",
                        "inline": True
                    },
                    {
                        "name": "📊 Intraday",
                        "value": f"High: ${spy_high:.2f}\nLow: ${spy_low:.2f}",
                        "inline": True
                    },
                    {
                        "name": "🎲 Gamma Status",
                        "value": gamma_status,
                        "inline": True
                    },
                    {
                        "name": "🔥 Exploitation",
                        "value": f"Squeeze: {'✅' if self.squeeze_enabled else '❌'}\nGamma: {'✅' if self.gamma_enabled else '❌'}",
                        "inline": True
                    }
                ],
                "footer": {"text": "Alpha Intelligence • Daily Recap"},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add key events
            morning_drop = ((spy_low - spy_open) / spy_open) * 100
            if morning_drop < -0.5:
                embed["fields"].append({
                    "name": "🔻 Key Event",
                    "value": f"Morning selloff: {morning_drop:.2f}%\nLow: ${spy_low:.2f}",
                    "inline": False
                })
            
            recovery = ((spy_close - spy_low) / spy_low) * 100
            if recovery > 0.3:
                embed["fields"].append({
                    "name": "📈 Recovery",
                    "value": f"+{recovery:.2f}% from lows",
                    "inline": False
                })
            
            content = f"📊 **DAILY RECAP** | SPY {spy_change:+.2f}% | QQQ {qqq_change:+.2f}% | VIX {vix_close:.2f}"
            
            # Mark as sent
            self._last_recap_date = now_et.date()
            
            logger.info(f"   📊 Daily recap sent! SPY {spy_change:+.2f}%")
            
            return [CheckerAlert(
                embed=embed,
                content=content,
                alert_type="daily_recap",
                source="daily_recap_checker",
                symbol="SPY,QQQ"
            )]
            
        except Exception as e:
            logger.error(f"   ❌ Daily recap error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

