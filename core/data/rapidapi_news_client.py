#!/usr/bin/env python3
"""
📰 RapidAPI News Client - Yahoo Finance 15

Fetches real-time market news for narrative analysis.
Tested and validated endpoints.

GOLD MINE DATA:
- 50 articles per request
- Headlines + summaries
- Source credibility
- Ticker mentions
- Timestamps
"""

import os
import sys
import requests
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

# Add parent paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@dataclass
class NewsArticle:
    """News article from RapidAPI"""
    url: str
    title: str
    text: str
    source: str
    article_type: str
    tickers: List[str]
    time: str
    ago: str
    img_url: Optional[str] = None
    
    @property
    def is_recent(self) -> bool:
        """Check if article is from last 4 hours"""
        return any(x in self.ago.lower() for x in ['minute', '1 hour', '2 hour', '3 hour', '4 hour'])
    
    @property
    def credibility_score(self) -> float:
        """Score source credibility (0-1)"""
        high_credibility = ['Reuters', 'Bloomberg', 'CNBC', 'Wall Street Journal', 'Financial Times']
        medium_credibility = ['Seeking Alpha', 'Investopedia', 'MarketWatch', 'Yahoo Finance', 'Barron\'s']
        
        source_lower = self.source.lower()
        for s in high_credibility:
            if s.lower() in source_lower:
                return 1.0
        for s in medium_credibility:
            if s.lower() in source_lower:
                return 0.7
        return 0.4


