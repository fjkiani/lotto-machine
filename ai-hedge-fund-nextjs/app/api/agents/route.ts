import { NextResponse } from 'next/server';
import { AgentType, orchestrateAgents, executeAgent, AgentRequest } from '@/lib/connectors/agent-hub';
import { fetchMarketData } from '@/lib/connectors/yahoo-finance';
import { fetchStockInsights } from '@/lib/connectors/yahoo-finance-insights';
import { fetchTimeSeries } from '@/lib/connectors/real-time-finance';
import { fetchOptionsChain, prepareOptionsForLLM } from '@/lib/connectors/options-chain';

/**
 * API route for orchestrating specialized LLM agents
 * 
 * This route can handle:
 * 1. Single agent execution with `/api/agents?agent=technical-analyst`
 * 2. Multiple agent orchestration with `/api/agents/orchestrate`
 */

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const agent = searchParams.get('agent');
    const ticker = searchParams.get('ticker') || 'AAPL';
    const period = searchParams.get('period') || '1y';
    const model = (searchParams.get('model') || 'gemini') as 'openai' | 'gemini';
    
    if (!agent) {
      return NextResponse.json(
        { error: 'Missing required parameter: agent' },
        { status: 400 }
      );
    }
    
    if (!Object.values(AgentType).includes(agent as AgentType)) {
      return NextResponse.json(
        { error: `Invalid agent type: ${agent}. Valid types are: ${Object.values(AgentType).join(', ')}` },
        { status: 400 }
      );
    }
    
    // Execute a single agent
    console.log(`[api/agents] Executing single agent: ${agent} for ticker: ${ticker}`);
    
    // Prepare agent request
    const agentRequest = await prepareAgentRequest(agent as AgentType, ticker, period, model);
    
    // Execute the agent
    const response = await executeAgent(agentRequest);
    
    return NextResponse.json(response);
  } catch (error: any) {
    console.error('[api/agents] Error executing agent:', error);
    return NextResponse.json(
      { 
        error: 'Failed to execute agent',
        details: error.message || 'Unknown error'
      },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    // Parse request body
    const body = await request.json();
    const { 
      agents, 
      ticker = 'AAPL', 
      period = '1y', 
      model = 'gemini',
      sequential = false,
      primaryAgent
    } = body;
    
    // Validate required parameters
    if (!agents || !Array.isArray(agents) || agents.length === 0) {
      return NextResponse.json(
        { error: 'Missing or invalid required parameter: agents (must be a non-empty array)' },
        { status: 400 }
      );
    }
    
    // Validate agent types
    for (const agent of agents) {
      if (!Object.values(AgentType).includes(agent as AgentType)) {
        return NextResponse.json(
          { error: `Invalid agent type: ${agent}. Valid types are: ${Object.values(AgentType).join(', ')}` },
          { status: 400 }
        );
      }
    }
    
    console.log(`[api/agents] Orchestrating ${agents.length} agents for ticker: ${ticker}`);
    
    // Prepare agent requests
    const agentRequests: AgentRequest[] = [];
    
    for (const agent of agents) {
      const request = await prepareAgentRequest(agent as AgentType, ticker, period, model as 'openai' | 'gemini');
      agentRequests.push(request);
    }
    
    // Orchestrate agents
    const response = await orchestrateAgents(agentRequests, {
      sequential,
      primaryAgent: primaryAgent as AgentType
    });
    
    return NextResponse.json(response);
  } catch (error: any) {
    console.error('[api/agents] Error orchestrating agents:', error);
    return NextResponse.json(
      { 
        error: 'Failed to orchestrate agents',
        details: error.message || 'Unknown error'
      },
      { status: 500 }
    );
  }
}

/**
 * Prepare agent request with required data based on agent type
 */
async function prepareAgentRequest(
  agentType: AgentType,
  ticker: string,
  period: string,
  model: 'openai' | 'gemini'
): Promise<AgentRequest> {
  const request: AgentRequest = {
    agent_type: agentType,
    ticker,
    model
  };
  
  try {
    // Common data needed by multiple agent types
    if ([
      AgentType.TECHNICAL_ANALYST, 
      AgentType.MARKET_OVERVIEW,
      AgentType.RISK_MANAGER
    ].includes(agentType)) {
      // Fetch market data
      request.marketData = await fetchMarketData(ticker);
      
      // Fetch technical insights
      request.technicalInsights = await fetchStockInsights(ticker);
      
      // Add time series data for charts
      if ([AgentType.TECHNICAL_ANALYST].includes(agentType)) {
        request.timeSeries = await fetchTimeSeries(ticker, period);
      }
    }
    
    // Options specialist needs options data
    if (agentType === AgentType.OPTIONS_SPECIALIST) {
      const optionsChain = await fetchOptionsChain(ticker);
      const technicalInsights = await fetchStockInsights(ticker);
      request.optionsData = prepareOptionsForLLM(optionsChain, technicalInsights);
    }
    
    // TODO: Add news items fetching for NEWS_EVALUATOR
    
    return request;
  } catch (error) {
    console.error(`[api/agents] Error preparing data for ${agentType}:`, error);
    // Return the request with available data, the agent will handle missing data
    return request;
  }
} 