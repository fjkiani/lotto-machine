import os
import json
import logging
import argparse
import http.client
from typing import Dict, List
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import pandas as pd
import matplotlib.pyplot as plt

from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.analysis.enhanced_analysis_pipeline import EnhancedAnalysisPipeline

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def fetch_options_from_rapidapi(ticker: str) -> Dict:
    """
    Fetch options data from RapidAPI Yahoo Finance endpoint
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with options data
    """
    logger.info(f"Fetching options data for {ticker} from RapidAPI")
    
    conn = http.client.HTTPSConnection("yahoo-finance166.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': os.getenv("RAPIDAPI_KEY", "9f107deaabmsh2efbc3559ddca05p17f1abjsn271e6df32f7c"),
        'x-rapidapi-host': "yahoo-finance166.p.rapidapi.com"
    }
    
    conn.request("GET", f"/api/stock/get-options?region=US&symbol={ticker}", headers=headers)
    
    res = conn.getresponse()
    data = res.read()
    
    return json.loads(data.decode("utf-8"))

def prepare_options_data_for_analysis(api_data: Dict, ticker: str) -> Dict:
    """
    Prepare option chain data for analysis
    
    Args:
        api_data: Raw API response from RapidAPI
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with formatted options data
    """
    logger.info(f"Preparing options data for {ticker}")
    
    # Extract quote data
    option_chain = api_data.get("optionChain", {})
    
    result = option_chain.get("result", [])
    if not result:
        logger.error("No result data in API response")
        return {
            "underlying_symbol": ticker,
            "current_price": 0,
            "error": "No options data available from API"
        }
    
    quote_data = result[0].get("quote", {})
    current_price = quote_data.get("regularMarketPrice", 0)
    
    # Convert option chain to dictionary for analysis
    option_chain_dict = {
        "underlying_symbol": ticker,
        "current_price": current_price,
        "expiration_dates": [],
        "strikes": [],
        "options_sample": []
    }
    
    # Process options data
    option_chain_data = result[0].get("options", [])
    if not option_chain_data:
        logger.error("No options data in API response")
        return option_chain_dict
    
    # Extract expiration dates
    for option_date in option_chain_data:
        timestamp = option_date.get("expirationDate")
        if timestamp:
            exp_date = datetime.fromtimestamp(timestamp)
            option_chain_dict["expiration_dates"].append(exp_date.strftime("%Y-%m-%d"))
    
    # Get all strikes from first expiration
    if option_chain_data:
        first_exp = option_chain_data[0]
        straddles = first_exp.get("straddles", [])

        if not straddles:
            logger.error("No straddles data in API response")
            return option_chain_dict
            
        strikes = []
        for straddle in straddles:
            if straddle.get("strike") not in strikes:
                strikes.append(straddle.get("strike"))

        option_chain_dict["strikes"] = strikes[:20]  # Limit to first 20 strikes
        
        if not strikes:
            logger.error("No strike prices in API response")
            return option_chain_dict
            
        # Find ATM strike
        atm_strike = min(strikes, key=lambda x: abs(x - current_price))
        atm_index = strikes.index(atm_strike)
        
        # Get a range of strikes around ATM
        start_idx = max(0, atm_index - 2)
        end_idx = min(len(strikes), atm_index + 3)
        sample_strikes = strikes[start_idx:end_idx]
        
        # Create a mapping of strikes to puts for easier lookup
        straddles_by_strike = {}
        for straddle in straddles:
            straddles_by_strike[straddle.get('strike')] = straddle

        # Add sample options
        for strike in sample_strikes:
            call_data = None
            put_data = None
            
            # Find call at this strike and put at this strike
            straddle = straddles_by_strike.get(strike)
            if straddle:
                call = straddle.get('call')
                put = straddle.get('put')
                if call:
                    call_data = {
                        "contract_symbol": call.get("contractSymbol"),
                        "strike": call.get("strike"),
                        "bid": call.get("bid"),
                        "ask": call.get("ask"),
                        "implied_volatility": call.get("impliedVolatility"),
                        "volume": call.get("volume"),
                        "open_interest": call.get("openInterest"),
                        "in_the_money": call.get("inTheMoney")
                    }
                if put:
                    put_data = {
                        "contract_symbol": put.get("contractSymbol"),
                        "strike": put.get("strike"),
                        "bid": put.get("bid"),
                        "ask": put.get("ask"),
                        "implied_volatility": put.get("impliedVolatility"),
                        "volume": put.get("volume"),
                        "open_interest": put.get("openInterest"),
                        "in_the_money": put.get("inTheMoney")
                    }
            
            option_chain_dict["options_sample"].append({
                "strike": strike,
                "call": call_data,
                "put": put_data
            })
    
    return option_chain_dict

