"""
📊 REDDIT HISTORICAL DATA COLLECTOR
Real historical Reddit data using PRAW (Reddit API).

Collects and stores daily mention counts, sentiment, and activity for backtesting.

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

import os
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

# Try to import praw
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not installed. Install with: pip install praw")


@dataclass
class DailyRedditData:
    """Daily aggregated Reddit data for a symbol"""
    symbol: str
    date: str  # YYYY-MM-DD
    total_mentions: int
    wsb_mentions: int
    stocks_mentions: int
    other_mentions: int
    avg_sentiment: float
    bullish_count: int
    bearish_count: int
    neutral_count: int
    top_posts: List[Dict]  # Top posts/comments for that day


class RedditHistoricalCollector:
    """
    Collects and stores historical Reddit data.
    
    Uses:
    1. PRAW for real-time collection going forward
    2. SQLite for persistent storage
    3. ChartExchange API as supplementary source
    """
    
    DB_PATH = "data/reddit_historical.db"
    
    # Subreddits to monitor
    SUBREDDITS = [
        'wallstreetbets',
        'stocks', 
        'investing',
        'StockMarket',
        'options',
        'thetagang',
        'ValueInvesting',
        'SecurityAnalysis'
    ]
    
    # Sentiment keywords
    BULLISH_WORDS = ['moon', 'rocket', 'calls', 'buy', 'bullish', 'long', 'pump', 'squeeze', 'tendies', 'diamond hands', 'yolo', 'all in']
    BEARISH_WORDS = ['puts', 'short', 'bearish', 'sell', 'crash', 'dump', 'dead', 'worthless', 'drill', 'paper hands', 'rug pull']
    
    def __init__(self, client_id: str = None, client_secret: str = None, user_agent: str = None):
        """
        Initialize Reddit collector.
        
        Args:
            client_id: Reddit API client ID (from .env or passed directly)
            client_secret: Reddit API client secret
            user_agent: User agent string for Reddit API
        """
        self.reddit = None
        
        if PRAW_AVAILABLE:
            # Try to get credentials from environment
            client_id = client_id or os.getenv('REDDIT_CLIENT_ID')
            client_secret = client_secret or os.getenv('REDDIT_CLIENT_SECRET')
            user_agent = user_agent or os.getenv('REDDIT_USER_AGENT', 'AlphaHedgeFund/1.0')
            
            if client_id and client_secret:
                try:
                    self.reddit = praw.Reddit(
                        client_id=client_id,
                        client_secret=client_secret,
                        user_agent=user_agent
                    )
                    logger.info("✅ PRAW Reddit client initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize PRAW: {e}")
            else:
                logger.warning("Reddit API credentials not found. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET")
        
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for storing historical data."""
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        # Daily aggregates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                total_mentions INTEGER DEFAULT 0,
                wsb_mentions INTEGER DEFAULT 0,
                stocks_mentions INTEGER DEFAULT 0,
                other_mentions INTEGER DEFAULT 0,
                avg_sentiment REAL DEFAULT 0,
                bullish_count INTEGER DEFAULT 0,
                bearish_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                collected_at TEXT,
                UNIQUE(symbol, date)
            )
        ''')
        
        # Individual posts/comments for detailed analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reddit_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                post_id TEXT NOT NULL,
                post_type TEXT,
                title TEXT,
                body TEXT,
                score INTEGER,
                num_comments INTEGER,
                created_utc INTEGER,
                sentiment REAL,
                collected_at TEXT,
                UNIQUE(post_id)
            )
        ''')
        
        # Create indices
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_symbol_date ON daily_mentions(symbol, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_symbol_created ON reddit_posts(symbol, created_utc)')
        
        conn.commit()
        conn.close()
        
        logger.info(f"📦 SQLite database initialized at {self.DB_PATH}")
    
    def collect_current_mentions(self, symbols: List[str], limit_per_sub: int = 100) -> Dict[str, Dict]:
        """
        Collect current Reddit mentions for given symbols.
        
        Args:
            symbols: List of ticker symbols to search for
            limit_per_sub: Number of posts to fetch per subreddit
            
        Returns:
            Dict with symbol -> data mapping
        """
        if not self.reddit:
            logger.error("Reddit client not initialized. Cannot collect data.")
            return {}
        
        results = {sym: {'mentions': [], 'count': 0, 'sentiment': 0} for sym in symbols}
        
        for subreddit_name in self.SUBREDDITS:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Search for each symbol
                for symbol in symbols:
                    try:
                        # Search recent posts
                        search_results = subreddit.search(
                            f"${symbol} OR {symbol}",
                            time_filter='week',
                            limit=limit_per_sub
                        )
                        
                        for post in search_results:
                            mention = {
                                'subreddit': subreddit_name,
                                'post_id': post.id,
                                'title': post.title,
                                'score': post.score,
                                'num_comments': post.num_comments,
                                'created_utc': post.created_utc,
                                'url': post.url
                            }
                            
                            # Simple sentiment analysis
                            text = f"{post.title} {post.selftext}".lower()
                            sentiment = self._analyze_sentiment(text)
                            mention['sentiment'] = sentiment
                            
                            results[symbol]['mentions'].append(mention)
                            results[symbol]['count'] += 1
                        
                        # Rate limiting
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.debug(f"Error searching {symbol} in r/{subreddit_name}: {e}")
                        continue
                        
            except Exception as e:
                logger.warning(f"Error accessing r/{subreddit_name}: {e}")
                continue
        
        # Calculate average sentiment
        for symbol in symbols:
            mentions = results[symbol]['mentions']
            if mentions:
                sentiments = [m['sentiment'] for m in mentions]
                results[symbol]['sentiment'] = sum(sentiments) / len(sentiments)
        
        return results
    
    def _analyze_sentiment(self, text: str) -> float:
        """Simple keyword-based sentiment analysis."""
        text_lower = text.lower()
        
        bullish_count = sum(1 for word in self.BULLISH_WORDS if word in text_lower)
        bearish_count = sum(1 for word in self.BEARISH_WORDS if word in text_lower)
        
        total = bullish_count + bearish_count
        if total == 0:
            return 0.0
        
        # Return sentiment score between -1 (bearish) and 1 (bullish)
        return (bullish_count - bearish_count) / total
    
    def store_daily_aggregate(self, symbol: str, date: str, data: Dict):
        """Store daily aggregated data to SQLite."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO daily_mentions 
                (symbol, date, total_mentions, wsb_mentions, stocks_mentions, other_mentions,
                 avg_sentiment, bullish_count, bearish_count, neutral_count, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                date,
                data.get('total_mentions', 0),
                data.get('wsb_mentions', 0),
                data.get('stocks_mentions', 0),
                data.get('other_mentions', 0),
                data.get('avg_sentiment', 0),
                data.get('bullish_count', 0),
                data.get('bearish_count', 0),
                data.get('neutral_count', 0),
                datetime.now().isoformat()
            ))
            conn.commit()
            logger.debug(f"Stored daily data for {symbol} on {date}")
        except Exception as e:
            logger.error(f"Error storing daily data: {e}")
        finally:
            conn.close()
    
    def get_historical_data(self, symbol: str, start_date: str, end_date: str) -> List[DailyRedditData]:
        """
        Retrieve historical Reddit data for a symbol.
        
        Args:
            symbol: Ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of DailyRedditData objects
        """
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, date, total_mentions, wsb_mentions, stocks_mentions, other_mentions,
                   avg_sentiment, bullish_count, bearish_count, neutral_count
            FROM daily_mentions
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date
        ''', (symbol, start_date, end_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        results = []
        for row in rows:
            results.append(DailyRedditData(
                symbol=row[0],
                date=row[1],
                total_mentions=row[2],
                wsb_mentions=row[3],
                stocks_mentions=row[4],
                other_mentions=row[5],
                avg_sentiment=row[6],
                bullish_count=row[7],
                bearish_count=row[8],
                neutral_count=row[9],
                top_posts=[]
            ))
        
        return results
    
    def get_available_dates(self, symbol: str) -> Tuple[Optional[str], Optional[str]]:
        """Get earliest and latest dates with data for a symbol."""
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT MIN(date), MAX(date) FROM daily_mentions WHERE symbol = ?
        ''', (symbol,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            return row[0], row[1]
        return None, None


class ChartExchangeRedditCollector:
    """
    Collect Reddit data from ChartExchange API.
    
    Since ChartExchange only returns ~100 recent mentions, we need to
    poll regularly and store the data ourselves.
    """
    
    def __init__(self, api_key: str):
        from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
        self.client = UltimateChartExchangeClient(api_key, tier=3)
        self.db_path = "data/chartexchange_reddit.db"
        self._init_db()
    
    def _init_db(self):
        """Initialize database for ChartExchange Reddit data."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                subreddit TEXT,
                created TEXT,
                sentiment REAL,
                thing_id TEXT UNIQUE,
                thing_type TEXT,
                author TEXT,
                text TEXT,
                collected_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_aggregates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                mention_count INTEGER,
                avg_sentiment REAL,
                wsb_count INTEGER,
                stocks_count INTEGER,
                positive_count INTEGER,
                negative_count INTEGER,
                UNIQUE(symbol, date)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mentions_symbol ON mentions(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mentions_created ON mentions(created)')
        
        conn.commit()
        conn.close()
    
    def collect_and_store(self, symbols: List[str]):
        """
        Collect current Reddit data and store it.
        Should be called periodically (e.g., every hour) to build historical database.
        """
        now = datetime.now().isoformat()
        
        for symbol in symbols:
            try:
                mentions = self.client.get_reddit_mentions(symbol, days=7)
                
                if not mentions:
                    continue
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for m in mentions:
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO mentions 
                            (symbol, subreddit, created, sentiment, thing_id, thing_type, author, text, collected_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            symbol,
                            m.get('subreddit'),
                            m.get('created'),
                            float(m.get('sentiment', 0)),
                            m.get('thing_id'),
                            m.get('thing_type'),
                            m.get('author'),
                            m.get('text', '')[:1000],  # Limit text length
                            now
                        ))
                    except Exception as e:
                        logger.debug(f"Error storing mention: {e}")
                
                conn.commit()
                conn.close()
                
                logger.info(f"✅ Collected {len(mentions)} mentions for {symbol}")
                
            except Exception as e:
                logger.error(f"Error collecting {symbol}: {e}")
    
    def aggregate_daily(self, symbol: str, date: str) -> Dict:
        """Aggregate mentions for a specific date."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*), AVG(sentiment),
                   SUM(CASE WHEN subreddit = 'wallstreetbets' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN subreddit = 'stocks' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN sentiment > 0.1 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN sentiment < -0.1 THEN 1 ELSE 0 END)
            FROM mentions
            WHERE symbol = ? AND date(created) = ?
        ''', (symbol, date))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'mention_count': row[0] or 0,
            'avg_sentiment': row[1] or 0,
            'wsb_count': row[2] or 0,
            'stocks_count': row[3] or 0,
            'positive_count': row[4] or 0,
            'negative_count': row[5] or 0
        }
    
    def get_historical_aggregates(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Get historical daily aggregates for a symbol."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT date, mention_count, avg_sentiment, wsb_count, stocks_count, positive_count, negative_count
            FROM daily_aggregates
            WHERE symbol = ? AND date >= ? AND date <= ?
            ORDER BY date
        ''', (symbol, start_date, end_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'date': row[0],
            'mention_count': row[1],
            'avg_sentiment': row[2],
            'wsb_count': row[3],
            'stocks_count': row[4],
            'positive_count': row[5],
            'negative_count': row[6]
        } for row in rows]


def test_collector():
    """Test the Reddit collector."""
    print("="*80)
    print("📊 TESTING REDDIT HISTORICAL COLLECTOR")
    print("="*80)
    
    # Test ChartExchange collector
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
    
    if api_key:
        print("\n📱 Testing ChartExchange Reddit Collector...")
        collector = ChartExchangeRedditCollector(api_key)
        
        # Collect data for TSLA
        collector.collect_and_store(['TSLA', 'NVDA', 'GME'])
        
        # Check what we have
        conn = sqlite3.connect(collector.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM mentions')
        total = cursor.fetchone()[0]
        print(f"   Total mentions stored: {total}")
        
        cursor.execute('SELECT symbol, COUNT(*), AVG(sentiment) FROM mentions GROUP BY symbol')
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]} mentions, avg sentiment: {row[2]:.3f}")
        
        conn.close()
    else:
        print("❌ No ChartExchange API key found")


if __name__ == "__main__":
    test_collector()

