# RapidAPI Integration: Real-Time Finance Data

## Overview

This document describes the integration of the Real-Time Finance Data API from RapidAPI into the AI Hedge Fund project. We've successfully integrated several endpoints that provide financial data for market analysis.

## Integrated Endpoints

The following endpoints have been successfully integrated:

1. **Search** (`/search`)
   - Functionality: Search for stocks, ETFs, funds, and indices by name or symbol
   - Parameters: `query` (search term)
   - Response: List of matching instruments with symbols, names, prices, and change percentages

2. **Market Trends** (`/market-trends`)
   - Functionality: Get market trends such as gainers, losers, and most active stocks
   - Parameters: `trend_type` (gainers, losers, actives, etc.)
   - Response: List of stocks with price and performance data

3. **Stock Time Series** (`/stock-time-series-yahoo-finance`)
   - Functionality: Get historical price data for a stock
   - Parameters: `symbol`, `period` (1D, 5D, 1M, etc.), optional `interval`
   - Response: OHLC data points with volume and timestamps

4. **Stock News** (`/stock-news`)
   - Functionality: Get news articles related to a stock or general financial news
   - Parameters: `symbol`, `language`
   - Response: List of news articles with titles, sources, URLs, and publication times

## Implementation

### Connector Class

The integration is implemented through the `RealTimeFinanceConnector` class located at `src/data/connectors/real_time_finance.py`. The connector:

- Handles API authentication using RapidAPI keys
- Implements caching to minimize API calls
- Provides error handling for API requests
- Formats and transforms data for easier consumption

### Helper Methods

Several helper methods simplify common tasks:

- `get_symbol_search_results()`: Format search results for display
- `get_gainers_and_losers()`: Fetch both gainers and losers in a single call
- `get_stock_quote_with_time_series()`: Get comprehensive stock data with time series

### Testing

A comprehensive test script (`test_real_time_finance.py`) verifies the functionality of each endpoint and saves response examples for reference.

## Example Usage

### Search for Stocks

```python
from src.data.connectors.real_time_finance import RealTimeFinanceConnector

connector = RealTimeFinanceConnector()
results = connector.search("apple")
symbols = connector.get_symbol_search_results("apple")
```

### Get Market Trends

```python
# Get gainers
gainers = connector.get_market_trends("gainers")

# Get losers
losers = connector.get_market_trends("losers")

# Get both in a single call
trends = connector.get_gainers_and_losers()
```

### Get Stock Time Series

```python
# Daily data for SPY
spy_daily = connector.get_stock_time_series("SPY", period="1D")

# Monthly data for Apple
aapl_monthly = connector.get_stock_time_series("AAPL", period="1M")
```

### Get Stock News

```python
# Get news for Apple
apple_news = connector.get_stock_news("AAPL:NASDAQ")

# Get general financial news
general_news = connector.get_stock_news()  # Uses SPY as a default symbol
```

## Demonstration

A demonstration script (`demo_real_time_finance.py`) showcases the functionality:

- Displays search results for stocks
- Shows top gainers and losers
- Presents the latest news for a stock
- Generates stock charts with price and volume data

## Next Steps

1. **Integration with Streamlit UI**
   - Add the new data sources to the existing Streamlit application
   - Create UI components for market trends and news display

2. **LLM Analysis Enhancement**
   - Update Gemini prompts to analyze market trends
   - Add news sentiment analysis to insights

3. **Visualization Improvements**
   - Add interactive charts for market data
   - Create visualizations that combine price movements with news events

## Notes and Limitations

- Not all initially targeted endpoints are available or functioning in the API
- The stock news endpoint requires a symbol parameter even for general news
- API response structures may change and should be monitored
- API rate limits should be considered for production use 