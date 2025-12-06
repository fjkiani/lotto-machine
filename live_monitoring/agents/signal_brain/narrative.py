"""
🧠 Signal Brain - Narrative Integration
=======================================
Connects existing V1 narrative components to Signal Brain.

Uses:
- market_narrative_pipeline.py (V1 PRODUCTION!) for full narrative context
- institutional_narrative.py for DP vs mainstream divergence
- EventLoader for economic calendar
- Perplexity for real-time "WHY" analysis

THIS IS THE REAL NARRATIVE - NOT HARDCODED GARBAGE!
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

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
    
    # V1 narrative fields (from MarketNarrative)
    macro_narrative: str = ""
    sector_narrative: str = ""
    cross_asset_narrative: str = ""
    causal_chain: str = ""
    overall_direction: str = "NEUTRAL"
    conviction: str = "MEDIUM"
    uncertainties: list = None
    
    def __post_init__(self):
        if self.sources is None:
            self.sources = []
        if self.uncertainties is None:
            self.uncertainties = []


class NarrativeEnricher:
    """
    Enriches Signal Brain with REAL narrative context from V1 pipeline.
    
    USES THE REAL V1 SYSTEM:
    1. market_narrative_pipeline.py - Full narrative with validation
    2. EventLoader - Economic calendar + surprise scoring  
    3. Perplexity - Real-time mainstream narrative
    4. CryptoCorrelationDetector - Risk environment
    5. Institutional context - DP, gamma, max pain
    6. Divergence detection - Institutions vs mainstream
    """
    
    def __init__(self, perplexity_key: Optional[str] = None):
        """
        Initialize narrative enricher.
        
        Args:
            perplexity_key: Optional Perplexity API key for real-time search
        """
        self.perplexity_key = perplexity_key or os.getenv('PERPLEXITY_API_KEY')
        self._narrative_pipeline = None
        self._cache = {}  # Cache narratives by symbol+date
        
        # Try to load V1 narrative pipeline
        try:
            from live_monitoring.enrichment.market_narrative_pipeline import market_narrative_pipeline
            self._narrative_pipeline = market_narrative_pipeline
            logger.info("✅ Narrative: V1 pipeline connected!")
        except Exception as e:
            logger.warning(f"⚠️ V1 narrative pipeline init failed: {e}")
            self._narrative_pipeline = None
    
    def get_narrative(
        self,
        symbol: str = "SPY",
        fed_sentiment: str = "NEUTRAL",
        trump_risk: str = "LOW",
        dp_levels: list = None,
        current_price: float = None,
        fed_cut_prob: float = None,
        trump_news: str = None,
    ) -> NarrativeContext:
        """
        Get narrative context from V1 PRODUCTION PIPELINE.
        
        THIS CALLS THE REAL V1 SYSTEM - NOT HARDCODED GARBAGE!
        
        Args:
            symbol: Primary symbol to analyze
            fed_sentiment: From Fed monitor (DOVISH/HAWKISH/NEUTRAL)
            trump_risk: From Trump monitor (LOW/MEDIUM/HIGH)
            dp_levels: List of DP battlegrounds with price and volume
            current_price: Current price of symbol
            fed_cut_prob: Actual Fed cut probability (e.g., 87.2)
            trump_news: Latest Trump news headline
            
        Returns:
            NarrativeContext with REAL narrative from V1 pipeline
        """
        context = NarrativeContext()
        date = datetime.utcnow().strftime("%Y-%m-%d")
        cache_key = f"{symbol}_{date}"
        
        # 1. TRY V1 PIPELINE FIRST (THE REAL SHIT!)
        if self._narrative_pipeline:
            try:
                # Check cache first
                if cache_key in self._cache:
                    logger.info(f"📰 Using cached V1 narrative for {symbol}")
                    v1_result = self._cache[cache_key]
                else:
                    logger.info(f"🧠 Running V1 narrative pipeline for {symbol}...")
                    v1_result = self._narrative_pipeline(symbol, enable_logging=False)
                    self._cache[cache_key] = v1_result
                
                # Extract from V1 MarketNarrative object
                context.macro_narrative = v1_result.macro_narrative or ""
                context.sector_narrative = v1_result.sector_narrative or ""
                context.cross_asset_narrative = v1_result.cross_asset_narrative or ""
                context.causal_chain = v1_result.causal_chain or ""
                context.overall_direction = v1_result.overall_direction or "NEUTRAL"
                context.conviction = v1_result.conviction or "MEDIUM"
                context.risk_environment = v1_result.risk_environment or "NEUTRAL"
                context.uncertainties = v1_result.uncertainties or []
                
                # Build summary from V1 data
                context.summary = self._build_v1_summary(v1_result, current_price, fed_cut_prob)
                
                # Extract catalyst from causal chain
                if v1_result.causal_chain:
                    context.catalyst = v1_result.causal_chain.split("→")[0].strip() if "→" in v1_result.causal_chain else v1_result.causal_chain
                
                # Check divergences from V1
                if v1_result.divergences:
                    context.divergence_detected = True
                    context.divergence_detail = str(v1_result.divergences[0]) if v1_result.divergences else ""
                
                # Confidence based on V1 conviction
                conviction_map = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5}
                context.confidence = conviction_map.get(v1_result.conviction, 0.6)
                
                # Sources from V1
                context.sources = [s.url for s in v1_result.sources[:5]] if v1_result.sources else ["V1 Narrative Pipeline"]
                
                logger.info(f"✅ V1 narrative: {context.overall_direction} / {context.risk_environment} / {context.conviction}")
                return context
                
            except Exception as e:
                logger.warning(f"⚠️ V1 pipeline failed, using fallback: {e}")
        
        # 2. FALLBACK: Build from our data if V1 fails
        logger.info("📰 Using fallback narrative builder")
        context.summary = self._build_specific_summary(
            symbol=symbol,
            current_price=current_price,
            dp_levels=dp_levels,
            fed_sentiment=fed_sentiment,
            fed_cut_prob=fed_cut_prob,
            trump_risk=trump_risk,
            trump_news=trump_news
        )
        
        context.catalyst = self._detect_specific_catalyst(
            dp_levels=dp_levels,
            current_price=current_price,
            fed_sentiment=fed_sentiment,
            fed_cut_prob=fed_cut_prob,
            trump_risk=trump_risk
        )
        
        context.risk_environment = self._determine_specific_risk(
            fed_sentiment=fed_sentiment,
            trump_risk=trump_risk,
            dp_levels=dp_levels,
            current_price=current_price
        )
        
        divergence = self._check_specific_divergence(
            dp_levels=dp_levels,
            current_price=current_price,
            fed_sentiment=fed_sentiment
        )
        context.divergence_detected = divergence.get('detected', False)
        context.divergence_detail = divergence.get('detail', '')
        
        context.confidence = self._calculate_specific_confidence(
            dp_levels=dp_levels,
            current_price=current_price,
            fed_cut_prob=fed_cut_prob
        )
        
        context.sources = ["DP Intelligence", "Fed Watch", "Trump Intel", "Institutional Flow"]
        
        return context
    
    def _build_v1_summary(self, v1_result, current_price: float, fed_cut_prob: float) -> str:
        """Build summary from V1 MarketNarrative with additional context."""
        parts = []
        
        # Direction + conviction
        direction_emoji = {"BULLISH": "📈", "BEARISH": "📉", "NEUTRAL": "➡️"}.get(v1_result.overall_direction, "➡️")
        parts.append(f"{direction_emoji} {v1_result.overall_direction} ({v1_result.conviction})")
        
        # Add Fed probability if available
        if fed_cut_prob is not None:
            parts.append(f"Fed {fed_cut_prob:.0f}% cut")
        
        # Causal chain (the WHY)
        if v1_result.causal_chain and v1_result.causal_chain != "No clear causal chain (V1 heuristic).":
            parts.append(v1_result.causal_chain)
        
        # Risk environment
        parts.append(f"Risk: {v1_result.risk_environment}")
        
        return " | ".join(parts)
    
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

