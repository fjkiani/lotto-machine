#!/usr/bin/env python3
"""
🎤 FED OFFICIALS MONITOR - Track Every Fed Mouth!

Monitors Fed officials' speeches and comments in real-time.
When Powell, Waller, Bowman, or ANY FOMC member says something about rates,
we want to be FIRST to know!

FOMC Members (2025):
- Jerome Powell (Chair)
- John Williams (Vice Chair NY Fed)
- Philip Jefferson (Vice Chair)
- Michelle Bowman (Governor)
- Christopher Waller (Governor)
- Lisa Cook (Governor)
- Adriana Kugler (Governor)
- Michael Barr (Vice Chair for Supervision)

Plus rotating regional Fed presidents

Usage:
    from fed_officials_monitor import FedOfficialsMonitor
    monitor = FedOfficialsMonitor()
    monitor.scan_for_fed_comments()
"""

import os
import sys
import json
import logging
import requests
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

logger = logging.getLogger(__name__)


# ============================================================================
# FOMC MEMBERS DATABASE
# ============================================================================

class FedPosition(Enum):
    CHAIR = "Chair"
    VICE_CHAIR = "Vice Chair"
    GOVERNOR = "Governor"
    REGIONAL_PRESIDENT = "Regional President"
    VICE_CHAIR_SUPERVISION = "Vice Chair for Supervision"


@dataclass
class FedOfficial:
    """FOMC member info."""
    name: str
    position: FedPosition
    voting_member: bool = True
    hawkish_dovish: str = "NEUTRAL"  # HAWKISH, DOVISH, NEUTRAL
    keywords: List[str] = field(default_factory=list)


# Current FOMC Members (2025)
FOMC_MEMBERS = [
    FedOfficial(
        name="Jerome Powell",
        position=FedPosition.CHAIR,
        voting_member=True,
        hawkish_dovish="NEUTRAL",
        keywords=["powell", "fed chair", "jerome powell", "chairman powell"]
    ),
    FedOfficial(
        name="John Williams",
        position=FedPosition.VICE_CHAIR,
        voting_member=True,
        hawkish_dovish="NEUTRAL",
        keywords=["williams", "john williams", "ny fed", "new york fed"]
    ),
    FedOfficial(
        name="Philip Jefferson",
        position=FedPosition.VICE_CHAIR,
        voting_member=True,
        hawkish_dovish="DOVISH",
        keywords=["jefferson", "philip jefferson", "fed vice chair"]
    ),
    FedOfficial(
        name="Michelle Bowman",
        position=FedPosition.GOVERNOR,
        voting_member=True,
        hawkish_dovish="HAWKISH",
        keywords=["bowman", "michelle bowman", "governor bowman"]
    ),
    FedOfficial(
        name="Christopher Waller",
        position=FedPosition.GOVERNOR,
        voting_member=True,
        hawkish_dovish="HAWKISH",
        keywords=["waller", "christopher waller", "governor waller", "chris waller"]
    ),
    FedOfficial(
        name="Lisa Cook",
        position=FedPosition.GOVERNOR,
        voting_member=True,
        hawkish_dovish="DOVISH",
        keywords=["lisa cook", "governor cook", "cook"]
    ),
    FedOfficial(
        name="Adriana Kugler",
        position=FedPosition.GOVERNOR,
        voting_member=True,
        hawkish_dovish="NEUTRAL",
        keywords=["kugler", "adriana kugler", "governor kugler"]
    ),
    FedOfficial(
        name="Michael Barr",
        position=FedPosition.VICE_CHAIR_SUPERVISION,
        voting_member=True,
        hawkish_dovish="NEUTRAL",
        keywords=["barr", "michael barr", "vice chair barr"]
    ),
    # Regional Fed Presidents (rotating voters)
    FedOfficial(
        name="Austan Goolsbee",
        position=FedPosition.REGIONAL_PRESIDENT,
        voting_member=True,  # 2025 voter
        hawkish_dovish="DOVISH",
        keywords=["goolsbee", "chicago fed", "austan goolsbee"]
    ),
    FedOfficial(
        name="Raphael Bostic",
        position=FedPosition.REGIONAL_PRESIDENT,
        voting_member=True,  # 2025 voter
        hawkish_dovish="NEUTRAL",
        keywords=["bostic", "atlanta fed", "raphael bostic"]
    ),
    FedOfficial(
        name="Mary Daly",
        position=FedPosition.REGIONAL_PRESIDENT,
        voting_member=False,
        hawkish_dovish="DOVISH",
        keywords=["daly", "sf fed", "san francisco fed", "mary daly"]
    ),
    FedOfficial(
        name="Neel Kashkari",
        position=FedPosition.REGIONAL_PRESIDENT,
        voting_member=False,
        hawkish_dovish="DOVISH",
        keywords=["kashkari", "minneapolis fed", "neel kashkari"]
    ),
    FedOfficial(
        name="Loretta Mester",
        position=FedPosition.REGIONAL_PRESIDENT,
        voting_member=False,
        hawkish_dovish="HAWKISH",
        keywords=["mester", "cleveland fed", "loretta mester"]
    ),
    FedOfficial(
        name="James Bullard",
        position=FedPosition.REGIONAL_PRESIDENT,
        voting_member=False,
        hawkish_dovish="HAWKISH",
        keywords=["bullard", "st louis fed", "james bullard"]
    ),
]


