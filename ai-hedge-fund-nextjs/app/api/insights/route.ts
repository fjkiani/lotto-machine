import { NextRequest, NextResponse } from 'next/server';
import { fetchStockInsights } from '@/lib/connectors/yahoo-finance-insights';

/**
 * GET /api/insights?ticker=SYMBOL
 * Fetches technical insights for a given ticker
 */
export async function GET(request: NextRequest) {
  try {
    // Extract ticker from URL
    const url = new URL(request.url);
    const ticker = url.searchParams.get('ticker');
    
    console.log(`[api/insights] Received request for ticker: ${ticker}`);
    
    // Validate ticker
    if (!ticker) {
      console.warn('[api/insights] Missing ticker parameter');
      return NextResponse.json(
        { error: 'Missing ticker parameter' },
        { status: 400 }
      );
    }
    
    // Try to fetch technical insights
    console.log(`[api/insights] Fetching technical insights for ${ticker}`);
    const insights = await fetchStockInsights(ticker);
    
    // Handle missing data
    if (!insights) {
      console.warn(`[api/insights] Failed to fetch insights for ${ticker}`);
      return NextResponse.json(
        { 
          error: 'Failed to fetch insights',
          message: `Could not retrieve technical insights for ${ticker}. Please try again later.`,
          timestamp: new Date().toISOString()
        },
        { status: 404 }
      );
    }
    
    // Log successful fetch
    console.log(`[api/insights] Successfully fetched insights for ${ticker}`);
    
    // Return the insights data
    return NextResponse.json({
      data: insights,
      ticker: ticker,
      timestamp: new Date().toISOString()
    });
  } catch (error: any) {
    // Log the error
    console.error('[api/insights] Error fetching insights:', error);
    
    // Return an appropriate error response
    return NextResponse.json(
      { 
        error: 'Failed to fetch insights',
        message: error.message || 'An unexpected error occurred',
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    );
  }
} 