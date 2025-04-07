import { NextResponse } from 'next/server';
import { fetchMarketData } from '@/lib/connectors/yahoo-finance';

/**
 * API route for fetching market data
 * GET /api/market?ticker=AAPL
 */
export async function GET(request: Request) {
  // Extract ticker parameter from URL
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker');
  
  // Validate ticker parameter
  if (!ticker) {
    return NextResponse.json(
      { error: 'Missing required parameter: ticker' },
      { status: 400 }
    );
  }
  
  try {
    // Fetch market data
    const marketData = await fetchMarketData(ticker);
    
    // Return the market data
    return NextResponse.json(marketData);
  } catch (error) {
    console.error(`Error in market API route:`, error);
    
    // Return error response
    return NextResponse.json(
      { error: 'Failed to fetch market data' },
      { status: 500 }
    );
  }
} 