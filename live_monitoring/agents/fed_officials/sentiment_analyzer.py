"""
🧠 LLM-Based Sentiment Analyzer — OpenRouter Nemotron 120B
==========================================================
Migrated from Groq to OpenRouter (2026-05-23).
Same structured JSON output, 10s timeout, keyword fallback.
"""

import logging
import json
import re
import os
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)

# ── OpenRouter Config (Nemotron 120B free) ──
from backend.app.graph.openrouter_client import _openrouter_post, NEMOTRON_MODEL, OPENROUTER_API_KEY


class SentimentAnalyzer:
    """LLM-based sentiment analysis via Groq (migrated from Cohere)."""

    def __init__(self, database):
        self.db = database
        self._groq_key = None

        # Initialize OpenRouter key
        try:
            from dotenv import load_dotenv
            load_dotenv()

            self._groq_key = OPENROUTER_API_KEY  # field name kept for compat
            if self._groq_key:
                logger.info("✅ SentimentAnalyzer initialized (OpenRouter Nemotron 120B)")
            else:
                logger.warning("OPENROUTER_API_KEY not found. Sentiment analysis will use keyword fallback.")
        except Exception as e:
            logger.warning(f"OpenRouter init failed: {e}")

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

        # If no pattern, use Groq LLM
        if self._groq_key:
            return self._analyze_with_openrouter(text, official_name)
        else:
            return self._analyze_fallback(text)

    def _analyze_with_openrouter(self, text: str, official_name: str) -> Tuple[str, float, str]:
        """Use OpenRouter Nemotron 120B for sentiment analysis."""
        prompt = f"""Classify this Federal Reserve speech as HAWKISH, DOVISH, or NEUTRAL.
Return JSON only: {{"tone": "HAWKISH|DOVISH|NEUTRAL", "confidence": 0.0-1.0, "reasoning": "one sentence"}}

Official: {official_name}
Speech: {text[:1500]}"""

        try:
            raw_text = _openrouter_post(
                messages=[
                    {"role": "system", "content": (
                        "You are a Fed monetary policy tone analyzer. "
                        "Analyze the text and return ONLY a JSON object. "
                        "No markdown, no explanation, no code blocks."
                    )},
                    {"role": "user", "content": prompt},
                ],
                model=NEMOTRON_MODEL,
                max_tokens=200,
                timeout=10,
            )
            if not raw_text:
                raise ValueError("empty response")
            raw_text = raw_text.strip()

            # Parse JSON from response
            json_match = re.search(r'\{[^}]+\}', raw_text)
            if json_match:
                data = json.loads(json_match.group())
                sentiment = data.get('tone', data.get('sentiment', 'NEUTRAL')).upper()
                confidence = float(data.get('confidence', 0.5))
                reasoning = data.get('reasoning', 'OpenRouter analysis')

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

                logger.info(f"✅ OpenRouter tone: {sentiment} ({confidence:.0%}) for {official_name}")
                return sentiment, confidence, reasoning

            logger.warning(f"OpenRouter returned non-JSON: {raw_text[:100]}")
            return self._analyze_fallback(text)

        except Exception as e:
            logger.warning(f"OpenRouter sentiment analysis failed: {e}")
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
