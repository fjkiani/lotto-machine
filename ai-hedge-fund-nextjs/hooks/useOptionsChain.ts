'use client';

import { useState, useEffect } from 'react';
import { OptionsChain } from '@/lib/connectors/options-chain';

interface UseOptionsChainOptions {
  ticker: string;
  expiration?: string;
  autoFetch?: boolean;
}

interface UseOptionsChainResult {
  data: OptionsChain | null;
  isLoading: boolean;
  error: string | null;
  fetchOptionsChain: (newExpiration?: string) => Promise<void>;
  expirationDates?: string[];
}

/**
 * Hook for fetching options chain data
 */
export function useOptionsChain({
  ticker,
  expiration,
  autoFetch = true
}: UseOptionsChainOptions): UseOptionsChainResult {
  const [data, setData] = useState<OptionsChain | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Function to fetch options chain data
  const fetchOptionsChain = async (newTicker?: string) => {
    const targetTicker = newTicker || ticker;
    
    if (!targetTicker) {
      setError('Ticker is required');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Build the API URL with query parameters
      let url = `/api/options/${targetTicker.toUpperCase()}`;
      const params = new URLSearchParams();
      
      if (expiration) {
        params.append('expiration', expiration);
      }
      
      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      console.log(`[useOptionsChain] Fetching data from ${url}`);
      console.log(`[useOptionsChain] Using host: ${process.env.NEXT_PUBLIC_RAPIDAPI_HOST}`);

      // Fetch options chain data
      const response = await fetch(url);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error: ${response.status}. ${errorText}`);
      }

      const responseData = await response.json();

      if (!responseData.success) {
        throw new Error(responseData.error || 'Failed to fetch options chain data');
      }

      console.log(`[useOptionsChain] Successfully fetched options chain data for ${targetTicker}`);
      console.log(`[useOptionsChain] Data has expirationDates: ${responseData.data && responseData.data.expirationDates && responseData.data.expirationDates.length > 0}`);
      
      setData(responseData.data);
    } catch (e: any) {
      console.error(`[useOptionsChain] Error: ${e.message}`);
      setError(e.message || 'Failed to fetch options chain data');
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch data on component mount if autoFetch is true
  useEffect(() => {
    if (autoFetch && ticker) {
      fetchOptionsChain();
    }
  }, [ticker, expiration, autoFetch]);

  // Get the expiration dates from data
  const expirationDates = data?.expirationDates?.map(exp => exp.date) || [];

  return {
    data,
    isLoading,
    error,
    fetchOptionsChain,
    expirationDates
  };
} 