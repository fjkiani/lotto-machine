#!/usr/bin/env python3
"""
🔍 TRUMP NEWS MONITOR - Stay Ahead of the Market

Continuously monitors news about Trump, filters for exploitable opportunities,
and enriches with market context to give us an edge.

Capabilities:
- Real-time news search (Perplexity + RSS)
- Exploit filter (only actionable news)
- Market correlation (what's SPY doing?)
- Sector impact analysis
- Historical parallel matching
- Sentiment trend tracking
- Volume anomaly detection

Usage:
    from trump_news_monitor import TrumpNewsMonitor
    monitor = TrumpNewsMonitor()
    exploitable = monitor.get_exploitable_news()
"""

import os
import sys
import logging
import hashlib
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'enrichment', 'apis'))

from trump_database import TrumpDatabase
from trump_playbook import TrumpPlaybookAnalyzer

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class NewsItem:
    """Raw news item."""
    id: str
    timestamp: datetime
    source: str
    headline: str
    summary: str
    url: Optional[str] = None
    
    @staticmethod
    def generate_id(headline: str, timestamp: datetime) -> str:
        content = f"{headline[:50]}{timestamp.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class MarketContext:
    """Current market conditions when news dropped."""
    spy_price: float = 0.0
    spy_change_pct: float = 0.0
    vix_level: float = 0.0
    
    # Volume analysis
    spy_volume_ratio: float = 1.0  # vs 20-day avg
    volume_anomaly: bool = False
    
    # Sector leadership
    leading_sectors: List[str] = field(default_factory=list)
    lagging_sectors: List[str] = field(default_factory=list)
    
    # Market session
    is_market_hours: bool = False
    session: str = "CLOSED"  # PRE, RTH, AFTER, CLOSED


@dataclass 
class ExploitContext:
    """Context that helps us exploit the news."""
    # Historical parallels
    similar_events: List[Dict[str, Any]] = field(default_factory=list)
    historical_avg_impact: float = 0.0
    
    # Playbook match
    playbook_pattern: Optional[str] = None
    playbook_strategy: Optional[str] = None
    is_likely_bluff: bool = False
    
    # Sector impact
    affected_sectors: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    
    # Sentiment context
    sentiment_trend: str = "STABLE"  # IMPROVING, STABLE, DETERIORATING
    recent_sentiment_avg: float = 0.0


@dataclass
class ExploitableNews:
    """News that we can potentially exploit for profit."""
    news: NewsItem
    
    # Exploit assessment
    is_exploitable: bool = False
    exploit_score: float = 0.0  # 0-100, higher = more exploitable
    exploit_reason: str = ""
    
    # Context
    market_context: MarketContext = field(default_factory=MarketContext)
    exploit_context: ExploitContext = field(default_factory=ExploitContext)
    
    # Trading signal
    suggested_action: str = "WATCH"  # BUY, SELL, SHORT, FADE, WATCH, AVOID
    suggested_symbols: List[str] = field(default_factory=list)
    confidence: float = 0.0
    urgency: str = "LOW"  # IMMEDIATE, HIGH, MEDIUM, LOW
    
    # Timing
    optimal_entry_window: str = ""  # e.g., "Wait for initial selloff to stabilize"


# ============================================================================
# EXPLOIT KEYWORDS - What makes news exploitable
# ============================================================================

EXPLOIT_KEYWORDS = {
    # High impact - immediate market movers
    "HIGH_IMPACT": {
        "keywords": ["tariff", "sanction", "executive order", "ban", "trade war", 
                     "currency", "rate", "fed", "powell", "treasury", "emergency",
                     "military", "war", "attack", "invasion"],
        "weight": 3.0
    },
    # Medium impact - sector-specific
    "MEDIUM_IMPACT": {
        "keywords": ["regulation", "antitrust", "merger", "investigation", "lawsuit",
                     "climate", "energy", "oil", "gas", "solar", "ev", "electric",
                     "pharma", "drug", "healthcare", "tech", "social media"],
        "weight": 2.0
    },
    # Low impact but actionable
    "LOW_IMPACT": {
        "keywords": ["meeting", "speech", "rally", "interview", "statement",
                     "comment", "tweet", "post", "announcement"],
        "weight": 1.0
    }
}

