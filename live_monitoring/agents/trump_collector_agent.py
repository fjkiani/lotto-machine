#!/usr/bin/env python3
"""
TRUMP COLLECTOR AGENT
=====================
Autonomous agent that collects Trump statements from multiple sources.
Extracts features using LLM. Links to market data.

This is AGENT 1 in the Trump Intelligence System.
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import feedparser

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from trump_data_models import TrumpStatement, StatementSource
from trump_database import TrumpDatabase

logger = logging.getLogger(__name__)


class TrumpCollectorAgent:
    """
    Autonomous agent that:
    1. Collects Trump statements from multiple sources
    2. Extracts features (entities, topics, sentiment) using LLM
    3. Stores in database
    4. Links market reaction data
    """
    
    def __init__(self, db: TrumpDatabase = None, perplexity_key: str = None):
        self.db = db or TrumpDatabase()
        self.perplexity_key = perplexity_key or os.getenv('PERPLEXITY_API_KEY')
        
        # News sources
        self.rss_feeds = [
            "https://news.google.com/rss/search?q=trump+tariff&hl=en-US&gl=US",
            "https://news.google.com/rss/search?q=trump+china&hl=en-US&gl=US",
            "https://news.google.com/rss/search?q=trump+market&hl=en-US&gl=US",
            "https://news.google.com/rss/search?q=trump+fed&hl=en-US&gl=US",
            "https://news.google.com/rss/search?q=trump+powell&hl=en-US&gl=US",
            "https://news.google.com/rss/search?q=trump+economy&hl=en-US&gl=US",
        ]
        
        # Entity keywords for extraction
        self.entity_keywords = {
            # Countries
            'china': 'China', 'chinese': 'China', 'beijing': 'China', 'xi': 'China',
            'mexico': 'Mexico', 'mexican': 'Mexico',
            'canada': 'Canada', 'canadian': 'Canada',
            'russia': 'Russia', 'russian': 'Russia', 'putin': 'Russia',
            'ukraine': 'Ukraine', 'ukrainian': 'Ukraine',
            'iran': 'Iran', 'iranian': 'Iran',
            'israel': 'Israel', 'israeli': 'Israel',
            'europe': 'EU', 'european': 'EU', 'eu': 'EU',
            
            # Companies
            'apple': 'AAPL', 'amazon': 'AMZN', 'google': 'GOOGL', 'alphabet': 'GOOGL',
            'microsoft': 'MSFT', 'facebook': 'META', 'meta': 'META',
            'tesla': 'TSLA', 'elon': 'TSLA', 'musk': 'TSLA',
            'boeing': 'BA', 'nvidia': 'NVDA', 'intel': 'INTC',
            'jpmorgan': 'JPM', 'goldman': 'GS', 'bank of america': 'BAC',
            
            # People
            'powell': 'Powell', 'yellen': 'Yellen', 'biden': 'Biden',
        }
        
        # Topic keywords
        self.topic_keywords = {
            'tariff': 'tariff', 'tariffs': 'tariff', 'trade war': 'tariff',
            'import': 'tariff', 'duty': 'tariff', 'duties': 'tariff',
            
            'fed': 'fed', 'federal reserve': 'fed', 'interest rate': 'fed',
            'rate cut': 'fed', 'rate hike': 'fed', 'monetary': 'fed',
            
            'trade': 'trade', 'deal': 'trade', 'agreement': 'trade',
            'negotiate': 'trade', 'negotiation': 'trade',
            
            'war': 'geopolitical', 'military': 'geopolitical', 'troops': 'geopolitical',
            'sanction': 'geopolitical', 'sanctions': 'geopolitical',
            
            'oil': 'energy', 'drill': 'energy', 'energy': 'energy',
            'gas': 'energy', 'pipeline': 'energy',
            
            'tech': 'tech', 'big tech': 'tech', 'antitrust': 'tech',
            'regulation': 'regulation', 'regulate': 'regulation',
        }
        
        logger.info("🤖 Trump Collector Agent initialized")
    
    def collect_from_perplexity(self, hours: int = 6) -> List[Dict]:
        """Collect Trump news from Perplexity API"""
        if not self.perplexity_key:
            logger.warning("No Perplexity API key - skipping")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {self.perplexity_key}",
                "Content-Type": "application/json"
            }
            
            queries = [
                f"What are Trump's statements about tariffs, trade, or China in the last {hours} hours? Include exact quotes if available.",
                f"What has Trump said about the Federal Reserve, interest rates, or Powell in the last {hours} hours?",
                f"Has Trump mentioned any specific companies or made market-moving statements in the last {hours} hours?"
            ]
            
            all_results = []
            
            for query in queries:
                payload = {
                    "model": "llama-3.1-sonar-small-128k-online",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a financial news analyst. Report Trump's exact statements with timestamps when available. Be factual and specific."
                        },
                        {"role": "user", "content": query}
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.1
                }
                
                response = requests.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                    if content and len(content) > 50:  # Filter empty responses
                        all_results.append({
                            "source": "perplexity",
                            "content": content,
                            "query": query,
                            "timestamp": datetime.now().isoformat()
                        })
            
            logger.info(f"📰 Collected {len(all_results)} results from Perplexity")
            return all_results
            
        except Exception as e:
            logger.error(f"Error collecting from Perplexity: {e}")
            return []
    
    def collect_from_rss(self, hours: int = 24) -> List[Dict]:
        """Collect Trump news from RSS feeds"""
        cutoff = datetime.now() - timedelta(hours=hours)
        results = []
        
        for feed_url in self.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # Limit per feed
                    title = entry.get('title', '')
                    summary = entry.get('summary', entry.get('description', ''))
                    link = entry.get('link', '')
                    pub_date = entry.get('published', '')
                    
                    # Check if Trump-related (should be, but double check)
                    content = f"{title} {summary}".lower()
                    if 'trump' not in content:
                        continue
                    
                    results.append({
                        "source": "rss",
                        "title": title,
                        "content": f"{title}. {summary}",
                        "url": link,
                        "published": pub_date,
                        "timestamp": datetime.now().isoformat()
                    })
                    
            except Exception as e:
                logger.warning(f"Error fetching RSS {feed_url}: {e}")
        
        logger.info(f"📰 Collected {len(results)} results from RSS")
        return results
    
    def extract_features(self, text: str) -> Dict[str, Any]:
        """
        Extract entities, topics, sentiment from text.
        Uses simple keyword matching + optional LLM enhancement.
        """
        text_lower = text.lower()
        
        # Extract entities
        entities = set()
        for keyword, entity in self.entity_keywords.items():
            if keyword in text_lower:
                entities.add(entity)
        
        # Extract topics
        topics = set()
        for keyword, topic in self.topic_keywords.items():
            if keyword in text_lower:
                topics.add(topic)
        
        # Simple sentiment analysis
        bullish_words = ['great', 'beautiful', 'tremendous', 'winning', 'success', 'deal', 
                        'agreement', 'progress', 'strong', 'best', 'love']
        bearish_words = ['bad', 'terrible', 'disaster', 'enemy', 'threat', 'attack', 
                        'war', 'tariff', 'sanction', 'worst', 'failing', 'weak']
        
        bullish_count = sum(1 for w in bullish_words if w in text_lower)
        bearish_count = sum(1 for w in bearish_words if w in text_lower)
        
        if bullish_count + bearish_count > 0:
            sentiment = (bullish_count - bearish_count) / (bullish_count + bearish_count)
        else:
            sentiment = 0.0
        
        # Intensity (based on caps, exclamation marks, strong words)
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        exclamation_count = text.count('!')
        intensity = min(1.0, caps_ratio * 2 + exclamation_count * 0.1)
        
        # Urgency (based on urgent words)
        urgent_words = ['immediately', 'now', 'today', 'must', 'will', 'going to', 'announce']
        urgency = min(1.0, sum(0.2 for w in urgent_words if w in text_lower))
        
        return {
            'entities': list(entities),
            'topics': list(topics),
            'sentiment': round(sentiment, 3),
            'intensity': round(intensity, 3),
            'urgency': round(urgency, 3)
        }
    
    def extract_features_with_llm(self, text: str) -> Dict[str, Any]:
        """
        Enhanced feature extraction using LLM.
        Falls back to simple extraction if LLM unavailable.
        """
        if not self.perplexity_key:
            return self.extract_features(text)
        
        try:
            headers = {
                "Authorization": f"Bearer {self.perplexity_key}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""Analyze this Trump-related statement for financial market impact:

"{text}"

Return JSON only (no markdown):
{{
    "entities": ["list of companies, countries, people mentioned"],
    "topics": ["list of topics: tariff, fed, trade, geopolitical, tech, energy, regulation"],
    "sentiment": 0.0,  // -1 (very negative) to +1 (very positive)
    "intensity": 0.0,  // 0 (mild) to 1 (extreme)
    "urgency": 0.0,    // 0 (no immediate action) to 1 (immediate)
    "market_relevant": true  // Is this likely to move markets?
}}"""
            
            payload = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [
                    {"role": "system", "content": "You are a financial analyst. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.1
            }
            
            response = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                # Try to parse JSON
                try:
                    # Handle markdown code blocks
                    if '```' in content:
                        content = content.split('```')[1]
                        if content.startswith('json'):
                            content = content[4:]
                    
                    features = json.loads(content.strip())
                    return features
                except json.JSONDecodeError:
                    logger.warning("LLM returned invalid JSON, falling back to simple extraction")
                    return self.extract_features(text)
            
            return self.extract_features(text)
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return self.extract_features(text)
    
    def create_statement(self, raw_data: Dict, use_llm: bool = True) -> Optional[TrumpStatement]:
        """Create a TrumpStatement from raw collected data"""
        try:
            content = raw_data.get('content', '')
            if not content or len(content) < 20:
                return None
            
            # Generate ID from content
            timestamp = datetime.now()
            statement_id = TrumpStatement.generate_id(content, timestamp)
            
            # Check if already exists
            if self.db.statement_exists(statement_id):
                logger.debug(f"Statement already exists: {statement_id[:8]}...")
                return None
            
            # Extract features
            if use_llm:
                features = self.extract_features_with_llm(content)
            else:
                features = self.extract_features(content)
            
            # Determine source
            source_str = raw_data.get('source', 'unknown')
            if source_str == 'perplexity':
                source = StatementSource.NEWS
            elif source_str == 'rss':
                source = StatementSource.NEWS
            else:
                source = StatementSource.UNKNOWN
            
            # Check if market hours
            hour = timestamp.hour
            is_market_hours = (9 <= hour < 16) and timestamp.weekday() < 5
            
            statement = TrumpStatement(
                id=statement_id,
                timestamp=timestamp,
                source=source,
                raw_text=content[:2000],  # Limit size
                url=raw_data.get('url'),
                entities=features.get('entities', []),
                topics=features.get('topics', []),
                sentiment=features.get('sentiment', 0.0),
                intensity=features.get('intensity', 0.0),
                urgency=features.get('urgency', 0.0),
                is_market_hours=is_market_hours
            )
            
            return statement
            
        except Exception as e:
            logger.error(f"Error creating statement: {e}")
            return None
    
    def collect_and_store(self, use_llm: bool = True) -> Tuple[int, int]:
        """
        Main collection routine.
        Returns: (collected_count, stored_count)
        """
        logger.info("🔄 Starting collection cycle...")
        
        all_raw_data = []
        
        # Collect from all sources
        all_raw_data.extend(self.collect_from_perplexity(hours=6))
        all_raw_data.extend(self.collect_from_rss(hours=24))
        
        collected = len(all_raw_data)
        stored = 0
        
        # Process and store
        for raw_data in all_raw_data:
            statement = self.create_statement(raw_data, use_llm=use_llm)
            if statement:
                if self.db.save_statement(statement):
                    stored += 1
                    logger.info(f"💾 Stored: {statement.raw_text[:50]}...")
                    logger.debug(f"   Topics: {statement.topics}, Entities: {statement.entities}")
        
        logger.info(f"✅ Collection complete: {collected} collected, {stored} new stored")
        return collected, stored
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about collected data"""
        return self.db.get_stats()


class MarketReactionLinker:
    """
    Links market reaction data to Trump statements.
    Runs periodically to fill in T+1min, T+5min, T+1hr, T+1day data.
    """
    
    def __init__(self, db: TrumpDatabase = None):
        self.db = db or TrumpDatabase()
    
    def link_market_data(self, statement: TrumpStatement) -> TrumpStatement:
        """
        Link market reaction data to a statement.
        Uses yfinance to get SPY prices at various intervals.
        """
        import yfinance as yf
        
        try:
            timestamp = statement.timestamp
            
            # Fetch minute-level data around the statement time
            start = timestamp - timedelta(hours=1)
            end = timestamp + timedelta(days=2)
            
            spy = yf.Ticker("SPY")
            vix = yf.Ticker("^VIX")
            
            # Get intraday data (1-minute)
            spy_data = spy.history(start=start, end=end, interval="1m")
            vix_data = vix.history(start=start, end=end, interval="1m")
            
            if spy_data.empty:
                logger.warning(f"No SPY data for statement {statement.id}")
                return statement
            
            # Find closest price at statement time
            spy_data.index = spy_data.index.tz_localize(None)
            closest_idx = spy_data.index.get_indexer([timestamp], method='nearest')[0]
            
            if closest_idx >= 0 and closest_idx < len(spy_data):
                base_price = spy_data.iloc[closest_idx]['Close']
                statement.spy_price_at_statement = float(base_price)
                
                # Calculate changes at different intervals
                for minutes, attr in [(1, 'spy_change_1min'), (5, 'spy_change_5min'), 
                                      (15, 'spy_change_15min'), (60, 'spy_change_1hr')]:
                    target_idx = closest_idx + minutes
                    if target_idx < len(spy_data):
                        target_price = spy_data.iloc[target_idx]['Close']
                        change = (target_price - base_price) / base_price * 100
                        setattr(statement, attr, round(change, 4))
            
            # Get daily data for T+1day
            spy_daily = spy.history(start=timestamp.date(), end=timestamp.date() + timedelta(days=2), interval="1d")
            if len(spy_daily) >= 2:
                day_change = (spy_daily.iloc[1]['Close'] - spy_daily.iloc[0]['Close']) / spy_daily.iloc[0]['Close'] * 100
                statement.spy_change_1day = round(day_change, 4)
            
            # VIX data
            if not vix_data.empty:
                vix_data.index = vix_data.index.tz_localize(None)
                vix_closest_idx = vix_data.index.get_indexer([timestamp], method='nearest')[0]
                if vix_closest_idx >= 0 and vix_closest_idx < len(vix_data):
                    statement.vix_at_statement = float(vix_data.iloc[vix_closest_idx]['Close'])
                    
                    vix_1hr_idx = vix_closest_idx + 60
                    if vix_1hr_idx < len(vix_data):
                        vix_change = (vix_data.iloc[vix_1hr_idx]['Close'] - statement.vix_at_statement) / statement.vix_at_statement * 100
                        statement.vix_change_1hr = round(vix_change, 4)
            
            statement.market_data_collected = True
            
            logger.info(f"📊 Linked market data: SPY {statement.spy_change_1hr:+.2f}% (1hr)")
            
        except Exception as e:
            logger.error(f"Error linking market data: {e}")
        
        return statement
    
    def process_pending_statements(self, limit: int = 20) -> int:
        """Process statements that need market data"""
        statements = self.db.get_statements_needing_market_data(limit=limit)
        
        processed = 0
        for statement in statements:
            updated = self.link_market_data(statement)
            if updated.market_data_collected:
                self.db.save_statement(updated)
                processed += 1
        
        logger.info(f"📊 Processed {processed} statements with market data")
        return processed


if __name__ == "__main__":
    # Test the collector
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("=" * 60)
    print("🤖 TRUMP COLLECTOR AGENT - TEST")
    print("=" * 60)
    
    db = TrumpDatabase()
    collector = TrumpCollectorAgent(db=db)
    
    # Collect
    collected, stored = collector.collect_and_store(use_llm=False)  # No LLM for test
    
    print(f"\n📊 Results:")
    print(f"   Collected: {collected}")
    print(f"   Stored: {stored}")
    
    # Stats
    stats = collector.get_collection_stats()
    print(f"\n📊 Database Stats:")
    for key, value in stats.items():
        print(f"   {key}: {value}")

