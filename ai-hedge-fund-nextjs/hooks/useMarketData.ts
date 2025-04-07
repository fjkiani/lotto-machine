'use client';

import useSWR from 'swr';
import { MarketData } from '@/lib/connectors/yahoo-finance';

const fetcher = (url: string) => fetch(url).then(res => {
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
});

interface UseMarketDataResult {
  data: MarketData | null;
  isLoading: boolean;
  isError: Error | null;
  mutate: () => void;
}

/**
 * Custom hook for fetching market data using SWR
 */
export function useMarketData(ticker: string): UseMarketDataResult {
  const { data, error, isLoading, mutate } = useSWR(
    ticker ? `/api/market?ticker=${ticker}` : null,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 60000, // 1 minute
    }
  );
  
  return {
    data: data as MarketData,
    isLoading,
    isError: error,
    mutate,
  };
} 