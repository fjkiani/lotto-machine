"""
🧠 LLM-Based Sentiment Analyzer — Groq (Llama 3.3 70B)
========================================================
Migrated from Cohere (hanging/429) to Groq free tier.
Same structured JSON output, 10s timeout, keyword fallback.
"""

import logging
import json
import re
import os
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)

# ── Groq Config (same as signal_explainer.py) ──
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


class SentimentAnalyzer:
    """LLM-based sentiment analysis via Groq (migrated from Cohere)."""

    def __init__(self, database):
        self.db = database
        self._groq_key = None

        # Initialize Groq key
        try:
            from dotenv import load_dotenv
            load_dotenv()

            self._groq_key = os.getenv('GROQ_API_KEY', '')
            if self._groq_key:
                logger.info("✅ SentimentAnalyzer initialized (Groq Llama 3.3 70B)")
            else:
                logger.warning("GROQ_API_KEY not found. Sentiment analysis will use keyword fallback.")
        except Exception as e:
            logger.warning(f"Groq init failed: {e}")

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
            return self._analyze_with_groq(text, official_name)
        else:
            return self._analyze_fallback(text)

    def _analyze_with_groq(self, text: str, official_name: str) -> Tuple[str, float, str]:
        """Use Groq Llama 3.3 70B for sentiment analysis."""
        prompt = f"""Classify this Federal Reserve speech as HAWKISH, DOVISH, or NEUTRAL.
Return JSON only: {{"tone": "HAWKISH|DOVISH|NEUTRAL", "confidence": 0.0-1.0, "reasoning": "one sentence"}}

Official: {official_name}
Speech: {text[:1500]}"""

        try:
            import httpx
            resp = httpx.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self._groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": (
                            "You are a Fed monetary policy tone analyzer. "
                            "Analyze the text and return ONLY a JSON object. "
                            "No markdown, no explanation, no code blocks."
                        )},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 200,
                },
                timeout=10.0,
            )
            resp.raise_for_status()
            raw_text = resp.json()["choices"][0]["message"]["content"].strip()

            # Parse JSON from response
            json_match = re.search(r'\{[^}]+\}', raw_text)
            if json_match:
                data = json.loads(json_match.group())
                sentiment = data.get('tone', data.get('sentiment', 'NEUTRAL')).upper()
                confidence = float(data.get('confidence', 0.5))
                reasoning = data.get('reasoning', 'Groq analysis')

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

                logger.info(f"✅ Groq tone: {sentiment} ({confidence:.0%}) for {official_name}")
                return sentiment, confidence, reasoning

            logger.warning(f"Groq returned non-JSON: {raw_text[:100]}")
            return self._analyze_fallback(text)

        except Exception as e:
            logger.warning(f"Groq sentiment analysis failed: {e}")
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
