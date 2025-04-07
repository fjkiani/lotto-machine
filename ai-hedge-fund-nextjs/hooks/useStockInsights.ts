'use client';

import useSWR from 'swr';
import { InstrumentInfo } from '@/lib/connectors/yahoo-finance-insights';

const fetcher = async (url: string) => {
  try {
    console.log(`[useStockInsights] Fetching from ${url}`);
    const res = await fetch(url);
    
    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[useStockInsights] API error (${res.status}): ${errorText}`);
      throw new Error(`API error: ${res.status}. ${errorText}`);
    }
    
    const data = await res.json();
    console.log(`[useStockInsights] Successfully fetched insights data for ${data?.ticker || 'unknown ticker'}`);
    
    // Updated to use the new response format where insights are under 'data' key
    return data.data; // Return just the insights part of the response
  } catch (error) {
    console.error('[useStockInsights] Fetch error:', error);
    throw error;
  }
};

interface UseStockInsightsResult {
  data: InstrumentInfo | null;
  isLoading: boolean;
  isError: Error | null;
  mutate: () => void;
}

/**
 * Custom hook for fetching stock technical insights using SWR
 */
export function useStockInsights(ticker: string): UseStockInsightsResult {
  const { data, error, isLoading, mutate } = useSWR(
    ticker ? `/api/insights?ticker=${ticker}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 900000, // 15 minutes
      shouldRetryOnError: true,
      errorRetryCount: 3
    }
  );
  
  return {
    data: data as InstrumentInfo,
    isLoading,
    isError: error,
    mutate,
  };
} 