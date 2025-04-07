import { NextRequest, NextResponse } from 'next/server';
import { fetchOptionsChain, prepareOptionsForLLM } from '@/lib/connectors/options-chain';
import { fetchStockInsights } from '@/lib/connectors/yahoo-finance-insights';

/**
 * GET /api/options/{ticker}?expiration={YYYY-MM-DD}
 * Fetches options chain data for a specific ticker, with optional expiration date
 */
export async function GET(
  request: NextRequest,
  { params }: { params: { ticker: string } }
) {
  try {
    // Extract ticker from URL params
    const ticker = params.ticker.toUpperCase();
    
    // Extract expiration date from query params if provided
    const url = new URL(request.url);
    const expiration = url.searchParams.get('expiration') || undefined;
    const format = url.searchParams.get('format') || 'chain';
    
    console.log(`[api/options/${ticker}] Fetching options data${expiration ? ` for ${expiration}` : ''}`);
    console.log(`[api/options/${ticker}] Using RapidAPI Host: ${process.env.RAPIDAPI_HOST || process.env.NEXT_PUBLIC_RAPIDAPI_HOST}`);
    console.log(`[api/options/${ticker}] API Key Defined: ${!!process.env.RAPIDAPI_KEY || !!process.env.NEXT_PUBLIC_RAPIDAPI_KEY}`);
    
    // Fetch options chain data
    try {
      const optionsChain = await fetchOptionsChain(ticker, expiration);
      
      // If format is 'llm', prepare the data for LLM consumption
      if (format === 'llm') {
        try {
          // Try to fetch technical insights to enrich the options data
          const insights = await fetchStockInsights(ticker);
          const llmData = prepareOptionsForLLM(optionsChain, insights);
          
          console.log(`[api/options/${ticker}] Returning LLM formatted options data`);
          return NextResponse.json({
            success: true,
            data: llmData
          });
        } catch (insightError) {
          console.warn(`[api/options/${ticker}] Error fetching insights: ${insightError}`);
          // If insights fetch fails, still return the options data without insights
          const llmData = prepareOptionsForLLM(optionsChain);
          
          return NextResponse.json({
            success: true,
            data: llmData,
            warnings: ['Failed to fetch technical insights']
          });
        }
      }
      
      // Default format - return chain data directly
      console.log(`[api/options/${ticker}] Returning options chain data`);
      return NextResponse.json({
        success: true,
        data: optionsChain
      });
    } catch (fetchError: any) {
      console.error(`[api/options/${ticker}] Error fetching options chain: ${fetchError.message}`);
      console.error(`[api/options/${ticker}] Full error:`, fetchError);
      
      return NextResponse.json(
        { 
          success: false, 
          error: fetchError.message || 'Failed to fetch options data'
        },
        { status: 500 }
      );
    }
  } catch (error: any) {
    console.error(`[api/options/[ticker]] Error: ${error.message}`);
    return NextResponse.json(
      { 
        success: false, 
        error: error.message || 'Failed to fetch options data'
      },
      { status: 500 }
    );
  }
} 