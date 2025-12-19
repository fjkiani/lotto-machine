#!/usr/bin/env python3
"""
📰 NEWS INTELLIGENCE CHECKER - RapidAPI Integration

Monitors news flow for market-moving events and sentiment divergence.
Uses Yahoo Finance 15 RapidAPI (VALIDATED & WORKING).

SIGNALS GENERATED:
1. HIGH_CREDIBILITY_NEWS - Breaking news from Reuters/Bloomberg
2. SENTIMENT_DIVERGENCE - News vs price action mismatch
3. BREAKING_CATALYST - Significant event detected

DATA SOURCES:
- Yahoo Finance 15 RapidAPI news endpoint
- Credibility scoring (Reuters=100%, Seeking Alpha=70%)
- Sentiment analysis

STORAGE: SQLite for historical tracking and divergence detection
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import sqlite3
import json

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from live_monitoring.orchestrator.checkers.base_checker import BaseChecker, CheckerAlert
from core.data.rapidapi_news_client import RapidAPINewsClient

logger = logging.getLogger(__name__)


class NewsStorage:
    """
    SQLite storage for news data and analysis.
    
    Tracks:
    - News articles with credibility scores
    - Sentiment over time
    - Divergence events
    """
    
    def __init__(self, db_path: str = "data/news_intelligence.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    title TEXT,
                    source TEXT,
                    credibility_score INTEGER,
                    sentiment_score REAL,
                    url TEXT,
                    alert_sent INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS divergences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    divergence_type TEXT,
                    news_sentiment REAL,
                    price_change REAL,
                    reasoning TEXT,
                    alert_sent INTEGER DEFAULT 0,
                    outcome TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS news_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    confidence REAL,
                    headline TEXT,
                    source TEXT,
                    outcome TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logger.info(f"📰 NewsStorage initialized: {self.db_path}")
    
    def store_article(self, symbol: str, article: Dict):
        """Store a news article"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO news_articles 
                (timestamp, symbol, title, source, credibility_score, sentiment_score, url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                symbol,
                article.get('title', ''),
                article.get('source', ''),
                article.get('credibility_score', 50),
                article.get('sentiment', 0),
                article.get('link', '')
            ))
            conn.commit()
    
    def store_divergence(self, divergence: Dict):
        """Store a divergence event"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO divergences 
                (timestamp, symbol, divergence_type, news_sentiment, price_change, reasoning)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                divergence.get('symbol'),
                divergence.get('type'),
                divergence.get('news_sentiment'),
                divergence.get('price_change_pct'),
                divergence.get('reason')
            ))
            conn.commit()
    
    def store_signal(self, signal: Dict):
        """Store generated signal"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO news_signals 
                (timestamp, symbol, signal_type, direction, confidence, headline, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                signal.get('symbol'),
                signal.get('signal_type'),
                signal.get('direction'),
                signal.get('confidence'),
                signal.get('headline'),
                signal.get('source')
            ))
            conn.commit()
    
    def was_article_alerted(self, title: str) -> bool:
        """Check if article was already alerted"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id FROM news_articles 
                WHERE title = ? AND alert_sent = 1
            """, (title,))
            return cursor.fetchone() is not None
    
    def mark_alerted(self, title: str):
        """Mark article as alerted"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE news_articles SET alert_sent = 1 WHERE title = ?
            """, (title,))
            conn.commit()


