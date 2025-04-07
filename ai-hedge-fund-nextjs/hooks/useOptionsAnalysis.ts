'use client';

import { useState } from 'react';
import { OptionsAnalysisResult } from '@/lib/connectors/options-analysis';

type RiskTolerance = 'low' | 'medium' | 'high';

interface UseOptionsAnalysisOptions {
  defaultRiskTolerance?: RiskTolerance;
  defaultModel?: string;
  defaultTemperature?: number;
}

interface UseOptionsAnalysisResult {
  analysis: any | null;
  isLoading: boolean;
  error: string | null;
  analyzeOptions: (ticker: string, riskTolerance?: RiskTolerance, expiration?: string) => Promise<void>;
}

/**
 * Hook for running options analysis
 */
export function useOptionsAnalysis({
  defaultRiskTolerance = 'medium',
  defaultModel = 'gemini-1.5-flash',
  defaultTemperature = 0.2
}: UseOptionsAnalysisOptions = {}): UseOptionsAnalysisResult {
  const [analysis, setAnalysis] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Function to analyze options for a ticker
  const analyzeOptions = async (
    ticker: string, 
    riskTolerance: RiskTolerance = defaultRiskTolerance,
    expiration?: string
  ) => {
    if (!ticker) {
      setError('Ticker is required');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      console.log(`[useOptionsAnalysis] Analyzing options for ${ticker} with ${riskTolerance} risk tolerance`);

      // Call the API to run the analysis
      const response = await fetch('/api/options/analysis', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          ticker,
          riskTolerance,
          expiration,
          model: defaultModel,
          temperature: defaultTemperature
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error: ${response.status}. ${errorText}`);
      }

      const responseData = await response.json();

      if (!responseData.success) {
        throw new Error(responseData.error || 'Failed to analyze options data');
      }

      console.log(`[useOptionsAnalysis] Successfully received analysis for ${ticker}`);
      setAnalysis(responseData.data);
    } catch (e: any) {
      console.error(`[useOptionsAnalysis] Error: ${e.message}`);
      setError(e.message || 'Failed to analyze options data');
    } finally {
      setIsLoading(false);
    }
  };

  return {
    analysis,
    isLoading,
    error,
    analyzeOptions
  };
} 