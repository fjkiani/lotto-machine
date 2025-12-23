"""
📰 MARKET CONTEXT DETECTOR
Analyzes news + price action to understand market regime.

PROVIDES:
1. Market direction (UP/DOWN/CHOP)
2. News sentiment analysis
3. Regime classification
4. Signal filtering based on context

This is the BRAIN that tells other detectors whether to be bullish or bearish.

Author: Zo (Alpha's AI)
"""

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple
import pandas as pd
import yfinance as yf

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from dotenv import load_dotenv
load_dotenv()


@dataclass
class MarketContext:
    """Current market context and regime"""
    date: str
    
    # Price action
    spy_change_pct: float
    qqq_change_pct: float
    vix_level: float
    
    # Direction
    direction: str  # UP, DOWN, CHOP
    trend_strength: float  # 0-100
    
    # News sentiment
    news_sentiment: str  # BULLISH, BEARISH, NEUTRAL
    key_headlines: List[str]
    
    # Regime
    regime: str  # TRENDING_UP, TRENDING_DOWN, CHOPPY, BREAKOUT, BREAKDOWN
    
    # Trading recommendations
    favor_longs: bool
    favor_shorts: bool
    reduce_size: bool
    avoid_trading: bool
    
    # Reasoning
    reasoning: str


