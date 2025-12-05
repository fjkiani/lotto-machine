"""
🎤 Fed Officials Engine - MODULAR & DYNAMIC
============================================
Orchestrates all components for data-driven Fed monitoring.
"""

import logging
import hashlib
from datetime import datetime
from typing import List, Optional
import os
import sys

from .models import FedComment, FedCommentReport, FedOfficial
from .database import FedOfficialsDatabase
from .query_generator import QueryGenerator
from .sentiment_analyzer import SentimentAnalyzer
from .official_tracker import OfficialTracker
from .impact_learner import ImpactLearner

logger = logging.getLogger(__name__)


class FedOfficialsEngine:
    """
    Main orchestrator for dynamic Fed officials monitoring.
    
    Features:
    - Dynamic official discovery (not hardcoded)
    - LLM-based sentiment (not keywords)
    - Learned queries (not hardcoded)
    - Market impact learning (not static weights)
    """
    
    def __init__(self):
        # Initialize database
        self.db = FedOfficialsDatabase()
        
        # Initialize components
        self.query_gen = QueryGenerator(self.db)
        self.sentiment_analyzer = SentimentAnalyzer(self.db)
        self.official_tracker = OfficialTracker(self.db)
        self.impact_learner = ImpactLearner(self.db)
        
        # Perplexity client (for fetching news)
        self.perplexity_client = None
        self._init_perplexity()
        
        # Track seen comments (for deduplication)
        self.seen_hashes = set()
        
        logger.info("🎤 FedOfficialsEngine initialized (MODULAR & DYNAMIC)")
        logger.info(f"   📊 Tracking {len(self.db.get_officials())} officials (learned from data)")
    
    def _init_perplexity(self):
        """Initialize Perplexity client for news fetching."""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if api_key:
                # Try multiple import paths
                try:
                    from live_monitoring.enrichment.apis.perplexity_search import PerplexitySearchClient
                    self.perplexity_client = PerplexitySearchClient(api_key=api_key)
                except ImportError:
                    # Fallback: direct path
                    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
                    sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'enrichment', 'apis'))
                    from perplexity_search import PerplexitySearchClient
                    self.perplexity_client = PerplexitySearchClient(api_key=api_key)
                
                logger.info("   ✅ Perplexity client initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Perplexity not available: {e}")
    
    def fetch_comments(self, hours: int = 24) -> List[FedComment]:
        """
        Fetch recent Fed comments using dynamic queries.
        
        Returns list of new comments (deduplicated).
        """
        if not self.perplexity_client:
            logger.warning("No Perplexity client - cannot fetch comments")
            return []
        
        comments = []
        
        # Get officials to query (learned from data, not hardcoded!)
        officials = self.db.get_officials()
        if not officials:
            # Seed with common officials if database is empty
            from .models import FedPosition
            seed_officials = [
                FedOfficial(name="Jerome Powell", position=FedPosition.CHAIR, comment_frequency=0),
                FedOfficial(name="John Williams", position=FedPosition.VICE_CHAIR, comment_frequency=0),
                FedOfficial(name="Christopher Waller", position=FedPosition.GOVERNOR, comment_frequency=0),
                FedOfficial(name="Michelle Bowman", position=FedPosition.GOVERNOR, comment_frequency=0),
            ]
            # Save seed officials
            for official in seed_officials:
                self.db.update_official(official)
            officials = seed_officials
            logger.info(f"   🌱 Seeded database with {len(seed_officials)} initial officials")
        
        official_names = [o.name for o in officials[:5]]  # Top 5 most active
        
        # Generate dynamic queries (learned + exploration)
        timeframe = "today" if hours <= 24 else f"in the last {hours} hours"
        queries = self.query_gen.generate_queries(official_names, timeframe)
        
        # Execute queries
        for query in queries[:5]:  # Limit to 5 queries per run
            try:
                result = self.perplexity_client.search(query)
                
                if result and 'answer' in result:
                    answer = result['answer']
                    
                    # Discover officials from text
                    found_officials = self.official_tracker.discover_from_text(answer)
                    
                    # Extract comments for each official
                    for official_name in found_officials:
                        # Find mentions of this official
                        official_lower = official_name.lower()
                        if official_lower in answer.lower():
                            # Extract context
                            start_idx = max(0, answer.lower().find(official_lower) - 50)
                            end_idx = min(len(answer), answer.lower().find(official_lower) + 300)
                            context = answer[start_idx:end_idx].strip()
                            
                            # Create hash for deduplication
                            comment_hash = hashlib.md5(
                                f"{official_name}:{context}".encode()
                            ).hexdigest()
                            
                            # Skip if already seen
                            if comment_hash in self.seen_hashes:
                                continue
                            
                            self.seen_hashes.add(comment_hash)
                            if len(self.seen_hashes) > 500:
                                # Keep last 500
                                self.seen_hashes = set(list(self.seen_hashes)[-500:])
                            
                            # Analyze sentiment (LLM-based!)
                            sentiment, confidence, reasoning = self.sentiment_analyzer.analyze(
                                context, official_name
                            )
                            
                            # Predict market impact (learned!)
                            impact, impact_conf, impact_reason = self.impact_learner.predict_impact(
                                official_name, sentiment
                            )
                            
                            # Create comment
                            comment = FedComment(
                                timestamp=datetime.now(),
                                official_name=official_name,
                                headline=f"{official_name} comments on monetary policy",
                                content=context,
                                source="Perplexity",
                                sentiment=sentiment,
                                sentiment_confidence=confidence,
                                sentiment_reasoning=reasoning,
                                predicted_market_impact=impact,
                                comment_hash=comment_hash,
                            )
                            
                            # Save to database
                            comment_id = self.db.save_comment(comment)
                            if comment_id:
                                comments.append(comment)
                                
                                # Update official stats
                                self.official_tracker.update_official_stats(official_name)
                                
                                # Track query performance
                                self.query_gen.record_result(query, True, 1)
                            else:
                                # Duplicate
                                self.query_gen.record_result(query, False, 0)
                
            except Exception as e:
                logger.warning(f"Query failed: {e}")
                self.query_gen.record_result(query, False, 0)
        
        logger.info(f"📊 Fetched {len(comments)} new Fed comments")
        return comments
    
    def get_report(self) -> FedCommentReport:
        """Get comprehensive report of recent Fed comments."""
        # Fetch new comments
        new_comments = self.fetch_comments(hours=24)
        
        # Get recent comments from database
        recent_comments = self.db.get_recent_comments(hours=24, limit=20)
        
        # Combine (avoid duplicates)
        all_comments = {}
        for comment in new_comments + recent_comments:
            if comment.comment_hash not in all_comments:
                all_comments[comment.comment_hash] = comment
        
        comments = list(all_comments.values())
        
        # Generate report
        report = FedCommentReport()
        report.comments = comments
        
        if comments:
            # Calculate overall sentiment
            hawk_count = sum(1 for c in comments if c.sentiment == "HAWKISH")
            dove_count = sum(1 for c in comments if c.sentiment == "DOVISH")
            
            if hawk_count > dove_count:
                report.overall_sentiment = "HAWKISH"
                report.market_bias = "BEARISH"
                report.confidence = min(0.9, 0.5 + (hawk_count - dove_count) * 0.1)
            elif dove_count > hawk_count:
                report.overall_sentiment = "DOVISH"
                report.market_bias = "BULLISH"
                report.confidence = min(0.9, 0.5 + (dove_count - hawk_count) * 0.1)
            else:
                report.overall_sentiment = "MIXED"
                report.market_bias = "NEUTRAL"
                report.confidence = 0.3
            
            # Generate recommendation (data-driven)
            if report.overall_sentiment == "HAWKISH":
                report.recommendation = "Fed officials leaning hawkish - consider defensive positioning"
                report.suggested_positions = ["SHORT QQQ", "LONG TLT (bonds fall)"]
            elif report.overall_sentiment == "DOVISH":
                report.recommendation = "Fed officials leaning dovish - risk-on positioning favored"
                report.suggested_positions = ["LONG QQQ", "LONG TLT (bonds rise)"]
            else:
                report.recommendation = "Mixed Fed signals - wait for clarity"
        else:
            report.recommendation = "No recent Fed comments detected"
        
        return report
    
    def get_latest_comment(self, official_name: Optional[str] = None) -> Optional[FedComment]:
        """Get the most recent comment (optionally for a specific official)."""
        comments = self.db.get_recent_comments(hours=24, limit=1)
        if comments:
            if official_name:
                for comment in comments:
                    if comment.official_name == official_name:
                        return comment
            else:
                return comments[0]
        return None

