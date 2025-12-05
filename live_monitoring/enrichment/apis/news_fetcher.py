"""
NewsFetcher - lightweight news aggregation for narrative enrichment.

Phase A (quick win from manager's narrative plan):
- Integrate NewsAPI.org + Alpha Vantage NEWS_SENTIMENT
- Provide recent macro + ticker-specific headlines for Gemini prompts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class NewsFetcher:
    """
    Fetches recent news from multiple sources (NewsAPI + Alpha Vantage).

    Notes:
    - Keep this as a best-effort helper; if any source fails, return what we can.
    - Manager's full vision (SEC filings, transcripts) will live in separate modules.
    """

    def __init__(self, news_api_key: Optional[str] = None, alpha_vantage_key: Optional[str] = None) -> None:
        self.news_api_key = news_api_key
        self.alpha_vantage_key = alpha_vantage_key

        if not self.news_api_key and not self.alpha_vantage_key:
            logger.warning("NewsFetcher initialized with no API keys; will return empty results.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_market_news(self, lookback_hours: int = 6, max_items: int = 10) -> List[Dict]:
        """
        Fetch general market / macro news (Fed, inflation, SPY, QQQ, etc.).
        """
        articles: List[Dict] = []

        # Macro keywords tuned for regime / risk narrative
        keywords = ["Federal Reserve", "interest rates", "inflation", "SPY", "QQQ", "market selloff"]

        for kw in keywords:
            arts = self._fetch_from_newsapi(keyword=kw, lookback_hours=lookback_hours)
            articles.extend(arts)

        # Deduplicate by URL and trim
        return self._dedupe_and_trim(articles, max_items=max_items)

    def fetch_symbol_news(self, symbol: str, lookback_hours: int = 24, max_items: int = 10) -> List[Dict]:
        """
        Fetch symbol-specific news (ticker mention, sentiment).
        """
        articles: List[Dict] = []

        # NewsAPI for symbol
        articles.extend(self._fetch_from_newsapi(keyword=symbol, lookback_hours=lookback_hours))

        # Alpha Vantage sentiment if available
        articles.extend(self._fetch_from_alpha_vantage(symbol=symbol))

        return self._dedupe_and_trim(articles, max_items=max_items)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_from_newsapi(self, keyword: str, lookback_hours: int) -> List[Dict]:
        if not self.news_api_key:
            return []

        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": keyword,
                "from": (datetime.utcnow() - timedelta(hours=lookback_hours)).isoformat(timespec="seconds") + "Z",
                "sortBy": "publishedAt",
                "apiKey": self.news_api_key,
                "language": "en",
                "pageSize": 20,
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                logger.warning("NewsAPI error %s for keyword %s", resp.status_code, keyword)
                return []

            data = resp.json()
            raw_articles = data.get("articles", [])

            articles: List[Dict] = []
            for a in raw_articles:
                try:
                    articles.append(
                        {
                            "title": a.get("title", "") or "",
                            "url": a.get("url", "") or "",
                            "source": (a.get("source") or {}).get("name", ""),
                            "published_at": a.get("publishedAt", ""),
                            "description": a.get("description", "") or "",
                            "provider": "newsapi",
                        }
                    )
                except Exception:
                    continue

            return articles
        except Exception as e:
            logger.error("Error fetching from NewsAPI for %s: %s", keyword, e)
            return []

    def _fetch_from_alpha_vantage(self, symbol: str) -> List[Dict]:
        if not self.alpha_vantage_key:
            return []

        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "apikey": self.alpha_vantage_key,
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                logger.warning("Alpha Vantage NEWS_SENTIMENT error %s for %s", resp.status_code, symbol)
                return []

            data = resp.json()
            feed = data.get("feed", []) or []

            articles: List[Dict] = []
            for item in feed:
                try:
                    articles.append(
                        {
                            "title": item.get("title", "") or "",
                            "url": item.get("url", "") or "",
                            "source": item.get("source", "") or "",
                            "published_at": item.get("time_published", ""),
                            "description": item.get("summary", "") or "",
                            "sentiment_score": float(item.get("overall_sentiment_score", 0.0) or 0.0),
                            "sentiment_label": item.get("overall_sentiment_label", ""),
                            "provider": "alpha_vantage",
                        }
                    )
                except Exception:
                    continue

            return articles
        except Exception as e:
            logger.error("Error fetching Alpha Vantage sentiment for %s: %s", symbol, e)
            return []

    @staticmethod
    def _dedupe_and_trim(articles: List[Dict], max_items: int) -> List[Dict]:
        seen: set = set()
        unique: List[Dict] = []
        for a in articles:
            url = a.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            unique.append(a)
            if len(unique) >= max_items:
                break
        return unique


def _demo() -> None:
    """
    Simple CLI demo:
        python -m live_monitoring.enrichment.apis.news_fetcher
    Requires NEWS_API_KEY and/or ALPHA_VANTAGE_KEY env vars to actually pull data.
    """
    import os

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    nf = NewsFetcher(
        news_api_key=os.getenv("NEWS_API_KEY"),
        alpha_vantage_key=os.getenv("ALPHA_VANTAGE_KEY"),
    )

    print("=" * 80)
    print("📰 TESTING NewsFetcher (market news)")
    print("=" * 80)
    market_news = nf.fetch_market_news()
    print(f"Got {len(market_news)} market articles")
    for a in market_news[:5]:
        print(f"- [{a.get('source')}] {a.get('title')}")

    print("\n" + "=" * 80)
    print("📰 TESTING NewsFetcher (symbol news: SPY)")
    print("=" * 80)
    spy_news = nf.fetch_symbol_news("SPY")
    print(f"Got {len(spy_news)} SPY articles")
    for a in spy_news[:5]:
        print(f"- [{a.get('source')}] {a.get('title')}")


if __name__ == "__main__":
    _demo()


