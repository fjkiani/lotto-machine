import os
import json
import logging
from dotenv import load_dotenv
from src.data.connectors.real_time_finance import RealTimeFinanceConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_search(connector, query="apple"):
    """Test search functionality"""
    logger.info(f"Testing search for '{query}'")
    result = connector.search(query)
    
    if "error" in result:
        logger.error(f"Error performing search: {result['error']}")
        return False
    
    logger.info(f"Successfully performed search")
    # Save the response to a file for inspection
    with open(f"real_time_finance_search_{query}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_search_{query}.json")
    
    return True

def test_stock_quote(connector, symbol="AAPL:NASDAQ"):
    """Test retrieving a stock quote"""
    logger.info(f"Testing stock quote for {symbol}")
    result = connector.get_stock_quote(symbol)
    
    if "error" in result:
        logger.error(f"Error retrieving stock quote: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved stock quote")
    # Save the response to a file for inspection
    with open(f"real_time_finance_stock_quote_{symbol.split(':')[0]}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_stock_quote_{symbol.split(':')[0]}.json")
    
    return True

def test_market_trends(connector, trend_type="gainers"):
    """Test retrieving market trends"""
    logger.info(f"Testing market trends for {trend_type}")
    result = connector.get_market_trends(trend_type)
    
    if "error" in result:
        logger.error(f"Error retrieving market trends: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved market trends")
    # Save the response to a file for inspection
    with open(f"real_time_finance_market_trends_{trend_type}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_market_trends_{trend_type}.json")
    
    return True

def test_stock_time_series_yahoo_finance(connector, symbol="SPY", period="1D"):
    """Test retrieving stock time series using Yahoo Finance data"""
    logger.info(f"Testing Yahoo Finance stock time series for {symbol} with period {period}")
    result = connector.get_stock_time_series(symbol, period=period)
    
    if "error" in result:
        logger.error(f"Error retrieving Yahoo Finance stock time series: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved Yahoo Finance stock time series")
    # Save the response to a file for inspection
    with open(f"real_time_finance_stock_time_series_yf_{symbol}_{period}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_stock_time_series_yf_{symbol}_{period}.json")
    
    return True

def test_stock_news(connector, symbol="AAPL:NASDAQ"):
    """Test retrieving stock news"""
    logger.info(f"Testing stock news for {symbol}")
    result = connector.get_stock_news(symbol)
    
    if "error" in result:
        logger.error(f"Error retrieving stock news: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved stock news")
    # Save the response to a file for inspection
    with open(f"real_time_finance_stock_news_{symbol.split(':')[0]}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_stock_news_{symbol.split(':')[0]}.json")
    
    return True

def test_company_profile(connector, symbol="AAPL:NASDAQ"):
    """Test retrieving company profile"""
    logger.info(f"Testing company profile for {symbol}")
    result = connector.get_company_profile(symbol)
    
    if "error" in result:
        logger.error(f"Error retrieving company profile: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved company profile")
    # Save the response to a file for inspection
    with open(f"real_time_finance_company_profile_{symbol.split(':')[0]}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_company_profile_{symbol.split(':')[0]}.json")
    
    return True

def test_financial_data(connector, symbol="AAPL:NASDAQ", statement_type="income"):
    """Test retrieving financial data"""
    logger.info(f"Testing financial data for {symbol}, statement type: {statement_type}")
    result = connector.get_financial_data(symbol, statement_type=statement_type)
    
    if "error" in result:
        logger.error(f"Error retrieving financial data: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved financial data")
    # Save the response to a file for inspection
    with open(f"real_time_finance_financial_{symbol.split(':')[0]}_{statement_type}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_financial_{symbol.split(':')[0]}_{statement_type}.json")
    
    return True

def test_forex_rates(connector, base_currency="USD"):
    """Test retrieving forex rates"""
    logger.info(f"Testing forex rates for base currency {base_currency}")
    result = connector.get_forex_rates(base_currency)
    
    if "error" in result:
        logger.error(f"Error retrieving forex rates: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved forex rates")
    # Save the response to a file for inspection
    with open(f"real_time_finance_forex_rates_{base_currency}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_forex_rates_{base_currency}.json")
    
    return True

def test_forex_time_series(connector, symbol="EUR/USD", interval="1day", period="1month"):
    """Test retrieving forex time series"""
    logger.info(f"Testing forex time series for {symbol} with interval {interval}")
    result = connector.get_forex_time_series(symbol, interval=interval, period=period)
    
    if "error" in result:
        logger.error(f"Error retrieving forex time series: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved forex time series")
    # Save the response to a file for inspection
    with open(f"real_time_finance_forex_time_series_{symbol.replace('/', '_')}_{interval}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_forex_time_series_{symbol.replace('/', '_')}_{interval}.json")
    
    return True

def test_general_news(connector):
    """Test retrieving general financial news"""
    logger.info(f"Testing general news")
    result = connector.get_stock_news()
    
    if "error" in result:
        logger.error(f"Error retrieving general news: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved general news")
    # Save the response to a file for inspection
    with open(f"real_time_finance_general_news.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to real_time_finance_general_news.json")
    
    return True

def run_specific_tests():
    """Run only the tests for working endpoints"""
    ticker = "AAPL:NASDAQ"
    
    logger.info("=== Testing Real-Time Finance Data API (Working Endpoints) ===")
    
    # Check for API key
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY not found in environment variables")
        return
    
    # Create connector
    connector = RealTimeFinanceConnector(api_key)
    
    # Dictionary to track test results
    test_results = {}
    
    # Run tests for confirmed working endpoints
    logger.info("=== Testing Working Endpoints ===")
    test_results["search"] = test_search(connector, "apple")
    test_results["market_trends_gainers"] = test_market_trends(connector, "gainers")
    test_results["market_trends_losers"] = test_market_trends(connector, "losers")
    test_results["stock_time_series_yf"] = test_stock_time_series_yahoo_finance(connector, "SPY", "1D")
    test_results["stock_news"] = test_stock_news(connector, "AAPL:NASDAQ")
    test_results["general_news"] = test_general_news(connector)
    
    # Print summary
    logger.info("=== Test Summary ===")
    for test_name, test_result in test_results.items():
        result_str = "SUCCESS" if test_result else "FAILED"
        logger.info(f"{test_name}: {result_str}")
        
    # Overall success
    success_rate = sum(1 for result in test_results.values() if result) / len(test_results) * 100
    logger.info(f"Overall success rate: {success_rate:.1f}%")

if __name__ == "__main__":
    run_specific_tests() 