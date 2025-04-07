'use client';

import useSWR from 'swr';
import { NewsArticle } from '@/lib/connectors/real-time-finance';

const fetcher = async (url: string) => {
  try {
    console.log(`[useNews] Fetching from ${url}`);
    const res = await fetch(url);
    
    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[useNews] API error (${res.status}): ${errorText}`);
      throw new Error(`API error: ${res.status}. ${errorText}`);
    }
    
    const data = await res.json();
    console.log(`[useNews] Successfully fetched ${data?.news?.length || 0} news items`);
    return data;
  } catch (error) {
    console.error('[useNews] Fetch error:', error);
    throw error;
  }
};

interface UseNewsResult {
  data: {
    ticker: string;
    news: NewsArticle[];
  } | null;
  isLoading: boolean;
  isError: Error | null;
  mutate: () => void;
}

/**
 * Custom hook for fetching news using SWR
 * @param ticker Optional stock ticker for stock-specific news, if undefined fetches market news
 */
export function useNews(ticker?: string): UseNewsResult {
  const url = ticker ? `/api/news?ticker=${ticker}` : '/api/news';
  
  const { data, error, isLoading, mutate } = useSWR(url, fetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 300000, // 5 minutes
    shouldRetryOnError: true,
    errorRetryCount: 3,
    errorRetryInterval: 5000,
    fallbackData: ticker 
      ? { ticker, news: [] } 
      : { ticker: 'MARKET', news: [] },
  });
  
  return {
    data: data || { ticker: ticker || 'MARKET', news: [] },
    isLoading,
    isError: error,
    mutate,
  };
} 