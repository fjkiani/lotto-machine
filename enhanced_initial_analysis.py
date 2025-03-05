import os
import json
import logging
import argparse
from typing import Dict, List
from dotenv import load_dotenv
import google.generativeai as genai

from src.data.connectors.yahoo_finance import YahooFinanceConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def perform_enhanced_initial_analysis(market_data: Dict, ticker: str) -> Dict:
    """
    Perform an enhanced initial analysis using the experimental deep reasoning model
    
    Args:
        market_data: Dictionary containing market data for the ticker
        ticker: The ticker symbol being analyzed
        
    Returns:
        Dictionary containing the enhanced initial analysis
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    # Initialize Gemini
    genai.configure(api_key=api_key)
    
    # Prepare the prompt for enhanced initial analysis
    prompt = f"""
    I need you to perform a comprehensive market analysis for {ticker} based on the following market data:
    
    {json.dumps(market_data, indent=2)}
    
    Please provide a detailed analysis that includes:
    
    1. Market Overview:
       - Overall market sentiment (bullish, bearish, or neutral)
       - Key observations about the current market state
       - Market condition assessment (normal, volatile, overbought, oversold)
    
    2. Ticker Analysis for {ticker}:
       - Sentiment assessment
       - Technical signals (including both short-term and long-term moving averages)
       - Support and resistance levels
       - Volume analysis in context
       - Position within 52-week range
       - Risk assessment (with specific risk factors)
       - Price targets (short-term and long-term)
    
    3. Trading Opportunities:
       - Range of potential strategies for different risk profiles
       - Conditional recommendations based on price action
       - Risk-reward ratios
       - Time horizons
    
    4. Macroeconomic Considerations:
       - Brief assessment of relevant macroeconomic factors
       - Potential impact on the ticker
    
    Return your analysis as a JSON object with the following structure:
    {{
        "market_overview": {{
            "sentiment": "bullish/bearish/neutral",
            "key_observations": ["observation 1", "observation 2", ...],
            "market_condition": "normal/volatile/overbought/oversold"
        }},
        "ticker_analysis": {{
            "{ticker}": {{
                "sentiment": "bullish/bearish/neutral",
                "technical_signals": ["signal 1", "signal 2", ...],
                "support_levels": [level1, level2, ...],
                "resistance_levels": [level1, level2, ...],
                "volume_analysis": "description of volume analysis",
                "52w_range_position": "description of position in 52-week range",
                "risk_factors": ["risk 1", "risk 2", ...],
                "risk_level": "low/medium/high",
                "price_target": {{
                    "short_term": value,
                    "long_term": value
                }}
            }}
        }},
        "trading_opportunities": [
            {{
                "ticker": "{ticker}",
                "strategy": "description of strategy",
                "conditions": ["condition 1", "condition 2", ...],
                "rationale": "rationale for the strategy",
                "time_horizon": "short/medium/long",
                "risk_reward_ratio": "ratio",
                "suitable_for": "conservative/moderate/aggressive investors"
            }}
        ],
        "macroeconomic_factors": [
            {{
                "factor": "description of factor",
                "potential_impact": "description of potential impact"
            }}
        ],
        "overall_recommendation": "summary recommendation"
    }}
    
    Ensure your analysis is nuanced, considers multiple perspectives, and avoids overly simplistic recommendations.
    """
    
    # Try to use the experimental model first
    try:
        model_name = "gemini-2.0-flash-thinking-exp-01-21"
        print(f"Attempting to use experimental model for enhanced initial analysis: {model_name}")
        model = genai.GenerativeModel(model_name)
        
        # Set generation config for deep reasoning
        generation_config = {
            "temperature": 0.2,  # Lower temperature for more precise analysis
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
        }
        
        # Generate the response
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        print("Successfully used experimental model for enhanced initial analysis")
        
    except Exception as e:
        print(f"Error using experimental model: {str(e)}")
        print("Falling back to standard Gemini model")
        
        # Fall back to the standard model
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
    
    # Parse the response
    try:
        # Extract JSON from the response text
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            analysis_result = json.loads(json_match.group(0))
        else:
            logger.warning("Could not extract JSON from response")
            analysis_result = {"error": "Could not extract JSON from model response"}
    except Exception as e:
        logger.error(f"Error parsing analysis result: {str(e)}")
        analysis_result = {"error": f"Error parsing model response: {str(e)}"}
    
    return analysis_result

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Perform enhanced initial market analysis using deep reasoning model')
    parser.add_argument('--tickers', nargs='+', default=['SPY'], help='Ticker symbols to analyze (default: SPY)')
    args = parser.parse_args()
    
    tickers = args.tickers
    
    try:
        # Create Yahoo Finance connector
        connector = YahooFinanceConnector()
        
        # Fetch market quotes
        logger.info(f"Fetching market quotes for {', '.join(tickers)}")
        quotes = connector.get_market_quotes(tickers)
        
        # Prepare market data for analysis
        market_data = {}
        for ticker, quote in quotes.items():
            market_data[ticker] = {
                "price": quote.regular_market_price,
                "previous_close": quote.regular_market_previous_close,
                "open": quote.regular_market_open,
                "high": quote.regular_market_day_high,
                "low": quote.regular_market_day_low,
                "volume": quote.regular_market_volume,
                "avg_volume": quote.average_volume,
                "market_cap": quote.market_cap,
                "pe_ratio": quote.trailing_pe,
                "dividend_yield": quote.get_dividend_yield(),
                "52w_high": quote.fifty_two_week_high,
                "52w_low": quote.fifty_two_week_low,
                "50d_avg": quote.fifty_day_average,
                "200d_avg": quote.two_hundred_day_average,
                "day_change_pct": quote.get_day_change_percent(),
                "market_state": quote.market_state,
                "exchange": quote.exchange_name
            }
        
        # Perform enhanced initial analysis for each ticker
        for ticker in tickers:
            logger.info(f"Performing enhanced initial analysis for {ticker}")
            
            # Get market data for this ticker
            ticker_market_data = {ticker: market_data[ticker]} if ticker in market_data else {}
            
            if not ticker_market_data:
                logger.error(f"No market data available for {ticker}")
                continue
            
            # Perform enhanced initial analysis
            analysis_result = perform_enhanced_initial_analysis(ticker_market_data, ticker)
            
            # Save analysis result to file
            output_file = f"enhanced_initial_analysis_{ticker}.json"
            with open(output_file, "w") as f:
                json.dump(analysis_result, f, indent=2)
            logger.info(f"Saved enhanced initial analysis to {output_file}")
            
            # Display results
            print(f"\n===== Enhanced Initial Analysis for {ticker} =====\n")
            
            # Market Overview
            print("Market Overview:")
            print(f"Sentiment: {analysis_result.get('market_overview', {}).get('sentiment', 'N/A')}")
            print(f"Market Condition: {analysis_result.get('market_overview', {}).get('market_condition', 'N/A')}")
            print("\nKey Observations:")
            for observation in analysis_result.get('market_overview', {}).get('key_observations', []):
                print(f"- {observation}")
            
            # Ticker Analysis
            ticker_analysis = analysis_result.get('ticker_analysis', {}).get(ticker, {})
            print(f"\n{ticker} Analysis:")
            print(f"Sentiment: {ticker_analysis.get('sentiment', 'N/A')}")
            print(f"Risk Level: {ticker_analysis.get('risk_level', 'N/A')}")
            
            print("\nTechnical Signals:")
            for signal in ticker_analysis.get('technical_signals', []):
                print(f"- {signal}")
            
            print("\nSupport Levels:")
            for level in ticker_analysis.get('support_levels', []):
                print(f"- {level}")
            
            print("\nResistance Levels:")
            for level in ticker_analysis.get('resistance_levels', []):
                print(f"- {level}")
            
            print(f"\nVolume Analysis: {ticker_analysis.get('volume_analysis', 'N/A')}")
            print(f"52-Week Range Position: {ticker_analysis.get('52w_range_position', 'N/A')}")
            
            print("\nRisk Factors:")
            for risk in ticker_analysis.get('risk_factors', []):
                print(f"- {risk}")
            
            price_target = ticker_analysis.get('price_target', {})
            print(f"\nPrice Targets:")
            print(f"Short-term: {price_target.get('short_term', 'N/A')}")
            print(f"Long-term: {price_target.get('long_term', 'N/A')}")
            
            # Trading Opportunities
            print("\nTrading Opportunities:")
            for opportunity in analysis_result.get('trading_opportunities', []):
                print(f"\nStrategy: {opportunity.get('strategy', 'N/A')}")
                print(f"Time Horizon: {opportunity.get('time_horizon', 'N/A')}")
                print(f"Risk-Reward Ratio: {opportunity.get('risk_reward_ratio', 'N/A')}")
                print(f"Suitable For: {opportunity.get('suitable_for', 'N/A')}")
                print("Conditions:")
                for condition in opportunity.get('conditions', []):
                    print(f"- {condition}")
                print(f"Rationale: {opportunity.get('rationale', 'N/A')}")
            
            # Macroeconomic Factors
            print("\nMacroeconomic Factors:")
            for factor in analysis_result.get('macroeconomic_factors', []):
                print(f"- {factor.get('factor', 'N/A')}: {factor.get('potential_impact', 'N/A')}")
            
            # Overall Recommendation
            print(f"\nOverall Recommendation: {analysis_result.get('overall_recommendation', 'N/A')}")
            
    except Exception as e:
        logger.error(f"Error in enhanced initial analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 