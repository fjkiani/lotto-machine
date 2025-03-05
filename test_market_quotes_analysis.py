import os
import json
import logging
import re
import argparse
from dotenv import load_dotenv
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.llm.models import analyze_market_quotes_with_gemini, deep_reasoning_analysis

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add command-line argument parsing
parser = argparse.ArgumentParser(description='Analyze market quotes with Gemini')
parser.add_argument('--analysis-type', choices=['basic', 'technical', 'fundamental', 'comprehensive'], 
                    default='technical', help='Type of analysis to perform')
parser.add_argument('--deep-reasoning', action='store_true', 
                    help='Perform deep reasoning analysis using Gemini 2.0 Flash Thinking')
parser.add_argument('--tickers', nargs='+', default=['SPY'], 
                    help='Ticker symbols to analyze (default: SPY)')
args = parser.parse_args()

def extract_json_from_markdown(text):
    """Extract JSON content from markdown-formatted text with code blocks"""
    # Look for JSON content between ```json and ``` markers
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    
    # If not found, try to find any JSON object in the text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    # If still not found, return the original text
    return text

def main():
    # Get tickers and analysis type from command-line arguments
    tickers = args.tickers
    analysis_type = args.analysis_type
    perform_deep_reasoning = args.deep_reasoning

    try:
        # Create Yahoo Finance connector
        connector = YahooFinanceConnector()
        
        # Try to fetch market quotes using RapidAPI
        try:
            logger.info(f"Fetching market quotes for {', '.join(tickers)} using RapidAPI")
            quotes = connector.get_market_quotes(tickers)
        except Exception as e:
            logger.warning(f"RapidAPI fetch failed: {str(e)}. Falling back to yfinance.")
            # Fall back to yfinance
            import yfinance as yf
            quotes = {}
            
            for ticker in tickers:
                stock = yf.Ticker(ticker)
                info = stock.info
                
                from src.data.models import MarketQuote
                quotes[ticker] = MarketQuote(
                    symbol=ticker,
                    quote_type=info.get("quoteType", ""),
                    market_state=info.get("marketState", ""),
                    regular_market_price=info.get("regularMarketPrice", 0),
                    regular_market_previous_close=info.get("regularMarketPreviousClose", 0),
                    regular_market_open=info.get("regularMarketOpen", 0),
                    regular_market_day_high=info.get("regularMarketDayHigh", 0),
                    regular_market_day_low=info.get("regularMarketDayLow", 0),
                    regular_market_volume=info.get("regularMarketVolume", 0),
                    average_volume=info.get("averageVolume", 0),
                    average_volume_10_days=info.get("averageVolume10days", 0),
                    bid=info.get("bid", 0),
                    ask=info.get("ask", 0),
                    bid_size=info.get("bidSize", 0),
                    ask_size=info.get("askSize", 0),
                    market_cap=info.get("marketCap", 0),
                    fifty_two_week_high=info.get("fiftyTwoWeekHigh", 0),
                    fifty_two_week_low=info.get("fiftyTwoWeekLow", 0),
                    fifty_day_average=info.get("fiftyDayAverage", 0),
                    two_hundred_day_average=info.get("twoHundredDayAverage", 0),
                    trailing_annual_dividend_rate=info.get("trailingAnnualDividendRate", 0),
                    trailing_annual_dividend_yield=info.get("trailingAnnualDividendYield", 0),
                    trailing_pe=info.get("trailingPE", 0),
                    exchange=info.get("exchange", ""),
                    exchange_name=info.get("fullExchangeName", ""),
                    currency=info.get("currency", "USD"),
                    raw_data=info
                )
        
        # Prepare market data for deep reasoning
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
        
        # Save raw data to file for inspection
        with open("market_quotes.json", "w") as f:
            json.dump({ticker: quote.raw_data for ticker, quote in quotes.items()}, f, indent=2)
        logger.info("Saved raw market quotes to market_quotes.json")
        
        # Analyze market quotes with Gemini
        logger.info(f"Analyzing market quotes with Gemini ({analysis_type} analysis)")
        raw_response = analyze_market_quotes_with_gemini(quotes, analysis_type)
        logger.info(f"Raw Gemini Response:\n{raw_response}")
        
        # Extract JSON from the markdown-formatted response
        json_str = extract_json_from_markdown(raw_response)
        
        # Parse the JSON
        try:
            analysis_result = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Gemini response is not valid JSON: {e}")
            analysis_result = {
                "error": "Gemini response is not valid JSON",
                "market_overview": {
                    "sentiment": "neutral",
                    "key_observations": ["Error in analysis"],
                    "market_condition": "normal"
                },
                "overall_recommendation": "Unable to provide recommendations due to analysis error"
            }
        
        # Save analysis result to file
        with open("market_analysis.json", "w") as f:
            json.dump(analysis_result, f, indent=2)
        logger.info("Saved market analysis to market_analysis.json")
        
        # Perform deep reasoning analysis if requested
        if perform_deep_reasoning:
            logger.info("Performing deep reasoning analysis with Gemini 2.0 Flash Thinking")
            deep_analysis = deep_reasoning_analysis(market_data, analysis_result)
            
            # Save deep reasoning analysis to file
            with open("deep_reasoning_analysis.txt", "w") as f:
                f.write(deep_analysis)
            logger.info("Saved deep reasoning analysis to deep_reasoning_analysis.txt")
            
            # Display deep reasoning analysis
            print("\n===== Deep Reasoning Analysis =====\n")
            print(deep_analysis)
        
        # Display results of initial analysis
        print("\n===== Market Analysis Results =====\n")
        
        # Market Overview
        market_overview = analysis_result.get("market_overview", {})
        print(f"Market Sentiment: {market_overview.get('sentiment', 'N/A')}")
        print(f"Market Condition: {market_overview.get('market_condition', 'N/A')}")
        print("\nKey Observations:")
        for observation in market_overview.get("key_observations", []):
            print(f"  - {observation}")
        
        # Ticker Analysis
        print("\nTicker Analysis:")
        ticker_analysis = analysis_result.get("ticker_analysis", {})
        for ticker, analysis in ticker_analysis.items():
            print(f"\n  {ticker}:")
            print(f"    Sentiment: {analysis.get('sentiment', 'N/A')}")
            print(f"    Recommendation: {analysis.get('recommendation', 'N/A')}")
            print(f"    Risk Level: {analysis.get('risk_level', 'N/A')}")
            
            price_target = analysis.get("price_target", {})
            if price_target:
                print(f"    Price Targets: Short-term ${price_target.get('short_term', 'N/A')}, Long-term ${price_target.get('long_term', 'N/A')}")
            
            print("    Key Insights:")
            for insight in analysis.get("key_insights", []):
                print(f"      - {insight}")
        
        # Trading Opportunities
        print("\nTrading Opportunities:")
        for opportunity in analysis_result.get("trading_opportunities", []):
            print(f"\n  {opportunity.get('ticker', 'N/A')}:")
            print(f"    Strategy: {opportunity.get('strategy', 'N/A')}")
            print(f"    Time Horizon: {opportunity.get('time_horizon', 'N/A')}")
            print(f"    Risk/Reward: {opportunity.get('risk_reward_ratio', 'N/A')}")
            print(f"    Rationale: {opportunity.get('rationale', 'N/A')}")
        
        # Overall Recommendation
        print(f"\nOverall Recommendation: {analysis_result.get('overall_recommendation', 'N/A')}")
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()