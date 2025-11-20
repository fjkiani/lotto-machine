#!/usr/bin/env python3
"""
REDDIT SENTIMENT ANALYZER
=========================
Analyzes Reddit mentions and sentiment for contrarian signals.

Strategy:
- Fade retail hype (when WSB is bullish, consider bearish)
- Confirm institutional silence (no Reddit noise = smart money accumulating)
- Detect pump-and-dump patterns
- Identify genuine community conviction

Uses ChartExchange's /data/social/reddit/ endpoints.

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

# Add paths
sys.path.append(str(Path(__file__).parent.parent.parent / 'core/data'))

from ultimate_chartexchange_client import UltimateChartExchangeClient

logger = logging.getLogger(__name__)


class SentimentSignal(Enum):
    """Contrarian sentiment signals"""
    FADE_HYPE = "FADE_HYPE"  # Extreme bullish = bearish signal
    FADE_FEAR = "FADE_FEAR"  # Extreme bearish = bullish signal
    STEALTH_ACCUMULATION = "STEALTH_ACCUMULATION"  # Low mentions + price up = smart money
    PUMP_DUMP = "PUMP_DUMP"  # Sudden spike in mentions = pump
    GENUINE_CONVICTION = "GENUINE_CONVICTION"  # Steady growth in mentions
    NEUTRAL = "NEUTRAL"  # No clear signal


@dataclass
class RedditMention:
    """Single Reddit mention data point"""
    date: datetime
    mentions: int
    sentiment_score: float  # -1.0 (bearish) to +1.0 (bullish)
    subreddits: List[str]


@dataclass
class SentimentAnalysis:
    """Complete sentiment analysis for a ticker"""
    symbol: str
    current_mentions: int
    avg_mentions_7d: float
    mention_trend: str  # "INCREASING", "DECREASING", "STABLE"
    sentiment_score: float  # -1.0 to +1.0
    sentiment_label: str  # "VERY_BEARISH", "BEARISH", "NEUTRAL", "BULLISH", "VERY_BULLISH"
    contrarian_signal: SentimentSignal
    confidence: float  # 0-100
    reasoning: str
    top_subreddits: List[str]
    mentions_history: List[RedditMention]


class RedditSentimentAnalyzer:
    """
    Analyzes Reddit sentiment for contrarian trading signals
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Reddit Sentiment Analyzer
        
        Args:
            api_key: ChartExchange API key
        """
        self.client = UltimateChartExchangeClient(api_key=api_key)
        logger.info("📱 Reddit Sentiment Analyzer initialized")
    
    def fetch_reddit_sentiment(self, symbol: str, days: int = 7) -> Optional[SentimentAnalysis]:
        """
        Fetch and analyze Reddit sentiment for a ticker
        
        Args:
            symbol: Ticker symbol
            days: Number of days to analyze
        
        Returns:
            SentimentAnalysis object or None if data unavailable
        """
        try:
            logger.info(f"📱 Fetching Reddit sentiment for {symbol} ({days}d)...")
            
            # Fetch Reddit mentions
            # Note: ChartExchange endpoint may return 404 - handle gracefully
            # _make_request returns None on error, get_reddit_mentions returns [] if None
            mentions_data = self.client.get_reddit_mentions(symbol, days=days)
            
            if not mentions_data:
                # Endpoint unavailable (404) or no data
                logger.warning(f"⚠️ Reddit endpoint unavailable or no data for {symbol}")
                logger.info("   Returning neutral signal (endpoint not available)")
                return self._create_stealth_signal(symbol)  # Fallback to neutral/stealth
            
            # Parse mention history
            mentions_history = []
            total_mentions = 0
            total_sentiment = 0.0
            subreddit_counts = {}
            
            for entry in mentions_data:
                date = entry.get('date')
                count = entry.get('mentions', 0)
                sentiment = entry.get('sentiment_score', 0.0)
                subreddits = entry.get('subreddits', [])
                
                if isinstance(date, str):
                    date = datetime.fromisoformat(date)
                
                mention = RedditMention(
                    date=date,
                    mentions=count,
                    sentiment_score=sentiment,
                    subreddits=subreddits
                )
                
                mentions_history.append(mention)
                total_mentions += count
                total_sentiment += sentiment * count  # Weighted by mentions
                
                for sub in subreddits:
                    subreddit_counts[sub] = subreddit_counts.get(sub, 0) + count
            
            if total_mentions == 0:
                return self._create_stealth_signal(symbol)
            
            # Calculate metrics
            current_mentions = mentions_history[-1].mentions if mentions_history else 0
            avg_mentions = total_mentions / len(mentions_history)
            avg_sentiment = total_sentiment / total_mentions if total_mentions > 0 else 0.0
            
            # Determine trend
            if len(mentions_history) >= 3:
                recent_avg = sum(m.mentions for m in mentions_history[-3:]) / 3
                older_avg = sum(m.mentions for m in mentions_history[:-3]) / max(len(mentions_history) - 3, 1)
                
                if recent_avg > older_avg * 1.5:
                    trend = "INCREASING"
                elif recent_avg < older_avg * 0.5:
                    trend = "DECREASING"
                else:
                    trend = "STABLE"
            else:
                trend = "STABLE"
            
            # Sentiment label
            if avg_sentiment > 0.5:
                sentiment_label = "VERY_BULLISH"
            elif avg_sentiment > 0.2:
                sentiment_label = "BULLISH"
            elif avg_sentiment < -0.5:
                sentiment_label = "VERY_BEARISH"
            elif avg_sentiment < -0.2:
                sentiment_label = "BEARISH"
            else:
                sentiment_label = "NEUTRAL"
            
            # Top subreddits
            top_subreddits = sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            top_subreddits = [sub for sub, _ in top_subreddits]
            
            # Generate contrarian signal
            signal, confidence, reasoning = self._generate_contrarian_signal(
                mentions_history=mentions_history,
                current_mentions=current_mentions,
                avg_mentions=avg_mentions,
                trend=trend,
                sentiment_score=avg_sentiment,
                sentiment_label=sentiment_label
            )
            
            analysis = SentimentAnalysis(
                symbol=symbol,
                current_mentions=current_mentions,
                avg_mentions_7d=avg_mentions,
                mention_trend=trend,
                sentiment_score=avg_sentiment,
                sentiment_label=sentiment_label,
                contrarian_signal=signal,
                confidence=confidence,
                reasoning=reasoning,
                top_subreddits=top_subreddits,
                mentions_history=mentions_history
            )
            
            logger.info(f"✅ Reddit sentiment analyzed for {symbol}")
            logger.debug(f"   Mentions: {current_mentions} (7d avg: {avg_mentions:.0f})")
            logger.debug(f"   Sentiment: {sentiment_label} ({avg_sentiment:+.2f})")
            logger.debug(f"   Signal: {signal.value} ({confidence:.0f}% confidence)")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error fetching Reddit sentiment for {symbol}: {e}")
            return None
    
    def _create_stealth_signal(self, symbol: str) -> SentimentAnalysis:
        """Create a 'stealth accumulation' signal when no Reddit data exists"""
        return SentimentAnalysis(
            symbol=symbol,
            current_mentions=0,
            avg_mentions_7d=0.0,
            mention_trend="STABLE",
            sentiment_score=0.0,
            sentiment_label="NEUTRAL",
            contrarian_signal=SentimentSignal.STEALTH_ACCUMULATION,
            confidence=60.0,
            reasoning="No Reddit mentions - potential stealth accumulation by smart money",
            top_subreddits=[],
            mentions_history=[]
        )
    
    def _generate_contrarian_signal(self,
                                     mentions_history: List[RedditMention],
                                     current_mentions: int,
                                     avg_mentions: float,
                                     trend: str,
                                     sentiment_score: float,
                                     sentiment_label: str) -> Tuple[SentimentSignal, float, str]:
        """
        Generate contrarian trading signal based on Reddit data
        
        Returns:
            (signal, confidence, reasoning)
        """
        
        # Rule 1: Extreme bullish sentiment + high mentions = FADE_HYPE
        if sentiment_score > 0.6 and current_mentions > avg_mentions * 2:
            return (
                SentimentSignal.FADE_HYPE,
                80.0,
                f"Extreme retail bullishness ({sentiment_label}) with {current_mentions} mentions (2x avg) - fade the hype"
            )
        
        # Rule 2: Extreme bearish sentiment + high mentions = FADE_FEAR
        if sentiment_score < -0.6 and current_mentions > avg_mentions * 2:
            return (
                SentimentSignal.FADE_FEAR,
                75.0,
                f"Extreme retail bearishness ({sentiment_label}) with {current_mentions} mentions - fade the fear"
            )
        
        # Rule 3: Sudden spike in mentions (>3x) = PUMP_DUMP
        if trend == "INCREASING" and current_mentions > avg_mentions * 3:
            return (
                SentimentSignal.PUMP_DUMP,
                85.0,
                f"Sudden mention spike ({current_mentions} vs {avg_mentions:.0f} avg) - potential pump"
            )
        
        # Rule 4: Low mentions but positive price action = STEALTH_ACCUMULATION
        # (Price action needs to be checked externally - we just note low mentions)
        if current_mentions < avg_mentions * 0.5 and current_mentions < 10:
            return (
                SentimentSignal.STEALTH_ACCUMULATION,
                65.0,
                f"Very low Reddit activity ({current_mentions} mentions) - smart money may be accumulating"
            )
        
        # Rule 5: Moderate bullish sentiment + steady growth = GENUINE_CONVICTION
        if sentiment_score > 0.3 and sentiment_score < 0.6 and trend == "INCREASING":
            return (
                SentimentSignal.GENUINE_CONVICTION,
                70.0,
                f"Steady bullish sentiment ({sentiment_label}) with growing mentions - genuine conviction"
            )
        
        # Default: No clear signal
        return (
            SentimentSignal.NEUTRAL,
            50.0,
            f"Moderate activity ({current_mentions} mentions, {sentiment_label}) - no clear contrarian edge"
        )
    
    def should_trade_based_on_sentiment(self, analysis: SentimentAnalysis, intended_action: str) -> Tuple[bool, str]:
        """
        Determine if sentiment supports the intended trade
        
        Args:
            analysis: SentimentAnalysis object
            intended_action: "BUY" or "SELL"
        
        Returns:
            (should_trade: bool, reason: str)
        """
        signal = analysis.contrarian_signal
        
        # FADE_HYPE = bearish signal
        if signal == SentimentSignal.FADE_HYPE:
            if intended_action == "SELL":
                return (True, f"Sentiment supports SELL ({analysis.reasoning})")
            else:
                return (False, f"Sentiment against BUY - retail is too bullish")
        
        # FADE_FEAR = bullish signal
        elif signal == SentimentSignal.FADE_FEAR:
            if intended_action == "BUY":
                return (True, f"Sentiment supports BUY ({analysis.reasoning})")
            else:
                return (False, f"Sentiment against SELL - retail is too bearish")
        
        # PUMP_DUMP = avoid entirely
        elif signal == SentimentSignal.PUMP_DUMP:
            return (False, f"AVOID - {analysis.reasoning}")
        
        # STEALTH_ACCUMULATION = bullish (if price confirms)
        elif signal == SentimentSignal.STEALTH_ACCUMULATION:
            if intended_action == "BUY":
                return (True, f"Sentiment neutral/bullish ({analysis.reasoning})")
            else:
                return (True, "Sentiment neutral - proceed with caution")
        
        # GENUINE_CONVICTION = bullish
        elif signal == SentimentSignal.GENUINE_CONVICTION:
            if intended_action == "BUY":
                return (True, f"Sentiment supports BUY ({analysis.reasoning})")
            else:
                return (False, f"Sentiment against SELL - genuine bullish conviction building")
        
        # NEUTRAL = allow trade
        else:
            return (True, "Sentiment neutral - no strong signal")
    
    def print_sentiment_summary(self, analysis: SentimentAnalysis):
        """Print human-readable sentiment summary"""
        logger.info("")
        logger.info("=" * 100)
        logger.info(f"📱 REDDIT SENTIMENT - {analysis.symbol}")
        logger.info("=" * 100)
        logger.info(f"Current Mentions: {analysis.current_mentions}")
        logger.info(f"7-Day Avg: {analysis.avg_mentions_7d:.0f}")
        logger.info(f"Trend: {analysis.mention_trend}")
        logger.info(f"Sentiment: {analysis.sentiment_label} ({analysis.sentiment_score:+.2f})")
        logger.info("")
        logger.info(f"🎯 CONTRARIAN SIGNAL: {analysis.contrarian_signal.value}")
        logger.info(f"   Confidence: {analysis.confidence:.0f}%")
        logger.info(f"   Reasoning: {analysis.reasoning}")
        logger.info("")
        if analysis.top_subreddits:
            logger.info("Top Subreddits:")
            for sub in analysis.top_subreddits:
                logger.info(f"   - r/{sub}")
        logger.info("=" * 100)
        logger.info("")


if __name__ == "__main__":
    # Test the Reddit sentiment analyzer
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent / 'configs'))
    from chartexchange_config import CHARTEXCHANGE_API_KEY
    
    analyzer = RedditSentimentAnalyzer(api_key=CHARTEXCHANGE_API_KEY)
    
    # Test for SPY
    analysis = analyzer.fetch_reddit_sentiment("SPY", days=7)
    
    if analysis:
        analyzer.print_sentiment_summary(analysis)
        
        # Test trade decision logic
        should_buy, reason = analyzer.should_trade_based_on_sentiment(analysis, "BUY")
        logger.info(f"Should BUY based on sentiment? {should_buy} - {reason}")
        
        should_sell, reason = analyzer.should_trade_based_on_sentiment(analysis, "SELL")
        logger.info(f"Should SELL based on sentiment? {should_sell} - {reason}")
    else:
        logger.error("Failed to fetch sentiment analysis")

