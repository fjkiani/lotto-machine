"""
🔥 SAVAGE LLM AGENT API ENDPOINTS

Grounded in REAL data structures from the codebase.
"""

import logging
import threading
import time as _time
from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.dependencies import get_monitor_bridge, get_redis
from backend.app.services.savage_agents import (
    MarketAgent, SignalAgent, DarkPoolAgent, NarrativeBrainAgent,
    GammaAgent, SqueezeAgent, OptionsAgent, RedditAgent, MacroAgent
)
from backend.app.integrations.unified_monitor_bridge import MonitorBridge

logger = logging.getLogger(__name__)

router = APIRouter()

# Agent registry
_agents = {}


class AgentAnalysisRequest(BaseModel):
    """Request body for agent analysis"""
    symbol: Optional[str] = "SPY"
    data: Optional[Dict] = None
    context: Optional[Dict] = None


def get_agent(agent_name: str, monitor_bridge: MonitorBridge, redis_client):
    """Get or create agent instance"""
    if agent_name not in _agents:
        if agent_name == "market":
            _agents[agent_name] = MarketAgent(redis_client)
        elif agent_name == "signal":
            _agents[agent_name] = SignalAgent(redis_client)
        elif agent_name == "darkpool":
            _agents[agent_name] = DarkPoolAgent(redis_client)
        elif agent_name == "gamma":
            _agents[agent_name] = GammaAgent(redis_client)
        elif agent_name == "squeeze":
            _agents[agent_name] = SqueezeAgent(redis_client)
        elif agent_name == "options":
            _agents[agent_name] = OptionsAgent(redis_client)
        elif agent_name == "reddit":
            _agents[agent_name] = RedditAgent(redis_client)
        elif agent_name == "macro":
            _agents[agent_name] = MacroAgent(redis_client)
        else:
            raise HTTPException(404, f"Unknown agent: {agent_name}")
    
    return _agents[agent_name]


@router.post("/agents/{agent_name}/analyze")
async def analyze_with_agent(
    agent_name: str,
    request: AgentAnalysisRequest,
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge),
    redis_client = Depends(get_redis)
):
    """
    Analyze data with a specific savage agent
    
    Request body:
    {
        "symbol": "SPY",  # Optional
        "data": {...},  # Optional - domain-specific data
        "context": {...}  # Optional - additional context
    }
    """
    agent = get_agent(agent_name, monitor_bridge, redis_client)
    
    # Get actual data from monitor bridge if not provided
    data = request.data or {}
    if not data:
        # Fetch from monitor bridge based on agent type
        if agent_name == "market":
            # Fetch market data
            market_data = monitor_bridge.get_market_data(request.symbol or "SPY")
            if market_data:
                data = market_data
            else:
                raise HTTPException(404, f"No market data available for {request.symbol}")
        
        elif agent_name == "signal":
            # Fetch signals
            signals = monitor_bridge.get_current_signals(request.symbol or "SPY")
            synthesis = monitor_bridge.get_synthesis_result()
            data = {
                "signals": signals,
                "synthesis": synthesis
            }
        
        elif agent_name == "darkpool":
            # Fetch DP data
            symbol = request.symbol or "SPY"
            levels = monitor_bridge.get_dp_levels(symbol)
            current_price = 0.0
            market_data = monitor_bridge.get_market_data(symbol)
            if market_data:
                current_price = market_data.get('price', 0.0)
            
            data = {
                "levels": levels,
                "prints": [],  # TODO: Fetch actual prints
                "battlegrounds": [],  # TODO: Fetch actual battlegrounds
                "summary": {
                    "buying_pressure": 0,  # TODO: Calculate from data
                    "dp_percent": 0,  # TODO: Calculate from data
                    "total_volume": 0  # TODO: Calculate from data
                },
                "symbol": symbol,
                "current_price": current_price
            }
        
        elif agent_name == "gamma":
            # Fetch gamma data
            symbol = request.symbol or "SPY"
            gamma_data = monitor_bridge.get_gamma_data(symbol)
            if gamma_data:
                data = gamma_data
            else:
                raise HTTPException(404, f"No gamma data available for {symbol}")
        
        elif agent_name == "squeeze":
            # Fetch squeeze data
            symbol = request.symbol or "SPY"
            squeeze_data = monitor_bridge.get_squeeze_data(symbol)
            if squeeze_data:
                data = squeeze_data
            else:
                raise HTTPException(404, f"No squeeze data available for {symbol}")
        
        elif agent_name == "options":
            # Fetch options data
            symbol = request.symbol or "SPY"
            options_data = monitor_bridge.get_options_data(symbol)
            if options_data:
                data = options_data
            else:
                raise HTTPException(404, f"No options data available for {symbol}")
        
        elif agent_name == "reddit":
            # Fetch Reddit data
            symbol = request.symbol or "SPY"
            reddit_data = monitor_bridge.get_reddit_data(symbol)
            if reddit_data:
                data = {
                    "symbol": symbol,
                    "reddit_data": reddit_data
                }
            else:
                # Return empty data if not available
                data = {
                    "symbol": symbol,
                    "reddit_data": {
                        "mentions": 0,
                        "sentiment": "NEUTRAL",
                        "score": 0,
                        "signal_type": "NONE"
                    }
                }
        
        elif agent_name == "macro":
            # Fetch macro data
            macro_data = monitor_bridge.get_macro_data()
            if macro_data:
                data = macro_data
            else:
                raise HTTPException(404, "No macro data available")
    
    context = request.context or {}
    
    # Add synthesis to context if available
    if not context.get('synthesis_result'):
        synthesis = monitor_bridge.get_synthesis_result()
        if synthesis:
            context['synthesis_result'] = synthesis
    
    # Analyze
    try:
        insight = agent.analyze(data, context)
        return insight
    except Exception as e:
        logger.error(f"Error in agent analysis: {e}", exc_info=True)
        raise HTTPException(500, f"Agent analysis failed: {str(e)}")




