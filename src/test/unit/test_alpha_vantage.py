#!/usr/bin/env python
"""
Test script for Alpha Vantage connector
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add the project root directory to the Python path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from src.data.connectors.alpha_vantage import AlphaVantageConnector

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Check if API key is set
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY environment variable is not set. Please set it and try again.")
        sys.exit(1)
    
    # Create Alpha Vantage connector
    alpha_vantage = AlphaVantageConnector(api_key)
    
    # Test stock ticker (can be changed)
    ticker = "MSFT"
    
    # Test time series endpoints
    print("\n=== Testing Time Series Daily ===")
    try:
        daily_data = alpha_vantage.get_time_series(ticker, interval="daily", outputsize="compact")
        print(f"Meta Data: {json.dumps(daily_data.get('Meta Data', {}), indent=2)}")
        time_series_key = [k for k in daily_data.keys() if k.startswith("Time Series")][0]
        dates = list(daily_data[time_series_key].keys())
        print(f"Got {len(dates)} daily data points")
        print(f"Latest date: {dates[0]}")
        print(f"Sample data for {dates[0]}: {json.dumps(daily_data[time_series_key][dates[0]], indent=2)}")
    except Exception as e:
        logger.error(f"Error testing daily time series: {str(e)}")
    
    print("\n=== Testing Time Series Weekly ===")
    try:
        weekly_data = alpha_vantage.get_time_series(ticker, interval="weekly", outputsize="compact")
        print(f"Meta Data: {json.dumps(weekly_data.get('Meta Data', {}), indent=2)}")
        time_series_key = [k for k in weekly_data.keys() if k.startswith("Weekly")][0]
        dates = list(weekly_data[time_series_key].keys())
        print(f"Got {len(dates)} weekly data points")
        print(f"Latest date: {dates[0]}")
        print(f"Sample data for {dates[0]}: {json.dumps(weekly_data[time_series_key][dates[0]], indent=2)}")
    except Exception as e:
        logger.error(f"Error testing weekly time series: {str(e)}")
    
    print("\n=== Testing Quote Endpoint ===")
    try:
        quote_data = alpha_vantage.get_quote(ticker)
        print(f"Quote data: {json.dumps(quote_data.get('Global Quote', {}), indent=2)}")
    except Exception as e:
        logger.error(f"Error testing quote endpoint: {str(e)}")
    
    print("\n=== Testing Search Endpoint ===")
    try:
        search_data = alpha_vantage.search_ticker("Microsoft")
        print(f"Search data: {json.dumps(search_data.get('bestMatches', [])[:3], indent=2)}")
    except Exception as e:
        logger.error(f"Error testing search endpoint: {str(e)}")
    
if __name__ == "__main__":
    main() 