#!/usr/bin/env python3
"""
LLM Narrative Agent - Answer "WHY is the market moving?"

Uses Google Gemini 2.5 Pro to generate real-time market narratives.
"""
import google.generativeai as genai
import json
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent  # live_monitoring/

sys.path.append(str(BASE_DIR / "models"))
sys.path.append(str(ROOT_DIR))  # so 'live_monitoring.enrichment' is importable

from enriched_signal import NarrativeAnalysis, EnrichedSignal, RiskEnvironment
from live_monitoring.enrichment.apis.news_fetcher import NewsFetcher

logger = logging.getLogger(__name__)


class NarrativeAgent:
    """
    Uses Google Gemini 2.5 Pro to analyze market context and generate narratives
    
    Purpose: Transform raw momentum signals into narrative-driven insights
    - WHY is this selloff happening?
    - Is this noise or a real trend?
    - What are the catalysts?
    - What's the likely follow-through?
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        news_api_key: Optional[str] = None,
        alpha_vantage_key: Optional[str] = None,
    ):
        """
        Initialize Gemini narrative agent.

        Args:
            api_key: Google AI API key
            model: Gemini model (default: gemini-2.5-flash, latest fast model)
            news_api_key: Optional NewsAPI.org key for headlines
            alpha_vantage_key: Optional Alpha Vantage key for sentiment feed
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.context_window_minutes = 30

        # Wire news fetcher (manager's Phase 1 - quick win subset)
        news_api_key = news_api_key or os.getenv("NEWS_API_KEY")
        alpha_vantage_key = alpha_vantage_key or os.getenv("ALPHA_VANTAGE_KEY")
        self.news_fetcher: Optional[NewsFetcher] = None
        if news_api_key or alpha_vantage_key:
            self.news_fetcher = NewsFetcher(
                news_api_key=news_api_key, alpha_vantage_key=alpha_vantage_key
            )
            logger.info("📰 NewsFetcher wired into NarrativeAgent")
        else:
            logger.warning(
                "NarrativeAgent initialized without NEWS_API_KEY / ALPHA_VANTAGE_KEY; "
                "headlines will be empty."
            )

        logger.info(f"🧠 Narrative Agent initialized (Gemini {model})")
    
    def analyze_selloff(
        self, 
        signal: EnrichedSignal,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[NarrativeAnalysis]:
        """
        Generate narrative for why a selloff is happening.

        Args:
            signal: The selloff signal
            market_data: Optional context (BTC, VIX, sector moves, news headlines).
                         If None, we auto-build it from available sources.

        Returns:
            NarrativeAnalysis with narrative, catalysts, conviction, etc.
        """
        try:
            # Auto-build context if caller didn't provide one
            if market_data is None:
                market_data = self._build_market_context(signal.symbol)

            # Build prompt
            prompt = self._build_selloff_prompt(signal, market_data)
            
            # Query Gemini
            logger.info("🧠 Querying Gemini for narrative analysis...")
            response = self.model.generate_content(prompt)
            
            # Parse JSON response
            try:
                # Extract JSON from markdown code block if present
                text = response.text
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                
                data = json.loads(text.strip())
                
                # Validate required fields
                required_fields = ['narrative', 'catalysts', 'conviction', 'duration', 'risk_environment', 'confidence_boost']
                if not all(field in data for field in required_fields):
                    logger.error(f"Missing required fields in Gemini response: {data.keys()}")
                    return None
                
                # Create analysis
                analysis = NarrativeAnalysis(
                    narrative=data['narrative'],
                    catalysts=data['catalysts'],
                    conviction=data['conviction'],
                    duration=data['duration'],
                    risk_environment=data['risk_environment'],
                    confidence_boost=float(data['confidence_boost']) / 100  # Convert to 0-0.15
                )
                
                logger.info(f"   ✅ Narrative generated: {analysis.conviction} conviction")
                logger.info(f"   📝 {analysis.narrative[:100]}...")
                
                return analysis
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini JSON response: {e}")
                logger.error(f"Response text: {response.text[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            return None
    
    def _build_selloff_prompt(self, signal: EnrichedSignal, market_data: Dict) -> str:
        """Build prompt for selloff narrative analysis"""
        
        # Extract market data with defaults
        btc_price = market_data.get('btc_price', 'N/A')
        btc_change = market_data.get('btc_change', 'N/A')
        vix = market_data.get('vix', 'N/A')
        xlk_change = market_data.get('xlk_change', 'N/A')
        headlines = market_data.get("headlines", [])
        
        prompt = f"""
You are an elite institutional trader analyzing a real-time market selloff.

SIGNAL DETECTED:
- Symbol: {signal.symbol}
- Action: {signal.action.value if hasattr(signal.action, 'value') else signal.action}
- Price: ${signal.entry_price:.2f}
- Move: {((signal.entry_price - signal.stop_price) / signal.stop_price * 100):.2f}% drop detected
- Time: {signal.timestamp.strftime('%Y-%m-%d %H:%M')}
- Volume: Spike detected (2x+ average)

MARKET CONTEXT:
- Bitcoin: {btc_price} ({btc_change}% change)
- VIX (Fear Index): {vix}
- Tech Sector (XLK): {xlk_change}%
- Recent Headlines: {', '.join(headlines[:3]) if headlines else 'None available'}

YOUR TASK:
Analyze WHY this selloff is happening right now. Be specific and actionable.

1. ROOT CAUSE: What triggered this move? (e.g., Bitcoin breakdown, Fed speak, macro event)
2. SIGNAL vs NOISE: Is this a real trend or just intraday chop?
3. CATALYSTS: List 2-4 specific catalysts driving this move
4. DURATION: How long will this last? (INTRADAY / MULTI_DAY / WEEK)
5. RISK ENVIRONMENT: Is this risk-off rotation or isolated weakness?

RESPOND IN VALID JSON FORMAT (NO MARKDOWN, NO COMMENTS):
{{
    "narrative": "2-sentence summary explaining WHY this selloff is happening and what it means",
    "catalysts": ["Catalyst 1", "Catalyst 2", "Catalyst 3"],
    "conviction": "HIGH or MEDIUM or LOW",
    "duration": "INTRADAY or MULTI_DAY or WEEK",
    "risk_environment": "RISK_OFF or RISK_ON or NEUTRAL",
    "confidence_boost": 12
}}

CONFIDENCE BOOST SCALE:
- 15: Extremely clear narrative with multiple confirming factors
- 10-12: Strong narrative with 2+ catalysts
- 5-8: Moderate narrative, single catalyst
- 0-3: Weak/unclear narrative

BE DIRECT. BE ACTIONABLE. NO FLUFF.
"""
        return prompt
    
    def enrich_signal(
        self, 
        signal: EnrichedSignal,
        market_data: Optional[Dict[str, Any]] = None,
    ) -> EnrichedSignal:
        """
        Enrich signal with narrative analysis.

        This is the main entry point for the enrichment pipeline.
        """
        # Generate narrative (auto-context if market_data is None)
        analysis = self.analyze_selloff(signal, market_data)
        
        if not analysis:
            logger.warning("   ⏭️  Skipping narrative enrichment (generation failed)")
            return signal
        
        # Add to signal
        signal.narrative_analysis = analysis
        
        # Build rationale
        rationale = f"Narrative: {analysis.narrative} | Catalysts: {', '.join(analysis.catalysts[:2])}"
        
        # Add enrichment
        signal.add_enrichment('narrative_agent', analysis.confidence_boost, rationale)
        
        logger.info(f"   ✅ Narrative enrichment: {analysis.confidence_boost*100:+.0f}% confidence")
        
        return signal

    # ------------------------------------------------------------------
    # Context builder (quick-win subset of manager's Phase 1)
    # ------------------------------------------------------------------

    def _build_market_context(self, symbol: str) -> Dict[str, Any]:
        """
        Build a lightweight market context dict for prompts:
        - Crypto (BTC) via CryptoCorrelationDetector is already used elsewhere;
          here we keep it simple and focus on headlines + placeholders.
        """
        context: Dict[str, Any] = {}

        # TODO: Optionally query existing CryptoCorrelationDetector for BTC/VIX
        # For now, keep neutral placeholders so prompts remain stable.
        context["btc_price"] = "N/A"
        context["btc_change"] = "0.0"
        context["vix"] = "N/A"
        context["xlk_change"] = "0.0"

        # Headlines via NewsFetcher (if configured)
        headlines: list[str] = []
        if self.news_fetcher:
            try:
                market_news = self.news_fetcher.fetch_market_news()
                symbol_news = self.news_fetcher.fetch_symbol_news(symbol)
                combined = market_news + symbol_news
                headlines = [a.get("title", "") for a in combined if a.get("title")]  # type: ignore[assignment]
            except Exception as e:
                logger.error("Error fetching news for narrative context: %s", e)

        context["headlines"] = headlines[:5]
        return context


def test_narrative_agent():
    """
    Test Google Gemini narrative agent
    
    Usage:
        python3 -m live_monitoring.enrichment.narrative_agent
    """
    import sys
    sys.path.append('/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main')
    
    from live_monitoring.core.lottery_signals import LiveSignal, SignalAction, SignalType
    
    print("=" * 80)
    print("🧪 TESTING GEMINI NARRATIVE AGENT")
    print("=" * 80)
    print()
    
    # API key (from user)
    api_key = "AIzaSyDqlcmojJjbr4jv7XUxNpkL3VlUJs2zSCI"
    
    # Initialize agent
    print("🧠 Initializing Gemini 2.5 Pro...")
    agent = NarrativeAgent(api_key=api_key)
    print()
    
    # Create test signal (today's selloff)
    print("📊 Creating test signal (2025-11-20 selloff)...")
    test_signal = EnrichedSignal.from_base_signal(LiveSignal(
        symbol='SPY',
        action=SignalAction.SELL,
        signal_type=SignalType.SELLOFF,
        entry_price=669.10,
        stop_price=676.17,
        target_price=659.44,
        confidence=0.66,
        rationale="REAL-TIME SELLOFF: -0.65% in last 20 min, volume spike 2.4x"
    ))
    print(f"   Signal: SELLOFF @ ${test_signal.entry_price}")
    print(f"   Base confidence: {test_signal.confidence*100:.0f}%")
    print()
    
    # Build market context (today's actual data)
    market_data = {
        'btc_price': '$87,500',
        'btc_change': '+0.4',
        'vix': '18.5',
        'xlk_change': '-2.8',
        'headlines': [
            'Bitcoin consolidates near $88k after NVIDIA earnings',
            'Tech stocks lead broad market selloff',
            'Fed minutes show hawkish tone concerns'
        ]
    }
    
    print("🔍 Market Context:")
    print(f"   Bitcoin: {market_data['btc_price']} ({market_data['btc_change']}%)")
    print(f"   VIX: {market_data['vix']}")
    print(f"   Tech (XLK): {market_data['xlk_change']}%")
    print(f"   Headlines: {len(market_data['headlines'])}")
    print()
    
    # Generate narrative
    print("🧠 Generating narrative with Gemini...")
    print("-" * 80)
    enriched = agent.enrich_signal(test_signal, market_data)
    print("-" * 80)
    print()
    
    # Display results
    if enriched.narrative_analysis:
        print("✅ NARRATIVE ANALYSIS:")
        print(f"   Narrative: {enriched.narrative_analysis.narrative}")
        print(f"   Catalysts: {', '.join(enriched.narrative_analysis.catalysts)}")
        print(f"   Conviction: {enriched.narrative_analysis.conviction}")
        print(f"   Duration: {enriched.narrative_analysis.duration}")
        print(f"   Risk: {enriched.narrative_analysis.risk_environment}")
        print()
        print(f"   Base confidence: {test_signal.base_confidence*100:.0f}%")
        print(f"   Enriched confidence: {enriched.confidence*100:.0f}%")
        print(f"   Boost: {enriched.enrichment_boost*100:+.0f}%")
        print()
        print(f"   Full rationale: {enriched.rationale}")
    else:
        print("❌ Narrative generation failed")
    
    print()
    print("=" * 80)
    print("✅ Test complete!")
    print("=" * 80)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    test_narrative_agent()