# Keywords that suggest it's NOT immediately exploitable (background noise)
NOISE_KEYWORDS = ["opinion", "poll", "survey", "could", "might", "may consider",
                  "thinks about", "reacts to", "responds to criticism"]

# Sector mapping
SECTOR_MAPPING = {
    "tariff": ["XLI", "EWW", "FXI", "EWC", "GM", "F"],
    "china": ["FXI", "KWEB", "BABA", "PDD", "JD"],
    "trade": ["XLI", "SPY", "EEM"],
    "energy": ["XLE", "OXY", "CVX", "XOM"],
    "oil": ["USO", "XLE", "OXY"],
    "gas": ["UNG", "XLE"],
    "tech": ["QQQ", "XLK", "AAPL", "MSFT", "GOOGL"],
    "pharma": ["XLV", "PFE", "JNJ", "MRK"],
    "banks": ["XLF", "JPM", "BAC", "GS"],
    "defense": ["ITA", "LMT", "RTX", "NOC"],
    "auto": ["F", "GM", "TSLA"],
    "climate": ["ICLN", "TAN", "TSLA"],
    "fed": ["TLT", "IEF", "XLF", "SPY"],
    "rate": ["TLT", "XLF", "XLRE"],
}


# ============================================================================
# NEWS FETCHER - Get Trump news from multiple sources
# ============================================================================

class TrumpNewsFetcher:
    """Fetches Trump-related news from multiple sources."""
    
    def __init__(self):
        self.perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        self.seen_headlines = set()
        
        # Try to import Perplexity client
        try:
            from perplexity_search import PerplexitySearchClient
            self.perplexity = PerplexitySearchClient(api_key=self.perplexity_key)
        except:
            self.perplexity = None
        
        # Try to import RSS fetcher
        try:
            from free_news import FreeNewsFetcher
            self.rss_fetcher = FreeNewsFetcher()
        except:
            self.rss_fetcher = None
        
        logger.info(f"📰 TrumpNewsFetcher initialized")
        logger.info(f"   Perplexity: {'✅' if self.perplexity_key else '❌'}")
        logger.info(f"   RSS: {'✅' if self.rss_fetcher else '❌'}")
    
    def _is_trump_related(self, text: str) -> bool:
        """Check if news is Trump-related."""
        text_lower = text.lower()
        trump_terms = ["trump", "donald trump", "president trump", "potus", 
                       "white house", "mar-a-lago", "truth social"]
        return any(term in text_lower for term in trump_terms)
    
    def _deduplicate(self, headline: str) -> bool:
        """Check if we've seen this headline. Returns True if duplicate."""
        headline_hash = hashlib.md5(headline.lower()[:100].encode()).hexdigest()
        if headline_hash in self.seen_headlines:
            return True
        self.seen_headlines.add(headline_hash)
        return False
    
    def fetch_latest_news(self, hours: int = 6, max_items: int = 20) -> List[NewsItem]:
        """Fetch latest Trump news from all sources."""
        news_items = []
        
        # Perplexity search for breaking news
        if self.perplexity and self.perplexity_key:
            try:
                queries = [
                    "Latest breaking news about Donald Trump today market impact",
                    "Trump administration policy announcements today",
                    "Trump tariff trade China Mexico news today"
                ]
                for query in queries:
                    result = self.perplexity.search(query)
                    if result and 'answer' in result:
                        # Create news item from Perplexity response
                        if not self._deduplicate(result['answer'][:100]):
                            item = NewsItem(
                                id=NewsItem.generate_id(result['answer'][:100], datetime.now()),
                                timestamp=datetime.now(),
                                source="Perplexity",
                                headline=result['answer'][:200] + "...",
                                summary=result['answer'],
                                url=result.get('url')
                            )
                            news_items.append(item)
            except Exception as e:
                logger.warning(f"Perplexity fetch failed: {e}")
        
        # RSS feeds
        if self.rss_fetcher:
            try:
                rss_news = self.rss_fetcher.fetch_all_news(
                    max_per_source=20
                )
                for article in rss_news:
                    # Filter for Trump-related
                    full_text = f"{article.title} {article.summary}"
                    if self._is_trump_related(full_text):
                        if not self._deduplicate(article.title):
                            item = NewsItem(
                                id=NewsItem.generate_id(article.title, datetime.now()),
                                timestamp=datetime.now(),
                                source=f"RSS: {article.source}",
                                headline=article.title,
                                summary=article.summary,
                                url=article.url
                            )
                            news_items.append(item)
            except Exception as e:
                logger.warning(f"RSS fetch failed: {e}")
        
        # Limit and return
        return news_items[:max_items]


