import os
import json
import logging
from dotenv import load_dotenv
from src.data.connectors.yahoo_finance_insights import YahooFinanceInsightsConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_stock_insights(connector, symbol="SPY"):
    """Test retrieving stock insights"""
    logger.info(f"Testing stock insights for {symbol}")
    result = connector.get_stock_insights(symbol)
    
    if "error" in result:
        logger.error(f"Error retrieving stock insights: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved stock insights")
    # Save the response to a file for inspection
    with open(f"yahoo_finance_insights_{symbol}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to yahoo_finance_insights_{symbol}.json")
    
    return True

def test_condensed_insights(connector, symbol="SPY"):
    """Test retrieving condensed insights"""
    logger.info(f"Testing condensed insights for {symbol}")
    result = connector.get_condensed_insights(symbol)
    
    if "error" in result:
        logger.error(f"Error retrieving condensed insights: {result['error']}")
        return False
    
    logger.info(f"Successfully retrieved condensed insights")
    # Save the response to a file for inspection
    with open(f"yahoo_finance_condensed_insights_{symbol}.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info(f"Saved response to yahoo_finance_condensed_insights_{symbol}.json")
    
    return True

def run_tests():
    """Run tests for Yahoo Finance Insights API"""
    test_symbols = ["SPY", "AAPL", "MSFT", "AMZN"]
    
    logger.info("=== Testing Yahoo Finance Insights API ===")
    
    # Check for API key
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY not found in environment variables")
        return
    
    # Create connector
    connector = YahooFinanceInsightsConnector(api_key)
    
    # Dictionary to track test results
    test_results = {}
    
    # Test with multiple symbols
    for symbol in test_symbols:
        logger.info(f"=== Testing with symbol: {symbol} ===")
        test_results[f"insights_{symbol}"] = test_stock_insights(connector, symbol)
        test_results[f"condensed_{symbol}"] = test_condensed_insights(connector, symbol)
    
    # Print summary
    logger.info("=== Test Summary ===")
    for test_name, test_result in test_results.items():
        result_str = "SUCCESS" if test_result else "FAILED"
        logger.info(f"{test_name}: {result_str}")
    
    # Overall success
    success_count = sum(1 for result in test_results.values() if result)
    success_rate = (success_count / len(test_results)) * 100 if test_results else 0
    logger.info(f"Overall success rate: {success_rate:.1f}% ({success_count}/{len(test_results)})")

if __name__ == "__main__":
    run_tests() 