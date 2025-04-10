import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import time
import pandas as pd
from decimal import Decimal

from src.data.models import OptionChain, OptionContract, OptionChainOptions, OptionStraddle, OptionChainQuote, MarketQuote

logger = logging.getLogger(__name__)

class YahooFinanceConnector:
    """Connector for Yahoo Finance API"""
    
    def __init__(self, api_key: Optional[str] = None, use_rapidapi: bool = True):
        """Initialize the Yahoo Finance connector
        
        Args:
            api_key: RapidAPI key for Yahoo Finance API
            use_rapidapi: Whether to use RapidAPI (True) or direct yfinance (False)
        """
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY")
        self.use_rapidapi = use_rapidapi
        self.base_url = "https://yahoo-finance166.p.rapidapi.com"  # Updated base URL
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "yahoo-finance166.p.rapidapi.com"
        }
        self.rate_limit_remaining = 100
        self.rate_limit_reset = 0
        
        # Initialize cache
        self._cache = {}
        self._cache_expiry = {}
        self._cache_duration = 300  # 5 minutes default cache duration
        
        # Import yfinance only when needed to avoid unnecessary imports
        if not use_rapidapi:
            try:
                import yfinance as yf
                self._yf = yf
                logger.info("Successfully initialized yfinance")
            except ImportError:
                logger.error("Failed to import yfinance. Please install it with: pip install yfinance")
                raise
    
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
    
    def _handle_rate_limits(self) -> None:
        """Handle rate limiting by waiting if necessary"""
        if self.rate_limit_remaining <= 5:
            wait_time = max(0, self.rate_limit_reset - time.time())
            if wait_time > 0:
                logger.warning(f"Rate limit almost reached. Waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
    
    def _update_rate_limits(self, headers: Dict) -> None:
        """Update rate limit information from response headers"""
        if "X-RateLimit-Remaining" in headers:
            self.rate_limit_remaining = int(headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Reset" in headers:
            self.rate_limit_reset = int(headers["X-RateLimit-Reset"])
    
    def get_option_chain(self, ticker: str) -> OptionChain:
        """Get option chain data for a ticker
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            OptionChain object with option data
        """
        cache_key = f"option_chain_{ticker}"
        
        # Skip cache if we're switching between APIs
        if not self.use_rapidapi:
            # Clear any cached RapidAPI data
            if cache_key in self._cache:
                del self._cache[cache_key]
                if cache_key in self._cache_expiry:
                    del self._cache_expiry[cache_key]
            return self._get_option_chain_yfinance(ticker)
            
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        return self._get_option_chain_rapidapi(ticker)
    
    def _get_option_chain_rapidapi(self, ticker: str) -> OptionChain:
        """Get option chain using RapidAPI"""
        self._handle_rate_limits()
        
        url = f"{self.base_url}/api/stock/get-options"
        params = {"symbol": ticker, "region": "US"}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._update_rate_limits(response.headers)
            
            if response.status_code != 200:
                logger.error(f"Error fetching option chain: {response.status_code} - {response.text}")
                raise Exception(f"API request failed with status {response.status_code}")
            
            data = response.json()
            
            # Get quote data
            quote_data = data.get("optionChain", {}).get("result", [{}])[0].get("quote", {})
            quote = OptionChainQuote(
                quote_type=quote_data.get("quoteType", ""),
                market_state=quote_data.get("marketState", ""),
                currency=quote_data.get("currency", "USD"),
                regular_market_price=quote_data.get("regularMarketPrice", 0),
                regular_market_change=quote_data.get("regularMarketChange", 0),
                regular_market_change_percent=quote_data.get("regularMarketChangePercent", 0),
                regular_market_open=quote_data.get("regularMarketOpen", 0),
                regular_market_day_high=quote_data.get("regularMarketDayHigh", 0),
                regular_market_day_low=quote_data.get("regularMarketDayLow", 0),
                regular_market_volume=quote_data.get("regularMarketVolume", 0),
                market_cap=quote_data.get("marketCap", 0),
                trailing_pe=quote_data.get("trailingPE", 0),
                trailing_annual_dividend_rate=quote_data.get("trailingAnnualDividendRate", 0),
                dividend_rate=quote_data.get("dividendRate", 0),
                dividend_yield=quote_data.get("dividendYield", 0),
                eps_trailing_twelve_months=quote_data.get("epsTrailingTwelveMonths", 0),
                eps_forward=quote_data.get("epsForward", 0),
                eps_current_year=quote_data.get("epsCurrentYear", 0)
            )
            
            # Process options data
            option_chain_data = data.get("optionChain", {}).get("result", [{}])[0].get("options", [])
            expirations = []
            strikes = set()
            
            for option_date in option_chain_data:
                timestamp = option_date.get("expirationDate")
                if not timestamp:
                    continue
                    
                exp_date = datetime.fromtimestamp(timestamp)
                
                # Process straddles (call/put pairs)
                straddles = []
                for straddle_data in option_date.get("straddles", []):
                    strike = straddle_data.get("strike")
                    strikes.add(strike)
                    
                    call_data = straddle_data.get("call")
                    put_data = straddle_data.get("put")
                    
                    call_contract = None
                    if call_data:
                        call_contract = OptionContract(
                            contract_symbol=call_data["contractSymbol"],
                            option_type="CALL",
                            strike=Decimal(str(strike)),
                            currency=call_data.get("currency"),
                            last_price=Decimal(str(call_data.get("lastPrice", 0))),
                            change_price=Decimal(str(call_data.get("change", 0))),
                            percent_change=Decimal(str(call_data.get("percentChange", 0))),
                            volume=call_data.get("volume", 0),
                            open_interest=call_data.get("openInterest", 0),
                            bid=Decimal(str(call_data.get("bid", 0))),
                            ask=Decimal(str(call_data.get("ask", 0))),
                            contract_size=call_data.get("contractSize"),
                            expiration=exp_date,
                            last_trade_date=call_data.get("lastTradeDate"),
                            implied_volatility=Decimal(str(call_data.get("impliedVolatility", 0))),
                            in_the_money=call_data.get("inTheMoney", False)
                        )
                    
                    put_contract = None
                    if put_data:
                        put_contract = OptionContract(
                            contract_symbol=put_data["contractSymbol"],
                            option_type="PUT",
                            strike=Decimal(str(strike)),
                            currency=put_data.get("currency"),
                            last_price=Decimal(str(put_data.get("lastPrice", 0))),
                            change_price=Decimal(str(put_data.get("change", 0))),
                            percent_change=Decimal(str(put_data.get("percentChange", 0))),
                            volume=put_data.get("volume", 0),
                            open_interest=put_data.get("openInterest", 0),
                            bid=Decimal(str(put_data.get("bid", 0))),
                            ask=Decimal(str(put_data.get("ask", 0))),
                            contract_size=put_data.get("contractSize"),
                            expiration=exp_date,
                            last_trade_date=put_data.get("lastTradeDate"),
                            implied_volatility=Decimal(str(put_data.get("impliedVolatility", 0))),
                            in_the_money=put_data.get("inTheMoney", False)
                        )
                    
                    straddle = OptionStraddle(
                        strike=strike,
                        call_contract=call_contract,
                        put_contract=put_contract
                    )
                    straddles.append(straddle)
                
                expiration = OptionChainOptions(
                    expiration_date=exp_date,
                    has_mini_options=False,
                    straddles=straddles
                )
                expirations.append(expiration)
            
            # Create OptionChain object
            option_chain = OptionChain(
                underlying_symbol=ticker,
                quote=quote,
                expiration_dates=[exp.expiration_date for exp in expirations],
                strikes=sorted(list(strikes)),
                options=expirations
            )
            
            # Cache the result
            self._store_in_cache(cache_key, option_chain)
            
            return option_chain
            
        except Exception as e:
            logger.error(f"Error fetching option chain for {ticker}: {str(e)}")
            raise
    
    def _get_option_chain_yfinance(self, ticker: str) -> OptionChain:
        """Get option chain using yfinance library"""
        try:
            # Define cache key
            cache_key = f"option_chain_{ticker}"
            
            # Get stock info
            stock = self._yf.Ticker(ticker)
            
            # Get options expiration dates
            expiration_dates = stock.options
            if not expiration_dates:
                logger.error(f"No options data available for {ticker}")
                raise ValueError(f"No options data available for {ticker}")
            
            # Get quote data
            info = stock.info
            quote = OptionChainQuote(
                quote_type=info.get("quoteType", ""),
                market_state=info.get("marketState", ""),
                currency=info.get("currency", "USD"),
                regular_market_price=info.get("regularMarketPrice", 0),
                regular_market_change=info.get("regularMarketChange", 0),
                regular_market_change_percent=info.get("regularMarketChangePercent", 0),
                regular_market_open=info.get("regularMarketOpen", 0),
                regular_market_day_high=info.get("regularMarketDayHigh", 0),
                regular_market_day_low=info.get("regularMarketDayLow", 0),
                regular_market_volume=info.get("regularMarketVolume", 0),
                market_cap=info.get("marketCap", 0),
                trailing_pe=info.get("trailingPE", 0),
                trailing_annual_dividend_rate=info.get("trailingAnnualDividendRate", 0),
                dividend_rate=info.get("dividendRate", 0),
                dividend_yield=info.get("dividendYield", 0),
                eps_trailing_twelve_months=info.get("epsTrailingTwelveMonths", 0),
                eps_forward=info.get("epsForward", 0),
                eps_current_year=info.get("epsCurrentYear", 0)
            )
            
            # Process options data
            expirations = []
            all_strikes = set()
            
            for exp_date_str in expiration_dates:
                # Convert string date to datetime
                exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                
                # Get options for this expiration
                options = stock.option_chain(exp_date_str)
                calls = options.calls.fillna(0)  # Fill NaN values with 0
                puts = options.puts.fillna(0)    # Fill NaN values with 0
                
                # Create straddles by matching calls and puts by strike
                straddles = []
                call_by_strike = {float(call["strike"]): call for _, call in calls.iterrows()}
                put_by_strike = {float(put["strike"]): put for _, put in puts.iterrows()}
                
                # Get all unique strikes
                all_strikes_exp = set(call_by_strike.keys()) | set(put_by_strike.keys())
                all_strikes.update(all_strikes_exp)
                
                for strike in all_strikes_exp:
                    call_data = call_by_strike.get(strike)
                    put_data = put_by_strike.get(strike)
                    
                    call_contract = None
                    if call_data is not None:
                        call_contract = OptionContract(
                            contract_symbol=call_data.get("contractSymbol", ""),
                            strike=float(call_data.get("strike", 0)),
                            currency="USD",
                            last_price=float(call_data.get("lastPrice", 0) or 0),
                            change_price=float(call_data.get("change", 0) or 0),
                            percent_change=float(call_data.get("percentChange", 0) or 0),
                            volume=int(float(call_data.get("volume", 0) or 0)),
                            open_interest=int(float(call_data.get("openInterest", 0) or 0)),
                            bid=float(call_data.get("bid", 0) or 0),
                            ask=float(call_data.get("ask", 0) or 0),
                            implied_volatility=float(call_data.get("impliedVolatility", 0) or 0),
                            in_the_money=bool(call_data.get("inTheMoney", False)),
                            option_type="CALL"
                        )
                    
                    put_contract = None
                    if put_data is not None:
                        put_contract = OptionContract(
                            contract_symbol=put_data.get("contractSymbol", ""),
                            strike=float(put_data.get("strike", 0)),
                            currency="USD",
                            last_price=float(put_data.get("lastPrice", 0) or 0),
                            change_price=float(put_data.get("change", 0) or 0),
                            percent_change=float(put_data.get("percentChange", 0) or 0),
                            volume=int(float(put_data.get("volume", 0) or 0)),
                            open_interest=int(float(put_data.get("openInterest", 0) or 0)),
                            bid=float(put_data.get("bid", 0) or 0),
                            ask=float(put_data.get("ask", 0) or 0),
                            implied_volatility=float(put_data.get("impliedVolatility", 0) or 0),
                            in_the_money=bool(put_data.get("inTheMoney", False)),
                            option_type="PUT"
                        )
                    
                    straddle = OptionStraddle(
                        strike=float(strike),
                        call_contract=call_contract,
                        put_contract=put_contract
                    )
                    straddles.append(straddle)
                
                expiration = OptionChainOptions(
                    expiration_date=exp_date,
                    has_mini_options=False,
                    straddles=straddles
                )
                expirations.append(expiration)
            
            # Create OptionChain object
            option_chain = OptionChain(
                underlying_symbol=ticker,
                has_mini_options=False,
                quote=quote,
                expiration_dates=[exp.expiration_date for exp in expirations],
                strikes=sorted(list(all_strikes)),
                options=expirations
            )
            
            # Cache the result
            self._store_in_cache(cache_key, option_chain)
            
            return option_chain
            
        except Exception as e:
            logger.error(f"Error fetching option chain for {ticker} with yfinance: {str(e)}")
            raise
    
    def get_market_quotes(self, tickers: Union[str, List[str]]) -> Dict[str, MarketQuote]:
        """Get detailed market quotes for one or more tickers"""
        if isinstance(tickers, str):
            tickers = [tickers]
            
        # Join tickers with commas for the API
        tickers_str = ",".join(tickers)
        cache_key = f"market_quotes_{tickers_str}"
        
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
            
        self._handle_rate_limits()
        
        # Use the working endpoint structure
        url = f"{self.base_url}/api/stock/get-options"
        params = {"symbol": tickers[0], "region": "US"}  # Get first ticker since endpoint only supports one
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._update_rate_limits(response.headers)
            
            if response.status_code != 200:
                logger.error(f"Error fetching market quotes: {response.status_code} - {response.text}")
                raise Exception(f"API request failed with status {response.status_code}")
            
            data = response.json()
            
            # Process quote data from options response
            quotes = {}
            quote_data = data.get("optionChain", {}).get("result", [{}])[0].get("quote", {})
            
            if quote_data:
                market_quote = MarketQuote(
                    symbol=quote_data.get("symbol"),
                    quote_type=quote_data.get("quoteType", ""),
                    market_state=quote_data.get("marketState", ""),
                    regular_market_price=quote_data.get("regularMarketPrice", 0),
                    regular_market_previous_close=quote_data.get("regularMarketPreviousClose", 0),
                    regular_market_open=quote_data.get("regularMarketOpen", 0),
                    regular_market_day_high=quote_data.get("regularMarketDayHigh", 0),
                    regular_market_day_low=quote_data.get("regularMarketDayLow", 0),
                    regular_market_volume=quote_data.get("regularMarketVolume", 0),
                    average_volume=quote_data.get("averageVolume", 0),
                    average_volume_10_days=quote_data.get("averageVolume10days", 0),
                    bid=quote_data.get("bid", 0),
                    ask=quote_data.get("ask", 0),
                    bid_size=quote_data.get("bidSize", 0),
                    ask_size=quote_data.get("askSize", 0),
                    market_cap=quote_data.get("marketCap", 0),
                    fifty_two_week_high=quote_data.get("fiftyTwoWeekHigh", 0),
                    fifty_two_week_low=quote_data.get("fiftyTwoWeekLow", 0),
                    fifty_day_average=quote_data.get("fiftyDayAverage", 0),
                    two_hundred_day_average=quote_data.get("twoHundredDayAverage", 0),
                    trailing_annual_dividend_rate=quote_data.get("trailingAnnualDividendRate", 0),
                    trailing_annual_dividend_yield=quote_data.get("trailingAnnualDividendYield", 0),
                    trailing_pe=quote_data.get("trailingPE", 0),
                    exchange=quote_data.get("exchange", ""),
                    exchange_name=quote_data.get("fullExchangeName", ""),
                    currency=quote_data.get("currency", "USD"),
                    raw_data=quote_data
                )
                quotes[tickers[0]] = market_quote
            
            # Store in cache
            self._store_in_cache(cache_key, quotes)
            
            return quotes
            
        except Exception as e:
            logger.error(f"Error fetching market quotes: {str(e)}")
            return {}
    
    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get a quote for a single ticker
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dictionary with quote data
        """
        try:
            # Call get_market_quotes to fetch the data
            quotes = self.get_market_quotes(ticker)
            
            # Check if the ticker exists in the results
            if ticker in quotes:
                # Convert MarketQuote object to dictionary for compatibility
                quote = quotes[ticker]
                return {
                    "symbol": quote.symbol,
                    "quoteType": quote.quote_type,
                    "marketState": quote.market_state,
                    "regularMarketPrice": quote.regular_market_price,
                    "regularMarketPreviousClose": quote.regular_market_previous_close,
                    "regularMarketOpen": quote.regular_market_open,
                    "regularMarketDayHigh": quote.regular_market_day_high,
                    "regularMarketDayLow": quote.regular_market_day_low,
                    "regularMarketVolume": quote.regular_market_volume,
                    "regularMarketChangePercent": quote.get_day_change_percent(),
                    "averageVolume": quote.average_volume,
                    "marketCap": quote.market_cap,
                    "trailingPE": quote.trailing_pe,
                    "dividendYield": quote.get_dividend_yield(),
                    "fiftyTwoWeekHigh": quote.fifty_two_week_high,
                    "fiftyTwoWeekLow": quote.fifty_two_week_low,
                    "fiftyDayAverage": quote.fifty_day_average,
                    "twoHundredDayAverage": quote.two_hundred_day_average,
                    "exchange": quote.exchange_name,
                    "currency": quote.currency
                }
            else:
                logger.error(f"Ticker {ticker} not found in market quotes response")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting quote for {ticker}: {str(e)}")
            return {}
    
    def get_historical_data(self, ticker: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
        """Get historical price data for a ticker
        
        Args:
            ticker: Ticker symbol
            period: Data period (e.g., "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
            interval: Data interval (e.g., "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")
            
        Returns:
            Pandas DataFrame with historical data or None if data cannot be fetched
        """
        cache_key = f"historical_data_{ticker}_{period}_{interval}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
        
        try:
            # Try to use yfinance first
            logger.info(f"Fetching historical data for {ticker} with period={period}, interval={interval}")
            
            # Get the data using yfinance
            ticker_data = self._yf.Ticker(ticker)
            df = ticker_data.history(period=period, interval=interval)
            
            # Check if we got valid data
            if df is None or df.empty:
                logger.error(f"No historical data available for {ticker}")
                return None
            
            # Rename columns to ensure consistency
            df.columns = [col.capitalize() for col in df.columns]
            
            # Store in cache
            self._store_in_cache(cache_key, df)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {str(e)}")
            
            # Try to use RapidAPI as fallback
            if self.use_rapidapi:
                try:
                    return self._get_historical_data_rapidapi(ticker, period, interval)
                except Exception as e2:
                    logger.error(f"Error fetching historical data from RapidAPI: {str(e2)}")
            
            return None
    
    def _get_historical_data_rapidapi(self, ticker: str, period: str, interval: str) -> Optional[pd.DataFrame]:
        """Get historical data using RapidAPI
        
        Args:
            ticker: Ticker symbol
            period: Data period
            interval: Data interval
            
        Returns:
            Pandas DataFrame with historical data or None if data cannot be fetched
        """
        import pandas as pd
        
        self._handle_rate_limits()
        
        # Convert period to start/end dates
        end_date = datetime.now()
        
        if period == "1d":
            start_date = end_date - timedelta(days=1)
        elif period == "5d":
            start_date = end_date - timedelta(days=5)
        elif period == "1mo":
            start_date = end_date - timedelta(days=30)
        elif period == "3mo":
            start_date = end_date - timedelta(days=90)
        elif period == "6mo":
            start_date = end_date - timedelta(days=180)
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
        elif period == "2y":
            start_date = end_date - timedelta(days=730)
        elif period == "5y":
            start_date = end_date - timedelta(days=1825)
        elif period == "10y":
            start_date = end_date - timedelta(days=3650)
        elif period == "ytd":
            start_date = datetime(end_date.year, 1, 1)
        else:  # "max" or any other value
            start_date = end_date - timedelta(days=3650)  # Default to 10 years
        
        # Format dates for API
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Map interval to API format
        interval_map = {
            "1m": "1m", "2m": "2m", "5m": "5m", "15m": "15m", "30m": "30m",
            "60m": "60m", "90m": "90m", "1h": "1h",
            "1d": "1d", "5d": "5d", "1wk": "1wk", "1mo": "1mo", "3mo": "3mo"
        }
        api_interval = interval_map.get(interval, "1d")
        
        url = f"{self.base_url}/stock/get-histories"
        params = {
            "symbol": ticker,
            "region": "US",
            "interval": api_interval,
            "from": start_date_str,
            "to": end_date_str
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._update_rate_limits(response.headers)
            
            if response.status_code != 200:
                logger.error(f"Error fetching historical data: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            # Extract historical data
            history_data = data.get("prices", [])
            
            if not history_data:
                logger.error(f"No historical data available for {ticker}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(history_data)
            
            # Convert timestamp to datetime
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], unit="s")
                df.set_index("date", inplace=True)
            
            # Rename columns to match yfinance format
            column_map = {
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
                "adjclose": "Adj Close"
            }
            df.rename(columns=column_map, inplace=True)
            
            # Cache the result
            cache_key = f"historical_data_{ticker}_{period}_{interval}"
            self._store_in_cache(cache_key, df)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching historical data from RapidAPI: {str(e)}")
            return None
    
    def get_time_series(self, ticker, interval="daily", outputsize="compact"):
        """
        Fetch time series data for a ticker (Open, High, Low, Close, Volume).
        
        Args:
            ticker (str): The stock ticker symbol
            interval (str): Data interval - 'daily', 'weekly', or 'monthly'
            outputsize (str): 'compact' for last 100 datapoints, 'full' for all available data
        
        Returns:
            dict: Time series data in the format shown in the example
        """
        logger.info(f"Fetching {interval} time series data for {ticker}")
        
        try:
            # First try using RapidAPI (preferred method)
            url = f"{self.base_url}/api/stock/v3/get-historical-data"
            
            # Map our interval to API parameters
            interval_map = {
                "daily": "1d",
                "weekly": "1wk",
                "monthly": "1mo"
            }
            
            api_interval = interval_map.get(interval, "1d")
            
            # Set up parameters
            params = {
                "symbol": ticker,
                "region": "US",
                "interval": api_interval
            }
            
            # Make the API request
            response = requests.get(
                url, 
                headers=self.headers,
                params=params
            )
            
            # Check response status
            if response.status_code != 200:
                logger.warning(f"RapidAPI returned status code {response.status_code}")
                raise Exception(f"API request failed with status code {response.status_code}")
            
            # Parse response
            data = response.json()
            
            # Transform to the expected format
            result = {
                "Meta Data": {
                    "1. Information": f"{interval.capitalize()} Prices (open, high, low, close) and Volumes",
                    "2. Symbol": ticker,
                    "3. Last Refreshed": datetime.now().strftime("%Y-%m-%d"),
                    "4. Output Size": outputsize,
                    "5. Time Zone": "US/Eastern"
                },
                f"Time Series ({interval.capitalize()})": {}
            }
            
            # Process the data points
            for item in data.get("prices", []):
                # Get the date
                timestamp = item.get("date", 0)
                if not timestamp:
                    continue
                    
                date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                
                # Format the data point
                result[f"Time Series ({interval.capitalize()})"][date_str] = {
                    "1. open": str(item.get("open", 0)),
                    "2. high": str(item.get("high", 0)),
                    "3. low": str(item.get("low", 0)),
                    "4. close": str(item.get("close", 0)),
                    "5. volume": str(item.get("volume", 0))
                }
            
            return result
            
        except Exception as e:
            logger.warning(f"Error fetching time series from RapidAPI: {str(e)}. Falling back to yfinance.")
            
            # Fall back to yfinance
            try:
                import yfinance as yf
                import pandas as pd
                
                # Map interval to yfinance period and interval
                interval_map = {
                    "daily": ("1d", "6mo" if outputsize == "compact" else "max"),
                    "weekly": ("1wk", "2y" if outputsize == "compact" else "max"),
                    "monthly": ("1mo", "5y" if outputsize == "compact" else "max")
                }
                
                yf_interval, yf_period = interval_map.get(interval, ("1d", "6mo"))
                
                # Get historical data
                stock = yf.Ticker(ticker)
                history = stock.history(period=yf_period, interval=yf_interval)
                
                # Format the result
                result = {
                    "Meta Data": {
                        "1. Information": f"{interval.capitalize()} Prices (open, high, low, close) and Volumes",
                        "2. Symbol": ticker,
                        "3. Last Refreshed": datetime.now().strftime("%Y-%m-%d"),
                        "4. Output Size": outputsize,
                        "5. Time Zone": "US/Eastern"
                    },
                    f"Time Series ({interval.capitalize()})": {}
                }
                
                # Convert DataFrame to required format
                for date, row in history.iterrows():
                    date_str = date.strftime("%Y-%m-%d")
                    result[f"Time Series ({interval.capitalize()})"][date_str] = {
                        "1. open": str(round(row["Open"], 4)),
                        "2. high": str(round(row["High"], 4)),
                        "3. low": str(round(row["Low"], 4)),
                        "4. close": str(round(row["Close"], 4)),
                        "5. volume": str(int(row["Volume"]))
                    }
                
                return result
                
            except Exception as yf_error:
                logger.error(f"Error fetching time series with yfinance: {str(yf_error)}")
                raise yf_error 