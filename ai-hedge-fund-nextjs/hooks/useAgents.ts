import { useState, useCallback } from 'react';
import { AgentType, AgentResponse, OrchestratedAnalysisResult } from '@/lib/connectors/agent-hub';

/**
 * Return types for the useAgents hook
 */
interface UseAgentSingleReturn<T = any> {
  data: AgentResponse | null;
  isLoading: boolean;
  error: string | null;
  execute: (params: SingleAgentParams) => Promise<void>;
}

interface UseAgentOrchestrateReturn {
  data: OrchestratedAnalysisResult | null;
  isLoading: boolean;
  error: string | null;
  execute: (params: OrchestrateAgentsParams) => Promise<void>;
}

/**
 * Parameter types for agent execution
 */
interface SingleAgentParams {
  agent: AgentType;
  ticker: string;
  period?: string;
  model?: 'openai' | 'gemini';
}

interface OrchestrateAgentsParams {
  agents: AgentType[];
  ticker: string;
  period?: string;
  model?: 'openai' | 'gemini';
  sequential?: boolean;
  primaryAgent?: AgentType;
}

/**
 * Custom hook for executing a single specialized agent
 */
export function useSingleAgent<T = any>(): UseAgentSingleReturn<T> {
  const [data, setData] = useState<AgentResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  
  const execute = useCallback(async (params: SingleAgentParams) => {
    const { agent, ticker, period = '1y', model = 'gemini' } = params;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Build the query string
      const queryParams = new URLSearchParams();
      queryParams.append('agent', agent);
      queryParams.append('ticker', ticker);
      queryParams.append('period', period);
      queryParams.append('model', model);
      
      // Call the API
      const response = await fetch(`/api/agents?${queryParams.toString()}`);
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `API error: ${response.status}`);
      }
      
      const responseData = await response.json();
      setData(responseData);
    } catch (err: any) {
      console.error('Error executing agent:', err);
      setError(err.message || 'An error occurred while executing the agent');
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  return { data, isLoading, error, execute };
}

/**
 * Custom hook for orchestrating multiple specialized agents
 */
export function useOrchestrateAgents(): UseAgentOrchestrateReturn {
  const [data, setData] = useState<OrchestratedAnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  
  const execute = useCallback(async (params: OrchestrateAgentsParams) => {
    const { 
      agents, 
      ticker, 
      period = '1y', 
      model = 'gemini',
      sequential = false,
      primaryAgent
    } = params;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Call the API with POST
      const response = await fetch('/api/agents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          agents,
          ticker,
          period,
          model,
          sequential,
          primaryAgent
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `API error: ${response.status}`);
      }
      
      const responseData = await response.json();
      setData(responseData);
    } catch (err: any) {
      console.error('Error orchestrating agents:', err);
      setError(err.message || 'An error occurred while orchestrating agents');
    } finally {
      setIsLoading(false);
    }
  }, []);
  
  return { data, isLoading, error, execute };
}

/**
 * Main useAgents hook that provides both single and orchestrated agent execution
 */
export function useAgents() {
  const singleAgent = useSingleAgent();
  const orchestrateAgents = useOrchestrateAgents();
  
  return {
    singleAgent,
    orchestrateAgents
  };
} 