def analyze_options_with_deep_reasoning(ticker: str, option_chain: Dict, market_data: Dict) -> Dict:
    """
    Analyze options data using the experimental deep reasoning model
    
    Args:
        ticker: The ticker symbol
        option_chain: Dictionary containing options chain data
        market_data: Dictionary containing market data for the ticker
        
    Returns:
        Dictionary containing the options analysis
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not found. Please make sure GEMINI_API_KEY is set in your .env file.")
    
    # Initialize Gemini
    genai.configure(api_key=api_key)
    
    # Prepare the prompt for options analysis
    prompt = f"""
    I need you to perform a comprehensive options analysis for {ticker} based on the following data:
    
    Market Data:
    {json.dumps(market_data, indent=2)}
    
    Options Chain Data:
    {json.dumps(option_chain, indent=2)}
    
    Please provide a detailed analysis that includes:
    
    1. Options Market Overview:
       - Overall options sentiment (bullish, bearish, or neutral)
       - Key observations about current options pricing
       - Implied volatility assessment
       - Put-call ratio analysis
    
    2. Options Strategies Analysis:
       - Recommended options strategies based on market outlook
       - Risk-reward analysis for each strategy
       - Optimal strike prices and expiration dates
       - Greeks analysis (Delta, Gamma, Theta, Vega)
    
    3. Integration with Technical Analysis:
       - How options data confirms or contradicts technical signals
       - Key price levels indicated by options activity
       - Potential hedging strategies based on technical outlook
    
    4. Risk Assessment:
       - Specific risks for recommended options strategies
       - Maximum potential loss scenarios
       - Probability of profit estimates
       - Volatility risk considerations
    
    Return your analysis as a JSON object with the following structure:
    {{
        "options_market_overview": {{
            "sentiment": "bullish/bearish/neutral",
            "implied_volatility_assessment": "description of IV levels and skew",
            "put_call_ratio": "numerical value and interpretation",
            "key_observations": ["observation 1", "observation 2", ...]
        }},
        "recommended_strategies": [
            {{
                "strategy_name": "name of strategy (e.g., Bull Call Spread)",
                "construction": "description of how to construct the strategy",
                "optimal_strikes": ["strike price 1", "strike price 2", ...],
                "expiration": "recommended expiration date",
                "max_profit": "maximum potential profit",
                "max_loss": "maximum potential loss",
                "breakeven": "breakeven point(s)",
                "probability_of_profit": "estimated probability",
                "rationale": "rationale for this strategy"
            }}
        ],
        "technical_integration": {{
            "confirmation_points": ["point 1", "point 2", ...],
            "contradiction_points": ["point 1", "point 2", ...],
            "key_price_levels": ["level 1", "level 2", ...],
            "hedging_recommendations": ["recommendation 1", "recommendation 2", ...]
        }},
        "greeks_analysis": {{
            "delta_exposure": "analysis of delta exposure",
            "gamma_risk": "analysis of gamma risk",
            "theta_decay": "analysis of theta decay",
            "vega_sensitivity": "analysis of vega sensitivity"
        }},
        "risk_assessment": {{
            "specific_risks": ["risk 1", "risk 2", ...],
            "volatility_outlook": "outlook on future volatility",
            "market_event_risks": ["event risk 1", "event risk 2", ...],
            "risk_management_tips": ["tip 1", "tip 2", ...]
        }},
        "overall_recommendation": "summary recommendation for options trading"
    }}
    
    Ensure your analysis is nuanced, considers multiple perspectives, and provides specific actionable recommendations.
    """
    
    # Try to use the experimental model first
    try:
        model_name = "gemini-2.0-flash-thinking-exp-01-21"
        print(f"Attempting to use experimental model for options analysis: {model_name}")
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
        
        print("Successfully used experimental model for options analysis")
        
    except Exception as e:
        print(f"Error using experimental model: {str(e)}")
        print("Falling back to standard Gemini model")
        
        # Fall back to the standard model
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(prompt)
    
    # Parse the response
    try:
        # Extract JSON from the response text
        import re
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if json_match:
            options_analysis = json.loads(json_match.group(0))
        else:
            logger.warning("Could not extract JSON from response")
            options_analysis = {"error": "Could not extract JSON from model response"}
    except Exception as e:
        logger.error(f"Error parsing options analysis: {str(e)}")
        options_analysis = {"error": f"Error parsing model response: {str(e)}"}
    
    return options_analysis

def combine_market_and_options_analysis(market_analysis: Dict, options_analysis: Dict) -> Dict:
    """
    Combine market analysis and options analysis into a comprehensive analysis
    
    Args:
        market_analysis: Dictionary containing market analysis
        options_analysis: Dictionary containing options analysis
        
    Returns:
        Dictionary containing the combined analysis
    """
    # Create a new analysis that combines both
    combined_analysis = market_analysis.copy()
    
    # Add options analysis section
    combined_analysis["options_analysis"] = options_analysis
    
    # Update trading opportunities based on options strategies
    if "recommended_strategies" in options_analysis:
        for strategy in options_analysis["recommended_strategies"]:
            # Get the ticker from market_analysis
            ticker = "Unknown"
            if market_analysis.get("ticker_analysis") and len(market_analysis.get("ticker_analysis", {}).keys()) > 0:
                ticker = list(market_analysis.get("ticker_analysis", {}).keys())[0]
            
            # Create a trading opportunity from the options strategy
            opportunity = {
                "ticker": ticker,
                "strategy": f"Options: {strategy.get('strategy_name', 'Unknown Strategy')}",
                "conditions": [f"Expiration: {strategy.get('expiration', 'Unknown')}"],
                "rationale": strategy.get("rationale", "Based on options analysis"),
                "time_horizon": "short to medium",  # Options typically have shorter time horizons
                "risk_reward_ratio": f"{strategy.get('max_loss', 'Unknown')} : {strategy.get('max_profit', 'Unknown')}",
                "suitable_for": "Options traders"
            }
            
            # Add to trading opportunities
            if "trading_opportunities" not in combined_analysis:
                combined_analysis["trading_opportunities"] = []
            
            combined_analysis["trading_opportunities"].append(opportunity)
    
    # Update overall recommendation to include options perspective
    if "overall_recommendation" in options_analysis:
        combined_analysis["overall_recommendation"] = f"{combined_analysis.get('overall_recommendation', '')} | Options: {options_analysis['overall_recommendation']}"
    
    return combined_analysis

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Perform enhanced analysis with options integration')
    parser.add_argument('--tickers', nargs='+', default=['SPY'], help='Ticker symbols to analyze (default: SPY)')
    parser.add_argument('--analysis-type', choices=['basic', 'comprehensive'], default='comprehensive', 
                        help='Type of analysis to perform (default: comprehensive)')
    parser.add_argument('--use-feedback-loop', action='store_true', help='Use feedback loop for analysis refinement')
    parser.add_argument('--skip-options', action='store_true', help='Skip options analysis due to compatibility issues')
    args = parser.parse_args()
    
    tickers = args.tickers
    analysis_type = args.analysis_type
    use_feedback_loop = args.use_feedback_loop
    skip_options = args.skip_options
    
    try:
        # Create Yahoo Finance connector for market data
        connector = YahooFinanceConnector()
        
        # Create enhanced analysis pipeline
        pipeline = EnhancedAnalysisPipeline(use_feedback_loop=use_feedback_loop)
        
        # Analyze each ticker
        for ticker in tickers:
            logger.info(f"Analyzing {ticker} with options integration")
            
            # Fetch market quotes
            quotes = connector.get_market_quotes([ticker])
            
            # Prepare market data for analysis
            market_data = {}
            for t, quote in quotes.items():
                market_data[t] = {
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
            
            # Run the enhanced analysis pipeline
            logger.info(f"Running enhanced analysis pipeline for {ticker}")
            analysis_result = pipeline.analyze_tickers([ticker], analysis_type)
            
            # Try to fetch options data if not skipped
            has_options_data = False
            option_chain_dict = None
            
            if not skip_options:
                try:
                    # Use RapidAPI directly instead of YahooFinanceConnector
                    logger.info(f"Fetching options data for {ticker} using RapidAPI")
                    api_data = fetch_options_from_rapidapi(ticker)
                    
                    # Save raw API response to file for debugging
                    with open(f"options_api_response_{ticker}.json", "w") as f:
                        json.dump(api_data, f, indent=2)
                    logger.info(f"Saved raw API response to options_api_response_{ticker}.json")
                    
                    # Prepare options data for analysis
                    option_chain_dict = prepare_options_data_for_analysis(api_data, ticker)
                    
                    # Save prepared options data to file for debugging
                    with open(f"options_data_{ticker}.json", "w") as f:
                        json.dump(option_chain_dict, f, indent=2)
                    logger.info(f"Saved prepared options data to options_data_{ticker}.json")
                    
                    # Check if we have valid options data
                    if option_chain_dict.get("error"):
                        logger.error(f"Error in options data: {option_chain_dict.get('error')}")
                        has_options_data = False
                    else:
                        has_options_data = True
                        logger.info(f"Successfully prepared options data for {ticker}")
                    
                except Exception as e:
                    logger.error(f"Error fetching options data for {ticker}: {str(e)}")
                    has_options_data = False
            else:
                logger.info(f"Skipping options data for {ticker} as requested")
            
            # If we have options data, perform options analysis and combine results
            if has_options_data and option_chain_dict:
                logger.info(f"Performing options analysis for {ticker}")
                options_analysis = analyze_options_with_deep_reasoning(ticker, option_chain_dict, market_data)
                
                # Save options analysis to file
                with open(f"options_analysis_{ticker}.json", "w") as f:
                    json.dump(options_analysis, f, indent=2)
                logger.info(f"Saved options analysis to options_analysis_{ticker}.json")
                
                # Combine market and options analysis
                combined_analysis = combine_market_and_options_analysis(analysis_result, options_analysis)
                
                # Save combined analysis to file
                output_file = f"options_enhanced_analysis_{ticker}.json"
                with open(output_file, "w") as f:
                    json.dump(combined_analysis, f, indent=2)
                logger.info(f"Saved combined analysis to {output_file}")
                
                # Display results
                print(f"\n===== Enhanced Analysis with Options for {ticker} =====\n")
                
                # Market Overview
                print("Market Overview:")
                print(f"Sentiment: {combined_analysis.get('market_overview', {}).get('sentiment', 'N/A')}")
                print(f"Market Condition: {combined_analysis.get('market_overview', {}).get('market_condition', 'N/A')}")
                
                # Options Overview
                options_overview = combined_analysis.get('options_analysis', {}).get('options_market_overview', {})
                print("\nOptions Market Overview:")
                print(f"Options Sentiment: {options_overview.get('sentiment', 'N/A')}")
                print(f"Implied Volatility: {options_overview.get('implied_volatility_assessment', 'N/A')}")
                print(f"Put-Call Ratio: {options_overview.get('put_call_ratio', 'N/A')}")
                
                # Recommended Options Strategies
                print("\nRecommended Options Strategies:")
                for strategy in combined_analysis.get('options_analysis', {}).get('recommended_strategies', []):
                    print(f"\n- {strategy.get('strategy_name', 'Unknown Strategy')}:")
                    print(f"  Construction: {strategy.get('construction', 'N/A')}")
                    print(f"  Optimal Strikes: {', '.join(str(s) for s in strategy.get('optimal_strikes', []))}")
                    print(f"  Expiration: {strategy.get('expiration', 'N/A')}")
                    print(f"  Max Profit: {strategy.get('max_profit', 'N/A')}")
                    print(f"  Max Loss: {strategy.get('max_loss', 'N/A')}")
                    print(f"  Breakeven: {strategy.get('breakeven', 'N/A')}")
                    print(f"  Probability of Profit: {strategy.get('probability_of_profit', 'N/A')}")
                    print(f"  Rationale: {strategy.get('rationale', 'N/A')}")
                
                # Greeks Analysis
                greeks = combined_analysis.get('options_analysis', {}).get('greeks_analysis', {})
                print("\nGreeks Analysis:")
                print(f"Delta Exposure: {greeks.get('delta_exposure', 'N/A')}")
                print(f"Gamma Risk: {greeks.get('gamma_risk', 'N/A')}")
                print(f"Theta Decay: {greeks.get('theta_decay', 'N/A')}")
                print(f"Vega Sensitivity: {greeks.get('vega_sensitivity', 'N/A')}")
                
                # Risk Assessment
                risk = combined_analysis.get('options_analysis', {}).get('risk_assessment', {})
                print("\nRisk Assessment:")
                print("Specific Risks:")
                for r in risk.get('specific_risks', []):
                    print(f"- {r}")
                print(f"\nVolatility Outlook: {risk.get('volatility_outlook', 'N/A')}")
                
                # Overall Recommendation
                print(f"\nOverall Recommendation: {combined_analysis.get('overall_recommendation', 'N/A')}")
                
                # If feedback loop was used, show learning points
                if use_feedback_loop and 'feedback' in combined_analysis:
                    print("\nFeedback Loop Results:")
                    print("Changes Made:")
                    for change in combined_analysis.get('feedback', {}).get('changes_made', []):
                        print(f"- {change}")
                    
                    print("\nLearning Points:")
                    for i, point in enumerate(combined_analysis.get('feedback', {}).get('learning_points', []), 1):
                        print(f"{i}. {point}")
                
                # Get learning database and plot summary
                if use_feedback_loop:
                    learning_db = pipeline.get_learning_database()
                    if not learning_db.empty:
                        learning_summary = pipeline.get_learning_summary()
                        
                        # Plot learning summary
                        plt.figure(figsize=(10, 6))
                        categories = list(learning_summary.keys())
                        counts = list(learning_summary.values())
                        
                        plt.bar(categories, counts, color='skyblue')
                        plt.xlabel('Learning Categories')
                        plt.ylabel('Number of Learning Points')
                        plt.title('Learning Points by Category')
                        plt.xticks(rotation=45, ha='right')
                        plt.tight_layout()
                        
                        # Save plot
                        plt.savefig(f"options_learning_summary_{ticker}.png")
                        logger.info(f"Saved learning summary plot to options_learning_summary_{ticker}.png")
            else:
                # Save standard analysis to file
                output_file = f"enhanced_analysis_{ticker}.json"
                with open(output_file, "w") as f:
                    json.dump(analysis_result, f, indent=2)
                logger.info(f"Saved standard analysis to {output_file}")
                
                # Display results
                print(f"\n===== Enhanced Analysis for {ticker} =====\n")
                
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
                
                # Trading Opportunities
                print("\nTrading Opportunities:")
                for opportunity in analysis_result.get('trading_opportunities', []):
                    print(f"\n- Strategy: {opportunity.get('strategy', 'N/A')}")
                    print(f"  Rationale: {opportunity.get('rationale', 'N/A')}")
                    print(f"  Time Horizon: {opportunity.get('time_horizon', 'N/A')}")
                    print(f"  Risk-Reward Ratio: {opportunity.get('risk_reward_ratio', 'N/A')}")
                
                # Overall Recommendation
                print(f"\nOverall Recommendation: {analysis_result.get('overall_recommendation', 'N/A')}")
                
                # If feedback loop was used, show learning points
                if use_feedback_loop and 'feedback' in analysis_result:
                    print("\nFeedback Loop Results:")
                    print("Changes Made:")
                    for change in analysis_result.get('feedback', {}).get('changes_made', []):
                        print(f"- {change}")
                    
                    print("\nLearning Points:")
                    for i, point in enumerate(analysis_result.get('feedback', {}).get('learning_points', []), 1):
                        print(f"{i}. {point}")
                
                # Get learning database and plot summary
                if use_feedback_loop:
                    learning_db = pipeline.get_learning_database()
                    if not learning_db.empty:
                        learning_summary = pipeline.get_learning_summary()
                        
                        # Plot learning summary
                        plt.figure(figsize=(10, 6))
                        categories = list(learning_summary.keys())
                        counts = list(learning_summary.values())
                        
                        plt.bar(categories, counts, color='skyblue')
                        plt.xlabel('Learning Categories')
                        plt.ylabel('Number of Learning Points')
                        plt.title('Learning Points by Category')
                        plt.xticks(rotation=45, ha='right')
                        plt.tight_layout()
                        
                        # Save plot
                        plt.savefig(f"learning_summary_{ticker}.png")
                        logger.info(f"Saved learning summary plot to learning_summary_{ticker}.png")
    
    except Exception as e:
        logger.error(f"Error in options enhanced analysis: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 