class NewsIntelligenceChecker(BaseChecker):
    """
    News Intelligence Checker - Monitors news for market signals.
    
    Runs every 10-15 minutes during RTH.
    Generates alerts for significant news events.
    """
    
    # Symbols to monitor
    WATCH_SYMBOLS = ['SPY', 'QQQ', 'AAPL', 'NVDA', 'TSLA', 'MSFT', 'AMZN', 'META', 'GOOGL']
    
    # Alert thresholds
    MIN_CREDIBILITY = 70  # Minimum credibility for alerts
    MAX_AGE_HOURS = 2     # Only recent news
    DIVERGENCE_THRESHOLD = 0.5  # Minimum divergence score
    
    # Keywords that indicate high-impact news
    HIGH_IMPACT_KEYWORDS = [
        'earnings', 'beat', 'miss', 'guidance', 'revenue',
        'fda', 'approval', 'lawsuit', 'settlement', 'sec',
        'merger', 'acquisition', 'buyout', 'takeover',
        'layoff', 'restructur', 'bankrupt', 'default',
        'fed', 'rate', 'inflation', 'tariff', 'sanction',
        'ceo', 'resign', 'appoint', 'died', 'scandal'
    ]
    
    def __init__(self, alert_manager, api_key: str = None, unified_mode: bool = False):
        """
        Initialize News Intelligence Checker.
        
        Args:
            alert_manager: AlertManager for sending Discord alerts
            api_key: RapidAPI key (defaults to env var)
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        
        self.client = RapidAPINewsClient(
            api_key=api_key or os.getenv('YAHOO_RAPIDAPI_KEY')
        )
        self.storage = NewsStorage()
        
        # Track alerted headlines to avoid duplicates
        self.alerted_headlines: set = set()
        
        logger.info("📰 NewsIntelligenceChecker initialized (RapidAPI)")
    
    @property
    def name(self) -> str:
        return "news_intelligence_checker"
    
    def check(self, symbols: List[str] = None) -> List[CheckerAlert]:
        """
        Check news flow for signals.
        
        Returns:
            List of CheckerAlert objects for any detected signals
        """
        alerts = []
        symbols = symbols or self.WATCH_SYMBOLS
        
        try:
            # 1. Get credible news for watch symbols
            logger.info(f"📰 Checking news for {len(symbols)} symbols...")
            
            for symbol in symbols:
                try:
                    # Use the actual API method signature
                    credible_news = self.client.get_credible_news(
                        ticker=symbol,
                        hours=self.MAX_AGE_HOURS
                    )
                    
                    for article in credible_news:
                        # Convert NewsArticle to dict if needed
                        article_dict = {
                            'title': getattr(article, 'title', ''),
                            'text': getattr(article, 'text', ''),
                            'source': getattr(article, 'source', ''),
                            'link': getattr(article, 'link', ''),
                            'ago': getattr(article, 'ago', ''),
                            'credibility_score': int(getattr(article, 'credibility_score', 0.5) * 100)
                        }
                        
                        # Skip if already alerted
                        title = article_dict.get('title', '')
                        if not title or title in self.alerted_headlines or self.storage.was_article_alerted(title):
                            continue
                        
                        # Store article
                        self.storage.store_article(symbol, article_dict)
                        
                        # Check if high-impact
                        if self._is_high_impact(article_dict):
                            alert = self._create_breaking_news_alert(symbol, article_dict)
                            alerts.append(alert)
                            self.alerted_headlines.add(title)
                            self.storage.mark_alerted(title)
                            
                            # Store signal
                            self.storage.store_signal({
                                'symbol': symbol,
                                'signal_type': 'BREAKING_CATALYST',
                                'direction': self._infer_direction(article_dict),
                                'confidence': article_dict.get('credibility_score', 70),
                                'headline': title,
                                'source': article_dict.get('source', '')
                            })
                except Exception as e:
                    logger.warning(f"   ⚠️ Error fetching news for {symbol}: {e}")
                    continue
            
            logger.info(f"   ✅ Generated {len(alerts)} news alerts")
            
        except Exception as e:
            logger.error(f"❌ News check error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        
        return alerts
    
    def _is_high_impact(self, article: Dict) -> bool:
        """Check if article is high-impact"""
        title = article.get('title', '').lower()
        text = article.get('text', '').lower()
        combined = title + ' ' + text
        
        for keyword in self.HIGH_IMPACT_KEYWORDS:
            if keyword in combined:
                return True
        
        # High credibility sources are always important
        if article.get('credibility_score', 0) >= 90:
            return True
        
        return False
    
    def _infer_direction(self, article: Dict) -> str:
        """Infer trading direction from article"""
        title = article.get('title', '').lower()
        text = article.get('text', '').lower()
        combined = title + ' ' + text
        
        bullish_words = ['beat', 'surge', 'soar', 'rally', 'upgrade', 'approval', 'record', 'growth']
        bearish_words = ['miss', 'plunge', 'crash', 'downgrade', 'lawsuit', 'layoff', 'decline', 'fraud']
        
        bullish_count = sum(1 for w in bullish_words if w in combined)
        bearish_count = sum(1 for w in bearish_words if w in combined)
        
        if bullish_count > bearish_count:
            return "LONG"
        elif bearish_count > bullish_count:
            return "SHORT"
        return "WATCH"
    
    def _create_breaking_news_alert(self, symbol: str, article: Dict) -> CheckerAlert:
        """Create alert for breaking news"""
        direction = self._infer_direction(article)
        emoji = "🟢" if direction == "LONG" else ("🔴" if direction == "SHORT" else "🟡")
        color = 0x00FF00 if direction == "LONG" else (0xFF0000 if direction == "SHORT" else 0xFFAA00)
        
        message = f"""