# Cache for /agents/narrative/current — stale-while-revalidate pattern
_narrative_cache = {"result": None, "timestamp": 0, "computing": False}
_NARRATIVE_CACHE_TTL = 120  # Serve cached for 2 minutes


@router.get("/agents/narrative/current")
async def get_current_narrative(
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge),
    redis_client = Depends(get_redis)
):
    """
    Get current narrative brain synthesis.
    Uses stale-while-revalidate: returns cached result instantly,
    recomputes in background when stale.
    """
    now = _time.time()
    cached = _narrative_cache["result"]
    cache_age = now - _narrative_cache["timestamp"]

    # Return cached if fresh
    if cached and cache_age < _NARRATIVE_CACHE_TTL:
        return cached

    # Return stale cache immediately, trigger background refresh
    if cached and not _narrative_cache["computing"]:
        _narrative_cache["computing"] = True

        def _recompute():
            try:
                result = _compute_narrative(monitor_bridge)
                _narrative_cache["result"] = result
                _narrative_cache["timestamp"] = _time.time()
            except Exception as e:
                logger.error(f"Background narrative recompute failed: {e}")
            finally:
                _narrative_cache["computing"] = False

        threading.Thread(target=_recompute, daemon=True).start()
        return cached

    # No cache — compute synchronously (first request only)
    try:
        result = _compute_narrative(monitor_bridge)
        _narrative_cache["result"] = result
        _narrative_cache["timestamp"] = _time.time()
        return result
    except Exception as e:
        logger.error(f"Error synthesizing narrative: {e}", exc_info=True)
        raise HTTPException(500, f"Narrative synthesis failed: {str(e)}")


