import os
import logging
import requests
import time
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class RealTimeFinanceConnector:
    """Connector for Real-Time Finance Data API from RapidAPI."""
    
    BASE_URL = "https://real-time-finance-data.p.rapidapi.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the connector with API credentials."""
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RapidAPI key is required. Set RAPIDAPI_KEY environment variable or pass to constructor.")
        
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "real-time-finance-data.p.rapidapi.com"
        }
        
        # Cache for storing API responses
        self._cache = {}
        self._cache_timestamps = {}
    
    def _get_from_cache(self, key: str, max_age_seconds: int = 60) -> Optional[Dict]:
        """Get data from cache if it exists and is not expired."""
        if key in self._cache:
            timestamp = self._cache_timestamps.get(key, 0)
            if time.time() - timestamp < max_age_seconds:
                return self._cache[key]
        return None
    
    def _store_in_cache(self, key: str, data: Dict) -> None:
        """Store data in cache with current timestamp."""
        self._cache[key] = data
        self._cache_timestamps[key] = time.time()
    
    def _fetch_data(self, endpoint: str, params: Dict = None) -> Dict:
        """Fetch data from the API."""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            error_msg = f"Error fetching data from {endpoint}: {e.response.status_code}"
            if e.response.text:
                error_msg += f" - {e.response.text}"
            logger.error(error_msg)
            return {"error": f"API request failed with status {e.response.status_code}"}
        except requests.RequestException as e:
            logger.error(f"Error fetching data from {endpoint}: {str(e)}")
            return {"error": f"API request failed: {str(e)}"}
        except ValueError as e:
            logger.error(f"Error parsing response from {endpoint}: {str(e)}")
            return {"error": f"Failed to parse API response: {str(e)}"}
    
    def search(self, query: str) -> Dict:
        """
        Search for stocks, ETFs, funds, and indices by name or symbol.
        
        Args:
            query: The search query (e.g., "apple", "MSFT")
            
        Returns:
            Dictionary containing search results
        """
        cache_key = f"search_{query}"
        cached_data = self._get_from_cache(cache_key, 300)  # Cache for 5 minutes
        if cached_data:
            return cached_data
        
        params = {"query": query}
        response = self._fetch_data("/search", params)
        
        self._store_in_cache(cache_key, response)
        return response
    
    def get_market_trends(self, trend_type: str = "gainers") -> Dict:
        """
        Get market trends such as gainers, losers, or most active stocks.
        
        Args:
            trend_type: Type of trend to retrieve ("gainers", "losers", "actives", 
                        "advanced_decline", "price_volume")
                        
        Returns:
            Dictionary containing market trend data
        """
        cache_key = f"market_trends_{trend_type}"
        cached_data = self._get_from_cache(cache_key, 900)  # Cache for 15 minutes
        if cached_data:
            return cached_data
        
        params = {"trend_type": trend_type}
        response = self._fetch_data("/market-trends", params)
        
        self._store_in_cache(cache_key, response)
        return response
    
    def get_stock_time_series(self, symbol: str, period: str = "1D", interval: Optional[str] = None) -> Dict:
        """
        Get time series data for a stock using Yahoo Finance data.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "SPY")
            period: Time period for data ("1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "MAX")
            interval: Optional interval for data points
            
        Returns:
            Dictionary containing time series data
        """
        # Remove exchange suffix if present
        if ":" in symbol:
            symbol = symbol.split(":")[0]
            
        cache_key = f"stock_time_series_yf_{symbol}_{period}"
        cached_data = self._get_from_cache(cache_key, 300)  # Cache for 5 minutes
        if cached_data:
            return cached_data
        
        params = {"symbol": symbol, "period": period}
        if interval:
            params["interval"] = interval
            
        response = self._fetch_data("/stock-time-series-yahoo-finance", params)
        
        self._store_in_cache(cache_key, response)
        return response
    
    def get_stock_news(self, symbol: Optional[str] = None, language: str = "en") -> Dict:
        """
        Get news articles related to a stock or general financial news.
        
        Args:
            symbol: Stock symbol with exchange (e.g., "AAPL:NASDAQ") or None for general news
            language: Language code for news articles (e.g., "en" for English)
            
        Returns:
            Dictionary containing news articles
        """
        params = {"language": language}
        
        # The API requires a symbol, so we'll use a default one for general news
        if symbol:
            cache_key = f"stock_news_{symbol}_{language}"
            params["symbol"] = symbol
        else:
            # Use a broad market index for general financial news
            symbol = "SPY:PCX"  # S&P 500 ETF for general market news
            cache_key = f"general_news_{language}"
            params["symbol"] = symbol
        
        cached_data = self._get_from_cache(cache_key, 900)  # Cache for 15 minutes
        if cached_data:
            return cached_data
        
        response = self._fetch_data("/stock-news", params)
        
        self._store_in_cache(cache_key, response)
        return response
    
    def get_stock_quote_with_time_series(self, symbol: str, period: str = "1D") -> Dict:
        """
        Get a comprehensive stock quote with time series data.
        This combines the time series data which already includes quote information.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "SPY")
            period: Time period for data ("1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "MAX")
            
        Returns:
            Dictionary containing stock quote and time series data
        """
        return self.get_stock_time_series(symbol, period)
    
    def get_symbol_search_results(self, query: str) -> List[Dict]:
        """
        Get formatted search results for a query.
        
        Args:
            query: The search query
            
        Returns:
            List of dictionaries with symbol information
        """
        result = self.search(query)
        symbols = []
        
        if "error" in result:
            logger.error(f"Error searching for {query}: {result['error']}")
            return symbols
            
        if "data" in result and "stock" in result["data"]:
            for stock in result["data"]["stock"]:
                symbols.append({
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "type": stock["type"],
                    "exchange": stock["exchange"],
                    "price": stock.get("price"),
                    "change_percent": stock.get("change_percent"),
                    "currency": stock.get("currency"),
                })
                
        return symbols
    
    def get_gainers_and_losers(self) -> Dict:
        """
        Get top gainers and losers in the market.
        
        Returns:
            Dictionary containing gainers and losers data
        """
        gainers = self.get_market_trends("gainers")
        losers = self.get_market_trends("losers")
        
        return {
            "gainers": gainers.get("data", {}).get("trends", []),
            "losers": losers.get("data", {}).get("trends", [])
        } 