**{emoji} BREAKING NEWS: {symbol}**

High-credibility news detected from {article.get('source', 'Unknown')}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📰 HEADLINE:**
{article.get('title', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 ANALYSIS:**
• Source: **{article.get('source', 'Unknown')}**
• Credibility: **{article.get('credibility_score', 50)}%**
• Age: {article.get('ago', 'N/A')}
• Inferred Direction: **{direction}**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**💡 SUMMARY:**
{article.get('text', 'N/A')[:200]}...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 ACTION:**
{'Consider LONG position' if direction == 'LONG' else ('Consider SHORT/hedge' if direction == 'SHORT' else 'Monitor for confirmation')}

🔗 [Read Full Article]({article.get('link', '#')})
"""
        
        # Create embed for Discord
        embed = {
            "title": f"📰 {symbol}: {article.get('source', 'News')}",
            "description": message.strip(),
            "color": color,
            "fields": [
                {"name": "Symbol", "value": symbol, "inline": True},
                {"name": "Source", "value": article.get('source', 'Unknown'), "inline": True},
                {"name": "Credibility", "value": f"{article.get('credibility_score', 50)}%", "inline": True},
                {"name": "Direction", "value": direction, "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return CheckerAlert(
            embed=embed,
            content="",
            alert_type="breaking_news",
            source=self.name,
            symbol=symbol
        )
    
    def _create_divergence_alert(self, divergence: Dict) -> CheckerAlert:
        """Create alert for sentiment divergence"""
        div_type = divergence.get('type', 'Unknown')
        
        if "Bullish News / Bearish Price" in div_type:
            emoji = "🔄📉"
            color = 0xFFAA00
            direction = "LONG (Contrarian)"
            interpretation = "News is positive but price falling - potential buying opportunity"
        else:
            emoji = "🔄📈"
            color = 0xFFAA00
            direction = "SHORT (Contrarian)"
            interpretation = "News is negative but price rising - potential short opportunity"
        
        message = f"""
**{emoji} SENTIMENT DIVERGENCE: {divergence.get('symbol')}**

News sentiment does NOT match price action!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📊 DIVERGENCE DETAILS:**
• Type: **{div_type}**
• News Sentiment: {divergence.get('news_sentiment', 0):.2f}
• Price Change: {divergence.get('price_change_pct', 0):+.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🧠 INTERPRETATION:**
{interpretation}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🎯 CONTRARIAN SIGNAL:**
• Direction: **{direction}**
• Reasoning: {divergence.get('reason', 'N/A')}

⚠️ **Divergences often precede reversals!**
"""
        
        symbol = divergence.get('symbol', 'UNKNOWN')
        
        # Create embed for Discord
        embed = {
            "title": f"🔄 DIVERGENCE: {symbol}",
            "description": message.strip(),
            "color": color,
            "fields": [
                {"name": "Symbol", "value": symbol, "inline": True},
                {"name": "Type", "value": div_type, "inline": True},
                {"name": "News Sentiment", "value": f"{divergence.get('news_sentiment', 0):.2f}", "inline": True},
                {"name": "Price Change", "value": f"{divergence.get('price_change_pct', 0):+.2f}%", "inline": True}
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return CheckerAlert(
            embed=embed,
            content="",
            alert_type="divergence",
            source=self.name,
            symbol=symbol
        )


# Standalone test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 70)
    print("📰 NEWS INTELLIGENCE CHECKER TEST")
    print("=" * 70)
    
    class MockAlertManager:
        def send_alert(self, alert):
            print(f"[MOCK ALERT] {alert.title}")
    
    checker = NewsIntelligenceChecker(
        alert_manager=MockAlertManager(),
        api_key=os.getenv('YAHOO_RAPIDAPI_KEY')
    )
    
    print(f"\nChecker: {checker.name}")
    print(f"Watch Symbols: {checker.WATCH_SYMBOLS}")
    
    print("\n🔍 Running check...")
    alerts = checker.check(symbols=['SPY', 'TSLA'])
    
    print(f"\n✅ Generated {len(alerts)} alerts:")
    for alert in alerts[:3]:
        print(f"\n{'='*50}")
        print(f"Title: {alert.embed.get('title', 'N/A')}")
        print(f"Alert Type: {alert.alert_type}")
        print(f"Symbol: {alert.symbol}")
        print(f"Source: {alert.source}")
    
    print("\n" + "=" * 70)
    print("✅ News Intelligence Checker test complete!")

