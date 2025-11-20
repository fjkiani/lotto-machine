#!/usr/bin/env python3
"""
ULTIMATE CHARTEXCHANGE API CLIENT
- Complete integration of ALL ChartExchange Tier 3 endpoints
- Dark pool levels & prints
- Short volume, short interest, FTDs
- Exchange volume breakdowns
- Options chain summaries
- Borrow fees
- Stock screener
- EVERYTHING for institutional intelligence
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class DarkPoolPrintSummary:
    """Summary of dark pool prints"""
    symbol: str
    date: str
    total_volume: int
    total_trades: int
    buy_volume: int
    sell_volume: int
    avg_trade_size: float
    largest_print: int
    smallest_print: int

@dataclass
class ShortData:
    """Short volume and interest data"""
    symbol: str
    date: str
    short_volume: int
    total_volume: int
    short_pct: float
    short_interest: Optional[int]
    days_to_cover: Optional[float]

@dataclass
class ExchangeVolume:
    """Exchange volume breakdown"""
    symbol: str
    timestamp: datetime
    exchange: str
    volume: int
    pct_of_total: float

@dataclass
class OptionsChainSummary:
    """Options chain summary with max pain"""
    symbol: str
    date: str
    expiration: str
    max_pain: float
    total_call_oi: int
    total_put_oi: int
    put_call_ratio: float
    itm_calls: int
    otm_calls: int
    itm_puts: int
    otm_puts: int

@dataclass
class BorrowFee:
    """Interactive Brokers borrow fee"""
    symbol: str
    date: str
    fee_rate: float  # Percentage
    available_shares: int

@dataclass
class FTDData:
    """Failure to Deliver data"""
    symbol: str
    date: str
    quantity: int
    price: float

class UltimateChartExchangeClient:
    """Complete ChartExchange API client with ALL institutional data"""
    
    def __init__(self, api_key: str, tier: int = 3):
        self.api_key = api_key
        self.tier = tier
        self.base_url = "https://chartexchange.com/api/v1"
        self.session = requests.Session()
        
        self.rate_limits = {1: 60, 2: 250, 3: 1000}
        self.request_times = []
        
        logger.info(f"🚀 Ultimate ChartExchange Client initialized - Tier {tier}")
        logger.info(f"   API Key: {api_key[:10]}...")
    
    def _wait_for_rate_limit(self):
        """Rate limiting logic"""
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        if len(self.request_times) >= self.rate_limits[self.tier]:
            sleep_time = 61 - (now - self.request_times[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self.request_times = []
        
        self.request_times.append(now)
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Any]:
        """Make API request with error handling"""
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        # Add API key to params
        if params is None:
            params = {}
        params['api_key'] = self.api_key
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"URL: {response.url}")
            return None
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    # ==================== DARK POOL DATA ====================
    
    def get_dark_pool_levels(self, symbol: str, date: Optional[str] = None) -> List[Dict]:
        """Get dark pool levels for a symbol"""
        endpoint = "/data/dark-pool-levels/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d'),
            'decimals': '2',
            'page_size': 1000,
            'ordering': '-volume'
        }
        
        data = self._make_request(endpoint, params)
        return data if data else []
    
    def get_dark_pool_prints(self, symbol: str, date: Optional[str] = None) -> List[Dict]:
        """Get dark pool prints/trades"""
        endpoint = "/data/dark-pool-prints/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d'),
            'decimals': '2',
            'page_size': 1000,
            'ordering': '-time'
        }
        
        data = self._make_request(endpoint, params)
        return data if data else []
    
    def get_dark_pool_summary(self, symbol: str, date: Optional[str] = None) -> Optional[DarkPoolPrintSummary]:
        """Get dark pool prints summary"""
        endpoint = "/data/dark-pool-prints/summary/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        
        if data and isinstance(data, dict):
            return DarkPoolPrintSummary(
                symbol=symbol.upper(),
                date=data.get('date', ''),
                total_volume=int(data.get('total_volume', 0)),
                total_trades=int(data.get('total_trades', 0)),
                buy_volume=int(data.get('buy_volume', 0)),
                sell_volume=int(data.get('sell_volume', 0)),
                avg_trade_size=float(data.get('avg_trade_size', 0)),
                largest_print=int(data.get('largest_print', 0)),
                smallest_print=int(data.get('smallest_print', 0))
            )
        return None
    
    # ==================== SHORT DATA ====================
    
    def get_short_volume(self, symbol: str, date: Optional[str] = None) -> List[ShortData]:
        """Get short volume data"""
        endpoint = "/data/stocks/short-volume/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        
        shorts = []
        if data and isinstance(data, list):
            for item in data:
                shorts.append(ShortData(
                    symbol=symbol.upper(),
                    date=item.get('date', ''),
                    short_volume=int(item.get('short_volume', 0)),
                    total_volume=int(item.get('total_volume', 0)),
                    short_pct=float(item.get('short_pct', 0)),
                    short_interest=None,
                    days_to_cover=None
                ))
        
        return shorts
    
    def get_short_interest(self, symbol: str) -> Optional[Dict]:
        """Get short interest data"""
        endpoint = "/data/stocks/short-interest/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {'symbol': formatted_symbol}
        return self._make_request(endpoint, params)
    
    def get_short_interest_daily(self, symbol: str, date: Optional[str] = None) -> List[Dict]:
        """Get daily short interest"""
        endpoint = "/data/stocks/short-interest-daily/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        return data if data else []
    
    # ==================== EXCHANGE VOLUME ====================
    
    def get_exchange_volume(self, symbol: str, date: Optional[str] = None) -> List[ExchangeVolume]:
        """Get exchange volume breakdown"""
        endpoint = "/data/stocks/exchange-volume/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        
        volumes = []
        if data and isinstance(data, list):
            for item in data:
                # Handle timestamp parsing safely
                ts_str = item.get('timestamp', '')
                try:
                    ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
                except:
                    ts = datetime.now()
                
                volumes.append(ExchangeVolume(
                    symbol=symbol.upper(),
                    timestamp=ts,
                    exchange=item.get('exchange', ''),
                    volume=int(item.get('volume', 0)),
                    pct_of_total=float(item.get('pct_of_total', 0))
                ))
        
        return volumes
    
    def get_exchange_volume_intraday(self, symbol: str, date: Optional[str] = None) -> List[Dict]:
        """Get 30-minute interval exchange volume"""
        endpoint = "/data/stocks/exchange-volume-intraday/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        return data if data else []
    
    # ==================== OPTIONS DATA ====================
    
    def get_options_chain_summary(self, symbol: str, date: Optional[str] = None) -> Optional[OptionsChainSummary]:
        """Get options chain summary with max pain"""
        endpoint = "/data/options/chain-summary/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        
        if data and isinstance(data, dict):
            return OptionsChainSummary(
                symbol=symbol.upper(),
                date=data.get('date', ''),
                expiration=data.get('expiration', ''),
                max_pain=float(data.get('max_pain', 0)),
                total_call_oi=int(data.get('total_call_oi', 0)),
                total_put_oi=int(data.get('total_put_oi', 0)),
                put_call_ratio=float(data.get('put_call_ratio', 0)),
                itm_calls=int(data.get('itm_calls', 0)),
                otm_calls=int(data.get('otm_calls', 0)),
                itm_puts=int(data.get('itm_puts', 0)),
                otm_puts=int(data.get('otm_puts', 0))
            )
        return None
    
    # ==================== BORROW FEES ====================
    
    def get_borrow_fee(self, symbol: str, date: Optional[str] = None) -> Optional[BorrowFee]:
        """Get Interactive Brokers borrow fee"""
        endpoint = "/data/stocks/borrow-fee/ib/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': date or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        
        if data and isinstance(data, dict):
            return BorrowFee(
                symbol=symbol.upper(),
                date=data.get('date', ''),
                fee_rate=float(data.get('fee_rate', 0)),
                available_shares=int(data.get('available_shares', 0))
            )
        return None
    
    # ==================== FTDs ====================
    
    def get_failure_to_deliver(self, symbol: str, start_date: Optional[str] = None) -> List[FTDData]:
        """Get Failure to Deliver data"""
        endpoint = "/data/stocks/failure-to-deliver/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'start_date': start_date or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        
        ftds = []
        if data and isinstance(data, list):
            for item in data:
                ftds.append(FTDData(
                    symbol=symbol.upper(),
                    date=item.get('date', ''),
                    quantity=int(item.get('quantity', 0)),
                    price=float(item.get('price', 0))
                ))
        
        return ftds
    
    # ==================== STOCK BARS ====================
    
    def get_stock_bars(self, symbol: str, timeframe: str = "1m", 
                      start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        """Get OHLC bars"""
        endpoint = "/data/stocks/bars/"
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'timeframe': timeframe,
            'start': start or (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'end': end or datetime.now().strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        
        if data and isinstance(data, list):
            df = pd.DataFrame(data)
            if not df.empty and 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
            return df
        
        return pd.DataFrame()
    
    # ==================== STOCK SCREENER ====================
    
    def screen_stocks(self, filters: Dict[str, Any]) -> List[Dict]:
        """Screen stocks with filters"""
        endpoint = "/screener/stocks/"
        
        data = self._make_request(endpoint, params=filters)
        return data if data else []
    
    def get_stock_screener(self, 
                           min_price: Optional[float] = None,
                           min_volume: Optional[int] = None,
                           min_dark_pool_pct: Optional[float] = None) -> List[Dict]:
        """
        Screen for high-flow tickers with institutional activity
        
        Args:
            min_price: Minimum stock price
            min_volume: Minimum daily volume
            min_dark_pool_pct: Minimum dark pool percentage
        
        Returns:
            List of matching tickers with metrics
        """
        filters = {}
        if min_price is not None:
            filters['min_price'] = min_price
        if min_volume is not None:
            filters['min_volume'] = min_volume
        if min_dark_pool_pct is not None:
            filters['min_dark_pool_pct'] = min_dark_pool_pct
        
        return self.screen_stocks(filters)
    
    def get_screener_columns(self) -> List[str]:
        """Get available screener columns"""
        endpoint = "/screener/stocks/columns/"
        data = self._make_request(endpoint)
        return data if data else []
    
    # ==================== REDDIT SENTIMENT ====================
    
    def get_reddit_mentions(self, symbol: str, days: int = 7) -> List[Dict]:
        """
        Get Reddit mentions for a symbol
        
        Args:
            symbol: Ticker symbol
            days: Number of days to fetch
        
        Returns:
            List of daily mention data with sentiment
        """
        endpoint = "/data/social/reddit/mentions/"
        
        params = {
            'symbol': f"US:{symbol.upper()}",
            'days': days
        }
        
        data = self._make_request(endpoint, params=params)
        return data if data else []
    
    def get_reddit_summary(self, symbol: str) -> Optional[Dict]:
        """
        Get Reddit sentiment summary for a symbol
        
        Args:
            symbol: Ticker symbol
        
        Returns:
            Summary data with overall sentiment
        """
        endpoint = "/data/social/reddit/summary/"
        
        params = {
            'symbol': f"US:{symbol.upper()}"
        }
        
        data = self._make_request(endpoint, params=params)
        return data if data else None
    
    # ==================== COMPOSITE INTELLIGENCE ====================
    
    def get_institutional_profile(self, symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete institutional profile for a symbol
        Combines: DP data, short data, exchange volume, options, borrow fees, FTDs
        """
        logger.info(f"🔍 Building institutional profile for {symbol}")
        
        date = date or datetime.now().strftime('%Y-%m-%d')
        
        profile = {
            'symbol': symbol.upper(),
            'date': date,
            'timestamp': datetime.now().isoformat()
        }
        
        # Dark pool data
        logger.info("   Fetching dark pool data...")
        profile['dp_summary'] = self.get_dark_pool_summary(symbol, date)
        profile['dp_levels'] = self.get_dark_pool_levels(symbol, date)
        
        # Short data
        logger.info("   Fetching short data...")
        profile['short_volume'] = self.get_short_volume(symbol, date)
        profile['short_interest'] = self.get_short_interest(symbol)
        
        # Exchange volume
        logger.info("   Fetching exchange volume...")
        profile['exchange_volume'] = self.get_exchange_volume(symbol, date)
        
        # Options
        logger.info("   Fetching options data...")
        profile['options_summary'] = self.get_options_chain_summary(symbol, date)
        
        # Borrow fee
        logger.info("   Fetching borrow fee...")
        profile['borrow_fee'] = self.get_borrow_fee(symbol, date)
        
        # FTDs
        logger.info("   Fetching FTDs...")
        profile['ftds'] = self.get_failure_to_deliver(symbol)
        
        logger.info(f"✅ Institutional profile complete for {symbol}")
        
        return profile

