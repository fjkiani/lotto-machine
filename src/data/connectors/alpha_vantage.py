import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import time
import pandas as pd

logger = logging.getLogger(__name__)

class AlphaVantageConnector:
    """Connector for Alpha Vantage API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Alpha Vantage connector
        
        Args:
            api_key: RapidAPI key for Alpha Vantage API
        """
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY")
        self.base_url = "https://alpha-vantage.p.rapidapi.com"
        self.headers = {
            "x-rapidapi-host": "alpha-vantage.p.rapidapi.com",
            "x-rapidapi-key": self.api_key
        }
        
        # Initialize cache
        self._cache = {}
        self._cache_expiry = {}
        self._cache_duration = 300  # 5 minutes default cache duration
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if available and not expired"""
        if cache_key in self._cache and self._cache_expiry.get(cache_key, 0) > time.time():
            logger.debug(f"Cache hit for {cache_key}")
            return self._cache[cache_key]
        return None
    
    def _store_in_cache(self, cache_key: str, data: Any, duration: Optional[int] = None) -> None:
        """Store data in cache with expiry time"""
        self._cache[cache_key] = data
        self._cache_expiry[cache_key] = time.time() + (duration or self._cache_duration)
        logger.debug(f"Cached {cache_key} for {duration or self._cache_duration} seconds")
    
    def get_time_series(self, ticker: str, interval: str = "daily", outputsize: str = "compact") -> Dict:
        """
        Get time series data for a ticker symbol
        
        Args:
            ticker: Stock ticker symbol
            interval: Time interval - 'intraday', 'daily', 'weekly', 'monthly'
            outputsize: Output size - 'compact' (100 data points) or 'full' (20+ years)
            
        Returns:
            Dictionary with time series data (already in the format we need)
        """
        cache_key = f"alpha_vantage_time_series_{ticker}_{interval}_{outputsize}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
            
        # Map interval to Alpha Vantage function
        function_map = {
            "intraday": "TIME_SERIES_INTRADAY",
            "daily": "TIME_SERIES_DAILY",
            "daily_adjusted": "TIME_SERIES_DAILY_ADJUSTED",
            "weekly": "TIME_SERIES_WEEKLY",
            "weekly_adjusted": "TIME_SERIES_WEEKLY_ADJUSTED",
            "monthly": "TIME_SERIES_MONTHLY",
            "monthly_adjusted": "TIME_SERIES_MONTHLY_ADJUSTED"
        }
        
        function = function_map.get(interval.lower(), "TIME_SERIES_DAILY")
        
        # Setup parameters
        params = {
            "function": function,
            "symbol": ticker,
            "outputsize": outputsize,
            "datatype": "json"
        }
        
        # Add interval parameter for intraday data
        if interval.lower() == "intraday":
            params["interval"] = "5min"  # Default to 5-minute intervals
        
        try:
            logger.info(f"Fetching {interval} time series data for {ticker} from Alpha Vantage")
            
            # Make the API request
            response = requests.get(
                f"{self.base_url}/query", 
                headers=self.headers,
                params=params
            )
            
            # Check response status
            if response.status_code != 200:
                logger.warning(f"Alpha Vantage API returned status code {response.status_code}")
                raise Exception(f"API request failed with status code {response.status_code}")
            
            # Parse the response
            data = response.json()
            
            # Check for error message
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API returned error: {data['Error Message']}")
                raise Exception(f"API returned error: {data['Error Message']}")
            
            # The data is already in the format we need
            # Store in cache and return
            self._store_in_cache(cache_key, data)
            return data
            
        except Exception as e:
            logger.error(f"Error fetching time series from Alpha Vantage: {str(e)}")
            raise
    
    def get_quote(self, ticker: str) -> Dict:
        """
        Get real-time quote for a ticker
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with quote data
        """
        cache_key = f"alpha_vantage_quote_{ticker}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
            
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": ticker,
            "datatype": "json"
        }
        
        try:
            logger.info(f"Fetching quote for {ticker} from Alpha Vantage")
            
            # Make the API request
            response = requests.get(
                f"{self.base_url}/query", 
                headers=self.headers,
                params=params
            )
            
            # Check response status
            if response.status_code != 200:
                logger.warning(f"Alpha Vantage API returned status code {response.status_code}")
                raise Exception(f"API request failed with status code {response.status_code}")
            
            # Parse the response
            data = response.json()
            
            # Check for error message
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API returned error: {data['Error Message']}")
                raise Exception(f"API returned error: {data['Error Message']}")
            
            # Store in cache and return
            self._store_in_cache(cache_key, data)
            return data
            
        except Exception as e:
            logger.error(f"Error fetching quote from Alpha Vantage: {str(e)}")
            raise
    
    def search_ticker(self, keywords: str) -> Dict:
        """
        Search for ticker symbols matching keywords
        
        Args:
            keywords: Search keywords
            
        Returns:
            Dictionary with search results
        """
        cache_key = f"alpha_vantage_search_{keywords}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
            
        params = {
            "function": "SYMBOL_SEARCH",
            "keywords": keywords,
            "datatype": "json"
        }
        
        try:
            logger.info(f"Searching for ticker symbols matching '{keywords}' using Alpha Vantage")
            
            # Make the API request
            response = requests.get(
                f"{self.base_url}/query", 
                headers=self.headers,
                params=params
            )
            
            # Check response status
            if response.status_code != 200:
                logger.warning(f"Alpha Vantage API returned status code {response.status_code}")
                raise Exception(f"API request failed with status code {response.status_code}")
            
            # Parse the response
            data = response.json()
            
            # Check for error message
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API returned error: {data['Error Message']}")
                raise Exception(f"API returned error: {data['Error Message']}")
            
            # Store in cache and return
            self._store_in_cache(cache_key, data)
            return data
            
        except Exception as e:
            logger.error(f"Error searching ticker symbols with Alpha Vantage: {str(e)}")
            raise 