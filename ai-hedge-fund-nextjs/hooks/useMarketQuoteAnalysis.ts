import { useState, useEffect } from 'react';
import { MarketQuoteAnalysis } from '@/lib/connectors/market-quotes';
import { MarketQuoteAnalysisType } from '@/app/api/agents/market-quotes/route';
import { NEXT_PUBLIC_API_BASE_URL } from '@/lib/config';

// Return type for the hook
interface UseMarketQuoteAnalysisReturn {
  analysis: MarketQuoteAnalysis | null;
  isLoading: boolean;
  error: string | null;
  refreshAnalysis: (tickers?: string[], analysisType?: MarketQuoteAnalysisType) => Promise<void>;
}

// Input options for the hook
interface UseMarketQuoteAnalysisOptions {
  initialTickers?: string[];
  analysisType?: MarketQuoteAnalysisType;
  modelProvider?: string;
  temperature?: number;
  autoLoad?: boolean;
}

/**
 * Custom hook for market quote analysis
 * 
 * @param options Configuration options for the hook
 * @returns Analysis results, loading state, and error information
 */
export function useMarketQuoteAnalysis(options: UseMarketQuoteAnalysisOptions = {}): UseMarketQuoteAnalysisReturn {
  const {
    initialTickers = ['AAPL', 'MSFT', 'GOOGL'],
    analysisType = 'technical',
    modelProvider = 'openai',
    temperature = 0.2,
    autoLoad = true
  } = options;

  const [tickers, setTickers] = useState<string[]>(initialTickers);
  const [analysis, setAnalysis] = useState<MarketQuoteAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Function to refresh analysis
  const refreshAnalysis = async (
    newTickers?: string[], 
    newAnalysisType?: MarketQuoteAnalysisType
  ): Promise<void> => {
    // Update tickers if provided
    if (newTickers) {
      setTickers(newTickers);
    }

    // Use new analysis type or fall back to current state
    const analysisTypeToUse = newAnalysisType || analysisType;
    
    // Reset states
    setError(null);
    setIsLoading(true);

    try {
      // Prepare API request
      const tickersToUse = newTickers || tickers;
      
      console.log(`[useMarketQuoteAnalysis] Fetching analysis for ${tickersToUse.join(', ')}`);
      
      // Make the API call
      const response = await fetch(`${NEXT_PUBLIC_API_BASE_URL}/api/agents/market-quotes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tickers: tickersToUse,
          analysisType: analysisTypeToUse,
          modelProvider,
          temperature
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `API responded with status ${response.status}`);
      }

      // Parse the response
      const result = await response.json();
      
      if (!result.success || !result.data) {
        throw new Error('API returned unsuccessful response');
      }

      console.log(`[useMarketQuoteAnalysis] Successfully received analysis for ${tickersToUse.join(', ')}`);
      
      // Set the analysis result
      setAnalysis(result.data);
    } catch (err) {
      console.error('[useMarketQuoteAnalysis] Error fetching analysis:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  // Initial load if autoLoad is true
  useEffect(() => {
    if (autoLoad && tickers.length > 0) {
      refreshAnalysis();
    }
  }, []); // Only run on initial mount

  return {
    analysis,
    isLoading,
    error,
    refreshAnalysis
  };
} 