class RapidAPINewsClient:
    """
    Client for Yahoo Finance 15 RapidAPI
    
    Primary endpoint: /api/v2/markets/news
    """
    
    # Credible sources for filtering
    CREDIBLE_SOURCES = [
        'Reuters', 'Bloomberg', 'CNBC', 'Wall Street Journal', 
        'Financial Times', 'Seeking Alpha', 'Investopedia', 
        'MarketWatch', 'Yahoo Finance', 'Barron\'s', 'FX Empire'
    ]
    
    def __init__(self, api_key: str = None):
        """
        Initialize the news client.
        
        Args:
            api_key: RapidAPI key (defaults to env var)
        """
        self.api_key = api_key or os.getenv('YAHOO_RAPIDAPI_KEY')
        self.host = os.getenv('YAHOO_RAPIDAPI_HOST', 'yahoo-finance15.p.rapidapi.com')
        self.base_url = f"https://{self.host}/api"
        
        if not self.api_key:
            print("⚠️  YAHOO_RAPIDAPI_KEY not set in environment")
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated request to RapidAPI"""
        if not self.api_key:
            return None
            
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ RapidAPI error: {e}")
            return None
    
    def fetch_news(self, ticker: str, news_type: str = "ALL") -> List[NewsArticle]:
        """
        Fetch latest news for a ticker.
        
        Args:
            ticker: Stock symbol (e.g., 'SPY', 'AAPL')
            news_type: Type of news ('ALL', 'VIDEO', etc.)
            
        Returns:
            List of NewsArticle objects
        """
        data = self._make_request(
            "v2/markets/news",
            params={"ticker": ticker, "type": news_type}
        )
        
        if not data or 'body' not in data:
            return []
        
        articles = []
        for item in data['body']:
            try:
                article = NewsArticle(
                    url=item.get('url', ''),
                    title=item.get('title', ''),
                    text=item.get('text', ''),
                    source=item.get('source', 'Unknown'),
                    article_type=item.get('type', 'Article'),
                    tickers=[t.replace('#', '') for t in item.get('tickers', [])],
                    time=item.get('time', ''),
                    ago=item.get('ago', ''),
                    img_url=item.get('img', None)
                )
                articles.append(article)
            except Exception as e:
                print(f"⚠️  Error parsing article: {e}")
                continue
        
        return articles
    
    def get_recent_news(self, ticker: str, hours: int = 4) -> List[NewsArticle]:
        """
        Get news from last N hours.
        
        Args:
            ticker: Stock symbol
            hours: Number of hours to look back
            
        Returns:
            List of recent NewsArticle objects
        """
        all_news = self.fetch_news(ticker)
        
        def is_within_hours(ago_str: str, max_hours: int) -> bool:
            ago_lower = ago_str.lower()
            if 'minute' in ago_lower:
                return True
            if 'hour' in ago_lower:
                # Extract number
                try:
                    num = int(''.join(filter(str.isdigit, ago_lower.split('hour')[0])))
                    return num <= max_hours
                except:
                    return True
            return False
        
        return [n for n in all_news if is_within_hours(n.ago, hours)]
    
    def get_credible_news(self, ticker: str, hours: int = 4) -> List[NewsArticle]:
        """
        Get recent news from credible sources only.
        
        Args:
            ticker: Stock symbol
            hours: Number of hours to look back
            
        Returns:
            List of credible NewsArticle objects sorted by credibility
        """
        recent = self.get_recent_news(ticker, hours)
        
        # Filter by credibility
        credible = [n for n in recent if n.credibility_score >= 0.7]
        
        # Sort by credibility (highest first)
        credible.sort(key=lambda x: x.credibility_score, reverse=True)
        
        return credible
    
    def get_headlines_summary(self, ticker: str, limit: int = 10) -> str:
        """
        Get formatted summary of recent headlines for LLM context.
        
        Args:
            ticker: Stock symbol
            limit: Max headlines to include
            
        Returns:
            Formatted string of headlines
        """
        credible = self.get_credible_news(ticker)[:limit]
        
        if not credible:
            return f"No recent credible news found for {ticker}"
        
        lines = [f"📰 RECENT NEWS FOR {ticker} ({len(credible)} articles):", ""]
        
        for i, article in enumerate(credible, 1):
            lines.append(f"{i}. [{article.source}] ({article.ago})")
            lines.append(f"   {article.title}")
            lines.append(f"   {article.text[:150]}...")
            lines.append("")
        
        return "\n".join(lines)
    
    def detect_sentiment_divergence(
        self, 
        ticker: str, 
        signal_bias: str
    ) -> Optional[Dict]:
        """
        Check if news sentiment diverges from signal bias.
        
        Args:
            ticker: Stock symbol
            signal_bias: 'BULLISH' or 'BEARISH'
            
        Returns:
            Dict with divergence info or None if aligned
        """
        news = self.get_credible_news(ticker, hours=2)
        
        if not news:
            return None
        
        # Simple keyword-based sentiment
        bullish_words = ['rally', 'surge', 'gain', 'rise', 'up', 'bullish', 'record', 'high']
        bearish_words = ['drop', 'fall', 'decline', 'plunge', 'down', 'bearish', 'sell', 'crash']
        
        bullish_count = 0
        bearish_count = 0
        
        for article in news:
            text = (article.title + " " + article.text).lower()
            bullish_count += sum(1 for w in bullish_words if w in text)
            bearish_count += sum(1 for w in bearish_words if w in text)
        
        total = bullish_count + bearish_count
        if total == 0:
            return None
        
        news_sentiment = 'BULLISH' if bullish_count > bearish_count else 'BEARISH'
        confidence = max(bullish_count, bearish_count) / total
        
        if news_sentiment != signal_bias and confidence > 0.6:
            return {
                'divergence': True,
                'signal_bias': signal_bias,
                'news_sentiment': news_sentiment,
                'confidence': confidence,
                'bullish_score': bullish_count,
                'bearish_score': bearish_count,
                'headline_sample': news[0].title if news else None
            }
        
        return None


# Standalone test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 70)
    print("📰 RAPIDAPI NEWS CLIENT TEST")
    print("=" * 70)
    
    # Use the hardcoded key for testing (should be in env)
    api_key = os.getenv('YAHOO_RAPIDAPI_KEY') or "9f107deaabmsh2efbc3559ddca05p17f1abjsn271e6df32f7c"
    
    client = RapidAPINewsClient(api_key=api_key)
    
    for ticker in ['SPY', 'QQQ']:
        print(f"\n📊 {ticker} NEWS:")
        print("-" * 50)
        
        # Fetch all news
        all_news = client.fetch_news(ticker)
        print(f"Total articles: {len(all_news)}")
        
        # Fetch credible news
        credible = client.get_credible_news(ticker, hours=4)
        print(f"Credible (last 4h): {len(credible)}")
        
        # Show top 3 headlines
        if credible:
            print("\n📰 Top Headlines:")
            for i, article in enumerate(credible[:3], 1):
                print(f"\n{i}. [{article.source}] ({article.ago})")
                print(f"   📌 {article.title}")
                print(f"   💬 {article.text[:100]}...")
                print(f"   📊 Credibility: {article.credibility_score:.0%}")
        
        # Test divergence detection
        print("\n🔄 Testing divergence detection...")
        divergence = client.detect_sentiment_divergence(ticker, "BULLISH")
        if divergence:
            print(f"   ⚠️ DIVERGENCE: Signal BULLISH but news is {divergence['news_sentiment']}")
        else:
            print(f"   ✅ No significant divergence detected")
    
    print("\n" + "=" * 70)
    print("✅ RapidAPI News Client test complete!")
    print("=" * 70)

