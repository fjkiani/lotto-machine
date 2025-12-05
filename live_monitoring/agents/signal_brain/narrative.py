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
        dp_levels: list = None,  # NEW: Actual DP battlegrounds
        current_price: float = None,  # NEW: Current price
        fed_cut_prob: float = None,  # NEW: Actual Fed Watch probability
        trump_news: str = None,  # NEW: Actual Trump news
    ) -> NarrativeContext:
        """
        Get SPECIFIC narrative context using ALL our intelligence.
        
        Args:
            symbol: Primary symbol to analyze
            fed_sentiment: From Fed monitor (DOVISH/HAWKISH/NEUTRAL)
            trump_risk: From Trump monitor (LOW/MEDIUM/HIGH)
            dp_levels: List of DP battlegrounds with price and volume
            current_price: Current price of symbol
            fed_cut_prob: Actual Fed cut probability (e.g., 87.2)
            trump_news: Latest Trump news headline
            
        Returns:
            NarrativeContext with SPECIFIC summary, catalyst, risk, divergence
        """
        context = NarrativeContext()
        
        # 1. Build SPECIFIC summary using our actual data
        context.summary = self._build_specific_summary(
            symbol=symbol,
            current_price=current_price,
            dp_levels=dp_levels,
            fed_sentiment=fed_sentiment,
            fed_cut_prob=fed_cut_prob,
            trump_risk=trump_risk,
            trump_news=trump_news
        )
        
        # 2. Detect specific catalyst from our data
        context.catalyst = self._detect_specific_catalyst(
            dp_levels=dp_levels,
            current_price=current_price,
            fed_sentiment=fed_sentiment,
            fed_cut_prob=fed_cut_prob,
            trump_risk=trump_risk
        )
        
        # 3. Determine risk environment from actual data
        context.risk_environment = self._determine_specific_risk(
            fed_sentiment=fed_sentiment,
            trump_risk=trump_risk,
            dp_levels=dp_levels,
            current_price=current_price
        )
        
        # 4. Check for specific divergences
        divergence = self._check_specific_divergence(
            dp_levels=dp_levels,
            current_price=current_price,
            fed_sentiment=fed_sentiment
        )
        context.divergence_detected = divergence.get('detected', False)
        context.divergence_detail = divergence.get('detail', '')
        
        # 5. Calculate confidence based on data completeness
        context.confidence = self._calculate_specific_confidence(
            dp_levels=dp_levels,
            current_price=current_price,
            fed_cut_prob=fed_cut_prob
        )
        
        context.sources = ["DP Intelligence", "Fed Watch", "Trump Intel", "Institutional Flow"]
        
        return context
    
    def _build_specific_summary(
        self,
        symbol: str,
        current_price: float,
        dp_levels: list,
        fed_sentiment: str,
        fed_cut_prob: float,
        trump_risk: str,
        trump_news: str
    ) -> str:
        """Build a SPECIFIC narrative using our actual intelligence."""
        parts = []
        
        # Price + DP level context
        if current_price and dp_levels:
            # Find nearest support and resistance
            supports = [l for l in dp_levels if l.get('price', 0) < current_price]
            resistances = [l for l in dp_levels if l.get('price', 0) > current_price]
            
            if supports:
                nearest_support = max(supports, key=lambda x: x.get('price', 0))
                vol = nearest_support.get('volume', 0)
                vol_str = f"{vol/1e6:.1f}M" if vol >= 1e6 else f"{vol/1e3:.0f}K"
                parts.append(f"{symbol} ${current_price:.2f} above ${nearest_support['price']:.2f} support ({vol_str} shares)")
            
            if resistances:
                nearest_resistance = min(resistances, key=lambda x: x.get('price', 0))
                vol = nearest_resistance.get('volume', 0)
                vol_str = f"{vol/1e6:.1f}M" if vol >= 1e6 else f"{vol/1e3:.0f}K"
                parts.append(f"Resistance at ${nearest_resistance['price']:.2f} ({vol_str} shares)")
        
        # Fed context with ACTUAL probability
        if fed_cut_prob is not None:
            if fed_cut_prob > 70:
                parts.append(f"Fed {fed_cut_prob:.0f}% DOVISH - supporting longs")
            elif fed_cut_prob < 30:
                parts.append(f"Fed {fed_cut_prob:.0f}% HAWKISH - risk to longs")
            else:
                parts.append(f"Fed {fed_cut_prob:.0f}% neutral")
        elif fed_sentiment != "NEUTRAL":
            parts.append(f"Fed {fed_sentiment}")
        
        # Trump context with actual news
        if trump_risk == "HIGH":
            if trump_news:
                parts.append(f"Trump risk HIGH: {trump_news[:50]}...")
            else:
                parts.append("Trump policy risk elevated")
        
        # Line in the sand (highest volume level)
        if dp_levels:
            max_vol_level = max(dp_levels, key=lambda x: x.get('volume', 0))
            vol = max_vol_level.get('volume', 0)
            vol_str = f"{vol/1e6:.1f}M" if vol >= 1e6 else f"{vol/1e3:.0f}K"
            level_price = max_vol_level.get('price', 0)
            
            if current_price and level_price:
                if level_price < current_price:
                    parts.append(f"LINE IN SAND: ${level_price:.2f} ({vol_str}) - break = institutional breakdown")
                else:
                    parts.append(f"KEY RESISTANCE: ${level_price:.2f} ({vol_str}) - break = continuation")
        
        if not parts:
            parts.append(f"{symbol} trading within institutional levels")
        
        return " | ".join(parts)
    
    def _detect_specific_catalyst(
        self,
        dp_levels: list,
        current_price: float,
        fed_sentiment: str,
        fed_cut_prob: float,
        trump_risk: str
    ) -> str:
        """Detect the PRIMARY catalyst based on our data."""
        # Priority: Fed > Trump > DP Level Test
        
        if fed_cut_prob is not None:
            if fed_cut_prob > 80:
                return f"Fed rate cut imminent ({fed_cut_prob:.0f}%)"
            elif fed_cut_prob < 20:
                return f"Fed holding rates ({fed_cut_prob:.0f}% cut)"
        
        if trump_risk == "HIGH":
            return "Trump policy risk"
        
        # Check if testing a major DP level
        if dp_levels and current_price:
            for level in dp_levels:
                price = level.get('price', 0)
                vol = level.get('volume', 0)
                if vol >= 1e6 and abs(current_price - price) / price < 0.003:  # Within 0.3%
                    vol_str = f"{vol/1e6:.1f}M"
                    return f"Testing major DP level ${price:.2f} ({vol_str})"
        
        return "Technical levels"
    
    def _determine_specific_risk(
        self,
        fed_sentiment: str,
        trump_risk: str,
        dp_levels: list,
        current_price: float
    ) -> str:
        """Determine risk environment from our data."""
        risk_score = 0
        
        # Fed sentiment
        if fed_sentiment == "DOVISH":
            risk_score += 2  # Risk on
        elif fed_sentiment == "HAWKISH":
            risk_score -= 2  # Risk off
        
        # Trump risk
        if trump_risk == "HIGH":
            risk_score -= 1
        elif trump_risk == "LOW":
            risk_score += 1
        
        # Price position relative to DP levels
        if dp_levels and current_price:
            supports_below = sum(1 for l in dp_levels if l.get('price', 0) < current_price)
            resistances_above = sum(1 for l in dp_levels if l.get('price', 0) > current_price)
            
            if supports_below > resistances_above:
                risk_score += 1  # More support = risk on
            elif resistances_above > supports_below:
                risk_score -= 1  # More resistance = risk off
        
        if risk_score >= 2:
            return "RISK_ON"
        elif risk_score <= -2:
            return "RISK_OFF"
        return "NEUTRAL"
    
    def _check_specific_divergence(
        self,
        dp_levels: list,
        current_price: float,
        fed_sentiment: str
    ) -> dict:
        """Check for specific divergences in our data."""
        if not dp_levels or not current_price:
            return {'detected': False, 'detail': ''}
        
        # Check: Fed dovish but price below major DP levels = divergence
        major_supports = [l for l in dp_levels if l.get('volume', 0) >= 1e6 and l.get('price', 0) < current_price]
        major_resistances = [l for l in dp_levels if l.get('volume', 0) >= 1e6 and l.get('price', 0) > current_price]
        
        if fed_sentiment == "DOVISH" and len(major_resistances) > len(major_supports):
            return {
                'detected': True,
                'detail': f"CAUTION: Fed dovish but {len(major_resistances)} major DP resistances above - institutions may be distributing"
            }
        
        if fed_sentiment == "HAWKISH" and len(major_supports) > len(major_resistances):
            return {
                'detected': True,
                'detail': f"OPPORTUNITY: Fed hawkish but {len(major_supports)} major DP supports below - institutions accumulating"
            }
        
        return {'detected': False, 'detail': ''}
    
    def _calculate_specific_confidence(
        self,
        dp_levels: list,
        current_price: float,
        fed_cut_prob: float
    ) -> float:
        """Calculate confidence based on data completeness."""
        confidence = 0.3  # Base
        
        if dp_levels:
            confidence += 0.3
        if current_price:
            confidence += 0.2
        if fed_cut_prob is not None:
            confidence += 0.2
        
        return min(1.0, confidence)
    
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

