"""
🧬 NARRATIVE SYNTHESIZER
========================
Combines all agent outputs into a unified, coherent narrative.

Takes:
- Fed Agent findings
- Trump Agent findings
- Institutional Agent findings
- Macro Agent findings
- Technical Agent findings

Produces:
- Unified narrative (not generic news)
- Weighted bias (based on confidence)
- Prioritized risk factors
- Actionable trade thesis
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SynthesizedNarrative:
    """The final, unified narrative."""
    
    # Core narrative
    headline: str = ""  # One-line hook
    full_story: str = ""  # Full narrative (3-5 sentences)
    key_points: List[str] = field(default_factory=list)  # Bullet points
    
    # Combined analysis
    overall_bias: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    confidence: float = 0.5  # 0-1
    risk_level: str = "MEDIUM"  # LOW, MEDIUM, HIGH
    
    # Actionable
    trade_thesis: str = ""  # What to do
    entry_trigger: str = ""  # When to enter
    risk_factors: List[str] = field(default_factory=list)
    
    # Agent contributions
    fed_summary: str = ""
    trump_summary: str = ""
    institutional_summary: str = ""
    macro_summary: str = ""
    technical_summary: str = ""
    
    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    sources: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'headline': self.headline,
            'full_story': self.full_story,
            'key_points': self.key_points,
            'overall_bias': self.overall_bias,
            'confidence': self.confidence,
            'risk_level': self.risk_level,
            'trade_thesis': self.trade_thesis,
            'entry_trigger': self.entry_trigger,
            'risk_factors': self.risk_factors,
            'agent_summaries': {
                'fed': self.fed_summary,
                'trump': self.trump_summary,
                'institutional': self.institutional_summary,
                'macro': self.macro_summary,
                'technical': self.technical_summary,
            },
            'timestamp': self.timestamp,
            'sources': self.sources,
        }
    
    def to_discord_embed(self) -> Dict[str, Any]:
        """Format for Discord alert."""
        bias_emoji = {"BULLISH": "📈", "BEARISH": "📉", "NEUTRAL": "➡️"}.get(self.overall_bias, "❓")
        risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(self.risk_level, "⚪")
        
        # Build fields
        fields = []
        
        # Key points as bullet list
        if self.key_points:
            points_text = "\n".join([f"• {p}" for p in self.key_points[:5]])
            fields.append({"name": "📌 Key Points", "value": points_text, "inline": False})
        
        # Agent summaries (collapsed)
        summaries = []
        if self.fed_summary:
            summaries.append(f"🏦 **Fed:** {self.fed_summary[:80]}")
        if self.trump_summary:
            summaries.append(f"🎯 **Trump:** {self.trump_summary[:80]}")
        if self.institutional_summary:
            summaries.append(f"🏛️ **Inst:** {self.institutional_summary[:80]}")
        if summaries:
            fields.append({"name": "🤖 Agent Insights", "value": "\n".join(summaries[:3]), "inline": False})
        
        # Trade thesis
        if self.trade_thesis:
            fields.append({"name": "💰 Trade Thesis", "value": self.trade_thesis, "inline": False})
        
        # Risk factors
        if self.risk_factors:
            risks_text = ", ".join(self.risk_factors[:3])
            fields.append({"name": f"{risk_emoji} Risks", "value": risks_text, "inline": True})
        
        # Confidence
        fields.append({"name": "💯 Confidence", "value": f"{self.confidence:.0%}", "inline": True})
        
        return {
            "title": f"{bias_emoji} {self.headline}",
            "description": self.full_story,
            "color": 3066993 if self.overall_bias == "BULLISH" else 15158332 if self.overall_bias == "BEARISH" else 9807270,
            "fields": fields,
            "footer": {"text": f"Narrative Intelligence | {len(self.sources)} sources"},
            "timestamp": datetime.utcnow().isoformat()
        }


class NarrativeSynthesizer:
    """
    Combines multiple agent results into unified narrative.
    
    Weighting:
    - Fed: 30% (major market driver)
    - Institutional: 25% (smart money)
    - Technical: 20% (price action)
    - Trump: 15% (policy risk)
    - Macro: 10% (regime context)
    """
    
    # Agent weights for bias calculation
    WEIGHTS = {
        'FED': 0.30,
        'INSTITUTIONAL': 0.25,
        'TECHNICAL': 0.20,
        'TRUMP': 0.15,
        'MACRO': 0.10,
    }
    
    def __init__(self):
        self.logger = logging.getLogger("narrative.synthesizer")
    
    def synthesize(
        self,
        agent_results: List,  # List of AgentResult
        symbol: str = "SPY",
        current_price: float = None
    ) -> SynthesizedNarrative:
        """
        Synthesize all agent results into unified narrative.
        
        Args:
            agent_results: List of AgentResult from specialized agents
            symbol: Symbol being analyzed
            current_price: Current price
            
        Returns:
            SynthesizedNarrative with unified analysis
        """
        self.logger.info(f"🧬 Synthesizing {len(agent_results)} agent results...")
        
        narrative = SynthesizedNarrative()
        
        # Index results by domain
        results_by_domain = {}
        for r in agent_results:
            results_by_domain[r.domain] = r
        
        # Extract agent summaries
        narrative.fed_summary = results_by_domain.get('FED', None)
        if narrative.fed_summary:
            narrative.fed_summary = narrative.fed_summary.summary
        
        narrative.trump_summary = results_by_domain.get('TRUMP', None)
        if narrative.trump_summary:
            narrative.trump_summary = narrative.trump_summary.summary
        
        narrative.institutional_summary = results_by_domain.get('INSTITUTIONAL', None)
        if narrative.institutional_summary:
            narrative.institutional_summary = narrative.institutional_summary.summary
        
        narrative.macro_summary = results_by_domain.get('MACRO', None)
        if narrative.macro_summary:
            narrative.macro_summary = narrative.macro_summary.summary
        
        narrative.technical_summary = results_by_domain.get('TECHNICAL', None)
        if narrative.technical_summary:
            narrative.technical_summary = narrative.technical_summary.summary
        
        # Calculate weighted bias
        narrative.overall_bias, narrative.confidence = self._calculate_weighted_bias(agent_results)
        
        # Combine key points (prioritized by impact)
        narrative.key_points = self._combine_key_points(agent_results)
        
        # Combine risk factors
        narrative.risk_factors = self._combine_risk_factors(agent_results)
        
        # Determine risk level
        narrative.risk_level = self._determine_risk_level(agent_results, narrative.risk_factors)
        
        # Build headline
        narrative.headline = self._build_headline(symbol, current_price, narrative.overall_bias, narrative.confidence)
        
        # Build full story
        narrative.full_story = self._build_full_story(agent_results, symbol, narrative.overall_bias)
        
        # Build trade thesis
        narrative.trade_thesis = self._build_trade_thesis(agent_results, narrative.overall_bias, narrative.confidence)
        
        # Entry trigger
        narrative.entry_trigger = self._get_entry_trigger(results_by_domain.get('TECHNICAL'), current_price)
        
        # Collect sources
        for r in agent_results:
            narrative.sources.extend(r.sources[:2])
        
        self.logger.info(f"   ✅ Synthesis complete: {narrative.overall_bias} ({narrative.confidence:.0%})")
        
        return narrative
    
    def _calculate_weighted_bias(self, results: List) -> tuple:
        """Calculate weighted overall bias and confidence."""
        bias_scores = {'BULLISH': 0, 'BEARISH': 0, 'NEUTRAL': 0}
        total_weight = 0
        total_confidence = 0
        
        for r in results:
            weight = self.WEIGHTS.get(r.domain, 0.1)
            
            # Weight by both domain weight and agent confidence
            effective_weight = weight * r.confidence
            
            bias_scores[r.bias] += effective_weight
            total_weight += effective_weight
            total_confidence += r.confidence * weight
        
        if total_weight == 0:
            return "NEUTRAL", 0.5
        
        # Determine winning bias
        max_bias = max(bias_scores, key=bias_scores.get)
        
        # Calculate confidence as weighted average
        avg_confidence = total_confidence / sum(self.WEIGHTS.values())
        
        # Boost confidence if agents agree
        if bias_scores[max_bias] > total_weight * 0.7:
            avg_confidence = min(1.0, avg_confidence + 0.1)
        
        return max_bias, avg_confidence
    
    def _combine_key_points(self, results: List) -> List[str]:
        """Combine key points, prioritizing by impact."""
        points = []
        
        # Sort by impact (HIGH first)
        sorted_results = sorted(results, key=lambda x: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(x.impact, 2))
        
        for r in sorted_results:
            for point in r.key_points[:2]:  # Max 2 per agent
                if point and point not in points:
                    points.append(point)
        
        return points[:7]  # Max 7 total
    
    def _combine_risk_factors(self, results: List) -> List[str]:
        """Combine risk factors, deduplicating."""
        risks = []
        
        for r in results:
            for risk in r.risk_factors:
                if risk and risk not in risks:
                    risks.append(risk)
        
        return risks[:5]  # Max 5
    
    def _determine_risk_level(self, results: List, risk_factors: List[str]) -> str:
        """Determine overall risk level."""
        high_impact_count = sum(1 for r in results if r.impact == "HIGH")
        
        if high_impact_count >= 2 or len(risk_factors) >= 4:
            return "HIGH"
        elif high_impact_count >= 1 or len(risk_factors) >= 2:
            return "MEDIUM"
        return "LOW"
    
    def _build_headline(self, symbol: str, price: float, bias: str, confidence: float) -> str:
        """Build attention-grabbing headline."""
        price_str = f" ${price:.2f}" if price else ""
        conf_str = "HIGH CONVICTION" if confidence > 0.75 else "MODERATE CONVICTION" if confidence > 0.5 else "LOW CONVICTION"
        
        return f"{symbol}{price_str} | {bias} ({conf_str})"
    
    def _build_full_story(self, results: List, symbol: str, overall_bias: str) -> str:
        """Build full narrative story."""
        parts = []
        
        # Index by domain
        by_domain = {r.domain: r for r in results}
        
        # Open with Fed (if available)
        if 'FED' in by_domain:
            fed = by_domain['FED']
            parts.append(fed.summary)
        
        # Add institutional context
        if 'INSTITUTIONAL' in by_domain:
            inst = by_domain['INSTITUTIONAL']
            parts.append(inst.summary)
        
        # Add Trump if high risk
        if 'TRUMP' in by_domain and by_domain['TRUMP'].impact == "HIGH":
            parts.append(by_domain['TRUMP'].summary)
        
        # Close with trade implication
        if parts:
            parts.append(f"Overall bias: {overall_bias}.")
        
        return " ".join(parts) if parts else f"{symbol} narrative unclear - multiple conflicting signals."
    
    def _build_trade_thesis(self, results: List, bias: str, confidence: float) -> str:
        """Build actionable trade thesis."""
        # Get trade implications from agents
        implications = [r.trade_implication for r in results if r.trade_implication]
        
        if confidence < 0.5:
            return "Low confidence - wait for clearer signals before acting"
        
        if bias == "BULLISH":
            if confidence > 0.75:
                return "HIGH CONVICTION LONG - Fed + Institutions aligned bullish. Buy dips to support."
            return "LEAN LONG - Bullish bias but monitor risk factors."
        
        elif bias == "BEARISH":
            if confidence > 0.75:
                return "HIGH CONVICTION REDUCE/SHORT - Multiple bearish signals aligned. Fade rallies."
            return "LEAN SHORT/DEFENSIVE - Bearish bias, consider hedges."
        
        return "NEUTRAL - No clear edge. Wait for price to test key levels."
    
    def _get_entry_trigger(self, technical_result, current_price: float) -> str:
        """Get specific entry trigger from technical analysis."""
        if not technical_result:
            return "Wait for price to test a key level"
        
        return technical_result.trade_implication or "Wait for clear price action signal"

