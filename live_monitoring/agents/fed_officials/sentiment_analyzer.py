"""
🧠 LLM-Based Sentiment Analyzer - Not Keyword Matching!
========================================================
Uses LLM to understand context, not just keyword counting.
"""

import logging
import os
from datetime import datetime
from typing import Tuple
from .database import FedOfficialsDatabase

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """LLM-based sentiment analysis (learns from patterns)."""
    
    def __init__(self, database: FedOfficialsDatabase):
        self.db = database
        self.llm_client = None
        
        # Try to load LLM client
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            # Try Perplexity first (we already have it)
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if api_key:
                import sys
                base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
                sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'enrichment', 'apis'))
                from perplexity_search import PerplexitySearchClient
                self.llm_client = PerplexitySearchClient(api_key=api_key)
                logger.info("✅ LLM client initialized for sentiment analysis")
        except Exception as e:
            logger.warning(f"LLM client not available: {e}")
    
    def analyze(self, text: str, official_name: str) -> Tuple[str, float, str]:
        """
        Analyze sentiment using LLM (not keywords!).
        
        Returns: (sentiment, confidence, reasoning)
        """
        # First, check learned patterns
        patterns = self.db.get_sentiment_patterns(limit=20)
        for pattern in patterns:
            if pattern.phrase.lower() in text.lower():
                # Found a learned pattern
                logger.debug(f"Using learned pattern: {pattern.phrase} → {pattern.sentiment}")
                return pattern.sentiment, pattern.confidence, f"Matched pattern: {pattern.phrase}"
        
        # If no pattern, use LLM
        if self.llm_client:
            return self._analyze_with_llm(text, official_name)
        else:
            # Fallback to simple keyword matching (temporary)
            return self._analyze_fallback(text)
    
    def _analyze_with_llm(self, text: str, official_name: str) -> Tuple[str, float, str]:
        """Use LLM to analyze sentiment."""
        prompt = f"""
Analyze this Fed official comment for monetary policy sentiment.

Official: {official_name}
Comment: "{text}"

Determine if this is:
- HAWKISH (suggests higher rates, fighting inflation, restrictive policy)
- DOVISH (suggests lower rates, easing, accommodative policy)
- NEUTRAL (data-dependent, balanced, no clear direction)

Respond in JSON format:
{{
    "sentiment": "HAWKISH|DOVISH|NEUTRAL",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
}}
"""
        try:
            result = self.llm_client.search(prompt)
            if result and 'answer' in result:
                answer = result['answer']
                
                # Parse JSON from answer
                import json
                import re
                
                # Try to extract JSON
                json_match = re.search(r'\{[^}]+\}', answer)
                if json_match:
                    data = json.loads(json_match.group())
                    sentiment = data.get('sentiment', 'NEUTRAL')
                    confidence = float(data.get('confidence', 0.5))
                    reasoning = data.get('reasoning', 'LLM analysis')
                    
                    # Learn this pattern
                    if len(text) < 100:  # Only learn short phrases
                        from .models import SentimentPattern
                        pattern = SentimentPattern(
                            phrase=text[:50],
                            sentiment=sentiment,
                            confidence=confidence,
                            sample_count=1,
                            last_seen=datetime.now()
                        )
                        self.db.save_sentiment_pattern(pattern)
                    
                    return sentiment, confidence, reasoning
            
            # Fallback if LLM fails
            return self._analyze_fallback(text)
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            return self._analyze_fallback(text)
    
    def _analyze_fallback(self, text: str) -> Tuple[str, float, str]:
        """Fallback keyword matching (temporary until LLM works)."""
        text_lower = text.lower()
        
        hawkish_phrases = [
            "rate hike", "raise rates", "higher rates", "inflation concerns",
            "too high inflation", "persistent inflation", "more work to do",
            "not ready to cut", "premature to cut", "inflation sticky",
        ]
        
        dovish_phrases = [
            "rate cut", "lower rates", "cutting rates", "inflation falling",
            "inflation progress", "labor market cooling", "easing",
            "ready to cut", "appropriate to cut", "less restrictive",
        ]
        
        hawk_count = sum(1 for phrase in hawkish_phrases if phrase in text_lower)
        dove_count = sum(1 for phrase in dovish_phrases if phrase in text_lower)
        
        if hawk_count > dove_count:
            return "HAWKISH", 0.5 + (hawk_count * 0.1), f"Found {hawk_count} hawkish phrases"
        elif dove_count > hawk_count:
            return "DOVISH", 0.5 + (dove_count * 0.1), f"Found {dove_count} dovish phrases"
        else:
            return "NEUTRAL", 0.3, "No clear signal"

