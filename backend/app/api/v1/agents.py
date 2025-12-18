"""
🔥 SAVAGE LLM AGENT API ENDPOINTS

Grounded in REAL data structures from the codebase.
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.dependencies import get_monitor_bridge, get_redis
from backend.app.services.savage_agents import (
    MarketAgent, SignalAgent, DarkPoolAgent, NarrativeBrainAgent
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


@router.get("/agents/narrative/current")
async def get_current_narrative(
    monitor_bridge: MonitorBridge = Depends(get_monitor_bridge),
    redis_client = Depends(get_redis)
):
    """
    Get current narrative brain synthesis
    
    Returns:
        Unified narrative with all agent insights
    """
    # Initialize all agents
    agents = [
        MarketAgent(redis_client),
        SignalAgent(redis_client),
        DarkPoolAgent(redis_client),
    ]
    
    narrative_brain = NarrativeBrainAgent(agents, redis_client)
    
    # Gather ALL data from monitor bridge
    all_data = {
        "market": monitor_bridge.get_market_data('SPY'),
        "signals": monitor_bridge.get_current_signals('SPY'),
        "synthesis_result": monitor_bridge.get_synthesis_result(),
        "narrative_update": monitor_bridge.get_narrative_update(),
        "dp_data": {
            "levels": monitor_bridge.get_dp_levels('SPY'),
            "prints": [],
            "battlegrounds": [],
            "summary": {},
            "symbol": "SPY",
            "current_price": monitor_bridge.get_market_data('SPY').get('price', 0.0) if monitor_bridge.get_market_data('SPY') else 0.0
        },
        "gamma_data": {},  # TODO: Fetch gamma data
        "institutional_context": {},  # TODO: Fetch inst context
        "checker_alerts": []  # TODO: Fetch recent alerts
    }
    
    # Synthesize
    try:
        narrative = narrative_brain.synthesize(all_data)
        return narrative
    except Exception as e:
        logger.error(f"Error synthesizing narrative: {e}", exc_info=True)
        raise HTTPException(500, f"Narrative synthesis failed: {str(e)}")


@router.post("/agents/narrative/ask")
async def ask_narrative_brain(
    question: str,
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
    if not question or not question.strip():
        raise HTTPException(400, "Question is required")
    
    # Initialize narrative brain
    agents = [
        MarketAgent(redis_client),
        SignalAgent(redis_client),
        DarkPoolAgent(redis_client),
    ]
    
    narrative_brain = NarrativeBrainAgent(agents, redis_client)
    
    # Gather current data
    all_data = {
        "market": monitor_bridge.get_market_data('SPY'),
        "signals": monitor_bridge.get_current_signals('SPY'),
        "synthesis_result": monitor_bridge.get_synthesis_result(),
        "narrative_update": monitor_bridge.get_narrative_update(),
        "dp_data": {
            "levels": monitor_bridge.get_dp_levels('SPY'),
            "prints": [],
            "battlegrounds": [],
            "summary": {},
            "symbol": "SPY",
            "current_price": monitor_bridge.get_market_data('SPY').get('price', 0.0) if monitor_bridge.get_market_data('SPY') else 0.0
        },
        "gamma_data": {},
        "institutional_context": {},
        "checker_alerts": []
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

