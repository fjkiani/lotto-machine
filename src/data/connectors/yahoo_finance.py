import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import time

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
        self.base_url = "https://yahoo-finance166.p.rapidapi.com/api"
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
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        if self.use_rapidapi:
            return self._get_option_chain_rapidapi(ticker)
        else:
            return self._get_option_chain_yfinance(ticker)
    
    def _get_option_chain_rapidapi(self, ticker: str) -> OptionChain:
        """Get option chain using RapidAPI"""
        self._handle_rate_limits()
        
        url = f"{self.base_url}/stock/get-options"
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
                symbol=ticker,
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
                            contract_symbol=call_data.get("contractSymbol", ""),
                            strike=call_data.get("strike", 0),
                            currency=call_data.get("currency", "USD"),
                            last_price=call_data.get("lastPrice", 0),
                            change=call_data.get("change", 0),
                            percent_change=call_data.get("percentChange", 0),
                            volume=call_data.get("volume", 0),
                            open_interest=call_data.get("openInterest", 0),
                            bid=call_data.get("bid", 0),
                            ask=call_data.get("ask", 0),
                            implied_volatility=call_data.get("impliedVolatility", 0),
                            in_the_money=call_data.get("inTheMoney", False),
                            contract_type="call"
                        )
                    
                    put_contract = None
                    if put_data:
                        put_contract = OptionContract(
                            contract_symbol=put_data.get("contractSymbol", ""),
                            strike=put_data.get("strike", 0),
                            currency=put_data.get("currency", "USD"),
                            last_price=put_data.get("lastPrice", 0),
                            change=put_data.get("change", 0),
                            percent_change=put_data.get("percentChange", 0),
                            volume=put_data.get("volume", 0),
                            open_interest=put_data.get("openInterest", 0),
                            bid=put_data.get("bid", 0),
                            ask=put_data.get("ask", 0),
                            implied_volatility=put_data.get("impliedVolatility", 0),
                            in_the_money=put_data.get("inTheMoney", False),
                            contract_type="put"
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
            import yfinance as yf
            
            # Get stock info
            stock = yf.Ticker(ticker)
            
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
                calls = options.calls
                puts = options.puts
                
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
                            last_price=float(call_data.get("lastPrice", 0)),
                            change=float(call_data.get("change", 0)),
                            percent_change=float(call_data.get("percentChange", 0)),
                            volume=int(call_data.get("volume", 0)),
                            open_interest=int(call_data.get("openInterest", 0)),
                            bid=float(call_data.get("bid", 0)),
                            ask=float(call_data.get("ask", 0)),
                            implied_volatility=float(call_data.get("impliedVolatility", 0)),
                            in_the_money=bool(call_data.get("inTheMoney", False)),
                            contract_type="call"
                        )
                    
                    put_contract = None
                    if put_data is not None:
                        put_contract = OptionContract(
                            contract_symbol=put_data.get("contractSymbol", ""),
                            strike=float(put_data.get("strike", 0)),
                            currency="USD",
                            last_price=float(put_data.get("lastPrice", 0)),
                            change=float(put_data.get("change", 0)),
                            percent_change=float(put_data.get("percentChange", 0)),
                            volume=int(put_data.get("volume", 0)),
                            open_interest=int(put_data.get("openInterest", 0)),
                            bid=float(put_data.get("bid", 0)),
                            ask=float(put_data.get("ask", 0)),
                            implied_volatility=float(put_data.get("impliedVolatility", 0)),
                            in_the_money=bool(put_data.get("inTheMoney", False)),
                            contract_type="put"
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
                quote=quote,
                expiration_dates=[exp.expiration_date for exp in expirations],
                strikes=sorted(list(all_strikes)),
                options=expirations
            )
            
            # Cache the result
            self._store_in_cache(cache_key, option_chain)
            
            return option_chain
            
        except ImportError:
            logger.error("yfinance library not installed. Please install with: pip install yfinance")
            raise
        except Exception as e:
            logger.error(f"Error fetching option chain for {ticker} with yfinance: {str(e)}")
            raise
    
    def get_market_quotes(self, tickers: Union[str, List[str]]) -> Dict[str, MarketQuote]:
        """Get detailed market quotes for one or more tickers using marketGetQuotesV2 endpoint
        
        Args:
            tickers: Single ticker or list of ticker symbols
            
        Returns:
            Dictionary mapping ticker symbols to MarketQuote objects
        """
        if isinstance(tickers, str):
            tickers = [tickers]
            
        # Join tickers with commas for the API
        tickers_str = ",".join(tickers)
        cache_key = f"market_quotes_{tickers_str}"
        
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
            
        self._handle_rate_limits()
        
        # Update to the correct endpoint based on the provided example
        url = f"{self.base_url}/market/get-quote-v2"
        params = {"symbols": tickers_str, "fields": "quoteSummary"}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            self._update_rate_limits(response.headers)
            
            if response.status_code != 200:
                logger.error(f"Error fetching market quotes: {response.status_code} - {response.text}")
                raise Exception(f"API request failed with status {response.status_code}")
            
            data = response.json()
            
            # Process quote data
            quotes = {}
            quote_results = data.get("quoteResponse", {}).get("result", [])
            
            for quote_data in quote_results:
                symbol = quote_data.get("symbol")
                
                # Extract summary detail data if available
                summary_detail = quote_data.get("quoteSummary", {}).get("summaryDetail", {})
                
                market_quote = MarketQuote(
                    symbol=symbol,
                    quote_type=quote_data.get("quoteType", ""),
                    market_state=quote_data.get("marketState", ""),
                    regular_market_price=quote_data.get("regularMarketPrice", 0),
                    regular_market_previous_close=summary_detail.get("previousClose", 0),
                    regular_market_open=summary_detail.get("open", 0),
                    regular_market_day_high=summary_detail.get("dayHigh", 0),
                    regular_market_day_low=summary_detail.get("dayLow", 0),
                    regular_market_volume=summary_detail.get("volume", 0),
                    average_volume=summary_detail.get("averageVolume", 0),
                    average_volume_10_days=summary_detail.get("averageVolume10days", 0),
                    bid=summary_detail.get("bid", 0),
                    ask=summary_detail.get("ask", 0),
                    bid_size=summary_detail.get("bidSize", 0),
                    ask_size=summary_detail.get("askSize", 0),
                    market_cap=quote_data.get("marketCap", 0),
                    fifty_two_week_high=summary_detail.get("fiftyTwoWeekHigh", 0),
                    fifty_two_week_low=summary_detail.get("fiftyTwoWeekLow", 0),
                    fifty_day_average=summary_detail.get("fiftyDayAverage", 0),
                    two_hundred_day_average=summary_detail.get("twoHundredDayAverage", 0),
                    trailing_annual_dividend_rate=summary_detail.get("trailingAnnualDividendRate", 0),
                    trailing_annual_dividend_yield=summary_detail.get("trailingAnnualDividendYield", 0),
                    trailing_pe=summary_detail.get("trailingPE", 0),
                    exchange=quote_data.get("exchange", ""),
                    exchange_name=quote_data.get("fullExchangeName", ""),
                    currency=summary_detail.get("currency", "USD"),
                    raw_data=quote_data  # Store the full raw data for additional fields
                )
                
                quotes[symbol] = market_quote
            
            # Cache the result
            self._store_in_cache(cache_key, quotes)
            
            return quotes
            
        except Exception as e:
            logger.error(f"Error fetching market quotes for {tickers_str}: {str(e)}")
            raise 