# Rate-related keywords
RATE_KEYWORDS = {
    "hawkish": [
        "rate hike", "raise rates", "higher rates", "inflation concerns",
        "too high inflation", "persistent inflation", "more work to do",
        "not ready to cut", "premature to cut", "inflation sticky",
        "wage pressures", "tight labor market", "restrictive policy",
        "above target", "higher for longer"
    ],
    "dovish": [
        "rate cut", "lower rates", "cutting rates", "inflation falling",
        "inflation progress", "labor market cooling", "easing",
        "more balanced risks", "downside risks", "ready to cut",
        "appropriate to cut", "less restrictive", "normalize rates",
        "soft landing", "disinflation"
    ],
    "neutral": [
        "data dependent", "watching data", "meeting by meeting",
        "balanced approach", "both sides", "uncertain outlook",
        "wait and see"
    ]
}


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class FedComment:
    """A Fed official's comment/speech."""
    timestamp: datetime
    official: FedOfficial
    headline: str
    content: str
    source: str
    url: Optional[str] = None
    
    # Analysis
    sentiment: str = "NEUTRAL"  # HAWKISH, DOVISH, NEUTRAL
    market_impact: str = "UNKNOWN"  # BULLISH, BEARISH, NEUTRAL
    confidence: float = 0.0
    
    # Keywords detected
    hawkish_keywords: List[str] = field(default_factory=list)
    dovish_keywords: List[str] = field(default_factory=list)


@dataclass
class FedCommentReport:
    """Report of Fed comments."""
    timestamp: datetime = field(default_factory=datetime.now)
    comments: List[FedComment] = field(default_factory=list)
    overall_sentiment: str = "NEUTRAL"
    market_bias: str = "NEUTRAL"
    recommendation: str = ""


# ============================================================================
# FED OFFICIALS MONITOR
# ============================================================================

