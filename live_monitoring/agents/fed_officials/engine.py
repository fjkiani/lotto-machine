"""
🎤 Fed Officials Engine — Thin Coordinator
============================================
Orchestrates modular components. Does NOT contain business logic itself.

Modules:
  - trade_normalizer.py  → per-source data parsing
  - tone_aggregator.py   → weighted hawk/dove scoring
  - report_builder.py    → data-driven recommendations
  - impact_learner.py    → learns from SPY price moves
  - official_tracker.py  → discovers officials from text
  - query_generator.py   → learned query templates
  - sentiment_analyzer.py → Cohere LLM analysis
  - fed_rss_calendar.py  → RSS polling + calendar
"""

import logging
import hashlib
from datetime import datetime
from typing import List, Optional

from .models import FedComment, FedCommentReport, FedOfficial
from .database import FedOfficialsDatabase
from .query_generator import QueryGenerator
from .sentiment_analyzer import SentimentAnalyzer
from .official_tracker import OfficialTracker
from .impact_learner import ImpactLearner
from .trade_normalizer import CapitolTradesNormalizer, OpenInsiderNormalizer
from .tone_aggregator import ToneAggregator
from .report_builder import ReportBuilder

logger = logging.getLogger(__name__)


class FedOfficialsEngine:
    """
    Thin coordinator for Fed officials monitoring.
    All intelligence lives in the modules — this just wires them together.
    """

    def __init__(self):
        # Database
        self.db = FedOfficialsDatabase()

        # Intelligence modules
        self.query_gen = QueryGenerator(self.db)
        self.sentiment_analyzer = SentimentAnalyzer(self.db)
        self.official_tracker = OfficialTracker(self.db)
        self.impact_learner = ImpactLearner(self.db)
        self.tone_aggregator = ToneAggregator(db_path=self.db.db_path)
        self.report_builder = ReportBuilder(impact_learner=self.impact_learner)
        self.latest_calendar_events = []  # Populated by fetch_comments()

        # Data normalizers
        self._pol_normalizer = CapitolTradesNormalizer()
        self._insider_normalizer = OpenInsiderNormalizer()

        # RSS poller
        from .fed_rss_calendar import FedRSSCalendarPoller
        self.poller = FedRSSCalendarPoller(self.db, self.sentiment_analyzer)

        # Hidden layer monitors
        try:
            from live_monitoring.agents.hidden_layers.politician_monitor import PoliticianMonitor
            from live_monitoring.agents.hidden_layers.insider_monitor import InsiderMonitor
            self.politician_monitor = PoliticianMonitor()
            self.insider_monitor = InsiderMonitor()
        except ImportError:
            logger.warning("Hidden layer monitors not found. Fed-only mode.")
            self.politician_monitor = None
            self.insider_monitor = None

    # ── Data Ingestion ─────────────────────────────────────────────────────

    def fetch_hidden_layers(self) -> dict:
        """Scrape and normalize politician + insider trades."""
        results = {"politicians_saved": 0, "insiders_saved": 0}

        if self.politician_monitor:
            for raw in self.politician_monitor.poll_latest_trades():
                clean = self._pol_normalizer.normalize(raw)
                if self.db.save_politician_trade(clean):
                    results["politicians_saved"] += 1

        if self.insider_monitor:
            for raw in self.insider_monitor.poll_latest_trades():
                clean = self._insider_normalizer.normalize(raw)
                if self.db.save_insider_trade(clean):
                    results["insiders_saved"] += 1

        logger.info(
            f"Hidden Layers: {results['politicians_saved']} pol, "
            f"{results['insiders_saved']} insider trades saved"
        )
        return results

    def fetch_comments(self, hours: int = 24) -> List[FedComment]:
        """Fetch + process Fed speeches via RSS/Diffbot."""
        comments = []

        for data in self.poller.poll_speeches():
            try:
                official_name = data.get("speaker", "Unknown")
                context = data.get("full_text", "")
                title = data.get("title", f"{official_name} comments on monetary policy")
                comment_hash = hashlib.md5(
                    f"{official_name}:{context[:100]}".encode()
                ).hexdigest()

                # Predict impact using learned model
                impact, impact_conf, impact_reason = self.impact_learner.predict_impact(
                    official_name, data.get("sentiment", "NEUTRAL")
                )

                comment = FedComment(
                    timestamp=datetime.now(),
                    official_name=official_name,
                    headline=title,
                    content=context,
                    source="Federal Reserve RSS (Diffbot extracted)",
                    sentiment=data.get("sentiment", "NEUTRAL"),
                    sentiment_confidence=data.get("sentiment_confidence", 0.0),
                    sentiment_reasoning=data.get("reasoning", ""),
                    predicted_market_impact=impact,
                    comment_hash=comment_hash,
                )

                comment_id = self.db.save_comment(comment)
                if comment_id:
                    comments.append(comment)
                    self.official_tracker.update_official_stats(official_name)

                    # Wire learning: record query performance
                    self.query_gen.record_result(
                        f"{official_name} monetary policy",
                        success=True, comments_found=1
                    )

            except Exception as e:
                logger.warning(f"Error processing speech: {e}")

        # Learn from past outcomes (comments older than 4 hours)
        self._run_learning_loop()

        # Poll calendar events and return them (not just log-and-discard)
        self.latest_calendar_events = self.poller.poll_calendar()
        if self.latest_calendar_events:
            logger.info(f"📅 {len(self.latest_calendar_events)} upcoming events fetched")

        logger.info(f"📊 {len(comments)} new Fed speeches processed")
        return comments

    def _run_learning_loop(self):
        """
        Post-comment learning: check comments older than 4 hours
        and learn what actually happened to SPY after each one.
        This is the loop that makes ImpactLearner real, not theater.
        """
        try:
            recent = self.db.get_recent_comments(hours=24, limit=20)
            for comment in recent:
                # Only learn from comments older than 4 hours
                if hasattr(comment, 'timestamp') and comment.timestamp:
                    from datetime import datetime, timedelta
                    age = datetime.now() - comment.timestamp
                    if age > timedelta(hours=4):
                        self.impact_learner.learn_from_outcome(
                            comment_id=getattr(comment, 'id', 0) or 0,
                            official_name=comment.official_name,
                            sentiment=comment.sentiment,
                        )
        except Exception as e:
            logger.debug(f"Learning loop skipped: {e}")

    # ── Intelligence ───────────────────────────────────────────────────────

    def get_report(self) -> FedCommentReport:
        """Build comprehensive report using weighted tone analysis."""
        # 1. Fetch new + recent comments
        new_comments = self.fetch_comments(hours=24)
        recent_comments = self.db.get_recent_comments(hours=24, limit=20)

        # 2. Deduplicate
        seen = {}
        for c in new_comments + recent_comments:
            if c.comment_hash not in seen:
                seen[c.comment_hash] = c
        comments = list(seen.values())

        # 3. Weighted tone aggregation (not simple counting)
        tone_result = self.tone_aggregator.aggregate(
            comments, impact_learner=self.impact_learner
        )

        # 4. Build report with data-driven recommendations
        return self.report_builder.build(comments, tone_result)

    # ── Backward-Compatible API ────────────────────────────────────────────

    def get_latest_comment(self, official_name: Optional[str] = None) -> Optional[FedComment]:
        """Get most recent comment (optionally for a specific official)."""
        comments = self.db.get_recent_comments(hours=24, limit=1)
        if comments:
            if official_name:
                return next(
                    (c for c in comments if c.official_name == official_name),
                    None
                )
            return comments[0]
        return None

    def print_report(self, report: Optional[FedCommentReport] = None):
        """Legacy print method — kept for backward compatibility."""
        if report is None:
            report = self.get_report()

        sent_emoji = {"HAWKISH": "🦅", "DOVISH": "🕊️", "MIXED": "⚖️", "NEUTRAL": "➡️"}.get(
            report.overall_sentiment, "❓"
        )
        bias_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(
            report.market_bias, "❓"
        )

        print(f"\n{'=' * 80}")
        print(f"  {sent_emoji} OVERALL: {report.overall_sentiment} | "
              f"{bias_emoji} BIAS: {report.market_bias} | "
              f"Confidence: {report.confidence:.0%}")
        print(f"  💡 {report.recommendation}")

        if report.suggested_positions:
            for pos in report.suggested_positions:
                print(f"     → {pos}")

        if report.comments:
            print(f"\n  📢 RECENT ({len(report.comments)} comments):")
            for i, c in enumerate(report.comments[:5], 1):
                emoji = {"HAWKISH": "🦅", "DOVISH": "🕊️", "NEUTRAL": "➡️"}.get(
                    c.sentiment, "❓"
                )
                print(f"  {i}. {emoji} {c.official_name}: {c.sentiment} "
                      f"({c.sentiment_confidence*100:.0f}%)")
        print(f"{'=' * 80}\n")
