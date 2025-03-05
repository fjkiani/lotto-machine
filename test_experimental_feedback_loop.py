import os
import json
import logging
from dotenv import load_dotenv
from src.data.connectors.yahoo_finance import YahooFinanceConnector
from deep_reasoning_fix_experimental import deep_reasoning_analysis
from src.analysis.feedback_loop_experimental import implement_feedback_loop

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
        
        # Create initial analysis
        initial_analysis = {
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
                    "technical_signals": [
                        "Price closed below previous close.",
                        "Price is below 50-day moving average.",
                        "Increased volume suggests selling pressure."
                    ],
                    "recommendation": "sell",
                    "risk_level": "medium",
                    "price_target": {
                        "short_term": 570.00,
                        "long_term": 550.00
                    }
                }
            },
            "trading_opportunities": [
                {
                    "ticker": "SPY",
                    "strategy": "Sell short or buy put options",
                    "rationale": "The bearish technical signals and increased volume suggest further downside potential.",
                    "time_horizon": "short",
                    "risk_reward_ratio": "1:2"
                }
            ],
            "overall_recommendation": "Exercise caution in current market conditions."
        }
        
        # Save initial analysis to file
        with open("experimental_initial_analysis.json", "w") as f:
            json.dump(initial_analysis, f, indent=2)
        logger.info("Saved initial analysis to experimental_initial_analysis.json")
        
        # Perform deep reasoning analysis with experimental model
        logger.info("Performing deep reasoning analysis with experimental Gemini model")
        deep_analysis = deep_reasoning_analysis(market_data, initial_analysis)
        
        # Save deep reasoning analysis to file
        with open("experimental_deep_reasoning_analysis.txt", "w") as f:
            f.write(deep_analysis)
        logger.info("Saved deep reasoning analysis to experimental_deep_reasoning_analysis.txt")
        
        # Implement feedback loop with experimental models
        logger.info("Implementing experimental feedback loop between initial and deep analyses")
        updated_analysis, learning_points = implement_feedback_loop(initial_analysis, deep_analysis)
        
        # Save updated analysis to file
        with open("experimental_updated_analysis.json", "w") as f:
            json.dump(updated_analysis, f, indent=2)
        logger.info("Saved updated analysis to experimental_updated_analysis.json")
        
        # Save learning points to file
        with open("experimental_learning_points.txt", "w") as f:
            for i, point in enumerate(learning_points, 1):
                f.write(f"{i}. {point}\n")
        logger.info("Saved learning points to experimental_learning_points.txt")
        
        # Display results
        print("\n===== Initial Analysis =====\n")
        print(f"Sentiment: {initial_analysis['market_overview']['sentiment']}")
        print(f"Recommendation: {initial_analysis['ticker_analysis']['SPY']['recommendation']}")
        print(f"Risk Level: {initial_analysis['ticker_analysis']['SPY']['risk_level']}")
        
        print("\n===== Updated Analysis =====\n")
        print(f"Sentiment: {updated_analysis['market_overview']['sentiment']}")
        print(f"Recommendation: {updated_analysis['ticker_analysis']['SPY']['recommendation']}")
        print(f"Risk Level: {updated_analysis['ticker_analysis']['SPY']['risk_level']}")
        
        print("\n===== Changes Made =====\n")
        for change in updated_analysis.get('feedback', {}).get('changes_made', []):
            print(f"- {change}")
        
        print("\n===== Learning Points =====\n")
        for i, point in enumerate(learning_points, 1):
            print(f"{i}. {point}")
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 