# ============================================================================
# MARKET CONTEXT ENRICHER - What's the market doing?
# ============================================================================

class MarketContextEnricher:
    """Enriches news with current market context."""
    
    def __init__(self):
        self.sector_etfs = {
            "tech": "XLK",
            "financials": "XLF", 
            "energy": "XLE",
            "healthcare": "XLV",
            "industrials": "XLI",
            "materials": "XLB",
            "utilities": "XLU",
            "real_estate": "XLRE",
            "consumer_disc": "XLY",
            "consumer_staples": "XLP",
            "communications": "XLC"
        }
        self._cache = {}
        self._cache_time = None
    
    def _get_market_session(self) -> Tuple[bool, str]:
        """Determine current market session."""
        from datetime import time
        import pytz
        
        try:
            et = pytz.timezone('US/Eastern')
            now_et = datetime.now(et)
            current_time = now_et.time()
            
            # Check if weekday
            if now_et.weekday() >= 5:
                return False, "CLOSED"
            
            # Market hours
            pre_start = time(4, 0)
            rth_start = time(9, 30)
            rth_end = time(16, 0)
            after_end = time(20, 0)
            
            if pre_start <= current_time < rth_start:
                return True, "PRE"
            elif rth_start <= current_time < rth_end:
                return True, "RTH"
            elif rth_end <= current_time < after_end:
                return True, "AFTER"
            else:
                return False, "CLOSED"
        except:
            return False, "UNKNOWN"
    
    def get_context(self) -> MarketContext:
        """Get current market context."""
        # Check cache (refresh every 60 seconds)
        if self._cache_time and (datetime.now() - self._cache_time).seconds < 60:
            return self._cache.get('context', MarketContext())
        
        context = MarketContext()
        
        try:
            # SPY data
            spy = yf.Ticker("SPY")
            spy_info = spy.info
            context.spy_price = spy_info.get('regularMarketPrice', 0)
            context.spy_change_pct = spy_info.get('regularMarketChangePercent', 0)
            
            # Volume analysis
            hist = spy.history(period="1mo")
            if not hist.empty:
                avg_volume = hist['Volume'].mean()
                today_volume = hist['Volume'].iloc[-1] if len(hist) > 0 else 0
                context.spy_volume_ratio = today_volume / avg_volume if avg_volume > 0 else 1.0
                context.volume_anomaly = context.spy_volume_ratio > 1.5
            
            # VIX
            vix = yf.Ticker("^VIX")
            vix_info = vix.info
            context.vix_level = vix_info.get('regularMarketPrice', 0)
            
            # Sector analysis
            sector_changes = {}
            for sector, etf in self.sector_etfs.items():
                try:
                    ticker = yf.Ticker(etf)
                    info = ticker.info
                    change = info.get('regularMarketChangePercent', 0)
                    sector_changes[sector] = change
                except:
                    pass
            
            # Sort sectors
            sorted_sectors = sorted(sector_changes.items(), key=lambda x: x[1], reverse=True)
            context.leading_sectors = [s[0] for s in sorted_sectors[:3]]
            context.lagging_sectors = [s[0] for s in sorted_sectors[-3:]]
            
            # Market session
            context.is_market_hours, context.session = self._get_market_session()
            
        except Exception as e:
            logger.warning(f"Market context fetch failed: {e}")
        
        # Cache
        self._cache['context'] = context
        self._cache_time = datetime.now()
        
        return context


# ============================================================================
# EXPLOIT ANALYZER - Is this news exploitable?
# ============================================================================

