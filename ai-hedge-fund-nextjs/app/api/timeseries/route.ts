import { NextResponse } from 'next/server';
import { fetchStockTimeSeries } from '@/lib/connectors/real-time-finance';
import { generateMockTimeSeriesData } from '@/lib/mock/time-series-data';

/**
 * API route for fetching stock time series data
 * GET /api/timeseries?ticker=AAPL&period=1D&interval=1h
 */
export async function GET(request: Request) {
  // Extract parameters from URL
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker');
  const period = searchParams.get('period') || '1D';
  const interval = searchParams.get('interval') || undefined;
  
  // Validate ticker parameter
  if (!ticker) {
    return NextResponse.json(
      { error: 'Missing required parameter: ticker' },
      { status: 400 }
    );
  }
  
  try {
    console.log(`Fetching time series data for ${ticker}, period: ${period}`);
    
    // Check if API keys are available
    const apiKeyAvailable = !!(process.env.RAPIDAPI_KEY || process.env.NEXT_PUBLIC_RAPIDAPI_KEY);
    
    let timeSeriesData;
    let usedMockData = false;
    
    if (apiKeyAvailable) {
      try {
        // Attempt to fetch real data from the API
        timeSeriesData = await fetchStockTimeSeries(ticker, period as string, interval);
        console.log(`Successfully fetched ${timeSeriesData.time_series?.length || 0} data points for ${ticker}`);
      } catch (apiError) {
        // If API call fails, use mock data
        console.warn(`API call failed, falling back to mock data:`, apiError);
        usedMockData = true;
        timeSeriesData = generateMockTimeSeriesData(ticker, period);
        console.log(`Generated ${timeSeriesData.time_series?.length || 0} mock data points for ${ticker}`);
      }
    } else {
      // If no API key, use mock data
      console.log('RapidAPI Key is missing, using mock data');
      usedMockData = true;
      timeSeriesData = generateMockTimeSeriesData(ticker, period);
      console.log(`Generated ${timeSeriesData.time_series?.length || 0} mock data points for ${ticker}`);
    }
    
    // Return the time series data
    return NextResponse.json({
      ticker,
      ...timeSeriesData, // Spread all the properties directly
      source: usedMockData ? 'mock' : 'api',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error(`Error in time series API route:`, error);
    
    // Generate mock data as a last resort
    try {
      const mockData = generateMockTimeSeriesData(ticker, period);
      
      console.log(`Returning mock data after error`);
      
      return NextResponse.json({
        ticker,
        ...mockData,
        source: 'mock',
        warning: 'An error occurred with the primary data source',
        timestamp: new Date().toISOString()
      });
    } catch (mockError) {
      // If even mock data generation fails, return an error
      return NextResponse.json(
        { 
          error: 'Failed to fetch time series data',
          details: error instanceof Error ? error.message : 'Unknown error',
          ticker 
        },
        { status: 500 }
      );
    }
  }
} 