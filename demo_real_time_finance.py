#!/usr/bin/env python
"""
Real-Time Finance Data API Demonstration
----------------------------------------

This script demonstrates how to use the RealTimeFinanceConnector to fetch 
financial data from the real-time-finance-data.p.rapidapi.com API.
"""

import os
import json
import logging
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime
from src.data.connectors.real_time_finance import RealTimeFinanceConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def display_search_results(connector, query="apple"):
    """Search for stocks and display the results."""
    logger.info(f"Searching for: {query}")
    results = connector.get_symbol_search_results(query)
    
    if not results:
        logger.error(f"No results found for '{query}'")
        return
    
    print(f"\n=== Search Results for '{query}' ===")
    print(f"{'Symbol':<15}{'Name':<40}{'Exchange':<10}{'Price':<10}{'Change %':<10}")
    print("-" * 85)
    
    for item in results:
        symbol = item.get("symbol", "").split(":")[0]
        name = item.get("name", "")[:38]
        exchange = item.get("exchange", "")[:8]
        price = f"${item.get('price', 0):.2f}" if item.get('price') else "N/A"
        change = f"{item.get('change_percent', 0):.2f}%" if item.get('change_percent') is not None else "N/A"
        
        print(f"{symbol:<15}{name:<40}{exchange:<10}{price:<10}{change:<10}")

def display_market_trends(connector):
    """Display market trend data for gainers and losers."""
    trends = connector.get_gainers_and_losers()
    
    print("\n=== Top Gainers ===")
    print(f"{'Symbol':<15}{'Name':<40}{'Price':<10}{'Change %':<10}")
    print("-" * 75)
    
    for item in trends.get("gainers", [])[:5]:
        symbol = item.get("symbol", "").split(":")[0]
        name = item.get("name", "")[:38]
        price = f"${item.get('price', 0):.2f}" if item.get('price') else "N/A"
        change = f"{item.get('change_percent', 0):.2f}%" if item.get('change_percent') is not None else "N/A"
        
        print(f"{symbol:<15}{name:<40}{price:<10}{change:<10}")
    
    print("\n=== Top Losers ===")
    print(f"{'Symbol':<15}{'Name':<40}{'Price':<10}{'Change %':<10}")
    print("-" * 75)
    
    for item in trends.get("losers", [])[:5]:
        symbol = item.get("symbol", "").split(":")[0]
        name = item.get("name", "")[:38]
        price = f"${item.get('price', 0):.2f}" if item.get('price') else "N/A"
        change = f"{item.get('change_percent', 0):.2f}%" if item.get('change_percent') is not None else "N/A"
        
        print(f"{symbol:<15}{name:<40}{price:<10}{change:<10}")

def display_stock_news(connector, symbol="AAPL:NASDAQ", max_articles=5):
    """Display news articles for a stock."""
    logger.info(f"Fetching news for {symbol}")
    result = connector.get_stock_news(symbol)
    
    if "error" in result:
        logger.error(f"Error fetching news: {result['error']}")
        return
    
    if "data" not in result or "news" not in result["data"]:
        logger.error("No news articles found in response")
        return
    
    news_articles = result["data"]["news"]
    
    print(f"\n=== Latest News for {symbol.split(':')[0]} ===")
    print("-" * 100)
    
    for i, article in enumerate(news_articles[:max_articles]):
        title = article.get("article_title", "No Title")
        source = article.get("source", "Unknown Source")
        url = article.get("article_url", "")
        post_time = article.get("post_time_utc", "")
        
        try:
            # Try to format the date if it's available
            if post_time:
                date_obj = datetime.fromisoformat(post_time.replace(' ', 'T'))
                date_formatted = date_obj.strftime("%Y-%m-%d %H:%M")
            else:
                date_formatted = "Unknown Date"
        except Exception as e:
            logger.debug(f"Error parsing date: {e}")
            date_formatted = post_time or "Unknown Date"
        
        print(f"{i+1}. {title}")
        print(f"   Source: {source} | Date: {date_formatted}")
        print(f"   URL: {url}")
        print("-" * 100)

def plot_stock_time_series(connector, symbol="SPY", period="1D"):
    """Plot a stock's time series data."""
    logger.info(f"Fetching time series data for {symbol} ({period})")
    result = connector.get_stock_time_series(symbol, period)
    
    if "error" in result:
        logger.error(f"Error fetching time series data: {result['error']}")
        return
    
    if "data" not in result or "time_series" not in result["data"]:
        logger.error("No time series data in response")
        return
    
    # Extract data
    time_series = result["data"]["time_series"]
    data = {
        "datetime": [],
        "open": [],
        "close": [],
        "high": [],
        "low": [],
        "volume": []
    }
    
    for point in time_series:
        data["datetime"].append(point.get("datetime"))
        data["open"].append(point.get("open"))
        data["close"].append(point.get("close"))
        data["high"].append(point.get("high"))
        data["low"].append(point.get("low"))
        data["volume"].append(point.get("volume", 0))
    
    # Convert to DataFrame
    df = pd.DataFrame(data)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    
    # Create plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
    
    # Price plot
    ax1.plot(df.index, df["close"], label="Close")
    ax1.set_title(f"{symbol} - {result['data'].get('name', '')} ({period})")
    ax1.set_ylabel("Price")
    ax1.grid(True)
    
    # Add some stock info
    info_text = (
        f"Current: ${result['data'].get('price', 0):.2f}\n"
        f"Change: {result['data'].get('change', 0):.2f} ({result['data'].get('change_percent', 0)*100:.2f}%)\n"
        f"Day Range: ${result['data'].get('day_low', 0):.2f} - ${result['data'].get('day_high', 0):.2f}"
    )
    ax1.text(0.02, 0.95, info_text, transform=ax1.transAxes, 
             verticalalignment='top', bbox={'boxstyle': 'round', 'facecolor': 'wheat', 'alpha': 0.5})
    
    # Volume plot
    ax2.bar(df.index, df["volume"], color="blue", alpha=0.5)
    ax2.set_ylabel("Volume")
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig(f"{symbol}_{period}_chart.png")
    logger.info(f"Chart saved as {symbol}_{period}_chart.png")
    plt.close()

def main():
    """Run the demonstration."""
    print("\n=== Real-Time Finance Data API Demonstration ===\n")
    
    # Check for API key
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY not found in environment variables")
        print("Error: RAPIDAPI_KEY not found. Please set your RapidAPI key in the .env file.")
        return
    
    # Create connector
    connector = RealTimeFinanceConnector(api_key)
    
    # Demonstrate search
    display_search_results(connector, "apple")
    
    # Demonstrate market trends
    display_market_trends(connector)
    
    # Demonstrate news
    display_stock_news(connector, "AAPL:NASDAQ", max_articles=3)
    
    # Demonstrate time series
    plot_stock_time_series(connector, "SPY", "1D")
    plot_stock_time_series(connector, "AAPL", "1M")

if __name__ == "__main__":
    main() 