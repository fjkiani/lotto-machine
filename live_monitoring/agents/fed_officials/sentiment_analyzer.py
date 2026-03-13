"""
🧠 LLM-Based Sentiment Analyzer — Cohere command-a-reasoning
==============================================================
Uses the SAME Cohere model as NarrativeAgent. One brain, one model.
No more dead Perplexity, no more keyword fallback.
"""

import logging
import json
import re
import os
from datetime import datetime
from typing import Tuple
from .database import FedOfficialsDatabase

logger = logging.getLogger(__name__)

COHERE_MODEL = "command-a-reasoning-08-2025"


class SentimentAnalyzer:
    """LLM-based sentiment analysis via Cohere (same model as NarrativeAgent)."""
    
    def __init__(self, database: FedOfficialsDatabase):
        self.db = database
        self._cohere_client = None
        
        # Initialize Cohere — one brain, one model
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv('COHERE_API_KEY')
            if api_key:
                import cohere
                self._cohere_client = cohere.ClientV2(api_key=api_key)
                logger.info("✅ LLM client initialized for sentiment analysis (Cohere v2)")
            else:
                logger.warning("COHERE_API_KEY not found. Sentiment analysis will use keyword fallback.")
        except ImportError:
            logger.warning("cohere not installed — run: pip install cohere")
        except Exception as e:
            logger.warning(f"Cohere client not available: {e}")
    
    def analyze(self, text: str, official_name: str) -> Tuple[str, float, str]:
        """
        Analyze sentiment using LLM (not keywords!).
        
        Returns: (sentiment, confidence, reasoning)
        """
        # First, check learned patterns
        patterns = self.db.get_sentiment_patterns(limit=20)
        for pattern in patterns:
            if pattern.phrase.lower() in text.lower():
                logger.debug(f"Using learned pattern: {pattern.phrase} → {pattern.sentiment}")
                return pattern.sentiment, pattern.confidence, f"Matched pattern: {pattern.phrase}"
        
        # If no pattern, use Cohere LLM
        if self._cohere_client:
            return self._analyze_with_cohere(text, official_name)
        else:
            return self._analyze_fallback(text)
    
    def _analyze_with_cohere(self, text: str, official_name: str) -> Tuple[str, float, str]:
        """Use Cohere command-a-reasoning for sentiment analysis."""
        system_prompt = (
            "You are a Fed monetary policy tone analyzer. "
            "Analyze the text and return ONLY a JSON object. No markdown, no explanation."
        )
        
        user_prompt = f"""Analyze this Fed official comment for monetary policy sentiment.

Official: {official_name}
Comment: "{text[:2000]}"

Return ONLY this JSON:
{{
    "sentiment": "HAWKISH|DOVISH|NEUTRAL",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
}}"""
        
        try:
            response = self._cohere_client.chat(
                model=COHERE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            
            # Cohere V2 response - extract text from content blocks
            raw_text = ""
            msg = response.message
            if hasattr(msg, 'content') and msg.content:
                for block in msg.content:
                    if hasattr(block, 'text') and block.text:
                        raw_text += block.text
            elif hasattr(response, 'text'):
                raw_text = response.text
            
            # Parse JSON
            json_match = re.search(r'\{[^}]+\}', raw_text)
            if json_match:
                data = json.loads(json_match.group())
                sentiment = data.get('sentiment', 'NEUTRAL').upper()
                confidence = float(data.get('confidence', 0.5))
                reasoning = data.get('reasoning', 'Cohere analysis')
                
                # Learn this pattern for future fast lookups
                if len(text) < 100:
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
            
            return self._analyze_fallback(text)
        except Exception as e:
            logger.warning(f"Cohere sentiment analysis failed: {e}")
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