def _compute_narrative(monitor_bridge):
    """Heavy compute: gathers all data + LLM synthesis."""
    from backend.app.core.dependencies import get_savage_agents_service
    narrative_brain = get_savage_agents_service()

    symbol = "SPY"
    market_data = monitor_bridge.get_market_data(symbol)
    current_price = market_data.get('price', 0.0) if market_data else 0.0

    all_data = {
        "market": market_data,
        "signals": monitor_bridge.get_current_signals(symbol),
        "synthesis_result": monitor_bridge.get_synthesis_result(),
        "narrative_update": monitor_bridge.get_narrative_update(),
        "dp_data": {
            "levels": monitor_bridge.get_dp_levels(symbol),
            "prints": [],
            "battlegrounds": [],
            "summary": {},
            "symbol": symbol,
            "current_price": current_price
        },
        "gamma": monitor_bridge.get_gamma_data(symbol) or {},
        "squeeze": monitor_bridge.get_squeeze_data(symbol) or {},
        "options": monitor_bridge.get_options_data(symbol) or {},
        "reddit": {
            "symbol": symbol,
            "reddit_data": monitor_bridge.get_reddit_data(symbol) or {
                "mentions": 0,
                "sentiment": "NEUTRAL",
                "score": 0,
                "signal_type": "NONE"
            }
        },
        "macro": monitor_bridge.get_macro_data() or {}
    }

    return narrative_brain.synthesize(all_data)



class NarrativeAskRequest(BaseModel):
    """Request body for narrative brain question"""
    question: str


@router.post("/agents/narrative/ask")
async def ask_narrative_brain(
    request: NarrativeAskRequest,
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge),
    redis_client = Depends(get_redis)
):
    """
    Ask the Narrative Brain a question
    
    Request body:
    {
        "question": "What's happening with SPY right now?"
    }
    """
    question = request.question
    if not question or not question.strip():
        raise HTTPException(400, "Question is required")
    
    # Use the service from dependencies (includes all agents)
    from backend.app.core.dependencies import get_savage_agents_service
    narrative_brain = get_savage_agents_service()
    
    # Gather current data
    symbol = "SPY"
    market_data = monitor_bridge.get_market_data(symbol)
    current_price = market_data.get('price', 0.0) if market_data else 0.0
    
    all_data = {
        "market": market_data,
        "signals": monitor_bridge.get_current_signals(symbol),
        "synthesis_result": monitor_bridge.get_synthesis_result(),
        "narrative_update": monitor_bridge.get_narrative_update(),
        "dp_data": {
            "levels": monitor_bridge.get_dp_levels(symbol),
            "prints": [],
            "battlegrounds": [],
            "summary": {},
            "symbol": symbol,
            "current_price": current_price
        },
        "gamma": monitor_bridge.get_gamma_data(symbol) or {},
        "squeeze": monitor_bridge.get_squeeze_data(symbol) or {},
        "options": monitor_bridge.get_options_data(symbol) or {},
        "reddit": {
            "symbol": symbol,
            "reddit_data": monitor_bridge.get_reddit_data(symbol) or {
                "mentions": 0,
                "sentiment": "NEUTRAL",
                "score": 0,
                "signal_type": "NONE"
            }
        },
        "macro": monitor_bridge.get_macro_data() or {}
    }
    
    # Build question prompt
    from src.data.llm_api import query_llm_savage
    
    # Format all data for prompt
    data_summary = f"""
Market Data: {all_data.get('market', {})}
Signals: {len(all_data.get('signals', []))} active
Synthesis: {all_data.get('synthesis_result', {})}
Narrative: {all_data.get('narrative_update', {})}
"""
    
    prompt = f"""You are the Narrative Brain - the master savage intelligence agent.

USER QUESTION: {question}

CURRENT MARKET DATA:
{data_summary}

YOUR MISSION:
Answer the user's question with brutal honesty. Use ALL available data.
Be specific. Reference numbers. Connect dots. Be actionable.

Answer:"""
    
    # Call savage LLM
    try:
        response = query_llm_savage(prompt, level="chained_pro")
        answer = response.get('response', '') if isinstance(response, dict) else str(response)
        
        return {
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat(),
            "data_sources": list(all_data.keys())
        }
    except Exception as e:
        logger.error(f"Error asking narrative brain: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to answer question: {str(e)}")


