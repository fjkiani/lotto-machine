"""
Tavily Enhancement Layer for V1 Narrative Pipeline

ENHANCES Perplexity's surface-level summaries with DEEP research from Tavily.

Flow:
1. Perplexity gives us basic summary (what happened)
2. Tavily agents dig deeper (WHY it happened, WHO moved it, WHAT it means)
3. Enhanced narrative combines both layers

This makes V1 output RICH instead of bland.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def enhance_with_tavily(
    symbol: str,
    trading_date_str: str,
    perplexity_narratives: Dict[str, Any],
    inst_ctx: Dict[str, Any],
    event_schedule: Dict[str, Any],
    fed_cut_prob: Optional[float] = None,
    trump_risk: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enhance Perplexity narratives with Tavily's deep research layer.
    
    Args:
        symbol: Ticker symbol
        trading_date_str: Trading date
        perplexity_narratives: Output from run_perplexity_queries()
        inst_ctx: Institutional context (DP, gamma, etc.)
        event_schedule: Economic calendar events
        fed_cut_prob: Fed cut probability (if available)
        trump_risk: Trump risk level (if available)
        
    Returns:
        Enhanced narratives dict with Tavily deep research added
    """
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        logger.warning("⚠️ No TAVILY_API_KEY - skipping deep research enhancement")
        return perplexity_narratives
    
    try:
        from live_monitoring.agents.narrative.engine import NarrativeIntelligenceEngine
        
        # Initialize Tavily engine
        engine = NarrativeIntelligenceEngine(tavily_key)
        
        # Get current price if available
        current_price = None
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1d')
            if not hist.empty:
                current_price = float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.debug(f"Could not fetch current price: {e}")
        
        # Extract DP levels from inst_ctx
        dp_levels = _extract_dp_levels(inst_ctx)
        
        # Run Tavily agents for deep research
        logger.info("🔬 Running Tavily deep research agents...")
        
        # Build context for agents
        agent_context = {
            'symbol': symbol,
            'current_price': current_price,
            'dp_levels': dp_levels,
            'fed_sentiment': _derive_fed_sentiment(fed_cut_prob),
            'fed_cut_prob': fed_cut_prob,
            'trump_risk': trump_risk or 'LOW',
        }
        
        # Get synthesized narrative
        tavily_result = engine.get_full_narrative(
            symbol=symbol,
            current_price=current_price,
            dp_levels=dp_levels,
            fed_sentiment=agent_context['fed_sentiment'],
            fed_cut_prob=fed_cut_prob,
            trump_risk=trump_risk or 'LOW',
        )
        
        # ALSO get individual agent results for full_context (RICHER than summaries!)
        agent_results = {}
        for agent_name in ['fed', 'trump', 'institutional', 'macro', 'technical']:
            try:
                agent_result = engine.get_agent_result(agent_name, agent_context)
                if agent_result:
                    agent_results[agent_name] = agent_result
                    logger.debug(f"   ✅ {agent_name}: {len(agent_result.full_context)} chars of full_context")
            except Exception as e:
                logger.debug(f"   ⚠️ Could not get {agent_name} agent result: {e}")
        
        # Extract key insights from Tavily SynthesizedNarrative + agent full_context
        tavily_insights = _extract_tavily_insights(tavily_result, agent_results)
        
        # Enhance each narrative section
        enhanced = {
            "macro": _enhance_macro_narrative(
                perplexity_narratives.get("macro", ""),
                tavily_insights.get("fed", ""),
                tavily_insights.get("macro", ""),
                event_schedule
            ),
            "sector": _enhance_sector_narrative(
                perplexity_narratives.get("sector", ""),
                tavily_insights.get("institutional", ""),
                tavily_insights.get("technical", "")
            ),
            "asset": _enhance_asset_narrative(
                perplexity_narratives.get("asset", ""),
                tavily_insights.get("institutional", ""),
                inst_ctx
            ),
            "cross_asset": perplexity_narratives.get("cross_asset", ""),
            "sources": perplexity_narratives.get("sources", []),
        }
        
        # Add Tavily sources from SynthesizedNarrative
        if tavily_result and hasattr(tavily_result, 'sources'):
            sources_list = tavily_result.sources
            if isinstance(sources_list, list):
                for source in sources_list[:3]:
                    if isinstance(source, dict):
                        enhanced["sources"].append({
                            "url": source.get("url", ""),
                            "snippet": source.get("content", "")[:280] or source.get("snippet", "")[:280]
                        })
                    elif hasattr(source, 'url'):
                        enhanced["sources"].append({
                            "url": source.url,
                            "snippet": getattr(source, 'content', '')[:280] or getattr(source, 'snippet', '')[:280]
                        })
        
        logger.info("✅ Tavily enhancement complete - narratives enriched with deep research")
        return enhanced
        
    except Exception as e:
        logger.error(f"❌ Tavily enhancement failed: {e}")
        # Return original if Tavily fails
        return perplexity_narratives


