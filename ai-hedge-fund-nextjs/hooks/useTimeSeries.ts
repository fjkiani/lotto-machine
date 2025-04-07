'use client';

import useSWR from 'swr';
import { StockTimeSeriesResponse } from '@/lib/connectors/real-time-finance';

const fetcher = async (url: string) => {
  try {
    console.log(`[useTimeSeries] Fetching from ${url}`);
    const res = await fetch(url);
    
    if (!res.ok) {
      const errorText = await res.text();
      console.error(`[useTimeSeries] API error (${res.status}): ${errorText}`);
      throw new Error(`API error: ${res.status}. ${errorText}`);
    }
    
    const data = await res.json();
    console.log(`[useTimeSeries] Successfully fetched time series data. Source: ${data.source || 'api'}`);
    
    // Ensure time_series exists in the response
    if (!data.time_series || !Array.isArray(data.time_series)) {
      console.warn(`[useTimeSeries] Missing or invalid time_series data for ${data.ticker || 'unknown ticker'}`);
      return null;
    }
    
    console.log(`[useTimeSeries] Fetched ${data.time_series.length} data points`);
    return data;
  } catch (error) {
    console.error('[useTimeSeries] Fetch error:', error);
    throw error;
  }
};

type TimePeriod = '1D' | '5D' | '1M' | '3M' | '6M' | '1Y' | '5Y' | 'MAX';

interface UseTimeSeriesResult {
  data: StockTimeSeriesResponse | null;
  isLoading: boolean;
  isError: Error | null;
  mutate: () => void;
}

/**
 * Custom hook for fetching stock time series data using SWR
 * @param ticker Stock ticker symbol
 * @param period Time period for data
 * @param interval Optional interval for data points
 */
export function useTimeSeries(
  ticker: string, 
  period: TimePeriod = '1D',
  interval?: string
): UseTimeSeriesResult {
  // Construct URL with query parameters
  let url = `/api/timeseries?ticker=${ticker}&period=${period}`;
  if (interval) {
    url += `&interval=${interval}`;
  }
  
  // Create fallback data for empty/error responses
  const fallbackData: StockTimeSeriesResponse = {
    symbol: ticker,
    type: 'stock',
    name: ticker,
    price: 0,
    change: 0,
    change_percent: 0,
    previous_close: 0,
    time_series: []
  };
  
  const { data, error, isLoading, mutate } = useSWR(
    ticker ? url : null, // Only fetch if ticker is provided
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      dedupingInterval: 300000, // 5 minutes
      shouldRetryOnError: true,
      errorRetryCount: 3,
      errorRetryInterval: 5000,
      fallbackData
    }
  );
  
  return {
    data: data || fallbackData,
    isLoading,
    isError: error,
    mutate,
  };
} 