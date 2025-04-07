'use client';

import useSWR from 'swr';
import { TrendItem, MarketGainersLosers } from '@/lib/connectors/real-time-finance';

const fetcher = (url: string) => fetch(url).then(res => {
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
});

type TrendType = 'gainers' | 'losers' | 'actives' | 'advanced_decline' | 'price_volume' | 'all';

interface UseTrendsResult {
  data: TrendsData | null;
  isLoading: boolean;
  isError: Error | null;
  mutate: () => void;
}

// Multiple type options depending on the requested trend type
type TrendsData = 
  | { type: TrendType; trends: TrendItem[] } 
  | MarketGainersLosers;

/**
 * Custom hook for fetching market trends using SWR
 * @param type Type of trends to fetch (default: 'all')
 */
export function useMarketTrends(type: TrendType = 'all'): UseTrendsResult {
  const url = `/api/trends?type=${type}`;
  
  const { data, error, isLoading, mutate } = useSWR(url, fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 300000, // 5 minutes
  });
  
  return {
    data,
    isLoading,
    isError: error,
    mutate,
  };
} 