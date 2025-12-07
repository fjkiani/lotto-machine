"""
🧠 Signal Brain - Narrative Integration
=======================================
Connects existing narrative components to Signal Brain.

Uses:
- institutional_narrative.py for DP vs mainstream divergence
- market_narrative_pipeline.py for full narrative context
- Perplexity for real-time "WHY" analysis
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class NarrativeContext:
    """Narrative analysis result."""
    summary: str = ""  # One-line "WHY is market here?"
    catalyst: str = ""  # Key catalyst (e.g., "NFP miss", "Fed comments")
    risk_environment: str = "NEUTRAL"  # RISK_ON/RISK_OFF/NEUTRAL
    divergence_detected: bool = False  # Institutions vs mainstream diverging?
    divergence_detail: str = ""  # What's the divergence?
    confidence: float = 0.5  # 0-1 confidence in narrative
    sources: list = None  # Where did we get this info?
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = []


class NarrativeEnricher:
    """
    Enriches Signal Brain with narrative context.
    
    Integrates:
    1. institutional_narrative.py - DP vs mainstream
    2. Perplexity search - Real-time "WHY"
    3. Trump/Fed monitors - Macro context
    """
    
    def __init__(self, perplexity_key: Optional[str] = None):
        """
        Initialize narrative enricher.
        
        Args:
            perplexity_key: Optional Perplexity API key for real-time search
        """
        self.perplexity_key = perplexity_key or os.getenv('PERPLEXITY_API_KEY')
        self._perplexity_client = None
        self._institutional_loader = None
        
        # Initialize Perplexity client if available
        if self.perplexity_key:
            try:
                from live_monitoring.enrichment.apis.perplexity_search import PerplexitySearchClient
                self._perplexity_client = PerplexitySearchClient(self.perplexity_key)
                logger.info("📰 Narrative: Perplexity connected")
            except Exception as e:
                logger.warning(f"⚠️ Perplexity init failed: {e}")
        
        # Try to load institutional narrative loader
        try:
            from live_monitoring.enrichment.institutional_narrative import load_institutional_context
            self._load_institutional = load_institutional_context
            logger.info("🏛️ Narrative: Institutional loader connected")
        except Exception as e:
            logger.warning(f"⚠️ Institutional narrative init failed: {e}")
            self._load_institutional = None
    
    def get_narrative(
        self,
        symbol: str = "SPY",
        fed_sentiment: str = "NEUTRAL",
        trump_risk: str = "LOW",
    ) -> NarrativeContext:
        """
        Get narrative context for current market.
        
        Args:
            symbol: Primary symbol to analyze
            fed_sentiment: From Fed monitor
            trump_risk: From Trump monitor
            
        Returns:
            NarrativeContext with summary, catalyst, risk, divergence
        """
        context = NarrativeContext()
        
        # 1. Get institutional reality (DP vs lit)
        institutional_data = self._get_institutional_context(symbol)
        
        # 2. Get real-time narrative from Perplexity
        perplexity_narrative = self._get_perplexity_narrative(symbol)
        
        # 3. Build summary
        context.summary = self._build_summary(
            symbol, institutional_data, perplexity_narrative, 
            fed_sentiment, trump_risk
        )
        
        # 4. Detect catalyst
        context.catalyst = self._detect_catalyst(perplexity_narrative, fed_sentiment, trump_risk)
        
        # 5. Determine risk environment
        context.risk_environment = self._determine_risk(institutional_data, perplexity_narrative)
        
        # 6. Check for divergences
        divergence = self._check_divergence(institutional_data, perplexity_narrative)
        context.divergence_detected = divergence.get('detected', False)
        context.divergence_detail = divergence.get('detail', '')
        
        # 7. Calculate confidence
        context.confidence = self._calculate_confidence(
            institutional_data, perplexity_narrative, 
            fed_sentiment, trump_risk
        )
        
        return context
    
    def _get_institutional_context(self, symbol: str) -> Dict[str, Any]:
        """Load institutional data (DP, lit, max pain)."""
        if not self._load_institutional:
            return {}
        
        try:
            return self._load_institutional(symbol)
        except Exception as e:
            logger.warning(f"⚠️ Institutional load failed: {e}")
            return {}
    
    def _get_perplexity_narrative(self, symbol: str) -> Dict[str, Any]:
        """Get real-time narrative from Perplexity."""
        if not self._perplexity_client:
            return {}
        
        try:
            # Ask Perplexity: "Why is [symbol] moving today?"
            query = f"What is driving {symbol} stock price today? Key catalysts and market sentiment in one paragraph."
            result = self._perplexity_client.search(query)
            
            if result and 'answer' in result:
                return {
                    'narrative': result['answer'],
                    'sources': result.get('sources', []),
                }
        except Exception as e:
            logger.warning(f"⚠️ Perplexity search failed: {e}")
        
        return {}
    
    def _build_summary(
        self, symbol: str, 
        institutional: Dict, 
        perplexity: Dict,
        fed_sentiment: str,
        trump_risk: str
    ) -> str:
        """Build one-line narrative summary."""
        parts = []
        
        # Add Perplexity narrative if available
        if perplexity.get('narrative'):
            # Extract first sentence
            narrative = perplexity['narrative']
            first_sentence = narrative.split('.')[0] + '.'
            parts.append(first_sentence[:100])
        
        # Add institutional context
        if institutional.get('dark_pool', {}).get('pct'):
            dp_pct = institutional['dark_pool']['pct']
            if dp_pct > 50:
                parts.append(f"Heavy DP activity ({dp_pct:.0f}%).")
            elif dp_pct < 30:
                parts.append(f"Low DP activity ({dp_pct:.0f}%).")
        
        # Add macro context
        if fed_sentiment == "DOVISH":
            parts.append("Fed dovish sentiment supporting.")
        elif fed_sentiment == "HAWKISH":
            parts.append("Fed hawkish sentiment weighing.")
        
        if trump_risk == "HIGH":
            parts.append("Trump policy risk elevated.")
        
        if not parts:
            parts.append(f"{symbol} trading within institutional levels.")
        
        return " ".join(parts)
    
    def _detect_catalyst(
        self, perplexity: Dict, 
        fed_sentiment: str, 
        trump_risk: str
    ) -> str:
        """Detect primary catalyst."""
        # Check for specific catalysts in narrative
        narrative = perplexity.get('narrative', '').lower()
        
        catalysts = [
            ('fed', 'Fed commentary'),
            ('fomc', 'FOMC meeting'),
            ('inflation', 'Inflation data'),
            ('cpi', 'CPI release'),
            ('jobs', 'Jobs report'),
            ('nfp', 'NFP release'),
            ('trump', 'Trump policy'),
            ('tariff', 'Tariff announcement'),
            ('earnings', 'Earnings results'),
            ('guidance', 'Company guidance'),
        ]
        
        for keyword, catalyst in catalysts:
            if keyword in narrative:
                return catalyst
        
        # Fallback to macro context
        if fed_sentiment != "NEUTRAL":
            return "Fed policy shift"
        if trump_risk == "HIGH":
            return "Trump policy risk"
        
        return "No specific catalyst"
    
    def _determine_risk(self, institutional: Dict, perplexity: Dict) -> str:
        """Determine risk environment."""
        narrative = perplexity.get('narrative', '').lower()
        
        # Check narrative for risk keywords
        risk_off_keywords = ['fear', 'sell', 'crash', 'panic', 'recession', 'crisis']
        risk_on_keywords = ['rally', 'buy', 'optimism', 'growth', 'bullish', 'record']
        
        risk_off_count = sum(1 for k in risk_off_keywords if k in narrative)
        risk_on_count = sum(1 for k in risk_on_keywords if k in narrative)
        
        if risk_off_count > risk_on_count:
            return "RISK_OFF"
        elif risk_on_count > risk_off_count:
            return "RISK_ON"
        
        return "NEUTRAL"
    
    def _check_divergence(self, institutional: Dict, perplexity: Dict) -> Dict:
        """Check for institutional vs mainstream divergence."""
        if not institutional:
            return {'detected': False, 'detail': ''}
        
        narrative = perplexity.get('narrative', '').lower()
        
        # Check for divergence patterns
        dp_pct = institutional.get('dark_pool', {}).get('pct', 50)
        
        # High DP + bearish narrative = bullish divergence (smart money buying)
        bearish_keywords = ['sell', 'drop', 'fall', 'decline', 'bearish']
        narrative_bearish = any(k in narrative for k in bearish_keywords)
        
        if dp_pct > 60 and narrative_bearish:
            return {
                'detected': True,
                'detail': f"BULLISH DIVERGENCE: Heavy DP buying ({dp_pct:.0f}%) while narrative is bearish - institutions accumulating"
            }
        
        # Low DP + bullish narrative = bearish divergence (smart money selling)
        bullish_keywords = ['buy', 'rally', 'rise', 'gain', 'bullish']
        narrative_bullish = any(k in narrative for k in bullish_keywords)
        
        if dp_pct < 30 and narrative_bullish:
            return {
                'detected': True,
                'detail': f"BEARISH DIVERGENCE: Low DP activity ({dp_pct:.0f}%) while narrative is bullish - institutions not buying"
            }
        
        return {'detected': False, 'detail': ''}
    
    def _calculate_confidence(
        self, institutional: Dict, 
        perplexity: Dict,
        fed_sentiment: str,
        trump_risk: str
    ) -> float:
        """Calculate narrative confidence (0-1)."""
        confidence = 0.5  # Base
        
        # Boost if we have institutional data
        if institutional and institutional.get('dark_pool', {}).get('pct'):
            confidence += 0.2
        
        # Boost if we have Perplexity narrative
        if perplexity.get('narrative'):
            confidence += 0.15
        
        # Boost if Fed/Trump context available
        if fed_sentiment != "NEUTRAL":
            confidence += 0.1
        if trump_risk != "LOW":
            confidence += 0.05
        
        return min(1.0, confidence)


