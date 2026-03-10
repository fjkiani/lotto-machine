"""
⚖️ Tone Aggregator — Weighted Fed Sentiment Scoring
=====================================================
Not simple counting. Weights by official seniority and historical market impact.
Powell HAWKISH ≠ Regional President HAWKISH.
"""

import logging
import sqlite3
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default seniority weights — used when ImpactLearner has no data yet
SENIORITY_WEIGHTS = {
    "CHAIR": 5.0,
    "VICE_CHAIR": 3.5,
    "GOVERNOR": 2.5,
    "REGIONAL_PRESIDENT": 1.5,
    "FOMC_MEMBER": 1.0,
    "UNKNOWN": 1.0,
}

# Known Fed leaders (fallback for when OfficialTracker hasn't learned yet)
KNOWN_LEADERS = {
    "Powell": "CHAIR",
    "Jefferson": "VICE_CHAIR",
    "Barr": "VICE_CHAIR",
    "Bowman": "GOVERNOR",
    "Cook": "GOVERNOR",
    "Kugler": "GOVERNOR",
    "Waller": "GOVERNOR",
    "Williams": "REGIONAL_PRESIDENT",
    "Goolsbee": "REGIONAL_PRESIDENT",
    "Harker": "REGIONAL_PRESIDENT",
    "Bostic": "REGIONAL_PRESIDENT",
    "Daly": "REGIONAL_PRESIDENT",
    "Musalem": "REGIONAL_PRESIDENT",
    "Hammack": "REGIONAL_PRESIDENT",
}


class ToneAggregator:
    """
    Weighted tone aggregation.
    
    Instead of: sum(1 if HAWKISH) vs sum(1 if DOVISH)
    Does:       sum(weight * confidence) per tone bucket
    
    Weight = official seniority × historical market impact
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def aggregate(self, comments: List[Any], impact_learner=None) -> Dict[str, Any]:
        """
        Aggregate tone from a list of comments with weighted scoring.
        
        Returns:
            {
                "overall_tone": "HAWKISH" | "DOVISH" | "NEUTRAL" | "MIXED",
                "confidence": 0.0-1.0,
                "hawk_score": float,
                "dove_score": float,
                "breakdown": [{"official": ..., "tone": ..., "weight": ..., "reasoning": ...}],
                "reasoning": str,
            }
        """
        if not comments:
            return {
                "overall_tone": "NEUTRAL",
                "confidence": 0.0,
                "hawk_score": 0.0,
                "dove_score": 0.0,
                "breakdown": [],
                "reasoning": "No recent Fed comments detected",
            }

        hawk_score = 0.0
        dove_score = 0.0
        neutral_score = 0.0
        breakdown = []

        for comment in comments:
            name = getattr(comment, 'official_name', '') or ''
            sentiment = getattr(comment, 'sentiment', 'NEUTRAL') or 'NEUTRAL'
            confidence = getattr(comment, 'sentiment_confidence', 0.5) or 0.5

            # Determine weight
            weight = self._get_weight(name, sentiment, impact_learner)

            weighted = weight * confidence

            if sentiment == "HAWKISH":
                hawk_score += weighted
            elif sentiment == "DOVISH":
                dove_score += weighted
            else:
                neutral_score += weighted * 0.3  # Neutral contributes less

            breakdown.append({
                "official": name,
                "tone": sentiment,
                "weight": round(weight, 2),
                "confidence": round(confidence, 2),
                "weighted_score": round(weighted, 2),
            })

        # Determine overall tone
        total = hawk_score + dove_score + neutral_score
        if total == 0:
            overall = "NEUTRAL"
            conf = 0.0
        elif hawk_score > dove_score * 1.3:  # Need clear margin
            overall = "HAWKISH"
            conf = min(0.95, hawk_score / total)
        elif dove_score > hawk_score * 1.3:
            overall = "DOVISH"
            conf = min(0.95, dove_score / total)
        elif abs(hawk_score - dove_score) < 0.5:
            overall = "NEUTRAL"
            conf = 0.3
        else:
            overall = "MIXED"
            conf = 0.4

        # Build reasoning chain
        top_hawks = sorted(
            [b for b in breakdown if b["tone"] == "HAWKISH"],
            key=lambda x: x["weighted_score"], reverse=True
        )[:3]
        top_doves = sorted(
            [b for b in breakdown if b["tone"] == "DOVISH"],
            key=lambda x: x["weighted_score"], reverse=True
        )[:3]

        reasoning_parts = []
        if top_hawks:
            names = ", ".join(b["official"] or "Unknown" for b in top_hawks)
            reasoning_parts.append(f"Hawks ({hawk_score:.1f}): {names}")
        if top_doves:
            names = ", ".join(b["official"] or "Unknown" for b in top_doves)
            reasoning_parts.append(f"Doves ({dove_score:.1f}): {names}")

        reasoning = " | ".join(reasoning_parts) or "No clear signal"

        return {
            "overall_tone": overall,
            "confidence": round(conf, 2),
            "hawk_score": round(hawk_score, 2),
            "dove_score": round(dove_score, 2),
            "breakdown": breakdown,
            "reasoning": reasoning,
        }

    def _get_weight(self, official_name: str, sentiment: str, impact_learner=None) -> float:
        """
        Get weight for an official's comment.
        
        Priority:
        1. Learned market impact (from ImpactLearner DB data)
        2. Known seniority weight (KNOWN_LEADERS)
        3. Default = 1.0
        """
        # Try learned weight from ImpactLearner
        if impact_learner:
            try:
                _, learned_conf, _ = impact_learner.predict_impact(official_name, sentiment)
                if learned_conf and learned_conf > 0.3:
                    # Scale learned confidence to weight (0.3-1.0 → 1.0-5.0)
                    return 1.0 + (learned_conf * 4.0)
            except Exception:
                pass

        # Fallback to seniority
        for last_name, position in KNOWN_LEADERS.items():
            if last_name.lower() in official_name.lower():
                return SENIORITY_WEIGHTS.get(position, 1.0)

        return 1.0
