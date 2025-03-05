import os
import json
import logging
from dotenv import load_dotenv
from src.data.connectors.yahoo_finance import YahooFinanceConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def main():
    # Test tickers
    tickers = ["SPY", "AAPL", "MSFT", "TSLA"]
    
    try:
        # Create Yahoo Finance connector
        connector = YahooFinanceConnector()
        
        # Fetch market quotes
        logger.info(f"Fetching market quotes for {', '.join(tickers)}")
        quotes = connector.get_market_quotes(tickers)
        
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
            print(f"  Market State: {quote.market_state}")
            print(f"  Volume: {quote.regular_market_volume:,}")
            print(f"  Avg Volume: {quote.average_volume:,}")
            print(f"  Bid: ${quote.bid:.2f} x {quote.bid_size}")
            print(f"  Ask: ${quote.ask:.2f} x {quote.ask_size}")
            print(f"  52-Week Range: ${quote.fifty_two_week_low:.2f} - ${quote.fifty_two_week_high:.2f}")
            print(f"  P/E Ratio: {quote.trailing_pe:.2f}")
            print(f"  Dividend Yield: {quote.get_dividend_yield():.2f}%")
            print(f"  Exchange: {quote.exchange_name}")
            print()
        
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 