class ExploitAnalyzer:
    """Analyzes if news is exploitable and how to exploit it."""
    
    def __init__(self):
        self.db = TrumpDatabase()
        self.playbook = TrumpPlaybookAnalyzer()
    
    def _calculate_exploit_score(self, news: NewsItem) -> Tuple[float, str]:
        """Calculate how exploitable this news is (0-100)."""
        text = f"{news.headline} {news.summary}".lower()
        score = 0.0
        reasons = []
        
        # Check for exploit keywords
        for category, data in EXPLOIT_KEYWORDS.items():
            matches = sum(1 for kw in data["keywords"] if kw in text)
            if matches > 0:
                category_score = matches * data["weight"] * 10
                score += category_score
                reasons.append(f"{category}: {matches} matches")
        
        # Penalize noise keywords
        noise_matches = sum(1 for kw in NOISE_KEYWORDS if kw in text)
        if noise_matches > 0:
            score *= 0.7  # 30% penalty
            reasons.append(f"Noise penalty: {noise_matches} matches")
        
        # Boost for specific entities/numbers
        if any(char.isdigit() for char in text):  # Contains numbers (tariff %, rates)
            score *= 1.2
            reasons.append("Contains specifics (numbers)")
        
        # Cap at 100
        score = min(100, score)
        
        reason = " | ".join(reasons) if reasons else "Low impact news"
        return score, reason
    
    def _get_affected_sectors(self, news: NewsItem) -> Tuple[List[str], List[str]]:
        """Determine which sectors/symbols are affected."""
        text = f"{news.headline} {news.summary}".lower()
        
        sectors = []
        symbols = []
        
        for keyword, sector_symbols in SECTOR_MAPPING.items():
            if keyword in text:
                sectors.append(keyword)
                symbols.extend(sector_symbols)
        
        # Deduplicate
        sectors = list(set(sectors))
        symbols = list(set(symbols))[:10]  # Limit to 10
        
        return sectors, symbols
    
    def _find_historical_parallels(self, news: NewsItem) -> List[Dict[str, Any]]:
        """Find similar historical events."""
        parallels = []
        
        # Get all statements from DB
        try:
            correlations = self.db.get_all_correlations()
            text_lower = f"{news.headline} {news.summary}".lower()
            
            for corr in correlations:
                if corr.topic.lower() in text_lower and corr.statement_count >= 3:
                    parallels.append({
                        "topic": corr.topic,
                        "count": corr.statement_count,
                        "avg_impact": corr.avg_spy_change_1hr,
                        "direction": "BULLISH" if corr.avg_spy_change_1hr > 0 else "BEARISH"
                    })
        except:
            pass
        
        return parallels[:5]  # Top 5
    
    def _get_playbook_context(self, news: NewsItem) -> Tuple[Optional[str], Optional[str], bool]:
        """Analyze against Trump playbook."""
        text = f"{news.headline} {news.summary}"
        
        try:
            analysis = self.playbook.analyze_statement(text)
            
            patterns = analysis.get('patterns_detected', [])
            if patterns:
                primary = patterns[0]
                pattern_obj = primary.get('pattern')
                if pattern_obj:
                    pattern_name = getattr(pattern_obj, 'pattern_name', 'Unknown')
                    
                    # Check if it's a bluff pattern
                    is_bluff = 'bluff' in pattern_name.lower() or 'deadline' in pattern_name.lower()
                    
                    strategy = analysis.get('counter_strategy', '')
                    
                    return pattern_name, strategy, is_bluff
        except:
            pass
        
        return None, None, False
    
    def _get_sentiment_trend(self) -> Tuple[str, float]:
        """Get recent sentiment trend from our database."""
        try:
            recent = self.db.get_recent_statements(hours=24, limit=20)
            if recent:
                sentiments = [s.sentiment for s in recent]
                avg = sum(sentiments) / len(sentiments)
                
                # Compare to older
                older = self.db.get_recent_statements(hours=72, limit=50)
                if older:
                    older_sentiments = [s.sentiment for s in older]
                    older_avg = sum(older_sentiments) / len(older_sentiments)
                    
                    if avg > older_avg + 0.1:
                        return "IMPROVING", avg
                    elif avg < older_avg - 0.1:
                        return "DETERIORATING", avg
                
                return "STABLE", avg
        except:
            pass
        
        return "UNKNOWN", 0.0
    
    def _determine_action(self, score: float, parallels: List, is_bluff: bool, 
                          sentiment_trend: str, market_context: MarketContext) -> Tuple[str, str, float]:
        """Determine suggested trading action."""
        
        # Not exploitable
        if score < 30:
            return "WATCH", "LOW", 20.0
        
        # Calculate direction from historical parallels
        if parallels:
            avg_impact = sum(p['avg_impact'] for p in parallels) / len(parallels)
            
            # If it's a bluff, FADE the expected direction
            if is_bluff:
                if avg_impact < 0:
                    return "FADE_BEARISH", "MEDIUM", min(70, score)
                else:
                    return "FADE_BULLISH", "MEDIUM", min(70, score)
            
            # Otherwise, trade with history
            if avg_impact < -0.3:
                urgency = "HIGH" if score > 70 else "MEDIUM"
                return "SHORT", urgency, min(80, score)
            elif avg_impact > 0.3:
                urgency = "HIGH" if score > 70 else "MEDIUM"
                return "BUY", urgency, min(80, score)
        
        # High score but no clear direction
        if score > 60:
            return "PREPARE", "MEDIUM", score * 0.7
        
        return "WATCH", "LOW", score * 0.5
    
    def analyze(self, news: NewsItem, market_context: MarketContext) -> ExploitableNews:
        """Full analysis of a news item."""
        
        # Calculate exploit score
        score, reason = self._calculate_exploit_score(news)
        
        # Build exploit context
        exploit_context = ExploitContext()
        exploit_context.similar_events = self._find_historical_parallels(news)
        
        if exploit_context.similar_events:
            exploit_context.historical_avg_impact = sum(
                e['avg_impact'] for e in exploit_context.similar_events
            ) / len(exploit_context.similar_events)
        
        # Playbook analysis
        pattern, strategy, is_bluff = self._get_playbook_context(news)
        exploit_context.playbook_pattern = pattern
        exploit_context.playbook_strategy = strategy
        exploit_context.is_likely_bluff = is_bluff
        
        # Sector impact
        sectors, symbols = self._get_affected_sectors(news)
        exploit_context.affected_sectors = sectors
        exploit_context.affected_symbols = symbols
        
        # Sentiment trend
        trend, avg = self._get_sentiment_trend()
        exploit_context.sentiment_trend = trend
        exploit_context.recent_sentiment_avg = avg
        
        # Determine action
        action, urgency, confidence = self._determine_action(
            score, exploit_context.similar_events, is_bluff, trend, market_context
        )
        
        # Build result
        result = ExploitableNews(
            news=news,
            is_exploitable=score >= 40,
            exploit_score=score,
            exploit_reason=reason,
            market_context=market_context,
            exploit_context=exploit_context,
            suggested_action=action,
            suggested_symbols=symbols if symbols else ["SPY"],
            confidence=confidence,
            urgency=urgency
        )
        
        # Optimal entry timing
        if is_bluff:
            result.optimal_entry_window = "Wait for initial fear reaction to peak, then FADE"
        elif action in ["BUY", "SHORT"]:
            if market_context.session == "PRE":
                result.optimal_entry_window = "Consider entering at market open"
            elif market_context.session == "RTH":
                result.optimal_entry_window = "Enter now if confident, or wait for pullback"
            else:
                result.optimal_entry_window = "Prepare for next session"
        
        return result