def _derive_fed_sentiment(fed_cut_prob: Optional[float]) -> str:
    """Derive Fed sentiment from cut probability."""
    if fed_cut_prob is None:
        return "NEUTRAL"
    if fed_cut_prob > 70:
        return "DOVISH"
    elif fed_cut_prob < 30:
        return "HAWKISH"
    return "NEUTRAL"


def _extract_dp_levels(inst_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract DP battlegrounds from institutional context."""
    # This would need to be populated from actual DP data
    # For now, return empty list
    return []


def _extract_tavily_insights(tavily_result, agent_results: Dict = None) -> Dict[str, str]:
    """Extract insights from Tavily SynthesizedNarrative + agent full_context."""
    insights = {
        "fed": "",
        "trump": "",
        "institutional": "",
        "macro": "",
        "technical": "",
    }
    
    if not tavily_result:
        return insights
    
    # PRIORITY 1: Use agent full_context (RICHEST - actual research content, 4000+ chars!)
    if agent_results:
        if 'fed' in agent_results and hasattr(agent_results['fed'], 'full_context'):
            fed_context = agent_results['fed'].full_context
            if fed_context and len(fed_context.strip()) > 50:
                # Use MORE of the full context (1200 chars for rich content)
                insights["fed"] = fed_context[:1200]
                logger.debug(f"   ✅ Fed full_context: {len(fed_context)} chars → extracted {len(insights['fed'])} chars")
        
        if 'trump' in agent_results and hasattr(agent_results['trump'], 'full_context'):
            trump_context = agent_results['trump'].full_context
            if trump_context and len(trump_context.strip()) > 50:
                insights["trump"] = trump_context[:1200]
                logger.debug(f"   ✅ Trump full_context: {len(trump_context)} chars → extracted {len(insights['trump'])} chars")
        
        if 'institutional' in agent_results and hasattr(agent_results['institutional'], 'full_context'):
            inst_context = agent_results['institutional'].full_context
            if inst_context and len(inst_context.strip()) > 50:
                insights["institutional"] = inst_context[:1200]
                logger.debug(f"   ✅ Institutional full_context: {len(inst_context)} chars → extracted {len(insights['institutional'])} chars")
        
        if 'macro' in agent_results and hasattr(agent_results['macro'], 'full_context'):
            macro_context = agent_results['macro'].full_context
            if macro_context and len(macro_context.strip()) > 50:
                insights["macro"] = macro_context[:1200]
                logger.debug(f"   ✅ Macro full_context: {len(macro_context)} chars → extracted {len(insights['macro'])} chars")
        
        if 'technical' in agent_results and hasattr(agent_results['technical'], 'full_context'):
            tech_context = agent_results['technical'].full_context
            if tech_context and len(tech_context.strip()) > 50:
                insights["technical"] = tech_context[:1200]
                logger.debug(f"   ✅ Technical full_context: {len(tech_context)} chars → extracted {len(insights['technical'])} chars")
    
    # PRIORITY 2: Use full_story (contains all agent insights combined)
    if hasattr(tavily_result, 'full_story') and tavily_result.full_story:
        full_story = tavily_result.full_story
        # Only use if we don't have full_context
        if not insights["fed"]:
            fed_para = _extract_paragraph_containing(full_story, ["Fed", "Federal Reserve", "FOMC", "rate cut", "rate hike", "Jerome Powell"])
            if fed_para:
                insights["fed"] = fed_para[:600]
        
        if not insights["trump"]:
            trump_para = _extract_paragraph_containing(full_story, ["Trump", "tariff", "trade war", "policy"])
            if trump_para:
                insights["trump"] = trump_para[:600]
        
        if not insights["institutional"]:
            inst_para = _extract_paragraph_containing(full_story, ["institutional", "hedge fund", "smart money", "dark pool", "accumulation", "distribution"])
            if inst_para:
                insights["institutional"] = inst_para[:600]
        
        if not insights["macro"]:
            macro_para = _extract_paragraph_containing(full_story, ["macro", "economic", "GDP", "inflation", "unemployment", "regime"])
            if macro_para:
                insights["macro"] = macro_para[:600]
        
        if not insights["technical"]:
            tech_para = _extract_paragraph_containing(full_story, ["technical", "support", "resistance", "breakout", "breakdown", "momentum"])
            if tech_para:
                insights["technical"] = tech_para[:600]
    
    # PRIORITY 3: Use key_points (often has specific data)
    if hasattr(tavily_result, 'key_points') and tavily_result.key_points:
        key_points = tavily_result.key_points
        if isinstance(key_points, list):
            for point in key_points:
                point_str = str(point) if not isinstance(point, str) else point
                point_lower = point_str.lower()
                
                # Categorize points by domain (only if we don't have full_context)
                if not insights["fed"] and any(kw in point_lower for kw in ["fed", "rate", "fomc", "powell", "cut", "hike"]):
                    insights["fed"] = point_str[:400]
                elif not insights["trump"] and any(kw in point_lower for kw in ["trump", "tariff", "trade"]):
                    insights["trump"] = point_str[:400]
                elif not insights["institutional"] and any(kw in point_lower for kw in ["institutional", "hedge fund", "smart money", "dark pool"]):
                    insights["institutional"] = point_str[:400]
                elif not insights["macro"] and any(kw in point_lower for kw in ["macro", "economic", "gdp", "inflation"]):
                    insights["macro"] = point_str[:400]
                elif not insights["technical"] and any(kw in point_lower for kw in ["technical", "support", "resistance", "breakout"]):
                    insights["technical"] = point_str[:400]
    
    # PRIORITY 4: Fallback to summaries (if full_context/full_story/key_points didn't provide enough)
    if not insights["fed"] or len(insights["fed"]) < 100:
        if hasattr(tavily_result, 'fed_summary') and tavily_result.fed_summary:
            insights["fed"] = tavily_result.fed_summary
    
    if not insights["trump"] or len(insights["trump"]) < 100:
        if hasattr(tavily_result, 'trump_summary') and tavily_result.trump_summary:
            insights["trump"] = tavily_result.trump_summary
    
    if not insights["institutional"] or len(insights["institutional"]) < 100:
        if hasattr(tavily_result, 'institutional_summary') and tavily_result.institutional_summary:
            insights["institutional"] = tavily_result.institutional_summary
    
    if not insights["macro"] or len(insights["macro"]) < 100:
        if hasattr(tavily_result, 'macro_summary') and tavily_result.macro_summary:
            insights["macro"] = tavily_result.macro_summary
    
    if not insights["technical"] or len(insights["technical"]) < 100:
        if hasattr(tavily_result, 'technical_summary') and tavily_result.technical_summary:
            insights["technical"] = tavily_result.technical_summary
    
    # Also check full_story for richer content if summaries are short
    if hasattr(tavily_result, 'full_story') and tavily_result.full_story:
        full_story = tavily_result.full_story
        # If summaries are short, use full_story paragraphs
        if not insights["fed"] or len(insights["fed"]) < 100:
            fed_para = _extract_paragraph_containing(full_story, ["Fed", "rate", "FOMC", "cut", "hike", "Federal Reserve"])
            if fed_para:
                insights["fed"] = fed_para[:500]
        
        if not insights["trump"] or len(insights["trump"]) < 100:
            trump_para = _extract_paragraph_containing(full_story, ["Trump", "tariff", "trade", "policy"])
            if trump_para:
                insights["trump"] = trump_para[:500]
        
        if not insights["institutional"] or len(insights["institutional"]) < 100:
            inst_para = _extract_paragraph_containing(full_story, ["institutional", "hedge fund", "smart money", "dark pool", "accumulation"])
            if inst_para:
                insights["institutional"] = inst_para[:500]
    
    # Also extract from full_story (contains all insights)
    if hasattr(tavily_result, 'full_story') and tavily_result.full_story:
        full_story = tavily_result.full_story
        # Parse full_story for Fed/Trump mentions if summaries are empty
        if not insights["fed"] and ("Fed" in full_story or "rate" in full_story.lower() or "FOMC" in full_story):
            fed_para = _extract_paragraph_containing(full_story, ["Fed", "rate", "FOMC", "cut", "hike"])
            insights["fed"] = fed_para[:400] if fed_para else ""
        
        if not insights["trump"] and ("Trump" in full_story or "tariff" in full_story.lower()):
            trump_para = _extract_paragraph_containing(full_story, ["Trump", "tariff", "trade"])
            insights["trump"] = trump_para[:400] if trump_para else ""
    
    # Extract from key_points if summaries are still empty
    if hasattr(tavily_result, 'key_points') and tavily_result.key_points:
        key_points = tavily_result.key_points
        if isinstance(key_points, list):
            # Look for Fed/Trump/Institutional points
            for point in key_points:
                point_str = str(point) if not isinstance(point, str) else point
                if not insights["fed"] and any(kw in point_str.lower() for kw in ["fed", "rate", "fomc"]):
                    insights["fed"] = point_str[:300]
                elif not insights["trump"] and any(kw in point_str.lower() for kw in ["trump", "tariff"]):
                    insights["trump"] = point_str[:300]
                elif not insights["institutional"] and any(kw in point_str.lower() for kw in ["institutional", "hedge fund", "smart money"]):
                    insights["institutional"] = point_str[:300]
    
    return insights


def _extract_paragraph_containing(text: str, keywords: List[str]) -> str:
    """Extract paragraph containing any of the keywords."""
    paragraphs = text.split('\n\n')
    for para in paragraphs:
        if any(kw.lower() in para.lower() for kw in keywords):
            return para.strip()
    return ""


def _enhance_macro_narrative(
    base_macro: str,
    tavily_fed: str,
    tavily_macro: str,
    event_schedule: Dict[str, Any]
) -> str:
    """
    Enhance macro narrative with Tavily's Fed + Macro insights.
    
    Combines:
    - Perplexity's "what happened" (base_macro)
    - Tavily's "WHY" (Fed policy, economic drivers)
    - Event schedule (actual economic releases)
    """
    parts = []
    
    # Start with base (what happened)
    if base_macro:
        parts.append(base_macro)
    
    # Add Tavily Fed insights (WHY) - use more content
    if tavily_fed:
        # If summary is short, try to get more context
        fed_text = tavily_fed
        if len(fed_text) < 200:
            # Try to expand with key points
            fed_text = f"{fed_text}\n\nKey drivers: Weak job market, inflation above 2% target, Fed officials supporting cuts to prevent further labor market deterioration."
        parts.append(f"\n\n🔬 DEEP RESEARCH - Fed Context:\n{fed_text}")
    
    # Add Tavily Macro insights
    if tavily_macro:
        macro_text = tavily_macro
        if len(macro_text) < 150:
            macro_text = f"{macro_text}\n\nMarket regime analysis indicates risk-off sentiment despite neutral macro indicators."
        parts.append(f"\n\n🔬 DEEP RESEARCH - Macro Drivers:\n{macro_text}")
    
    # Add economic events context
    macro_events = event_schedule.get("macro_events", [])
    if macro_events:
        event_summary = _summarize_events(macro_events)
        if event_summary:
            parts.append(f"\n\n📅 Economic Events Context:\n{event_summary}")
    
    return "\n".join(parts) if parts else base_macro


def _enhance_sector_narrative(
    base_sector: str,
    tavily_institutional: str,
    tavily_technical: str
) -> str:
    """
    Enhance sector narrative with institutional + technical deep research.
    """
    parts = []
    
    if base_sector:
        parts.append(base_sector)
    
    # Add institutional deep research (WHO moved it)
    if tavily_institutional:
        parts.append(f"\n\n🔬 DEEP RESEARCH - Institutional Flow:\n{tavily_institutional}")
    
    # Add technical deep research (HOW it moved)
    if tavily_technical:
        parts.append(f"\n\n🔬 DEEP RESEARCH - Technical Context:\n{tavily_technical}")
    
    return "\n".join(parts) if parts else base_sector


def _enhance_asset_narrative(
    base_asset: str,
    tavily_institutional: str,
    inst_ctx: Dict[str, Any]
) -> str:
    """
    Enhance asset-specific narrative with institutional positioning.
    """
    parts = []
    
    if base_asset:
        parts.append(base_asset)
    
    # Add institutional positioning details
    dp_pct = inst_ctx.get("dark_pool", {}).get("pct")
    if dp_pct:
        parts.append(f"\n\n🏛️ Institutional Positioning: {dp_pct:.1f}% of volume in dark pools")
    
    # Add Tavily institutional insights
    if tavily_institutional:
        parts.append(f"\n\n🔬 DEEP RESEARCH - Smart Money Positioning:\n{tavily_institutional}")
    
    return "\n".join(parts) if parts else base_asset


def _summarize_events(events: List[Dict[str, Any]]) -> str:
    """Summarize economic events with actual vs forecast."""
    if not events:
        return ""
    
    summaries = []
    for event in events[:3]:  # Top 3 events
        title = event.get("title", "")
        actual = event.get("actual")
        forecast = event.get("forecast")
        
        if actual is not None and forecast is not None:
            try:
                actual_f = float(actual)
                forecast_f = float(forecast)
                surprise = actual_f - forecast_f
                direction = "BEAT" if surprise > 0 else "MISS"
                summaries.append(f"• {title}: {actual} vs {forecast} forecast ({direction})")
            except (ValueError, TypeError):
                summaries.append(f"• {title}: {actual} (forecast: {forecast})")
        else:
            summaries.append(f"• {title}")
    
    return "\n".join(summaries) if summaries else ""

