import os
import json
import logging
from dotenv import load_dotenv
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from src.llm.models import analyze_market_quotes_with_gemini
import argparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add command-line argument parsing
parser = argparse.ArgumentParser(description='Analyze market quotes with Gemini')
parser.add_argument('--analysis-type', choices=['basic', 'technical', 'fundamental', 'comprehensive'], 
                    default='comprehensive', help='Type of analysis to perform')
args = parser.parse_args()

# Then use args.analysis_type instead of hardcoding it
analysis_type = args.analysis_type

def test_data_retrieval():
    """Test market quotes data retrieval functionality"""
    tickers = ["SPY", "AAPL", "MSFT", "TSLA"]
    
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
                # ... yfinance fallback code ...
                pass
        
        # Save raw data to file for inspection
        with open("market_quotes.json", "w") as f:
            json.dump({ticker: quote.raw_data for ticker, quote in quotes.items()}, f, indent=2)
        logger.info("Saved raw market quotes to market_quotes.json")
        
        # Display results
        print("\n===== Market Quotes =====\n")
        
        for ticker, quote in quotes.items():
            print(f"Ticker: {ticker} ({quote.quote_type})")
            print(f"  Price: ${quote.regular_market_price:.2f}")
            print(f"  Change: {quote.get_day_change_percent():.2f}%")
            # ... display other quote data ...
            print()
        
        return quotes
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_market_analysis(quotes=None):
    """Test market quotes analysis functionality"""
    if quotes is None:
        # If quotes not provided, fetch them
        tickers = ["SPY"]
        # ... fetch quotes code ...
    
    try:
        # Analyze market quotes with Gemini
        logger.info(f"Analyzing market quotes with Gemini ({analysis_type} analysis)")
        analysis_result = analyze_market_quotes_with_gemini(quotes, analysis_type)
        
        # Save analysis result to file
        with open("market_analysis.json", "w") as f:
            json.dump(analysis_result, f, indent=2)
        logger.info("Saved market analysis to market_analysis.json")
        
        # Display results
        print("\n===== Market Analysis Results =====\n")
        
        # ... display analysis results ...
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """Run all tests"""
    print("=== Testing Market Quotes Data Retrieval ===")
    quotes = test_data_retrieval()
    
    if quotes:
        print("\n=== Testing Market Quotes Analysis ===")
        test_market_analysis(quotes)

if __name__ == "__main__":
    main() 