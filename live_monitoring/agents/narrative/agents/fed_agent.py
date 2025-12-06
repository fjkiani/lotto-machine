"""
🏦 FED NARRATIVE AGENT
======================
Deep research on Fed policy, FOMC, rate expectations.

Searches:
- Federal Reserve official statements
- FOMC meeting minutes
- Fed officials' speeches
- Rate probability analysis
- Economic projections
"""

import logging
from typing import Dict, Any, List
from .base_agent import BaseNarrativeAgent, AgentResult

logger = logging.getLogger(__name__)


class FedNarrativeAgent(BaseNarrativeAgent):
    """
    Specialized agent for Federal Reserve intelligence.
    
    Focuses on:
    - What Fed officials are REALLY saying (not headlines)
    - Rate cut/hike probability drivers
    - FOMC sentiment shifts
    - Economic data the Fed is watching
    """
    
    def __init__(self, tavily_client):
        super().__init__(tavily_client, name="FedAgent", domain="FED")
        
        # Fed officials to track
        self.key_officials = [
            "Jerome Powell",
            "John Williams",
            "Christopher Waller",
            "Michelle Bowman",
            "Raphael Bostic",
            "Mary Daly",
            "Austan Goolsbee",
            "Neel Kashkari",
        ]
    
    def research(self, context: Dict[str, Any]) -> AgentResult:
        """
        Research Fed policy and sentiment - GET THE REAL WHY.
        
        Args:
            context: {
                'fed_cut_prob': float,  # Current cut probability
                'fed_sentiment': str,   # DOVISH/HAWKISH/NEUTRAL
                'symbol': str,          # Symbol being analyzed
            }
        """
        self.logger.info("🏦 FedAgent researching...")
        
        # Handle None values properly
        fed_cut_prob = context.get('fed_cut_prob')
        if fed_cut_prob is None:
            fed_cut_prob = 50  # Default to neutral
        fed_sentiment = context.get('fed_sentiment', 'NEUTRAL')
        
        # SPECIFIC queries - we want the WHY, not generic news
        queries = [
            "Why is the Federal Reserve cutting rates December 2025 what economic data is driving this decision specific reasons",
            "Fed December 2025 unemployment jobs data inflation numbers driving rate decision",
        ]
        
        all_content = []
        all_sources = []
        raw_answers = []  # Store raw Tavily answers
        
        for query in queries:
            try:
                result = self.tavily.search_fed(query, max_results=3)
                if result.answer:
                    raw_answers.append(result.answer)
                # Also get the source content (the REAL shit)
                for r in result.results[:2]:
                    if r.content:
                        all_content.append(r.content)
                all_sources.extend(result.top_sources)
            except Exception as e:
                self.logger.warning(f"Fed query failed: {e}")
        
        # Use RAW Tavily answer as the summary - not our filtered garbage
        if raw_answers:
            summary = raw_answers[0][:200]  # First 200 chars of raw answer
        else:
            summary = f"Fed {fed_cut_prob:.0f}% cut probability"
        
        # Full context is ALL the content
        full_context = "\n\n".join(all_content) if all_content else ""
        
        # Extract SPECIFIC key points from raw content
        key_points = self._extract_specific_fed_points(full_context)
        
        # Determine bias
        bias = self._determine_fed_bias(full_context, fed_cut_prob)
        
        # Calculate confidence
        confidence = 0.8 if raw_answers else 0.4
        
        # Trade implication
        trade_implication = self._get_fed_trade_implication(bias, fed_cut_prob)
        
        return self._create_result(
            summary=summary,
            full_context=full_context,
            key_points=key_points,
            bias=bias,
            confidence=confidence,
            impact="HIGH",
            trade_implication=trade_implication,
            risk_factors=["FOMC meeting Dec 9-10", "Jobs data surprise risk"],
            sources=all_sources[:5]
        )
    
    def _extract_specific_fed_points(self, text: str) -> List[str]:
        """Extract SPECIFIC data points from Tavily content - not generic bullshit."""
        points = []
        text_lower = text.lower()
        
        # Look for SPECIFIC numbers and facts
        import re
        
        # Unemployment numbers
        unemployment_match = re.search(r'unemployment.*?(\d+\.?\d*)%', text_lower)
        if unemployment_match:
            points.append(f"Unemployment at {unemployment_match.group(1)}%")
        
        # Job numbers
        job_match = re.search(r'(\d+[,\d]*)\s*(job|jobs|private.sector)', text_lower)
        if job_match:
            points.append(f"Jobs: {job_match.group(1)} {job_match.group(2)}")
        
        # Rate numbers
        rate_match = re.search(r'(\d+\.?\d*)\s*(?:bps|basis points|%)', text_lower)
        if rate_match and 'rate' in text_lower:
            points.append(f"Rate move: {rate_match.group(1)}%")
        
        # Inflation
        if 'inflation' in text_lower:
            if 'elevated' in text_lower:
                points.append("Inflation still elevated")
            elif 'easing' in text_lower or 'cooling' in text_lower:
                points.append("Inflation easing")
        
        # Job market
        if 'job gains' in text_lower and 'slowing' in text_lower:
            points.append("Job gains slowing")
        if 'labor market' in text_lower and ('weak' in text_lower or 'soft' in text_lower):
            points.append("Labor market weakening")
        
        # If we found nothing specific, fall back to keywords
        if not points:
            if 'cut' in text_lower:
                points.append("Rate cut expected")
            if 'hold' in text_lower:
                points.append("Rate hold possible")
        
        return points[:5]
    
    def _extract_fed_points(self, text: str, fed_cut_prob: float) -> List[str]:
        """Extract key Fed-related points."""
        points = []
        
        # Add probability context
        if fed_cut_prob > 80:
            points.append(f"Rate cut nearly certain ({fed_cut_prob:.0f}% probability)")
        elif fed_cut_prob > 60:
            points.append(f"Rate cut likely ({fed_cut_prob:.0f}% probability)")
        elif fed_cut_prob < 30:
            points.append(f"Fed likely holding ({100-fed_cut_prob:.0f}% hold probability)")
        
        # Extract from content
        text_lower = text.lower()
        
        if "inflation" in text_lower:
            if "sticky" in text_lower or "persistent" in text_lower:
                points.append("Fed watching sticky inflation")
            elif "cooling" in text_lower or "declining" in text_lower:
                points.append("Inflation cooling - supports cuts")
        
        if "labor" in text_lower or "employment" in text_lower:
            if "strong" in text_lower or "tight" in text_lower:
                points.append("Labor market still strong")
            elif "softening" in text_lower or "weak" in text_lower:
                points.append("Labor market softening")
        
        if "dot plot" in text_lower:
            points.append("Dot plot projections being watched")
        
        if "data dependent" in text_lower:
            points.append("Fed remains data dependent")
        
        return points[:5]  # Max 5 points
    
    def _determine_fed_bias(self, text: str, fed_cut_prob: float) -> str:
        """Determine market bias from Fed context."""
        # High cut probability = DOVISH = BULLISH for stocks
        if fed_cut_prob > 70:
            return "BULLISH"
        elif fed_cut_prob < 30:
            return "BEARISH"
        
        # Check text for sentiment
        return self._extract_bias(text)
    
    def _build_fed_summary(self, fed_cut_prob: float, fed_sentiment: str, key_points: List[str]) -> str:
        """Build concise Fed summary."""
        parts = []
        
        if fed_cut_prob > 70:
            parts.append(f"Fed {fed_cut_prob:.0f}% DOVISH - rate cut expected")
        elif fed_cut_prob < 30:
            parts.append(f"Fed {fed_cut_prob:.0f}% HAWKISH - holding rates")
        else:
            parts.append(f"Fed {fed_cut_prob:.0f}% mixed signals")
        
        if key_points:
            parts.append(key_points[0])
        
        return " | ".join(parts)
    
    def _get_fed_trade_implication(self, bias: str, fed_cut_prob: float) -> str:
        """Get trading implication from Fed context."""
        if bias == "BULLISH":
            return f"Fed dovish ({fed_cut_prob:.0f}% cut) supports LONG equity positions, SHORT rates"
        elif bias == "BEARISH":
            return f"Fed hawkish ({100-fed_cut_prob:.0f}% hold) - risk to LONG positions, caution advised"
        return "Fed neutral - wait for clarity before major positions"