@router.get("/agents/health")
async def agents_health():
    """Health check for agents"""
    return {
        "status": "healthy",
        "agents_available": list(_agents.keys()),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/narrative/memory")
async def get_narrative_memory():
    """
    Get cross-session narrative memory.

    Returns daily context, market regime, narrative chain, and recent events
    from the NarrativeMemory database — the data that persists across restarts.
    """
    try:
        from live_monitoring.agents.narrative_brain.narrative_brain import NarrativeMemory
        memory = NarrativeMemory()

        today = datetime.now().strftime('%Y-%m-%d')
        daily_context = memory.get_daily_context(today)
        regime = memory.get_market_regime(today)
        chain = memory.get_narrative_chain(days=7)
        recent_events = memory.get_recent_events(hours=24)
        recent_narratives = memory.get_recent_narratives(hours=24)
        sentiment = memory.get_sentiment_history(days=7)

        return {
            "daily_context": daily_context,
            "market_regime": regime,
            "narrative_chain": chain,
            "recent_events": recent_events,
            "recent_narratives": recent_narratives,
            "sentiment_history": sentiment,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching narrative memory: {e}", exc_info=True)
        return {
            "daily_context": None,
            "market_regime": None,
            "narrative_chain": [],
            "recent_events": [],
            "recent_narratives": [],
            "sentiment_history": [],
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/narrative/previous-session")
async def get_previous_session():
    """
    Get yesterday's session context for morning seeding.
    
    Returns daily context, market regime, and narrative chain from the previous day.
    This is the cross-session bridge — what the system remembers from yesterday.
    """
    try:
        from live_monitoring.agents.narrative_brain.narrative_brain import NarrativeBrain
        brain = NarrativeBrain()
        prev = brain.load_previous_session()

        if prev:
            return {
                "has_data": True,
                "daily_context": prev.get('daily_context'),
                "market_regime": prev.get('market_regime'),
                "narrative_chain": prev.get('narrative_chain', []),
                "timestamp": datetime.now().isoformat()
            }
        return {
            "has_data": False,
            "daily_context": None,
            "market_regime": None,
            "narrative_chain": [],
            "note": "No previous session data (first day or no data saved yesterday)",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching previous session: {e}", exc_info=True)
        return {
            "has_data": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/reddit/trends/{symbol}")
async def get_reddit_sentiment_trend(symbol: str):
    """Get multi-day Reddit sentiment trend for a symbol."""
    try:
        from live_monitoring.exploitation.reddit_sentiment_trends import RedditSentimentTrends
        rt = RedditSentimentTrends()
        return rt.get_sentiment_trend(symbol, days=5)
    except Exception as e:
        logger.error(f"Error getting Reddit trend for {symbol}: {e}")
        return {"symbol": symbol.upper(), "has_data": False, "error": str(e)}


@router.get("/reddit/trending")
async def get_reddit_trending():
    """Get tickers with highest absolute sentiment momentum."""
    try:
        from live_monitoring.exploitation.reddit_sentiment_trends import RedditSentimentTrends
        rt = RedditSentimentTrends()
        trending = rt.get_trending_tickers(top_n=10)
        return {"trending": trending, "count": len(trending), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error getting trending: {e}")
        return {"trending": [], "count": 0, "error": str(e)}


@router.get("/options/pc-ratio-trend")
async def get_options_pc_ratio():
    """Get Put/Call ratio trend from options flow data."""
    try:
        from live_monitoring.exploitation.options_flow_trends import OptionsFlowTrends
        oft = OptionsFlowTrends()
        return oft.get_pc_ratio_trend(days=5)
    except Exception as e:
        logger.error(f"Error getting P/C ratio trend: {e}")
        return {"has_data": False, "error": str(e)}


@router.get("/options/accumulation")
async def get_options_accumulation(symbol: str = None):
    """Detect same-strike multi-day options accumulation."""
    try:
        from live_monitoring.exploitation.options_flow_trends import OptionsFlowTrends
        oft = OptionsFlowTrends()
        results = oft.detect_unusual_accumulation(ticker=symbol, days=5)
        return {"accumulation": results, "count": len(results), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error detecting options accumulation: {e}")
        return {"accumulation": [], "count": 0, "error": str(e)}


@router.get("/price/context/{symbol}")
async def get_price_context(symbol: str):
    """Get cached price context (1d/5d/20d changes, volume, range position)."""
    try:
        from live_monitoring.enrichment.price_context_provider import PriceContextProvider
        pcp = PriceContextProvider()
        return pcp.get_context(symbol)
    except Exception as e:
        logger.error(f"Error getting price context for {symbol}: {e}")
        return {"symbol": symbol.upper(), "has_data": False, "error": str(e)}
