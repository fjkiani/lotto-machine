#!/usr/bin/env python3
"""
FREE News Fetcher - No API keys required!

Uses RSS feeds and free public sources to get market news:
- Yahoo Finance RSS
- Google Finance RSS
- MarketWatch RSS
- Reuters RSS
- CNBC RSS

This allows us to exploit news 24/7 without needing paid APIs!
"""

import logging
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Standardized news article"""
    title: str
    url: str
    source: str
    published: str
    summary: str
    sentiment: Optional[str] = None  # BULLISH, BEARISH, NEUTRAL


class FreeNewsFetcher:
    """
    Fetches news from FREE RSS feeds - no API keys needed!
    
    Sources:
    - Yahoo Finance
    - Google News (Finance)
    - MarketWatch
    - Reuters
    - CNBC
    """
    
    RSS_FEEDS = {
        "yahoo_finance": "https://finance.yahoo.com/rss/topstories",
        "google_finance": "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
        "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "cnbc": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "reuters_business": "https://www.rssfeeds.com/reuters/business",
    }
    
    # Keywords for sentiment analysis
    BULLISH_KEYWORDS = [
        "rally", "surge", "jump", "gain", "rise", "bull", "bullish", "record high",
        "all-time high", "breakthrough", "soar", "climb", "advance", "optimism",
        "recovery", "boom", "upbeat", "positive", "momentum", "buy", "upgrade"
    ]
    
    BEARISH_KEYWORDS = [
        "crash", "plunge", "drop", "fall", "decline", "bear", "bearish", "selloff",
        "sell-off", "tumble", "slump", "fear", "panic", "recession", "downturn",
        "risk-off", "downgrade", "concern", "warning", "collapse", "crisis"
    ]
    
    def __init__(self):
        self.cache = {}
        self.cache_time = None
        self.cache_ttl = 300  # 5 minutes
    
    def fetch_all_news(self, max_per_source: int = 10) -> List[NewsArticle]:
        """Fetch news from all RSS feeds"""
        # Check cache
        if self._is_cache_valid():
            return self.cache.get('all_news', [])
        
        all_articles = []
        
        for source_name, feed_url in self.RSS_FEEDS.items():
            try:
                articles = self._fetch_rss_feed(feed_url, source_name, max_per_source)
                all_articles.extend(articles)
            except Exception as e:
                logger.warning(f"Failed to fetch {source_name}: {e}")
        
        # Sort by recency (newest first)
        all_articles.sort(key=lambda x: x.published, reverse=True)
        
        # Cache results
        self.cache['all_news'] = all_articles
        self.cache_time = datetime.now()
        
        return all_articles
    
    def fetch_ticker_news(self, ticker: str, max_articles: int = 20) -> List[NewsArticle]:
        """Fetch news specific to a ticker"""
        # Use Google News search for ticker
        search_url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        
        try:
            articles = self._fetch_rss_feed(search_url, f"google_{ticker}", max_articles)
            return articles
        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return []
    
    def get_market_sentiment(self) -> Dict:
        """
        Analyze overall market sentiment from recent news
        
        Returns:
        {
            "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
            "bullish_count": int,
            "bearish_count": int,
            "total_articles": int,
            "top_bullish_headlines": [...],
            "top_bearish_headlines": [...],
            "confidence": float
        }
        """
        articles = self.fetch_all_news(max_per_source=15)
        
        bullish_articles = []
        bearish_articles = []
        
        for article in articles:
            title_lower = article.title.lower()
            summary_lower = article.summary.lower() if article.summary else ""
            combined = title_lower + " " + summary_lower
            
            bullish_score = sum(1 for kw in self.BULLISH_KEYWORDS if kw in combined)
            bearish_score = sum(1 for kw in self.BEARISH_KEYWORDS if kw in combined)
            
            if bullish_score > bearish_score:
                article.sentiment = "BULLISH"
                bullish_articles.append(article)
            elif bearish_score > bullish_score:
                article.sentiment = "BEARISH"
                bearish_articles.append(article)
            else:
                article.sentiment = "NEUTRAL"
        
        total = len(articles)
        bullish_pct = len(bullish_articles) / total * 100 if total > 0 else 0
        bearish_pct = len(bearish_articles) / total * 100 if total > 0 else 0
        
        # Determine overall sentiment
        if bullish_pct > bearish_pct + 15:
            overall = "BULLISH"
            confidence = min((bullish_pct - bearish_pct) / 50, 1.0)
        elif bearish_pct > bullish_pct + 15:
            overall = "BEARISH"
            confidence = min((bearish_pct - bullish_pct) / 50, 1.0)
        else:
            overall = "NEUTRAL"
            confidence = 0.5
        
        return {
            "sentiment": overall,
            "bullish_count": len(bullish_articles),
            "bearish_count": len(bearish_articles),
            "neutral_count": total - len(bullish_articles) - len(bearish_articles),
            "total_articles": total,
            "bullish_pct": bullish_pct,
            "bearish_pct": bearish_pct,
            "confidence": confidence,
            "top_bullish_headlines": [a.title for a in bullish_articles[:5]],
            "top_bearish_headlines": [a.title for a in bearish_articles[:5]],
        }
    
    def get_ticker_sentiment(self, ticker: str) -> Dict:
        """Get sentiment for a specific ticker"""
        articles = self.fetch_ticker_news(ticker, max_articles=20)
        
        bullish = 0
        bearish = 0
        headlines = {"bullish": [], "bearish": [], "neutral": []}
        
        for article in articles:
            title_lower = article.title.lower()
            
            bullish_score = sum(1 for kw in self.BULLISH_KEYWORDS if kw in title_lower)
            bearish_score = sum(1 for kw in self.BEARISH_KEYWORDS if kw in title_lower)
            
            if bullish_score > bearish_score:
                bullish += 1
                headlines["bullish"].append(article.title)
            elif bearish_score > bullish_score:
                bearish += 1
                headlines["bearish"].append(article.title)
            else:
                headlines["neutral"].append(article.title)
        
        total = len(articles)
        if total == 0:
            return {"sentiment": "NEUTRAL", "confidence": 0, "reason": "No news found"}
        
        bullish_pct = bullish / total * 100
        bearish_pct = bearish / total * 100
        
        if bullish_pct > bearish_pct + 20:
            sentiment = "BULLISH"
        elif bearish_pct > bullish_pct + 20:
            sentiment = "BEARISH"
        else:
            sentiment = "NEUTRAL"
        
        return {
            "ticker": ticker,
            "sentiment": sentiment,
            "bullish_count": bullish,
            "bearish_count": bearish,
            "total_articles": total,
            "confidence": abs(bullish_pct - bearish_pct) / 100,
            "headlines": headlines
        }
    
    def _fetch_rss_feed(self, url: str, source_name: str, max_items: int) -> List[NewsArticle]:
        """Fetch and parse RSS feed"""
        try:
            feed = feedparser.parse(url)
            
            articles = []
            for entry in feed.entries[:max_items]:
                try:
                    # Parse publication date
                    pub_date = entry.get('published', entry.get('updated', ''))
                    
                    article = NewsArticle(
                        title=entry.get('title', 'No title'),
                        url=entry.get('link', ''),
                        source=source_name,
                        published=pub_date,
                        summary=entry.get('summary', entry.get('description', ''))[:500]
                    )
                    articles.append(article)
                except Exception as e:
                    logger.debug(f"Error parsing entry: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {e}")
            return []
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if not self.cache_time:
            return False
        return (datetime.now() - self.cache_time).total_seconds() < self.cache_ttl


def _demo():
    """Demo the free news fetcher"""
    import json
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("=" * 80)
    print("📰 FREE NEWS FETCHER - No API Keys Required!")
    print("=" * 80)
    
    fetcher = FreeNewsFetcher()
    
    # Get market sentiment
    print("\n🎯 MARKET SENTIMENT ANALYSIS:")
    print("-" * 40)
    sentiment = fetcher.get_market_sentiment()
    
    print(f"   Overall Sentiment: {sentiment['sentiment']}")
    print(f"   Confidence: {sentiment['confidence']:.0%}")
    print(f"   Total Articles: {sentiment['total_articles']}")
    print(f"   Bullish: {sentiment['bullish_count']} ({sentiment['bullish_pct']:.1f}%)")
    print(f"   Bearish: {sentiment['bearish_count']} ({sentiment['bearish_pct']:.1f}%)")
    
    if sentiment['top_bullish_headlines']:
        print("\n   📈 TOP BULLISH HEADLINES:")
        for h in sentiment['top_bullish_headlines'][:3]:
            print(f"      • {h[:80]}...")
    
    if sentiment['top_bearish_headlines']:
        print("\n   📉 TOP BEARISH HEADLINES:")
        for h in sentiment['top_bearish_headlines'][:3]:
            print(f"      • {h[:80]}...")
    
    # Get SPY specific sentiment
    print("\n" + "=" * 80)
    print("📊 SPY-SPECIFIC SENTIMENT:")
    print("-" * 40)
    spy_sentiment = fetcher.get_ticker_sentiment("SPY")
    
    print(f"   Sentiment: {spy_sentiment['sentiment']}")
    print(f"   Confidence: {spy_sentiment.get('confidence', 0):.0%}")
    print(f"   Articles Found: {spy_sentiment['total_articles']}")
    
    if spy_sentiment.get('headlines', {}).get('bullish'):
        print("\n   📈 Bullish Headlines:")
        for h in spy_sentiment['headlines']['bullish'][:2]:
            print(f"      • {h[:70]}...")
    
    if spy_sentiment.get('headlines', {}).get('bearish'):
        print("\n   📉 Bearish Headlines:")
        for h in spy_sentiment['headlines']['bearish'][:2]:
            print(f"      • {h[:70]}...")
    
    print("\n" + "=" * 80)
    print("✅ FREE NEWS FETCHER WORKING!")
    print("=" * 80)


if __name__ == "__main__":
    _demo()



