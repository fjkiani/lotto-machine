import os
import requests
import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class TechnicalIndicatorAPIConnector:
    """Connector for the Yahoo Finance 15 Technical Indicators API on RapidAPI."""

    BASE_URL = "https://yahoo-finance15.p.rapidapi.com"
    API_HOST = "yahoo-finance15.p.rapidapi.com"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the connector."""
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RapidAPI key is required. Set RAPIDAPI_KEY environment variable or pass to constructor.")
        
        self.headers = {
            "x-rapidapi-host": self.API_HOST,
            "x-rapidapi-key": self.api_key
        }
        logger.info(f"TechnicalIndicatorAPIConnector initialized for host: {self.API_HOST}")

    def _fetch_indicator(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Helper function to fetch data from a specific indicator endpoint."""
        url = f"{self.BASE_URL}{endpoint}"
        logger.debug(f"Fetching indicator data from {url} with params: {params}")
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            
            data = response.json()
            logger.debug(f"Successfully received data from {endpoint}. Status: {data.get('meta', {}).get('status')}")
            
            # Basic validation of response structure
            if not isinstance(data, dict) or 'meta' not in data or 'body' not in data:
                logger.error(f"Invalid response structure received from {endpoint}: {data}")
                return None
            if data['meta'].get('status') != 200:
                logger.error(f"API returned non-200 status in meta for {endpoint}: {data['meta']}")
                return None
            
            return data

        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred while fetching {endpoint}: {http_err} - Response: {response.text}")
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"Connection error occurred while fetching {endpoint}: {conn_err}")
        except requests.exceptions.Timeout as timeout_err:
            logger.error(f"Timeout error occurred while fetching {endpoint}: {timeout_err}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"An unexpected error occurred during request for {endpoint}: {req_err}")
        except ValueError as json_err: # Includes JSONDecodeError
            logger.error(f"Failed to parse JSON response from {endpoint}: {json_err}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in _fetch_indicator: {e}", exc_info=True)
            
        return None # Return None if any exception occurred

    def _parse_indicator_body(self, body: List[Dict[str, Any]], indicator_key: str) -> pd.DataFrame:
        """Parses the 'body' list from the API response into a DataFrame."""
        if not body:
            return pd.DataFrame() # Return empty DataFrame if body is empty
            
        try:
            df = pd.DataFrame(body)
            # Convert timestamp to datetime (assuming Unix timestamp in seconds)
            if 'timestamp' in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
                df = df.set_index('datetime')
                df = df.sort_index() # Ensure chronological order
                # Keep only the indicator value column and potentially timestamp if needed
                if indicator_key in df.columns:
                    df = df[[indicator_key]] # Select only the indicator column
                else:
                    logger.warning(f"Indicator key '{indicator_key}' not found in response body columns: {df.columns}")
                    return pd.DataFrame() # Return empty if key not found
            else:
                logger.warning("'timestamp' column not found in response body.")
                return pd.DataFrame() # Return empty if no timestamp
                
            return df
        except Exception as e:
            logger.error(f"Error parsing indicator body: {e}", exc_info=True)
            return pd.DataFrame()

    # --- Public Methods for Indicators --- 

    def get_sma(self, symbol: str, interval: str, time_period: int, series_type: str = 'close', limit: int = 50) -> Optional[pd.DataFrame]:
        """Get Simple Moving Average (SMA) data."""
        endpoint = "/api/v1/markets/indicators/sma"
        params = {
            "symbol": symbol,
            "interval": interval,
            "time_period": time_period,
            "series_type": series_type,
            "limit": limit
        }
        data = self._fetch_indicator(endpoint, params)
        if data and 'body' in data:
            # The key in the body seems to be uppercase 'SMA'
            return self._parse_indicator_body(data['body'], 'SMA') 
        return None

    def get_rsi(self, symbol: str, interval: str, time_period: int, series_type: str = 'close', limit: int = 50) -> Optional[pd.DataFrame]:
        """Get Relative Strength Index (RSI) data."""
        endpoint = "/api/v1/markets/indicators/rsi"
        params = {
            "symbol": symbol,
            "interval": interval,
            "time_period": time_period,
            "series_type": series_type,
            "limit": limit
        }
        data = self._fetch_indicator(endpoint, params)
        if data and 'body' in data:
            # Assuming the key is 'RSI'
            return self._parse_indicator_body(data['body'], 'RSI')
        return None

    def get_macd(self, symbol: str, interval: str, series_type: str = 'close', 
                 fastperiod: int = 12, slowperiod: int = 26, signalperiod: int = 9, 
                 limit: int = 50) -> Optional[pd.DataFrame]:
        """Get Moving Average Convergence Divergence (MACD) data."""
        endpoint = "/api/v1/markets/indicators/macd"
        params = {
            "symbol": symbol,
            "interval": interval,
            "series_type": series_type,
            "fastperiod": fastperiod,
            "slowperiod": slowperiod,
            "signalperiod": signalperiod,
            "limit": limit
        }
        data = self._fetch_indicator(endpoint, params)
        if data and 'body' in data:
            # MACD response might have multiple keys: 'MACD', 'MACD_Signal', 'MACD_Hist'
            # Need to adjust parsing if we want all three in the DataFrame
            # For now, let's parse assuming we want a DataFrame with all relevant columns
            try:
                df = pd.DataFrame(data['body'])
                if 'timestamp' in df.columns:
                    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
                    df = df.set_index('datetime')
                    df = df.sort_index()
                    # Keep relevant MACD columns if they exist
                    macd_cols = [col for col in ['MACD', 'MACD_Signal', 'MACD_Hist'] if col in df.columns]
                    if macd_cols:
                        return df[macd_cols]
                    else:
                        logger.warning(f"No MACD related columns found in response body for {symbol}")
                        return pd.DataFrame()
                else:
                    logger.warning("'timestamp' column not found in MACD response body.")
                    return pd.DataFrame()
            except Exception as e:
                logger.error(f"Error parsing MACD body: {e}", exc_info=True)
                return pd.DataFrame()
        return None

    def get_adx(self, symbol: str, interval: str, time_period: int, limit: int = 50) -> Optional[pd.DataFrame]:
        """Get Average Directional Index (ADX) data."""
        endpoint = "/api/v1/markets/indicators/adx"
        params = {
            "symbol": symbol,
            "interval": interval,
            "time_period": time_period,
            "limit": limit
        }
        data = self._fetch_indicator(endpoint, params)
        if data and 'body' in data:
            # Assuming the key is 'ADX'
            return self._parse_indicator_body(data['body'], 'ADX')
        return None

# Example Usage
if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv() # Load .env file for RAPIDAPI_KEY
    
    logging.basicConfig(level=logging.DEBUG) # Enable debug logging for testing
    
    connector = TechnicalIndicatorAPIConnector()
    
    symbol = "AAPL"
    interval = "1d" # Daily interval
    
    print(f"--- Testing SMA for {symbol} ({interval}) ---")
    sma_data = connector.get_sma(symbol=symbol, interval=interval, time_period=50, limit=10)
    if sma_data is not None:
        print(sma_data.tail())
    else:
        print("Failed to retrieve SMA data.")

    print(f"\n--- Testing RSI for {symbol} ({interval}) ---")
    rsi_data = connector.get_rsi(symbol=symbol, interval=interval, time_period=14, limit=10)
    if rsi_data is not None:
        print(rsi_data.tail())
    else:
        print("Failed to retrieve RSI data.")

    print(f"\n--- Testing MACD for {symbol} ({interval}) ---")
    macd_data = connector.get_macd(symbol=symbol, interval=interval, limit=10)
    if macd_data is not None:
        print(macd_data.tail())
    else:
        print("Failed to retrieve MACD data.")

    print(f"\n--- Testing ADX for {symbol} ({interval}) ---")
    adx_data = connector.get_adx(symbol=symbol, interval=interval, time_period=14, limit=10)
    if adx_data is not None:
        print(adx_data.tail())
    else:
        print("Failed to retrieve ADX data.") 