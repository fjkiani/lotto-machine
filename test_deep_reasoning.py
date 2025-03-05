import os
import json
import logging
from dotenv import load_dotenv
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from deep_reasoning_fix import deep_reasoning_analysis

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def main():
    # Test tickers
    tickers = ["SPY"]
    
    try:
        # Create Yahoo Finance connector
        connector = YahooFinanceConnector()
        
        # Fetch market quotes
        logger.info(f"Fetching market quotes for {', '.join(tickers)}")
        quotes = connector.get_market_quotes(tickers)
        
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
        
        # Create a simple analysis result for testing
        analysis_result = {
            "market_overview": {
                "sentiment": "bearish",
                "key_observations": [
                    "SPY is showing bearish signals with price closing below previous close.",
                    "Volume is higher than average, suggesting increased selling pressure."
                ],
                "market_condition": "normal"
            },
            "ticker_analysis": {
                "SPY": {
                    "sentiment": "bearish",
                    "recommendation": "sell",
                    "risk_level": "medium"
                }
            },
            "overall_recommendation": "Exercise caution in current market conditions."
        }
        
        # Perform deep reasoning analysis
        logger.info("Performing deep reasoning analysis with Gemini")
        deep_analysis = deep_reasoning_analysis(market_data, analysis_result)
        
        # Save deep reasoning analysis to file
        with open("deep_reasoning_analysis.txt", "w") as f:
            f.write(deep_analysis)
        logger.info("Saved deep reasoning analysis to deep_reasoning_analysis.txt")
        
        # Display deep reasoning analysis
        print("\n===== Deep Reasoning Analysis =====\n")
        print(deep_analysis)
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 