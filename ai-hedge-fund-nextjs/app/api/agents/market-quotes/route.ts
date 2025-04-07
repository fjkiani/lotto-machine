import { NextRequest, NextResponse } from 'next/server';
import { AgentType, getSystemPromptByType } from '@/lib/connectors/agent-hub';
import { fetchMarketQuotes, prepareMarketQuotesForLLM, generateMarketQuoteAnalysisPrompt } from '@/lib/connectors/market-quotes';
import { analyzeWithLLM } from '@/lib/connectors/llm-connector';

// Analysis types for market quotes
export type MarketQuoteAnalysisType = 'basic' | 'technical' | 'fundamental' | 'comprehensive';

/**
 * POST handler for market quote analysis
 */
export async function POST(req: NextRequest) {
  try {
    // Parse request body
    const body = await req.json();
    const { 
      tickers, 
      analysisType = 'technical' as MarketQuoteAnalysisType,
      modelProvider = 'openai',
      temperature = 0.2
    } = body;

    // Validate request
    if (!tickers || !Array.isArray(tickers) || tickers.length === 0) {
      return NextResponse.json(
        { error: 'Missing or invalid tickers parameter' },
        { status: 400 }
      );
    }

    // Log analysis request
    console.log(`[market-quotes/route] Analyzing quotes for ${tickers.join(', ')} using ${analysisType} analysis`);

    // Fetch market quotes
    const marketQuotes = await fetchMarketQuotes(tickers);
    
    if (Object.keys(marketQuotes).length === 0) {
      return NextResponse.json(
        { error: 'Failed to fetch market quotes data' },
        { status: 500 }
      );
    }

    // Prepare data for LLM analysis
    const preparedData = prepareMarketQuotesForLLM(marketQuotes);
    
    // Get the system prompt for market quote analysis
    const systemPrompt = getSystemPromptByType(AgentType.MARKET_QUOTE_ANALYST);

    // Generate the prompt for analysis
    const userPrompt = generateMarketQuoteAnalysisPrompt(preparedData, analysisType as MarketQuoteAnalysisType);

    // Call LLM for analysis
    const analysisResult = await analyzeWithLLM({
      systemPrompt,
      userPrompt,
      modelProvider,
      temperature,
      responseFormat: { type: 'json_object' }
    });

    if (!analysisResult.success) {
      return NextResponse.json(
        { error: 'Failed to generate analysis', details: analysisResult.error },
        { status: 500 }
      );
    }

    // Parse the LLM response
    let analysis;
    try {
      // If the result is a string, parse it as JSON
      if (typeof analysisResult.content === 'string') {
        analysis = JSON.parse(analysisResult.content);
      } else {
        // If it's already an object, use it directly
        analysis = analysisResult.content;
      }

      // Add timestamp to the analysis
      analysis.timestamp = new Date().toISOString();
      
      // Add raw market data for reference if needed
      analysis.raw_data = {
        tickers,
        analysisType
      };

    } catch (error) {
      console.error('[market-quotes/route] Error parsing LLM response:', error);
      return NextResponse.json(
        { 
          error: 'Failed to parse analysis result', 
          raw_response: analysisResult.content
        },
        { status: 500 }
      );
    }

    // Return the analysis
    return NextResponse.json({ 
      success: true, 
      data: analysis
    });
    
  } catch (error) {
    console.error('[market-quotes/route] Unexpected error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * GET handler to obtain available tickers and analysis types (metadata)
 */
export async function GET() {
  // Return supported analysis types and other metadata
  return NextResponse.json({
    supported_analysis_types: ['basic', 'technical', 'fundamental', 'comprehensive'],
    recommended_tickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'SPY', 'QQQ', 'DIA'],
    description: 'Market quote analysis provides insights based on current market data, including price, volume, and related metrics.'
  });
} 