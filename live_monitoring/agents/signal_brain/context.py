"""
🧠 Signal Brain - Context Enrichment
====================================
Adds market context: trend, VIX, time of day, Fed sentiment.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import pytz

import yfinance as yf

from .models import MarketContext, TimeOfDay, Bias

logger = logging.getLogger(__name__)

# Eastern timezone for market hours
ET = pytz.timezone('US/Eastern')


class ContextEnricher:
    """
    Enriches signals with full market context.
    """
    
    def __init__(self):
        self._cache = {}
        self._cache_time = None
        self._cache_duration = timedelta(minutes=1)
    
    def get_context(
        self,
        fed_sentiment: str = "NEUTRAL",
        trump_risk: str = "LOW"
    ) -> MarketContext:
        """
        Get current market context.
        
        Args:
            fed_sentiment: From Fed monitor (HAWKISH/DOVISH/NEUTRAL)
            trump_risk: From Trump monitor (HIGH/MEDIUM/LOW)
        """
        # Check cache
        if self._cache and self._cache_time:
            if datetime.now() - self._cache_time < self._cache_duration:
                ctx = self._cache.copy()
                ctx['fed_sentiment'] = fed_sentiment
                ctx['trump_risk'] = trump_risk
                return MarketContext(**ctx)
        
        # Fetch fresh data
        context = MarketContext(
            timestamp=datetime.now(),
            fed_sentiment=fed_sentiment,
            trump_risk=trump_risk,
        )
        
        # Time of day
        context.time_of_day = self._get_time_of_day()
        context.minutes_to_close = self._minutes_to_close()
        
        # SPY data
        try:
            spy = yf.Ticker("SPY")
            spy_hist = spy.history(period="2d", interval="1m")
            
            if not spy_hist.empty:
                context.spy_price = float(spy_hist['Close'].iloc[-1])
                
                # Today's change
                today_open = float(spy_hist['Open'].iloc[0])
                context.spy_change_pct = (context.spy_price - today_open) / today_open * 100
                
                # 1-hour trend
                if len(spy_hist) >= 60:
                    price_1h_ago = float(spy_hist['Close'].iloc[-60])
                    change_1h = (context.spy_price - price_1h_ago) / price_1h_ago * 100
                    if change_1h > 0.1:
                        context.spy_trend_1h = Bias.BULLISH
                    elif change_1h < -0.1:
                        context.spy_trend_1h = Bias.BEARISH
                    else:
                        context.spy_trend_1h = Bias.NEUTRAL
                
                # 1-day trend (using 2d data)
                if len(spy_hist) >= 390:  # Full day of minute bars
                    price_1d_ago = float(spy_hist['Close'].iloc[-390])
                    change_1d = (context.spy_price - price_1d_ago) / price_1d_ago * 100
                    if change_1d > 0.3:
                        context.spy_trend_1d = Bias.BULLISH
                    elif change_1d < -0.3:
                        context.spy_trend_1d = Bias.BEARISH
                
        except Exception as e:
            logger.warning(f"⚠️ SPY data error: {e}")
        
        # QQQ data
        try:
            qqq = yf.Ticker("QQQ")
            qqq_hist = qqq.history(period="1d", interval="1m")
            
            if not qqq_hist.empty:
                context.qqq_price = float(qqq_hist['Close'].iloc[-1])
                qqq_open = float(qqq_hist['Open'].iloc[0])
                context.qqq_change_pct = (context.qqq_price - qqq_open) / qqq_open * 100
                
        except Exception as e:
            logger.warning(f"⚠️ QQQ data error: {e}")
        
        # VIX
        try:
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="1d", interval="1m")
            
            if not vix_hist.empty:
                context.vix_level = float(vix_hist['Close'].iloc[-1])
                
                # VIX trend
                if len(vix_hist) >= 30:
                    vix_30m_ago = float(vix_hist['Close'].iloc[-30])
                    vix_change = context.vix_level - vix_30m_ago
                    if vix_change > 0.5:
                        context.vix_trend = "RISING"
                    elif vix_change < -0.5:
                        context.vix_trend = "FALLING"
                    else:
                        context.vix_trend = "STABLE"
                        
        except Exception as e:
            logger.warning(f"⚠️ VIX data error: {e}")
        
        # Cache result
        self._cache = {
            'spy_price': context.spy_price,
            'spy_change_pct': context.spy_change_pct,
            'spy_trend_1h': context.spy_trend_1h,
            'spy_trend_1d': context.spy_trend_1d,
            'qqq_price': context.qqq_price,
            'qqq_change_pct': context.qqq_change_pct,
            'vix_level': context.vix_level,
            'vix_trend': context.vix_trend,
            'time_of_day': context.time_of_day,
            'minutes_to_close': context.minutes_to_close,
        }
        self._cache_time = datetime.now()
        
        return context
    
    def _get_time_of_day(self) -> TimeOfDay:
        """Determine current trading session."""
        now = datetime.now(ET)
        hour = now.hour
        minute = now.minute
        
        if hour < 9 or (hour == 9 and minute < 30):
            return TimeOfDay.PREMARKET
        elif hour == 9 and minute >= 30:
            return TimeOfDay.OPEN
        elif hour == 10 or (hour == 11 and minute < 30):
            return TimeOfDay.MORNING
        elif hour >= 11 and hour < 14:
            return TimeOfDay.MIDDAY
        elif hour == 14:
            return TimeOfDay.AFTERNOON
        elif hour >= 15 and hour < 16:
            return TimeOfDay.POWER_HOUR
        else:
            return TimeOfDay.AFTER_HOURS
    
    def _minutes_to_close(self) -> int:
        """Minutes until market close (4:00 PM ET)."""
        now = datetime.now(ET)
        close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        if now >= close:
            return 0
        
        return int((close - now).total_seconds() / 60)




