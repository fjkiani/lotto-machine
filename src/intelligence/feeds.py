"""
Data Feed Manager
Handles all data sources from Alpha's blueprint

A. News/Headlines: Tavily API, RSS feeds, Twitter/X
B. Markets/Price: Broker feeds, Yahoo Finance, Options dashboards
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import aiohttp
import feedparser
import json

logger = logging.getLogger(__name__)

class DataFeedManager:
    """
    Manages all data feeds for real-time intelligence
    
    Sources:
    - Tavily API for rapid financial news
    - RSS/Atom feeds (CNBC, Reuters, Bloomberg, Yahoo Finance)
    - Twitter/X search APIs
    - Broker feeds (Interactive Brokers, Alpaca, TD Ameritrade)
    - Yahoo Finance API (backup)
    - Options flow dashboards (Barchart, TradingView)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # API keys and endpoints
        self.tavily_api_key = config.get('tavily_api_key')
        self.tavily_endpoint = config.get('tavily_endpoint', 'https://api.tavily.com/search')
        
        self.twitter_bearer_token = config.get('twitter_bearer_token')
        self.twitter_endpoint = config.get('twitter_endpoint', 'https://api.twitter.com/2/tweets/search/recent')
        
        # Broker API configs
        self.broker_configs = config.get('brokers', {})
        
        # RSS feed URLs
        self.rss_feeds = {
            'cnbc': 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114',
            'reuters': 'https://feeds.reuters.com/reuters/businessNews',
            'bloomberg': 'https://feeds.bloomberg.com/markets/news.rss',
            'yahoo_finance': 'https://feeds.finance.yahoo.com/rss/2.0/headline',
            'marketwatch': 'https://feeds.marketwatch.com/marketwatch/topstories/',
            'seeking_alpha': 'https://seekingalpha.com/api/sa/combined/feed.xml'
        }
        
        # HTTP session
        self.session = None
        
        logger.info("DataFeedManager initialized - ready for relentless data gathering")
    
    async def initialize(self):
        """Initialize HTTP session and connections"""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    'User-Agent': 'AI-Hedge-Fund-Intelligence/1.0'
                }
            )
            logger.info("DataFeedManager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing DataFeedManager: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
    
    # ==================== NEWS FEEDS ====================
    
    async def get_tavily_news(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get rapid financial news from Tavily API"""
        try:
            if not self.tavily_api_key:
                logger.warning("Tavily API key not configured")
                return []
            
            articles = []
            
            for ticker in tickers:
                # Search for ticker-specific news
                query = f"{ticker} stock news financial"
                
                payload = {
                    "api_key": self.tavily_api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_images": False,
                    "include_raw_content": False,
                    "max_results": 10
                }
                
                async with self.session.post(self.tavily_endpoint, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for result in data.get('results', []):
                            articles.append({
                                'ticker': ticker,
                                'headline': result.get('title', ''),
                                'url': result.get('url', ''),
                                'content': result.get('content', ''),
                                'published_date': result.get('published_date'),
                                'source': 'tavily'
                            })
                    else:
                        logger.warning(f"Tavily API error: {response.status}")
            
            logger.debug(f"Retrieved {len(articles)} articles from Tavily")
            return articles
            
        except Exception as e:
            logger.error(f"Error getting Tavily news: {e}")
            return []
    
    async def get_rss_feeds(self) -> List[Dict[str, Any]]:
        """Get news from RSS/Atom feeds"""
        try:
            articles = []
            
            for source, url in self.rss_feeds.items():
                try:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            feed = feedparser.parse(content)
                            
                            for entry in feed.entries[:5]:  # Top 5 per source
                                articles.append({
                                    'ticker': self._extract_ticker_from_text(entry.get('title', '')),
                                    'headline': entry.get('title', ''),
                                    'url': entry.get('link', ''),
                                    'content': entry.get('summary', ''),
                                    'published_date': entry.get('published'),
                                    'source': source
                                })
                        else:
                            logger.warning(f"RSS feed error for {source}: {response.status}")
                            
                except Exception as e:
                    logger.error(f"Error parsing RSS feed {source}: {e}")
                    continue
            
            logger.debug(f"Retrieved {len(articles)} articles from RSS feeds")
            return articles
            
        except Exception as e:
            logger.error(f"Error getting RSS feeds: {e}")
            return []
    
    async def get_twitter_finance(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get financial tweets from Twitter/X API"""
        try:
            if not self.twitter_bearer_token:
                logger.warning("Twitter API key not configured")
                return []
            
            tweets = []
            
            for ticker in tickers:
                # Search for ticker mentions
                query = f"${ticker} OR {ticker} -is:retweet lang:en"
                
                headers = {
                    'Authorization': f'Bearer {self.twitter_bearer_token}',
                    'Content-Type': 'application/json'
                }
                
                params = {
                    'query': query,
                    'max_results': 10,
                    'tweet.fields': 'created_at,public_metrics,context_annotations'
                }
                
                async with self.session.get(
                    self.twitter_endpoint,
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for tweet in data.get('data', []):
                            tweets.append({
                                'ticker': ticker,
                                'text': tweet.get('text', ''),
                                'tweet_id': tweet.get('id'),
                                'created_at': tweet.get('created_at'),
                                'retweet_count': tweet.get('public_metrics', {}).get('retweet_count', 0),
                                'like_count': tweet.get('public_metrics', {}).get('like_count', 0),
                                'source': 'twitter'
                            })
                    else:
                        logger.warning(f"Twitter API error: {response.status}")
            
            logger.debug(f"Retrieved {len(tweets)} tweets")
            return tweets
            
        except Exception as e:
            logger.error(f"Error getting Twitter finance: {e}")
            return []
    
    # ==================== MARKET DATA FEEDS ====================
    
    async def get_broker_feed(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get real-time data from broker APIs"""
        try:
            trades = []
            
            # Interactive Brokers
            if 'interactive_brokers' in self.broker_configs:
                ib_trades = await self._get_ib_trades(tickers)
                trades.extend(ib_trades)
            
            # Alpaca
            if 'alpaca' in self.broker_configs:
                alpaca_trades = await self._get_alpaca_trades(tickers)
                trades.extend(alpaca_trades)
            
            # TD Ameritrade
            if 'td_ameritrade' in self.broker_configs:
                td_trades = await self._get_td_trades(tickers)
                trades.extend(td_trades)
            
            logger.debug(f"Retrieved {len(trades)} trades from broker feeds")
            return trades
            
        except Exception as e:
            logger.error(f"Error getting broker feed: {e}")
            return []
    
    async def _get_ib_trades(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get trades from Interactive Brokers"""
        try:
            # TODO: Implement IB API integration
            # This would use IB's TWS API or Gateway
            return []
        except Exception as e:
            logger.error(f"Error getting IB trades: {e}")
            return []
    
    async def _get_alpaca_trades(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get trades from Alpaca"""
        try:
            alpaca_config = self.broker_configs.get('alpaca', {})
            api_key = alpaca_config.get('api_key')
            secret_key = alpaca_config.get('secret_key')
            base_url = alpaca_config.get('base_url', 'https://paper-api.alpaca.markets')
            
            if not api_key or not secret_key:
                return []
            
            headers = {
                'APCA-API-KEY-ID': api_key,
                'APCA-API-SECRET-KEY': secret_key
            }
            
            trades = []
            for ticker in tickers:
                # Get latest trades
                url = f"{base_url}/v2/stocks/{ticker}/trades/latest"
                
                async with self.session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'trade' in data:
                            trade = data['trade']
                            trades.append({
                                'ticker': ticker,
                                'price': float(trade.get('p', 0)),
                                'size': int(trade.get('s', 0)),
                                'timestamp': datetime.fromisoformat(trade.get('t', '').replace('Z', '+00:00')),
                                'exchange': trade.get('x', ''),
                                'conditions': trade.get('c', [])
                            })
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting Alpaca trades: {e}")
            return []
    
    async def _get_td_trades(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get trades from TD Ameritrade"""
        try:
            # TODO: Implement TD Ameritrade API integration
            return []
        except Exception as e:
            logger.error(f"Error getting TD trades: {e}")
            return []
    
    async def get_yahoo_finance(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get backup data from Yahoo Finance"""
        try:
            quotes = []
            
            for ticker in tickers:
                # Use Yahoo Finance API
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'chart' in data and 'result' in data['chart']:
                            result = data['chart']['result'][0]
                            meta = result.get('meta', {})
                            
                            quotes.append({
                                'ticker': ticker,
                                'price': meta.get('regularMarketPrice', 0),
                                'volume': meta.get('regularMarketVolume', 0),
                                'high': meta.get('regularMarketDayHigh', 0),
                                'low': meta.get('regularMarketDayLow', 0),
                                'open': meta.get('regularMarketOpen', 0),
                                'previous_close': meta.get('previousClose', 0),
                                'timestamp': datetime.now()
                            })
            
            logger.debug(f"Retrieved {len(quotes)} quotes from Yahoo Finance")
            return quotes
            
        except Exception as e:
            logger.error(f"Error getting Yahoo Finance data: {e}")
            return []
    
    # ==================== OPTIONS FEEDS ====================
    
    async def get_barchart_options(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get options flow from Barchart"""
        try:
            flows = []
            
            for ticker in tickers:
                # Barchart options flow API
                url = f"https://www.barchart.com/options/unusual-activity/{ticker}"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        # TODO: Parse Barchart HTML for options flow
                        # This would require HTML parsing
                        pass
            
            return flows
            
        except Exception as e:
            logger.error(f"Error getting Barchart options: {e}")
            return []
    
    async def get_tradingview_options(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get options flow from TradingView"""
        try:
            flows = []
            
            for ticker in tickers:
                # TradingView options flow
                url = f"https://www.tradingview.com/symbols/{ticker}/options/"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        # TODO: Parse TradingView for options flow
                        # This would require HTML parsing
                        pass
            
            return flows
            
        except Exception as e:
            logger.error(f"Error getting TradingView options: {e}")
            return []
    
    # ==================== SOCIAL FEEDS ====================
    
    async def get_reddit_finance(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Get Reddit finance posts"""
        try:
            posts = []
            
            for ticker in tickers:
                # Reddit API for r/wallstreetbets, r/stocks, etc.
                subreddits = ['wallstreetbets', 'stocks', 'investing', 'SecurityAnalysis']
                
                for subreddit in subreddits:
                    url = f"https://www.reddit.com/r/{subreddit}/search.json"
                    params = {
                        'q': ticker,
                        'sort': 'new',
                        'limit': 5
                    }
                    
                    async with self.session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            for post in data.get('data', {}).get('children', []):
                                post_data = post.get('data', {})
                                posts.append({
                                    'ticker': ticker,
                                    'title': post_data.get('title', ''),
                                    'text': post_data.get('selftext', ''),
                                    'score': post_data.get('score', 0),
                                    'num_comments': post_data.get('num_comments', 0),
                                    'created_utc': post_data.get('created_utc'),
                                    'subreddit': subreddit,
                                    'source': 'reddit'
                                })
            
            logger.debug(f"Retrieved {len(posts)} Reddit posts")
            return posts
            
        except Exception as e:
            logger.error(f"Error getting Reddit finance: {e}")
            return []
    
    # ==================== UTILITY METHODS ====================
    
    def _extract_ticker_from_text(self, text: str) -> str:
        """Extract ticker symbol from text"""
        try:
            # Simple ticker extraction - look for $SYMBOL pattern
            import re
            
            # Look for $SYMBOL pattern
            ticker_match = re.search(r'\$([A-Z]{1,5})', text)
            if ticker_match:
                return ticker_match.group(1)
            
            # Look for common tickers
            common_tickers = ['SPY', 'QQQ', 'IWM', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
            for ticker in common_tickers:
                if ticker in text.upper():
                    return ticker
            
            return 'MARKET'
            
        except Exception as e:
            logger.error(f"Error extracting ticker: {e}")
            return 'MARKET'



