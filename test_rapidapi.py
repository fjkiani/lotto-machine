import os
import json
import http.client
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_rapidapi_market_data(ticker="AAPL"):
    """Test RapidAPI Yahoo Finance market data endpoint"""
    logger.info(f"Testing RapidAPI market data for {ticker}")
    
    # Get API key
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY not found in environment variables")
        return
    
    logger.info(f"Using API key: {api_key[:5]}...{api_key[-5:]}")
    
    # Test yh-finance endpoint
    conn = http.client.HTTPSConnection("yh-finance.p.rapidapi.com")
    
    headers = {
        'X-RapidAPI-Key': api_key,
        'X-RapidAPI-Host': "yh-finance.p.rapidapi.com"
    }
    
    endpoint = f"/stock/v2/get-summary?symbol={ticker}&region=US"
    logger.info(f"Testing endpoint: {endpoint}")
    
    conn.request("GET", endpoint, headers=headers)
    
    res = conn.getresponse()
    status = res.status
    data = res.read()
    
    logger.info(f"Response status: {status}")
    
    if status != 200:
        logger.error(f"API error: {status} - {data.decode('utf-8')}")
        return
    
    try:
        json_data = json.loads(data.decode("utf-8"))
        logger.info(f"Successfully received data with keys: {list(json_data.keys())}")
        
        # Save response to file for inspection
        with open(f"rapidapi_market_data_{ticker}.json", "w") as f:
            json.dump(json_data, f, indent=2)
        logger.info(f"Saved response to rapidapi_market_data_{ticker}.json")
        
        return json_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return None

def test_rapidapi_options_data(ticker="AAPL"):
    """Test RapidAPI Yahoo Finance options data endpoint"""
    logger.info(f"Testing RapidAPI options data for {ticker}")
    
    # Get API key
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY not found in environment variables")
        return
    
    # Test yh-finance endpoint
    conn = http.client.HTTPSConnection("yh-finance.p.rapidapi.com")
    
    headers = {
        'X-RapidAPI-Key': api_key,
        'X-RapidAPI-Host': "yh-finance.p.rapidapi.com"
    }
    
    endpoint = f"/stock/v2/get-options?symbol={ticker}&region=US"
    logger.info(f"Testing endpoint: {endpoint}")
    
    conn.request("GET", endpoint, headers=headers)
    
    res = conn.getresponse()
    status = res.status
    data = res.read()
    
    logger.info(f"Response status: {status}")
    
    if status != 200:
        logger.error(f"API error: {status} - {data.decode('utf-8')}")
        return
    
    try:
        json_data = json.loads(data.decode("utf-8"))
        logger.info(f"Successfully received data with keys: {list(json_data.keys())}")
        
        # Save response to file for inspection
        with open(f"rapidapi_options_data_{ticker}.json", "w") as f:
            json.dump(json_data, f, indent=2)
        logger.info(f"Saved response to rapidapi_options_data_{ticker}.json")
        
        return json_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return None

def test_yahoo_finance166_endpoint(ticker="AAPL"):
    """Test the yahoo-finance166 RapidAPI endpoint (from options_enhanced_analysis.py)"""
    logger.info(f"Testing yahoo-finance166 endpoint for {ticker}")
    
    # Get API key
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY not found in environment variables")
        return
    
    # Test yahoo-finance166 endpoint
    conn = http.client.HTTPSConnection("yahoo-finance166.p.rapidapi.com")
    
    headers = {
        'x-rapidapi-key': api_key,
        'x-rapidapi-host': "yahoo-finance166.p.rapidapi.com"
    }
    
    endpoint = f"/api/stock/get-options?region=US&symbol={ticker}"
    logger.info(f"Testing endpoint: {endpoint}")
    
    conn.request("GET", endpoint, headers=headers)
    
    res = conn.getresponse()
    status = res.status
    data = res.read()
    
    logger.info(f"Response status: {status}")
    
    if status != 200:
        logger.error(f"API error: {status} - {data.decode('utf-8')}")
        return
    
    try:
        json_data = json.loads(data.decode("utf-8"))
        logger.info(f"Successfully received data with keys: {list(json_data.keys())}")
        
        # Save response to file for inspection
        with open(f"yahoo_finance166_options_data_{ticker}.json", "w") as f:
            json.dump(json_data, f, indent=2)
        logger.info(f"Saved response to yahoo_finance166_options_data_{ticker}.json")
        
        return json_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return None

def main():
    """Run all tests"""
    ticker = "AAPL"
    
    # Test yh-finance endpoints
    logger.info("=== Testing yh-finance.p.rapidapi.com endpoints ===")
    market_data = test_rapidapi_market_data(ticker)
    options_data = test_rapidapi_options_data(ticker)
    
    # Test yahoo-finance166 endpoint
    logger.info("=== Testing yahoo-finance166.p.rapidapi.com endpoint ===")
    yahoo_finance166_data = test_yahoo_finance166_endpoint(ticker)
    
    # Print summary
    logger.info("=== Test Summary ===")
    logger.info(f"yh-finance market data: {'SUCCESS' if market_data else 'FAILED'}")
    logger.info(f"yh-finance options data: {'SUCCESS' if options_data else 'FAILED'}")
    logger.info(f"yahoo-finance166 options data: {'SUCCESS' if yahoo_finance166_data else 'FAILED'}")

if __name__ == "__main__":
    main() 