"""
🧠 Signal Brain - Main Engine
=============================
Orchestrates all signal brain components.

Usage:
    brain = SignalBrainEngine(dp_client)
    result = brain.analyze(spy_levels, qqq_levels, fed_sentiment, trump_risk)
    embed = brain.to_discord(result)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    SynthesisResult, SignalState, MarketContext, SupportZone
)
from .zone_clustering import ZoneClusterer
from .context import ContextEnricher
from .cross_asset import CrossAssetAnalyzer
from .confluence import ConfluenceScorer
from .synthesizer import SignalSynthesizer

logger = logging.getLogger(__name__)


class SignalBrainEngine:
    """
    Main orchestrator for the Signal Synthesis Brain.
    
    Takes raw DP levels → outputs ONE unified synthesis.
    NOW INTEGRATES WITH DP LEARNING ENGINE + NARRATIVE! 🧠📰
    """
    
    # Only alert if confluence changes by this much
    ALERT_THRESHOLD = 10  # 10 point change
    
    def __init__(self, dp_learning_engine=None, narrative_enricher=None):
        """
        Args:
            dp_learning_engine: Optional DPLearningEngine instance for predictions
            narrative_enricher: Optional NarrativeEnricher instance for "WHY" context
        """
        self.clusterer = ZoneClusterer()
        self.context_enricher = ContextEnricher()
        self.cross_asset_analyzer = CrossAssetAnalyzer()
        self.confluence_scorer = ConfluenceScorer()
        self.synthesizer = SignalSynthesizer()
        
        # DP Learning integration
        self.dp_learning = dp_learning_engine
        
        # Narrative integration
        self.narrative_enricher = narrative_enricher
        
        # State for deduplication
        self._last_synthesis: Optional[SynthesisResult] = None
        self._last_alert_time: Optional[datetime] = None
    
    def analyze(
        self,
        spy_levels: List[Dict],
        qqq_levels: List[Dict],
        spy_price: float,
        qqq_price: float,
        fed_sentiment: str = "NEUTRAL",
        trump_risk: str = "LOW",
    ) -> SynthesisResult:
        """
        Analyze all inputs and produce unified synthesis.
        
        Args:
            spy_levels: List of {'price': float, 'volume': int} for SPY
            qqq_levels: List of {'price': float, 'volume': int} for QQQ
            spy_price: Current SPY price
            qqq_price: Current QQQ price
            fed_sentiment: HAWKISH/DOVISH/NEUTRAL
            trump_risk: HIGH/MEDIUM/LOW
            
        Returns:
            SynthesisResult with full analysis
        """
        logger.info("=" * 60)
        logger.info("🧠 SIGNAL BRAIN ANALYSIS")
        logger.info("=" * 60)
        
        # 1. Get market context
        context = self.context_enricher.get_context(
            fed_sentiment=fed_sentiment,
            trump_risk=trump_risk
        )
        # Override with actual prices if provided
        if spy_price > 0:
            context.spy_price = spy_price
        if qqq_price > 0:
            context.qqq_price = qqq_price
        
        logger.info(f"📊 SPY: ${context.spy_price:.2f} ({context.spy_trend_1h.value})")
        logger.info(f"📊 QQQ: ${context.qqq_price:.2f}")
        logger.info(f"📊 VIX: {context.vix_level:.1f} ({context.vix_trend})")
        logger.info(f"🕐 Session: {context.time_of_day.value}")
        
        # 2. Cluster SPY levels into zones
        spy_supports, spy_resistances = self.clusterer.cluster_levels(
            spy_levels, context.spy_price, "SPY"
        )
        
        # 3. Cluster QQQ levels into zones
        qqq_supports, qqq_resistances = self.clusterer.cluster_levels(
            qqq_levels, context.qqq_price, "QQQ"
        )
        
        # 4. Build signal states
        spy_state = self._build_state("SPY", context.spy_price, spy_supports, spy_resistances)
        qqq_state = self._build_state("QQQ", context.qqq_price, qqq_supports, qqq_resistances)
        
        # 5. Cross-asset analysis
        cross_result = self.cross_asset_analyzer.analyze(spy_state, qqq_state)
        logger.info(f"🔗 Cross-Asset: {cross_result['signal'].value} - {cross_result['detail']}")
        
        # 6. Get DP Learning prediction (if engine available)
        dp_learning_prediction = self._get_learning_prediction(spy_state, context.spy_price)
        if dp_learning_prediction:
            prob = dp_learning_prediction.get('bounce_probability', 0.5)
            conf = dp_learning_prediction.get('confidence', 'MEDIUM')
            logger.info(f"🧠 DP Learning: {prob:.0%} bounce | {conf}")
        
        # 7. Get Narrative context (if enricher available)
        narrative_context = self._get_narrative_context(fed_sentiment, trump_risk)
        if narrative_context and narrative_context.get('summary'):
            logger.info(f"📰 Narrative: {narrative_context['summary'][:50]}...")
            if narrative_context.get('divergence_detected'):
                logger.info(f"⚠️ Divergence: {narrative_context.get('divergence_detail', 'Detected')[:50]}")
        
        # 8. Calculate confluence (now includes learning + narrative)
        confluence = self.confluence_scorer.calculate(
            spy_state, qqq_state, context, cross_result,
            dp_learning_prediction=dp_learning_prediction,
            narrative_context=narrative_context  # NEW: Narrative integration
        )
        
        # 8. Synthesize
        result = self.synthesizer.synthesize(
            spy_state, qqq_state, context, confluence, cross_result
        )
        
        logger.info("=" * 60)
        logger.info(f"🎯 SYNTHESIS: {confluence.score:.0f}% {confluence.bias.value}")
        if result.recommendation:
            logger.info(f"💡 Action: {result.recommendation.action}")
            if result.recommendation.wait_for:
                logger.info(f"⏳ {result.recommendation.wait_for}")
        logger.info("=" * 60)
        
        self._last_synthesis = result
        
        return result
    
    def _build_state(
        self,
        symbol: str,
        price: float,
        supports: List[SupportZone],
        resistances: List[SupportZone]
    ) -> SignalState:
        """Build SignalState from zones."""
        state = SignalState(
            symbol=symbol,
            current_price=price,
            support_zones=supports,
            resistance_zones=resistances,
        )
        
        # Find nearest zones
        if supports:
            state.nearest_support = supports[0]
        if resistances:
            state.nearest_resistance = resistances[0]
        
        # Check if at level
        at_support, at_resistance = self.cross_asset_analyzer.check_at_level(state)
        state.at_support = at_support
        state.at_resistance = at_resistance
        
        return state
    
    def _get_learning_prediction(
        self, 
        spy_state: Optional[SignalState], 
        current_price: float
    ) -> Optional[Dict]:
        """
        Get prediction from DP Learning Engine for nearest zone.
        
        Returns:
            {
                'bounce_probability': 0.78,
                'confidence': 'HIGH',
                'patterns': ['vol_2m_plus', 'support', 'touch_1'],
            }
        """
        if not self.dp_learning or not spy_state:
            return None
        
        try:
            # Find nearest zone to get prediction for
            nearest_zone = None
            if spy_state.at_support and spy_state.nearest_support:
                nearest_zone = spy_state.nearest_support
            elif spy_state.at_resistance and spy_state.nearest_resistance:
                nearest_zone = spy_state.nearest_resistance
            elif spy_state.support_zones:
                nearest_zone = spy_state.support_zones[0]
            
            if not nearest_zone:
                return None
            
            # Get prediction from learning engine
            # The learning engine's predict method expects the level context
            prediction = self.dp_learning.predict(
                symbol='SPY',
                price=nearest_zone.center_price,
                volume=nearest_zone.combined_volume,
                level_type=nearest_zone.zone_type,
                touch_count=1,  # Will be refined with tracking
            )
            
            if prediction:
                return {
                    'bounce_probability': prediction.probability,
                    'confidence': prediction.confidence.value if hasattr(prediction.confidence, 'value') else prediction.confidence,
                    'patterns': prediction.supporting_patterns,
                }
        except Exception as e:
            logger.debug(f"DP Learning prediction error: {e}")
        
        return None
    
    def _get_narrative_context(
        self,
        fed_sentiment: str = "NEUTRAL",
        trump_risk: str = "LOW"
    ) -> Optional[Dict]:
        """
        Get narrative context ("WHY is market here?").
        
        Returns:
            {
                'summary': 'Market testing NFP lows...',
                'catalyst': 'Fed comments',
                'risk_environment': 'RISK_ON',
                'divergence_detected': False,
                'divergence_detail': '',
                'confidence': 0.8,
            }
        """
        if not self.narrative_enricher:
            return None
        
        try:
            narrative = self.narrative_enricher.get_narrative(
                symbol='SPY',
                fed_sentiment=fed_sentiment,
                trump_risk=trump_risk
            )
            
            return {
                'summary': narrative.summary,
                'catalyst': narrative.catalyst,
                'risk_environment': narrative.risk_environment,
                'divergence_detected': narrative.divergence_detected,
                'divergence_detail': narrative.divergence_detail,
                'confidence': narrative.confidence,
            }
        except Exception as e:
            logger.debug(f"Narrative context error: {e}")
        
        return None
    
    def should_alert(self, result: SynthesisResult) -> bool:
        """
        Determine if we should send an alert.
        
        Rules:
        - Confluence >= 50%
        - Not too soon after last alert (5 min)
        - Confluence changed significantly
        """
        # Minimum confluence
        if result.confluence.score < 50:
            return False
        
        # Time check
        now = datetime.now()
        if self._last_alert_time:
            minutes_since = (now - self._last_alert_time).total_seconds() / 60
            if minutes_since < 5:
                return False
        
        # Confluence change check
        if self._last_synthesis:
            change = abs(result.confluence.score - self._last_synthesis.confluence.score)
            if change < self.ALERT_THRESHOLD:
                return False
        
        self._last_alert_time = now
        return True
    
    def to_discord(self, result: SynthesisResult) -> Dict:
        """Convert to Discord embed."""
        return self.synthesizer.to_discord_embed(result)
    
    def format_summary(self, result: SynthesisResult) -> str:
        """Format as text summary for logging."""
        lines = [
            "═" * 50,
            f"🧠 SYNTHESIS: {result.confluence.score:.0f}% {result.confluence.bias.value}",
            "═" * 50,
        ]
        
        # Support structure
        if "SPY" in result.states:
            spy = result.states["SPY"]
            lines.append("📍 SUPPORT STRUCTURE:")
            for z in spy.support_zones[:3]:
                icon = "🔥" if z.rank.value == "PRIMARY" else "⚡"
                lines.append(f"   {icon} {z.rank.value}: {z.range_str} ({z.volume_str})")
        
        # Cross-asset
        lines.append(f"\n🔗 CROSS-ASSET: {result.cross_asset.value}")
        lines.append(f"   {result.cross_asset_detail}")
        
        # Thinking
        lines.append(f"\n💭 THINKING: {result.thinking[:200]}...")
        
        # Recommendation
        rec = result.recommendation
        if rec:
            lines.append(f"\n🎯 RECOMMENDATION: {rec.action}")
            if rec.action != "WAIT":
                lines.append(f"   Entry: ${rec.entry_price:.2f}")
                lines.append(f"   Stop: ${rec.stop_price:.2f}")
                lines.append(f"   Target: ${rec.target_price:.2f}")
                lines.append(f"   Size: {rec.size}")
            elif rec.wait_for:
                lines.append(f"   ⏳ {rec.wait_for}")
        
        lines.append("═" * 50)
        
        return "\n".join(lines)

