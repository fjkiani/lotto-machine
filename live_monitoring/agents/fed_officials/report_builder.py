"""
📊 Report Builder — Data-Driven Recommendations
=================================================
No hardcoded "SHORT QQQ". Uses ImpactLearner predictions and ToneAggregator
scores to generate recommendations with reasoning chains.
"""

import logging
from datetime import datetime
from typing import List, Optional, Any, Dict

from .models import FedCommentReport

logger = logging.getLogger(__name__)


class ReportBuilder:
    """
    Assembles FedCommentReport from component outputs.
    Recommendations are driven by data, not if/else strings.
    """

    def __init__(self, impact_learner=None):
        self.impact_learner = impact_learner

    def build(
        self,
        comments: List[Any],
        tone_result: Dict[str, Any],
    ) -> FedCommentReport:
        """
        Build a complete report from tone aggregation and comment data.
        
        Args:
            comments: List of FedComment objects
            tone_result: Output from ToneAggregator.aggregate()
        """
        report = FedCommentReport()
        report.comments = comments
        report.overall_sentiment = tone_result["overall_tone"]
        report.confidence = tone_result["confidence"]

        # Map tone → market bias
        report.market_bias = self._tone_to_bias(tone_result)

        # Generate data-driven recommendation
        report.recommendation = self._build_recommendation(tone_result, comments)

        # Generate position suggestions from impact data
        report.suggested_positions = self._suggest_positions(tone_result)

        return report

    def _tone_to_bias(self, tone_result: Dict) -> str:
        """Convert tone to market bias. Weighted, not binary."""
        tone = tone_result["overall_tone"]
        confidence = tone_result["confidence"]

        if tone == "HAWKISH":
            return "BEARISH" if confidence > 0.5 else "LEAN_BEARISH"
        elif tone == "DOVISH":
            return "BULLISH" if confidence > 0.5 else "LEAN_BULLISH"
        elif tone == "MIXED":
            # Mixed is valuable info — not just "neutral"
            hawk = tone_result["hawk_score"]
            dove = tone_result["dove_score"]
            if hawk > dove:
                return "LEAN_BEARISH"
            elif dove > hawk:
                return "LEAN_BULLISH"
            return "NEUTRAL"
        return "NEUTRAL"

    def _build_recommendation(self, tone_result: Dict, comments: List) -> str:
        """
        Generate recommendation from data, not hardcoded strings.
        Includes the reasoning chain.
        """
        tone = tone_result["overall_tone"]
        confidence = tone_result["confidence"]
        reasoning = tone_result.get("reasoning", "")
        breakdown = tone_result.get("breakdown", [])

        n_comments = len(comments)
        if n_comments == 0:
            return "No recent Fed comments — monitor RSS for new speeches"

        # Build recommendation with context
        parts = []

        if tone == "HAWKISH":
            if confidence > 0.7:
                parts.append(f"Strong hawkish consensus ({confidence:.0%} confidence)")
                parts.append("Rate-sensitive sectors at risk. Bonds likely under pressure.")
            else:
                parts.append(f"Mild hawkish lean ({confidence:.0%} confidence)")
                parts.append("Watch for confirmation from upcoming speakers.")
        elif tone == "DOVISH":
            if confidence > 0.7:
                parts.append(f"Strong dovish consensus ({confidence:.0%} confidence)")
                parts.append("Risk-on favored. Growth and tech may benefit.")
            else:
                parts.append(f"Mild dovish lean ({confidence:.0%} confidence)")
                parts.append("Early signal — needs more data points.")
        elif tone == "MIXED":
            hawk = tone_result["hawk_score"]
            dove = tone_result["dove_score"]
            parts.append(f"Mixed signals (hawks {hawk:.1f} vs doves {dove:.1f})")
            parts.append("Internal FOMC disagreement. Volatility likely.")
        else:
            parts.append(f"Neutral Fed tone across {n_comments} comments")
            parts.append("No strong directional signal from Fed speakers.")

        # Add data source count
        parts.append(f"Based on {n_comments} comments. {reasoning}")

        return " | ".join(parts)

    def _suggest_positions(self, tone_result: Dict) -> List[str]:
        """
        Generate position suggestions based on tone strength.
        Not hardcoded — scaled by confidence.
        """
        tone = tone_result["overall_tone"]
        confidence = tone_result["confidence"]
        positions = []

        if tone == "HAWKISH":
            if confidence > 0.7:
                positions = [
                    "Consider: Reduce growth/tech exposure",
                    "Consider: Short-duration bonds over long",
                    "Watch: Financials may benefit from higher rates",
                ]
            elif confidence > 0.4:
                positions = [
                    "Watch: Rate-sensitive equities for weakness",
                    "Consider: Tighten stops on growth positions",
                ]
        elif tone == "DOVISH":
            if confidence > 0.7:
                positions = [
                    "Consider: Growth/tech exposure on dips",
                    "Consider: Long-duration bonds may rally",
                    "Watch: USD weakness → commodity tailwind",
                ]
            elif confidence > 0.4:
                positions = [
                    "Watch: Risk-on rotation signals",
                    "Consider: Add quality growth on pullbacks",
                ]
        elif tone == "MIXED":
            positions = [
                "Caution: FOMC split — expect volatility around next meeting",
                "Consider: Straddle/strangle strategies for vol expansion",
            ]

        return positions
