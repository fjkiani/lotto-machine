#!/usr/bin/env python3
"""
TRUMP PULSE - "What's happening RIGHT NOW?"

This module answers: What has Trump said/done in the last 24 hours?
Returns: Latest statements, sentiment, and immediate market implications.

Usage:
    from trump_pulse import TrumpPulse
    pulse = TrumpPulse()
    situation = pulse.get_current_situation()
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trump_database import TrumpDatabase
from trump_data_models import TrumpStatement

logger = logging.getLogger(__name__)


@dataclass
class TrumpActivity:
    """Single Trump activity/statement."""
    timestamp: datetime
    source: str
    summary: str
    topics: List[str]
    sentiment: float  # -1 to +1
    market_impact: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float


@dataclass
class TrumpSituation:
    """Current Trump situation report."""
    as_of: datetime = field(default_factory=datetime.now)
    
    # Activity summary
    total_statements_24h: int = 0
    latest_statement: Optional[TrumpActivity] = None
    all_activities: List[TrumpActivity] = field(default_factory=list)
    
    # Aggregate sentiment
    overall_sentiment: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    sentiment_score: float = 0.0  # -1 to +1
    
    # Hot topics
    hot_topics: List[str] = field(default_factory=list)
    
    # Market implication
    market_bias: str = "NEUTRAL"
    market_confidence: float = 0.0
    
    # Actionable insight
    executive_summary: str = ""
    recommended_action: str = "HOLD"  # BUY, SELL, HOLD, FADE


class TrumpPulse:
    """
    Real-time Trump activity monitor.
    Answers: "What's happening RIGHT NOW?"
    """
    
    def __init__(self):
        self.db = TrumpDatabase()
        logger.info("📡 TrumpPulse initialized")
    
    def _classify_sentiment(self, score: float) -> str:
        """Convert sentiment score to label."""
        if score > 0.3:
            return "BULLISH"
        elif score < -0.3:
            return "BEARISH"
        return "NEUTRAL"
    
    def _get_market_impact(self, topics: List[str], sentiment: float) -> tuple:
        """Determine market impact based on topics and historical patterns."""
        # Get learned correlations from database
        correlations = self.db.get_all_correlations()
        
        total_impact = 0.0
        impact_count = 0
        
        for topic in topics:
            for corr in correlations:
                if corr.topic.lower() == topic.lower():
                    total_impact += corr.avg_spy_change_1hr
                    impact_count += 1
        
        if impact_count > 0:
            avg_impact = total_impact / impact_count
            if avg_impact > 0.1:
                return "BULLISH", abs(avg_impact)
            elif avg_impact < -0.1:
                return "BEARISH", abs(avg_impact)
        
        # Fallback to sentiment
        if sentiment > 0.3:
            return "BULLISH", abs(sentiment) * 0.5
        elif sentiment < -0.3:
            return "BEARISH", abs(sentiment) * 0.5
        
        return "NEUTRAL", 0.3
    
    def get_current_situation(self, hours: int = 24) -> TrumpSituation:
        """
        Get current Trump situation report.
        
        Args:
            hours: Look back period (default 24 hours)
        
        Returns:
            TrumpSituation with complete current state
        """
        situation = TrumpSituation()
        
        # Get recent statements
        recent = self.db.get_recent_statements(hours=hours, limit=50)
        situation.total_statements_24h = len(recent)
        
        if not recent:
            situation.executive_summary = "No significant Trump activity in the last 24 hours."
            situation.recommended_action = "HOLD"
            return situation
        
        # Convert to TrumpActivity objects
        activities = []
        all_topics = []
        sentiment_scores = []
        
        for stmt in recent:
            market_impact, confidence = self._get_market_impact(stmt.topics, stmt.sentiment)
            
            activity = TrumpActivity(
                timestamp=stmt.timestamp,
                source=stmt.source,
                summary=stmt.raw_text[:200] + "..." if len(stmt.raw_text) > 200 else stmt.raw_text,
                topics=stmt.topics,
                sentiment=stmt.sentiment,
                market_impact=market_impact,
                confidence=confidence
            )
            activities.append(activity)
            all_topics.extend(stmt.topics)
            sentiment_scores.append(stmt.sentiment)
        
        situation.all_activities = activities
        situation.latest_statement = activities[0] if activities else None
        
        # Aggregate sentiment
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        situation.sentiment_score = avg_sentiment
        situation.overall_sentiment = self._classify_sentiment(avg_sentiment)
        
        # Hot topics (most frequent)
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        situation.hot_topics = sorted(topic_counts.keys(), key=lambda x: topic_counts[x], reverse=True)[:5]
        
        # Market bias (weighted by recency)
        bullish_count = sum(1 for a in activities if a.market_impact == "BULLISH")
        bearish_count = sum(1 for a in activities if a.market_impact == "BEARISH")
        
        if bullish_count > bearish_count * 1.5:
            situation.market_bias = "BULLISH"
            situation.market_confidence = bullish_count / len(activities) * 100
        elif bearish_count > bullish_count * 1.5:
            situation.market_bias = "BEARISH"
            situation.market_confidence = bearish_count / len(activities) * 100
        else:
            situation.market_bias = "NEUTRAL"
            situation.market_confidence = 50.0
        
        # Generate executive summary
        situation.executive_summary = self._generate_summary(situation)
        situation.recommended_action = self._get_recommended_action(situation)
        
        return situation
    
    def _generate_summary(self, situation: TrumpSituation) -> str:
        """Generate human-readable executive summary."""
        parts = []
        
        # Activity level
        if situation.total_statements_24h > 10:
            parts.append(f"HIGH ACTIVITY: {situation.total_statements_24h} statements in 24h")
        elif situation.total_statements_24h > 3:
            parts.append(f"MODERATE ACTIVITY: {situation.total_statements_24h} statements in 24h")
        else:
            parts.append(f"LOW ACTIVITY: {situation.total_statements_24h} statements in 24h")
        
        # Hot topics
        if situation.hot_topics:
            parts.append(f"Focus: {', '.join(situation.hot_topics[:3])}")
        
        # Sentiment
        parts.append(f"Sentiment: {situation.overall_sentiment} ({situation.sentiment_score:+.2f})")
        
        # Latest
        if situation.latest_statement:
            parts.append(f"Latest: \"{situation.latest_statement.summary[:80]}...\"")
        
        return " | ".join(parts)
    
    def _get_recommended_action(self, situation: TrumpSituation) -> str:
        """Determine recommended trading action."""
        # High confidence bearish = SHORT / defensive
        if situation.market_bias == "BEARISH" and situation.market_confidence > 70:
            return "DEFENSIVE"
        
        # High confidence bullish = LONG / aggressive
        if situation.market_bias == "BULLISH" and situation.market_confidence > 70:
            return "AGGRESSIVE"
        
        # Moderate bias = consider position
        if situation.market_bias == "BEARISH":
            return "CAUTIOUS"
        elif situation.market_bias == "BULLISH":
            return "OPPORTUNISTIC"
        
        return "HOLD"
    
    def print_situation(self, situation: Optional[TrumpSituation] = None):
        """Print formatted situation report."""
        if situation is None:
            situation = self.get_current_situation()
        
        print("\n" + "=" * 70)
        print("╔══════════════════════════════════════════════════════════════════════╗")
        print("║              📡 TRUMP PULSE - CURRENT SITUATION                       ║")
        print("╚══════════════════════════════════════════════════════════════════════╝")
        print(f"  As of: {situation.as_of.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Activity summary
        print(f"\n📊 ACTIVITY LEVEL: {situation.total_statements_24h} statements in last 24h")
        
        # Hot topics
        if situation.hot_topics:
            print(f"\n🔥 HOT TOPICS: {', '.join(situation.hot_topics)}")
        
        # Sentiment
        sentiment_emoji = "📈" if situation.overall_sentiment == "BULLISH" else "📉" if situation.overall_sentiment == "BEARISH" else "➡️"
        print(f"\n{sentiment_emoji} OVERALL SENTIMENT: {situation.overall_sentiment} ({situation.sentiment_score:+.2f})")
        
        # Market bias
        bias_emoji = "🟢" if situation.market_bias == "BULLISH" else "🔴" if situation.market_bias == "BEARISH" else "🟡"
        print(f"\n{bias_emoji} MARKET BIAS: {situation.market_bias} ({situation.market_confidence:.0f}% confidence)")
        
        # Latest statement
        if situation.latest_statement:
            print(f"\n📰 LATEST ({situation.latest_statement.timestamp.strftime('%H:%M')}):")
            print(f"   \"{situation.latest_statement.summary}\"")
            print(f"   Topics: {', '.join(situation.latest_statement.topics) if situation.latest_statement.topics else 'N/A'}")
            print(f"   Impact: {situation.latest_statement.market_impact}")
        
        # Executive summary
        print(f"\n📋 EXECUTIVE SUMMARY:")
        print(f"   {situation.executive_summary}")
        
        # Recommended action
        action_emoji = {
            "AGGRESSIVE": "🚀",
            "OPPORTUNISTIC": "👀",
            "HOLD": "✋",
            "CAUTIOUS": "⚠️",
            "DEFENSIVE": "🛡️"
        }.get(situation.recommended_action, "❓")
        
        print(f"\n{action_emoji} RECOMMENDED ACTION: {situation.recommended_action}")
        
        print("\n" + "=" * 70)


def main():
    """Demo the Trump Pulse."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    pulse = TrumpPulse()
    situation = pulse.get_current_situation()
    pulse.print_situation(situation)


if __name__ == "__main__":
    main()