class MarketContextDetector:
    """
    Analyzes market to determine context for signal filtering.
    
    Uses:
    - Price action (SPY, QQQ, VIX)
    - News sentiment (RapidAPI)
    - Technical regime (trend, volatility)
    """
    
    # Thresholds
    TREND_THRESHOLD = 0.30      # % move to consider trending
    CHOP_THRESHOLD = 0.20       # % move below this = chop
    HIGH_VIX = 25.0             # VIX above this = high vol
    LOW_VIX = 15.0              # VIX below this = low vol
    
    def __init__(self):
        self.news_client = None
        try:
            from core.data.rapidapi_news_client import RapidAPINewsClient
            self.news_client = RapidAPINewsClient()
        except Exception as e:
            print(f"   ⚠️ News client unavailable: {e}")
    
    def analyze_market(self, date: str = None) -> MarketContext:
        """
        Analyze market context for a given date.
        
        Args:
            date: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            MarketContext with all analysis
        """
        date = date or datetime.now().strftime('%Y-%m-%d')
        
        # Get price data
        spy_change, qqq_change, vix, spy_data = self._get_price_action()
        
        # Determine direction
        direction, trend_strength = self._analyze_direction(spy_change, qqq_change, spy_data)
        
        # Get news sentiment
        news_sentiment, headlines = self._analyze_news()
        
        # Determine regime
        regime = self._determine_regime(direction, trend_strength, vix, news_sentiment)
        
        # Trading recommendations
        favor_longs, favor_shorts, reduce_size, avoid_trading = self._get_recommendations(
            direction, trend_strength, vix, news_sentiment
        )
        
        # Build reasoning
        reasoning = self._build_reasoning(
            spy_change, qqq_change, vix, direction, news_sentiment, headlines
        )
        
        return MarketContext(
            date=date,
            spy_change_pct=spy_change,
            qqq_change_pct=qqq_change,
            vix_level=vix,
            direction=direction,
            trend_strength=trend_strength,
            news_sentiment=news_sentiment,
            key_headlines=headlines,
            regime=regime,
            favor_longs=favor_longs,
            favor_shorts=favor_shorts,
            reduce_size=reduce_size,
            avoid_trading=avoid_trading,
            reasoning=reasoning
        )
    
    def _get_price_action(self) -> Tuple[float, float, float, pd.DataFrame]:
        """Get today's price action"""
        try:
            spy = yf.Ticker('SPY')
            qqq = yf.Ticker('QQQ')
            vix_ticker = yf.Ticker('^VIX')
            
            spy_data = spy.history(period='2d', interval='1d')
            qqq_data = qqq.history(period='2d', interval='1d')
            vix_data = vix_ticker.history(period='1d')
            
            spy_change = 0.0
            qqq_change = 0.0
            vix = 20.0  # Default
            
            if len(spy_data) >= 2:
                spy_change = (spy_data['Close'].iloc[-1] - spy_data['Close'].iloc[-2]) / spy_data['Close'].iloc[-2] * 100
            
            if len(qqq_data) >= 2:
                qqq_change = (qqq_data['Close'].iloc[-1] - qqq_data['Close'].iloc[-2]) / qqq_data['Close'].iloc[-2] * 100
            
            if not vix_data.empty:
                vix = vix_data['Close'].iloc[-1]
            
            # Get intraday for more detail
            spy_intra = spy.history(period='1d', interval='5m')
            
            return spy_change, qqq_change, vix, spy_intra
            
        except Exception as e:
            print(f"   ⚠️ Price data error: {e}")
            return 0.0, 0.0, 20.0, pd.DataFrame()
    
    def _analyze_direction(
        self, 
        spy_change: float, 
        qqq_change: float,
        spy_data: pd.DataFrame
    ) -> Tuple[str, float]:
        """Determine market direction"""
        
        avg_change = (spy_change + qqq_change) / 2
        
        # Strong trend
        if avg_change >= self.TREND_THRESHOLD:
            strength = min(100, 50 + avg_change * 30)
            return 'UP', strength
        elif avg_change <= -self.TREND_THRESHOLD:
            strength = min(100, 50 + abs(avg_change) * 30)
            return 'DOWN', strength
        else:
            # Check intraday volatility for chop detection
            if not spy_data.empty:
                intraday_range = (spy_data['High'].max() - spy_data['Low'].min()) / spy_data['Open'].iloc[0] * 100
                if intraday_range > 1.0 and abs(avg_change) < 0.3:
                    return 'CHOP', 70  # High range but small close = chop
            
            return 'CHOP', 50
    
    def _analyze_news(self) -> Tuple[str, List[str]]:
        """Analyze news sentiment"""
        
        headlines = []
        bullish_count = 0
        bearish_count = 0
        
        if not self.news_client:
            return 'NEUTRAL', headlines
        
        try:
            for ticker in ['SPY', 'QQQ']:
                news = self.news_client.get_credible_news(ticker)
                if news:
                    for article in news[:5]:
                        headlines.append(f"[{article.source}] {article.title}")
                        
                        # Simple sentiment analysis
                        title_lower = article.title.lower()
                        
                        bullish_words = ['rally', 'surge', 'jump', 'gains', 'bullish', 'rise', 'up', 'record', 'high']
                        bearish_words = ['drop', 'fall', 'crash', 'selloff', 'bearish', 'down', 'low', 'fear', 'crisis']
                        
                        for word in bullish_words:
                            if word in title_lower:
                                bullish_count += 1
                                break
                        
                        for word in bearish_words:
                            if word in title_lower:
                                bearish_count += 1
                                break
            
            if bullish_count > bearish_count + 1:
                return 'BULLISH', headlines
            elif bearish_count > bullish_count + 1:
                return 'BEARISH', headlines
            else:
                return 'NEUTRAL', headlines
                
        except Exception as e:
            print(f"   ⚠️ News analysis error: {e}")
            return 'NEUTRAL', headlines
    
    def _determine_regime(
        self,
        direction: str,
        trend_strength: float,
        vix: float,
        news_sentiment: str
    ) -> str:
        """Determine market regime"""
        
        # High conviction trending
        if direction == 'UP' and trend_strength > 70:
            return 'TRENDING_UP'
        elif direction == 'DOWN' and trend_strength > 70:
            return 'TRENDING_DOWN'
        
        # Breakout/Breakdown
        if direction == 'UP' and news_sentiment == 'BULLISH':
            return 'BREAKOUT'
        elif direction == 'DOWN' and news_sentiment == 'BEARISH':
            return 'BREAKDOWN'
        
        # Choppy
        if direction == 'CHOP' or trend_strength < 50:
            return 'CHOPPY'
        
        # Default to direction-based
        if direction == 'UP':
            return 'TRENDING_UP'
        elif direction == 'DOWN':
            return 'TRENDING_DOWN'
        else:
            return 'CHOPPY'
    
    def _get_recommendations(
        self,
        direction: str,
        trend_strength: float,
        vix: float,
        news_sentiment: str
    ) -> Tuple[bool, bool, bool, bool]:
        """Get trading recommendations"""
        
        favor_longs = False
        favor_shorts = False
        reduce_size = False
        avoid_trading = False
        
        # Direction-based
        if direction == 'UP':
            favor_longs = True
        elif direction == 'DOWN':
            favor_shorts = True
        
        # Sentiment confirmation
        if news_sentiment == 'BULLISH':
            favor_longs = True
            favor_shorts = False
        elif news_sentiment == 'BEARISH':
            favor_shorts = True
            favor_longs = False
        
        # High VIX = reduce size
        if vix > self.HIGH_VIX:
            reduce_size = True
        
        # Chop = avoid trading
        if direction == 'CHOP' and trend_strength < 40:
            avoid_trading = True
        
        return favor_longs, favor_shorts, reduce_size, avoid_trading
    
    def _build_reasoning(
        self,
        spy_change: float,
        qqq_change: float,
        vix: float,
        direction: str,
        news_sentiment: str,
        headlines: List[str]
    ) -> str:
        """Build human-readable reasoning"""
        
        parts = []
        
        # Price action
        if spy_change > 0:
            parts.append(f"SPY rallied +{spy_change:.2f}%")
        else:
            parts.append(f"SPY declined {spy_change:.2f}%")
        
        if qqq_change > 0:
            parts.append(f"QQQ up +{qqq_change:.2f}%")
        else:
            parts.append(f"QQQ down {qqq_change:.2f}%")
        
        # VIX
        if vix > self.HIGH_VIX:
            parts.append(f"VIX elevated at {vix:.1f}")
        elif vix < self.LOW_VIX:
            parts.append(f"VIX low at {vix:.1f} (complacency)")
        
        # News
        if headlines:
            parts.append(f"Key news: {headlines[0][:60]}...")
        
        # Direction
        if direction == 'UP':
            parts.append("Market in UPTREND - favor longs")
        elif direction == 'DOWN':
            parts.append("Market in DOWNTREND - favor shorts")
        else:
            parts.append("Market CHOPPY - reduce trading")
        
        return " | ".join(parts)
    
    def print_context(self, context: MarketContext):
        """Print formatted market context"""
        
        print(f"\n{'='*70}")
        print(f"📊 MARKET CONTEXT - {context.date}")
        print(f"{'='*70}")
        
        # Price action
        spy_emoji = "🟢" if context.spy_change_pct > 0 else "🔴"
        qqq_emoji = "🟢" if context.qqq_change_pct > 0 else "🔴"
        
        print(f"\n📈 PRICE ACTION:")
        print(f"   {spy_emoji} SPY: {context.spy_change_pct:+.2f}%")
        print(f"   {qqq_emoji} QQQ: {context.qqq_change_pct:+.2f}%")
        print(f"   📊 VIX: {context.vix_level:.1f}")
        
        # Direction
        dir_emoji = "⬆️" if context.direction == 'UP' else "⬇️" if context.direction == 'DOWN' else "↔️"
        print(f"\n🎯 DIRECTION: {dir_emoji} {context.direction} (Strength: {context.trend_strength:.0f}%)")
        print(f"   Regime: {context.regime}")
        
        # News
        print(f"\n📰 NEWS SENTIMENT: {context.news_sentiment}")
        for headline in context.key_headlines[:3]:
            print(f"   • {headline[:70]}")
        
        # Recommendations
        print(f"\n💡 TRADING RECOMMENDATIONS:")
        if context.favor_longs:
            print(f"   ✅ Favor LONG signals")
        if context.favor_shorts:
            print(f"   ✅ Favor SHORT signals")
        if context.reduce_size:
            print(f"   ⚠️ Reduce position size (high VIX)")
        if context.avoid_trading:
            print(f"   ❌ AVOID TRADING (choppy)")
        
        print(f"\n📋 REASONING: {context.reasoning}")


# Standalone test
if __name__ == "__main__":
    detector = MarketContextDetector()
    context = detector.analyze_market()
    detector.print_context(context)

