import { NextResponse } from 'next/server';
import { fetchMarketData } from '@/lib/connectors/yahoo-finance';
import { fetchStockInsights } from '@/lib/connectors/yahoo-finance-insights';
import { fetchStockTimeSeries } from '@/lib/connectors/real-time-finance';
import { 
  generateTechnicalAnalysis, 
  generateComprehensiveAnalysis 
} from '@/lib/connectors/llm';

/**
 * API route for LLM-powered analysis
 * GET /api/analysis?ticker=AAPL&type=technical|comprehensive&provider=openai|gemini
 */
export async function GET(request: Request) {
  // Extract parameters from URL
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker');
  const analysisType = searchParams.get('type') || 'technical';
  const provider = (searchParams.get('provider') || 'openai') as 'openai' | 'gemini';
  const period = searchParams.get('period') || '1M';
  
  // Validate ticker parameter
  if (!ticker) {
    return NextResponse.json(
      { error: 'Missing required parameter: ticker' },
      { status: 400 }
    );
  }
  
  // Validate analysis type parameter
  const validTypes = ['technical', 'comprehensive'];
  if (!validTypes.includes(analysisType)) {
    return NextResponse.json(
      { error: `Invalid analysis type: ${analysisType}. Valid options are: ${validTypes.join(', ')}` },
      { status: 400 }
    );
  }
  
  // Validate provider parameter
  const validProviders = ['openai', 'gemini'];
  if (!validProviders.includes(provider)) {
    return NextResponse.json(
      { error: `Invalid provider: ${provider}. Valid options are: ${validProviders.join(', ')}` },
      { status: 400 }
    );
  }
  
  try {
    // Fetch market data
    const marketData = await fetchMarketData(ticker);
    
    // Fetch technical insights
    const insights = await fetchStockInsights(ticker);
    
    if (!insights) {
      return NextResponse.json(
        { error: 'Failed to fetch technical insights for this ticker' },
        { status: 404 }
      );
    }
    
    // For comprehensive analysis, also fetch time series data
    let timeSeries = undefined;
    if (analysisType === 'comprehensive') {
      try {
        const timeSeriesData = await fetchStockTimeSeries(ticker, period as string);
        timeSeries = timeSeriesData.time_series;
      } catch (timeSeriesError) {
        console.warn(`Error fetching time series for ${ticker}:`, timeSeriesError);
        // Continue without time series data
      }
    }
    
    // Generate the analysis based on the specified type
    if (analysisType === 'technical') {
      const analysis = await generateTechnicalAnalysis(ticker, marketData, insights, provider);
      return NextResponse.json({
        ticker,
        analysis_type: analysisType,
        provider,
        result: analysis,
        timestamp: new Date().toISOString()
      });
    } else {
      const analysis = await generateComprehensiveAnalysis(ticker, marketData, insights, timeSeries, provider);
      return NextResponse.json({
        ticker,
        analysis_type: analysisType,
        provider,
        result: analysis,
        timestamp: new Date().toISOString()
      });
    }
  } catch (error) {
    console.error(`Error in analysis API route:`, error);
    
    // Return error response
    return NextResponse.json(
      { error: 'Failed to generate analysis. Please try again later.' },
      { status: 500 }
    );
  }
} 