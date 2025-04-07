'use client';

import useSWR from 'swr';
import { 
  TechnicalAnalysisResult, 
  ComprehensiveAnalysisResult 
} from '@/lib/connectors/llm';

export type AnalysisType = 'technical' | 'comprehensive';
export type AnalysisProvider = 'openai' | 'gemini';

interface UseAnalysisOptions {
  ticker: string;
  type: AnalysisType;
  provider: AnalysisProvider;
  period?: string;
}

interface AnalysisResponseCommon {
  ticker: string;
  analysis_type: AnalysisType;
  provider: AnalysisProvider;
  timestamp: string;
}

interface TechnicalAnalysisResponse extends AnalysisResponseCommon {
  analysis_type: 'technical';
  result: TechnicalAnalysisResult;
}

interface ComprehensiveAnalysisResponse extends AnalysisResponseCommon {
  analysis_type: 'comprehensive';
  result: ComprehensiveAnalysisResult;
}

type AnalysisResponse = TechnicalAnalysisResponse | ComprehensiveAnalysisResponse;

interface UseAnalysisResult {
  analysis: AnalysisResponse | null;
  isLoading: boolean;
  isValidating: boolean;
  error: string | null;
  timestamp: string | null;
  refresh: () => void;
}

/**
 * Hook for fetching stock analysis from the API
 */
export default function useAnalysis({ ticker, type, provider, period = '1M' }: UseAnalysisOptions): UseAnalysisResult {
  const fetcher = async (url: string) => {
    console.log(`[useAnalysis] Fetching analysis from: ${url}`);
    try {
      const response = await fetch(url);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        console.error(`[useAnalysis] API error: ${response.status}`, errorData);
        throw new Error(errorData.error || `API responded with status ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`[useAnalysis] Successfully fetched ${type} analysis for ${ticker} using ${provider}`);
      return data;
    } catch (error) {
      console.error(`[useAnalysis] Error fetching analysis:`, error);
      throw error;
    }
  };
  
  // Create a unique key for this analysis request
  const apiUrl = `/api/analysis?ticker=${ticker}&type=${type}&provider=${provider}&period=${period}`;
  
  // Use SWR for data fetching with caching and revalidation
  const { data, error, isLoading, isValidating, mutate } = useSWR(
    ticker ? apiUrl : null, 
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateIfStale: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: true,
      errorRetryCount: 2,
      dedupingInterval: 10000, // 10 seconds
      focusThrottleInterval: 5000, // 5 seconds
    }
  );
  
  return {
    analysis: data?.result || null,
    isLoading,
    isValidating,
    error: error?.message || data?.error,
    timestamp: data?.timestamp,
    refresh: mutate
  };
} 