class FedOfficialsMonitor:
    """
    Monitors Fed officials' speeches and comments for rate signals.
    """
    
    def __init__(self):
        self.members = {m.name: m for m in FOMC_MEMBERS}
        self.recent_comments: List[FedComment] = []
        
        # Try to load Perplexity for news fetching
        self.perplexity_client = None
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if api_key:
                sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'enrichment', 'apis'))
                from perplexity_search import PerplexitySearchClient
                self.perplexity_client = PerplexitySearchClient(api_key=api_key)
                logger.info("✅ Perplexity client initialized for Fed monitoring")
        except Exception as e:
            logger.warning(f"Perplexity not available: {e}")
        
        logger.info("🎤 FedOfficialsMonitor initialized")
        logger.info(f"   Tracking {len(self.members)} FOMC members")
    
    def _identify_official(self, text: str) -> Optional[FedOfficial]:
        """Identify which Fed official is mentioned in text."""
        text_lower = text.lower()
        
        for member in FOMC_MEMBERS:
            for keyword in member.keywords:
                if keyword in text_lower:
                    return member
        
        return None
    
    def _analyze_sentiment(self, text: str) -> Tuple[str, List[str], List[str], float]:
        """
        Analyze text for hawkish/dovish signals.
        Returns: (sentiment, hawkish_keywords, dovish_keywords, confidence)
        """
        text_lower = text.lower()
        
        hawkish_found = []
        dovish_found = []
        neutral_found = []
        
        for keyword in RATE_KEYWORDS["hawkish"]:
            if keyword in text_lower:
                hawkish_found.append(keyword)
        
        for keyword in RATE_KEYWORDS["dovish"]:
            if keyword in text_lower:
                dovish_found.append(keyword)
        
        for keyword in RATE_KEYWORDS["neutral"]:
            if keyword in text_lower:
                neutral_found.append(keyword)
        
        # Calculate sentiment
        hawk_score = len(hawkish_found)
        dove_score = len(dovish_found)
        
        if hawk_score > dove_score + 1:
            sentiment = "HAWKISH"
            confidence = min(0.9, 0.5 + (hawk_score - dove_score) * 0.1)
        elif dove_score > hawk_score + 1:
            sentiment = "DOVISH"
            confidence = min(0.9, 0.5 + (dove_score - hawk_score) * 0.1)
        else:
            sentiment = "NEUTRAL"
            confidence = 0.3 + len(neutral_found) * 0.1
        
        return sentiment, hawkish_found, dovish_found, confidence
    
    def _get_market_impact(self, sentiment: str, official: FedOfficial) -> str:
        """
        Determine market impact based on comment sentiment and official's position.
        """
        # Weight by position importance
        weight = 1.0
        if official.position == FedPosition.CHAIR:
            weight = 2.0  # Powell moves markets most
        elif official.position == FedPosition.VICE_CHAIR:
            weight = 1.5
        elif official.voting_member:
            weight = 1.2
        
        # Hawkish = bearish for stocks (higher rates)
        # Dovish = bullish for stocks (lower rates)
        if sentiment == "HAWKISH":
            return "BEARISH"
        elif sentiment == "DOVISH":
            return "BULLISH"
        else:
            return "NEUTRAL"
    
    def fetch_fed_comments(self) -> List[FedComment]:
        """
        Fetch recent Fed official comments from news sources.
        """
        comments = []
        
        if not self.perplexity_client:
            logger.warning("No Perplexity client - using fallback")
            return comments
        
        # Search for recent Fed comments
        queries = [
            "What did Federal Reserve officials say about interest rates today?",
            "Recent comments from Fed Chair Powell on rate cuts or hikes",
            "FOMC members statements on monetary policy today",
            "Fed governor speeches about inflation and rates"
        ]
        
        for query in queries:
            try:
                result = self.perplexity_client.search(query)
                
                if result and 'answer' in result:
                    answer = result['answer']
                    
                    # Try to parse out individual comments
                    # Look for official names and extract their statements
                    for member in FOMC_MEMBERS:
                        for keyword in member.keywords[:2]:  # Use first 2 keywords
                            if keyword.lower() in answer.lower():
                                # Extract context around the mention
                                start_idx = max(0, answer.lower().find(keyword.lower()) - 50)
                                end_idx = min(len(answer), answer.lower().find(keyword.lower()) + 300)
                                context = answer[start_idx:end_idx]
                                
                                # Analyze sentiment
                                sentiment, hawk_kw, dove_kw, confidence = self._analyze_sentiment(context)
                                
                                # Create comment
                                comment = FedComment(
                                    timestamp=datetime.now(),
                                    official=member,
                                    headline=f"{member.name} comments on monetary policy",
                                    content=context,
                                    source="Perplexity",
                                    sentiment=sentiment,
                                    market_impact=self._get_market_impact(sentiment, member),
                                    confidence=confidence,
                                    hawkish_keywords=hawk_kw,
                                    dovish_keywords=dove_kw
                                )
                                
                                # Avoid duplicates
                                if not any(c.official.name == member.name and c.content == context for c in comments):
                                    comments.append(comment)
                                break
                
            except Exception as e:
                logger.warning(f"Query failed: {e}")
        
        return comments
    
    def fetch_cme_fedwatch_data(self) -> Dict:
        """
        Fetch actual CME FedWatch probabilities using Perplexity.
        """
        if not self.perplexity_client:
            return {}
        
        try:
            query = """
            What are the exact current CME FedWatch probabilities for the December 2025 FOMC meeting?
            Give me the specific percentages for:
            1. Probability of a rate CUT (25bps or more)
            2. Probability of NO CHANGE (hold)
            3. Probability of a rate HIKE
            Also mention the current fed funds rate target range.
            """
            
            result = self.perplexity_client.search(query)
            
            if result and 'answer' in result:
                answer = result['answer']
                
                # Parse percentages
                data = {
                    'source': 'CME FedWatch via Perplexity',
                    'raw_answer': answer,
                    'prob_cut': 0.0,
                    'prob_hold': 0.0,
                    'prob_hike': 0.0
                }
                
                # Look for percentage patterns
                import re
                percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', answer.lower())
                
                # Try to associate percentages with actions
                cut_match = re.search(r'cut[^\d]*(\d+(?:\.\d+)?)\s*%', answer.lower())
                hold_match = re.search(r'(?:hold|no change|unchanged)[^\d]*(\d+(?:\.\d+)?)\s*%', answer.lower())
                hike_match = re.search(r'(?:hike|increase|raise)[^\d]*(\d+(?:\.\d+)?)\s*%', answer.lower())
                
                if cut_match:
                    data['prob_cut'] = float(cut_match.group(1))
                if hold_match:
                    data['prob_hold'] = float(hold_match.group(1))
                if hike_match:
                    data['prob_hike'] = float(hike_match.group(1))
                
                # If we found percentages but couldn't parse, try to infer
                if data['prob_cut'] == 0 and data['prob_hold'] == 0 and percentages:
                    # Common patterns: "X% chance of cut", "hold at X%"
                    for pct in percentages[:3]:
                        pct_val = float(pct)
                        if pct_val > 50 and data['prob_hold'] == 0:
                            data['prob_hold'] = pct_val
                        elif pct_val > 20 and data['prob_cut'] == 0:
                            data['prob_cut'] = pct_val
                
                return data
                
        except Exception as e:
            logger.warning(f"CME FedWatch fetch failed: {e}")
        
        return {}
    
    def get_report(self) -> FedCommentReport:
        """
        Get comprehensive Fed officials report.
        """
        report = FedCommentReport()
        
        # Fetch comments
        comments = self.fetch_fed_comments()
        report.comments = comments
        
        # Calculate overall sentiment
        if comments:
            hawk_count = sum(1 for c in comments if c.sentiment == "HAWKISH")
            dove_count = sum(1 for c in comments if c.sentiment == "DOVISH")
            
            if hawk_count > dove_count:
                report.overall_sentiment = "HAWKISH"
                report.market_bias = "BEARISH"
                report.recommendation = "Fed officials leaning hawkish - consider defensive positioning"
            elif dove_count > hawk_count:
                report.overall_sentiment = "DOVISH"
                report.market_bias = "BULLISH"
                report.recommendation = "Fed officials leaning dovish - risk-on positioning favored"
            else:
                report.overall_sentiment = "MIXED"
                report.market_bias = "NEUTRAL"
                report.recommendation = "Mixed Fed signals - wait for clarity"
        else:
            report.recommendation = "No recent Fed comments detected"
        
        return report
    
    def print_fed_officials_report(self, report: Optional[FedCommentReport] = None):
        """Print formatted Fed officials report."""
        if report is None:
            report = self.get_report()
        
        print("\n" + "=" * 80)
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║              🎤 FED OFFICIALS MONITOR - WHO SAID WHAT?                         ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        print(f"  Updated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Overall sentiment
        sent_emoji = {"HAWKISH": "🦅", "DOVISH": "🕊️", "MIXED": "⚖️", "NEUTRAL": "➡️"}.get(report.overall_sentiment, "❓")
        bias_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(report.market_bias, "❓")
        
        print(f"\n  {sent_emoji} OVERALL FED SENTIMENT: {report.overall_sentiment}")
        print(f"  {bias_emoji} MARKET BIAS: {report.market_bias}")
        print(f"  💡 {report.recommendation}")
        
        # FOMC Members cheat sheet
        print(f"\n  📋 FOMC MEMBERS CHEAT SHEET:")
        print(f"     🦅 HAWKS (want higher rates): Bowman, Waller, Mester")
        print(f"     🕊️  DOVES (want lower rates): Jefferson, Cook, Goolsbee, Kashkari, Daly")
        print(f"     ➡️  NEUTRAL: Powell, Williams, Kugler, Bostic")
        
        # Recent comments
        if report.comments:
            print(f"\n  📢 RECENT FED COMMENTS ({len(report.comments)} detected):")
            
            for i, comment in enumerate(report.comments[:5], 1):
                sent_emoji = {"HAWKISH": "🦅", "DOVISH": "🕊️", "NEUTRAL": "➡️"}.get(comment.sentiment, "❓")
                position = comment.official.position.value
                
                print(f"\n  {i}. {sent_emoji} {comment.official.name} ({position})")
                print(f"     Sentiment: {comment.sentiment} | Impact: {comment.market_impact}")
                
                # Truncate content
                content = comment.content[:150] + "..." if len(comment.content) > 150 else comment.content
                print(f"     📝 \"{content}\"")
                
                if comment.hawkish_keywords:
                    print(f"     🦅 Hawkish keywords: {', '.join(comment.hawkish_keywords[:3])}")
                if comment.dovish_keywords:
                    print(f"     🕊️  Dovish keywords: {', '.join(comment.dovish_keywords[:3])}")
        else:
            print(f"\n  📭 No recent Fed comments detected")
            print(f"     Check back after Fed speeches or interviews")
        
        # Trading implications
        print(f"\n  💰 TRADING IMPLICATIONS:")
        if report.market_bias == "BULLISH":
            print(f"     🟢 LONG: Tech (QQQ), Growth, Real Estate (XLRE)")
            print(f"     🟢 LONG: Bonds (TLT) - prices rise when rates expected to fall")
            print(f"     ⚠️ WATCH: Banks (XLF) may underperform")
        elif report.market_bias == "BEARISH":
            print(f"     🔴 CAUTION: Reduce exposure to rate-sensitive growth")
            print(f"     🟢 LONG: Banks (XLF), Value stocks")
            print(f"     🔴 SHORT/AVOID: Long duration bonds (TLT)")
        else:
            print(f"     ⏳ WAIT: Mixed signals - stay nimble")
            print(f"     🛡️ HEDGE: Consider options for protection")
        
        # Upcoming Fed events
        print(f"\n  📅 KEY FED EVENTS TO WATCH:")
        print(f"     • FOMC Meeting: December 16-17, 2025")
        print(f"     • Powell Press Conference: After decision")
        print(f"     • Dot Plot Update: Quarterly projection")
        
        print("\n" + "=" * 80)
        print("  💡 TIP: Powell's tone matters more than actual rate decision!")
        print("=" * 80 + "\n")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Demo the Fed Officials Monitor."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    monitor = FedOfficialsMonitor()
    
    # Get CME FedWatch data
    print("\n🏦 Fetching CME FedWatch data...")
    fedwatch = monitor.fetch_cme_fedwatch_data()
    if fedwatch:
        print(f"   Cut: {fedwatch.get('prob_cut', 0):.1f}%")
        print(f"   Hold: {fedwatch.get('prob_hold', 0):.1f}%")
        print(f"   Hike: {fedwatch.get('prob_hike', 0):.1f}%")
    
    # Get Fed officials report
    print("\n🎤 Scanning for Fed official comments...")
    report = monitor.get_report()
    monitor.print_fed_officials_report(report)


if __name__ == "__main__":
    main()

