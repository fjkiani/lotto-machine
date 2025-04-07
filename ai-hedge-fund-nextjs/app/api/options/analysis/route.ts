import { NextRequest, NextResponse } from 'next/server';
import { fetchOptionsChain, prepareOptionsForLLM, OptionsAnalysisData } from '@/lib/connectors/options-chain';
import { analyzeOptionsWithLLM } from '@/lib/connectors/options-analysis';
import { fetchStockInsights } from '@/lib/connectors/yahoo-finance-insights';
import { LLMAnalysisRequest } from '@/lib/connectors/llm-connector';

/**
 * POST /api/options/analysis
 * Performs LLM-powered options analysis given a ticker symbol and risk tolerance
 */
export async function POST(request: NextRequest) {
  try {
    // Parse request body
    const body = await request.json();
    const { 
      ticker, 
      riskTolerance = 'medium', 
      expiration,
      model = 'gemini-1.5-flash',
      temperature = 0.2 
    } = body;
    
    console.log(`[api/options/analysis] Analyzing options for ${ticker} with ${riskTolerance} risk tolerance`);
    
    if (!ticker) {
      return NextResponse.json(
        { error: 'Missing required parameter: ticker' },
        { status: 400 }
      );
    }
    
    // Validate risk tolerance
    if (!['low', 'medium', 'high'].includes(riskTolerance)) {
      return NextResponse.json(
        { error: 'Invalid risk tolerance. Must be one of: low, medium, high' },
        { status: 400 }
      );
    }
    
    // Fetch options chain data
    const optionsChain = await fetchOptionsChain(ticker.toUpperCase(), expiration);
    
    // Try to fetch technical insights to enrich the options data
    let optionsData: OptionsAnalysisData;
    try {
      const insights = await fetchStockInsights(ticker.toUpperCase());
      optionsData = prepareOptionsForLLM(optionsChain, insights);
    } catch (insightError) {
      console.warn(`[api/options/analysis] Error fetching insights: ${insightError}`);
      // If insights fetch fails, still prepare the options data without insights
      optionsData = prepareOptionsForLLM(optionsChain);
    }
    
    // Generate the prompt for the LLM
    const prompt = generateOptionsAnalysisPrompt(optionsData, riskTolerance);
    
    // Call the LLM connector
    const analysisRequest: LLMAnalysisRequest = {
      systemPrompt: 'You are a professional options trader and financial analyst.',
      userPrompt: prompt,
      modelProvider: model.includes('gemini') ? 'gemini' : 'openai',
      model: model,
      temperature: temperature,
      responseFormat: { type: 'json_object' }
    };
    
    // Import dynamically to avoid SSR issues
    const { analyzeWithLLM } = await import('@/lib/connectors/llm-connector');
    const analysisResponse = await analyzeWithLLM(analysisRequest);
    
    if (!analysisResponse.success) {
      throw new Error(`LLM analysis failed: ${analysisResponse.error}`);
    }
    
    // Process LLM response
    let content = analysisResponse.content;
    if (typeof content === 'string') {
      try {
        content = JSON.parse(content);
      } catch (e) {
        console.error('[api/options/analysis] Failed to parse LLM response as JSON');
      }
    }
    
    // Return the analysis results
    return NextResponse.json({
      success: true,
      ticker,
      analysis_type: 'options',
      risk_tolerance: riskTolerance,
      model: model,
      timestamp: new Date().toISOString(),
      data: content
    });
    
  } catch (error: any) {
    console.error(`[api/options/analysis] Error: ${error.message}`);
    return NextResponse.json(
      { 
        success: false, 
        error: error.message || 'Failed to analyze options'
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/options/analysis
 * Returns metadata about options analysis
 */
export async function GET() {
  return NextResponse.json({
    supported_risk_tolerances: ['low', 'medium', 'high'],
    supported_models: ['gemini-1.5-flash', 'gpt-4o'],
    default_model: 'gemini-1.5-flash',
    recommended_tickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'SPY', 'QQQ', 'IWM']
  });
}

/**
 * Generate a prompt for the LLM to analyze options data
 */
function generateOptionsAnalysisPrompt(
  optionsData: OptionsAnalysisData,
  riskTolerance: 'low' | 'medium' | 'high' = 'medium'
): string {
  const ticker = optionsData.underlying_symbol;
  
  return `
    Analyze the options data for ${ticker} and provide recommendations based on a ${riskTolerance} risk tolerance.
    
    Here is the options data:
    ${JSON.stringify(optionsData, null, 2)}
    
    1. Analyze the current market conditions, including implied volatility between calls and puts, and volume/open interest data.
    
    2. Calculate the Put/Call Ratio by dividing total put volume by total call volume.
    
    3. Calculate the IV Skew (difference between OTM put IV and OTM call IV).
    
    4. Evaluate whether the market is overbought or oversold.
    
    5. Recommend an options strategy with specific strikes and expiration, justifying your choice.
    
    6. Estimate the maximum profit and loss potential for the recommended strategy.
    
    7. Determine the overall market sentiment (bullish, bearish, neutral) with a confidence level.
    
    8. Provide the key Greeks (delta, gamma, theta, vega) for ATM options.
    
    9. Explain your reasoning in detail, referencing specific data points.
    
    Format your response as a JSON object with the following structure:
    {
        "market_conditions": {
            "put_call_ratio": float,
            "implied_volatility_skew": float,
            "sentiment": "bullish|bearish|neutral",
            "market_condition": "overbought|oversold|normal",
            "key_observations": [string]
        },
        "recommended_strategies": [
            {
                "strategy_name": string,
                "description": string,
                "implementation": string,
                "max_profit": string,
                "max_loss": string,
                "break_even": string,
                "ideal_conditions": string,
                "exit_strategy": string,
                "risk_level": "low|medium|high"
            }
        ],
        "greeks": {
            "call_delta": float,
            "call_gamma": float,
            "call_theta": float,
            "call_vega": float,
            "put_delta": float,
            "put_gamma": float,
            "put_theta": float,
            "put_vega": float
        },
        "confidence": float,
        "reasoning": string
    }
  `;
}