# ============================================================================
# MAIN MONITOR CLASS
# ============================================================================

class TrumpNewsMonitor:
    """
    Main Trump News Monitor - Continuously watches for exploitable news.
    """
    
    def __init__(self):
        self.fetcher = TrumpNewsFetcher()
        self.market_enricher = MarketContextEnricher()
        self.exploit_analyzer = ExploitAnalyzer()
        
        logger.info("🔍 TrumpNewsMonitor initialized - Ready to find exploits!")
    
    def get_exploitable_news(self, hours: int = 6, min_score: float = 30) -> List[ExploitableNews]:
        """
        Get all current exploitable news.
        
        Args:
            hours: How far back to look
            min_score: Minimum exploit score (0-100)
        
        Returns:
            List of ExploitableNews sorted by exploit score
        """
        # Fetch news
        news_items = self.fetcher.fetch_latest_news(hours=hours)
        
        # Get market context
        market_context = self.market_enricher.get_context()
        
        # Analyze each item
        exploitable = []
        for item in news_items:
            analysis = self.exploit_analyzer.analyze(item, market_context)
            if analysis.exploit_score >= min_score:
                exploitable.append(analysis)
        
        # Sort by score
        exploitable.sort(key=lambda x: x.exploit_score, reverse=True)
        
        return exploitable
    
    def get_top_exploit(self) -> Optional[ExploitableNews]:
        """Get the single most exploitable news right now."""
        exploitable = self.get_exploitable_news(hours=6, min_score=50)
        return exploitable[0] if exploitable else None
    
    def print_exploit_report(self, exploitable: Optional[List[ExploitableNews]] = None):
        """Print formatted exploit report with FULL CONTEXT and MEANING."""
        if exploitable is None:
            exploitable = self.get_exploitable_news()
        
        print("\n" + "=" * 80)
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║          🔍 TRUMP NEWS MONITOR - EXPLOITABLE OPPORTUNITIES                     ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        print(f"  Scanned: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Found: {len(exploitable)} exploitable items")
        print("=" * 80)
        
        if not exploitable:
            print("\n  📭 No highly exploitable news found right now.")
            print("     Keep monitoring - opportunities appear suddenly!\n")
            return
        
        # Market context
        ctx = self.market_enricher.get_context()
        session_emoji = {"PRE": "🌅", "RTH": "📈", "AFTER": "🌙", "CLOSED": "🔒"}.get(ctx.session, "❓")
        print(f"\n  📊 MARKET CONTEXT:")
        print(f"     SPY: ${ctx.spy_price:.2f} ({ctx.spy_change_pct:+.2f}%)")
        print(f"     VIX: {ctx.vix_level:.1f}")
        print(f"     Session: {session_emoji} {ctx.session}")
        if ctx.volume_anomaly:
            print(f"     ⚠️ VOLUME ANOMALY: {ctx.spy_volume_ratio:.1f}x average")
        
        # Top exploits - WITH FULL CONTEXT
        for i, exp in enumerate(exploitable[:5], 1):
            score_bar = "█" * int(exp.exploit_score / 10) + "░" * (10 - int(exp.exploit_score / 10))
            
            action_emoji = {
                "BUY": "🟢", "SHORT": "🔴", "FADE_BEARISH": "🔄", 
                "FADE_BULLISH": "🔄", "PREPARE": "⚠️", "WATCH": "👀"
            }.get(exp.suggested_action, "❓")
            
            urgency_color = {"IMMEDIATE": "🚨🚨🚨", "HIGH": "⚡⚡", "MEDIUM": "⏰", "LOW": "📌"}.get(exp.urgency, "")
            
            print("\n" + "─" * 80)
            print(f"  #{i} | SCORE: [{score_bar}] {exp.exploit_score:.0f}/100 | {urgency_color} {exp.urgency}")
            print("─" * 80)
            
            # FULL NEWS TEXT - NOT TRUNCATED
            print(f"\n  📰 THE NEWS:")
            print(f"     {exp.news.headline}")
            if exp.news.summary and exp.news.summary != exp.news.headline:
                # Word wrap the summary
                summary = exp.news.summary
                words = summary.split()
                line = "     "
                for word in words:
                    if len(line) + len(word) + 1 > 75:
                        print(line)
                        line = "     " + word
                    else:
                        line += " " + word if line != "     " else word
                if line.strip():
                    print(line)
            print(f"\n     Source: {exp.news.source}")
            
            # WHY WE CARE - THE MEANING
            print(f"\n  💡 WHY THIS MATTERS:")
            why_matters = self._explain_why_matters(exp)
            for line in why_matters:
                print(f"     {line}")
            
            # HISTORICAL PROOF
            if exp.exploit_context.similar_events:
                print(f"\n  📚 HISTORICAL PROOF:")
                for parallel in exp.exploit_context.similar_events[:3]:
                    direction = "📈" if parallel['avg_impact'] > 0 else "📉"
                    print(f"     {direction} When Trump talks '{parallel['topic']}': SPY moves {parallel['avg_impact']:+.2f}% on average")
                    print(f"        Based on {parallel['count']} historical events")
            
            # PLAYBOOK ANALYSIS
            if exp.exploit_context.playbook_pattern:
                print(f"\n  📖 TRUMP PLAYBOOK ANALYSIS:")
                print(f"     Pattern: {exp.exploit_context.playbook_pattern}")
                if exp.exploit_context.is_likely_bluff:
                    print(f"     🎭 THIS IS LIKELY A BLUFF!")
                    print(f"        Trump's playbook: Make extreme threats, then back down or 'win'")
                    print(f"        Strategy: FADE the initial fear reaction")
                if exp.exploit_context.playbook_strategy:
                    print(f"     Counter-strategy: {exp.exploit_context.playbook_strategy}")
            
            # THE TRADE
            print(f"\n  🎯 THE TRADE:")
            print(f"     {action_emoji} ACTION: {exp.suggested_action}")
            print(f"     📊 SYMBOLS: {', '.join(exp.suggested_symbols[:5])}")
            print(f"     💯 CONFIDENCE: {exp.confidence:.0f}%")
            if exp.optimal_entry_window:
                print(f"     ⏱️  TIMING: {exp.optimal_entry_window}")
            
            # BOTTOM LINE
            print(f"\n  📌 BOTTOM LINE:")
            bottom_line = self._get_bottom_line(exp)
            print(f"     {bottom_line}")
        
        print("\n" + "=" * 80)
        print("  💡 REMEMBER: Data-driven, not panic-driven. Trade the pattern, not the headline.")
        print("=" * 80 + "\n")
    
    def _explain_why_matters(self, exp: ExploitableNews) -> List[str]:
        """Generate explanation of WHY this news matters for trading."""
        lines = []
        
        # Check topics
        topics = exp.exploit_context.affected_sectors
        
        if "tariff" in str(topics).lower() or "tariff" in exp.news.headline.lower():
            lines.append("→ TARIFFS directly impact import costs and corporate margins")
            lines.append("→ Historically BEARISH for SPY short-term (-0.74% avg)")
            lines.append("→ Sectors hit: Industrials (XLI), Autos (GM, F), Retail")
        
        if "china" in str(topics).lower() or "china" in exp.news.headline.lower():
            lines.append("→ CHINA trade tensions = uncertainty = volatility")
            lines.append("→ Affects: Tech supply chains, Consumer goods, FXI, KWEB")
            lines.append("→ Watch for retaliatory measures")
        
        if "fed" in str(topics).lower() or "rate" in exp.news.headline.lower():
            lines.append("→ FED/RATES comments move bond yields and equity valuations")
            lines.append("→ Affects: Banks (XLF), Real Estate (XLRE), Tech (QQQ)")
        
        if "energy" in str(topics).lower() or "oil" in exp.news.headline.lower():
            lines.append("→ ENERGY policy impacts oil prices and energy stocks")
            lines.append("→ Affects: XLE, OXY, CVX, XOM")
        
        if "trade" in str(topics).lower() or "deal" in exp.news.headline.lower():
            lines.append("→ TRADE news creates binary outcomes: deal = rally, no deal = selloff")
            lines.append("→ Historically BULLISH when deals announced (+0.82% avg)")
        
        if "emergency" in exp.news.headline.lower() or "executive order" in exp.news.headline.lower():
            lines.append("→ EXECUTIVE ACTIONS have immediate policy impact")
            lines.append("→ Markets react to the specifics - read the details!")
        
        if not lines:
            lines.append(f"→ Keywords detected: {', '.join(topics[:3]) if topics else 'general market news'}")
            lines.append("→ Monitor for follow-up details and market reaction")
        
        return lines
    
    def _get_bottom_line(self, exp: ExploitableNews) -> str:
        """Generate a clear BOTTOM LINE for trading."""
        
        if exp.exploit_context.is_likely_bluff:
            return f"🎭 BLUFF DETECTED: Don't panic. Wait for initial selloff, then consider buying the dip. Historical pattern shows these threats often get walked back."
        
        if exp.suggested_action == "BUY":
            symbols = ', '.join(exp.suggested_symbols[:3])
            return f"🟢 BULLISH SETUP: Consider long positions in {symbols}. Historical data supports upside ({exp.confidence:.0f}% confidence)."
        
        if exp.suggested_action == "SHORT":
            symbols = ', '.join(exp.suggested_symbols[:3])
            return f"🔴 BEARISH SETUP: Consider defensive positioning or shorts in {symbols}. History shows negative impact ({exp.confidence:.0f}% confidence)."
        
        if exp.suggested_action == "PREPARE":
            return f"⚠️ HIGH IMPACT EVENT: Reduce position sizes, set stops tight, or stay flat until clarity. Volatility expected."
        
        if exp.suggested_action in ["FADE_BEARISH", "FADE_BULLISH"]:
            return f"🔄 FADE SETUP: Initial reaction likely overdone. Let dust settle, then position opposite to the panic direction."
        
        return f"👀 WATCH: Not immediately actionable but stay alert. Could develop into opportunity."


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Demo the Trump News Monitor."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    monitor = TrumpNewsMonitor()
    exploitable = monitor.get_exploitable_news()
    monitor.print_exploit_report(exploitable)


if __name__ == "__main__":
    main()

