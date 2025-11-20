#!/usr/bin/env python3
"""
CHARTEXCHANGE API CLIENT
Real dark pool data from ChartExchange API v1
"""

import requests
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class DarkPoolLevel:
    """Dark pool level data"""
    symbol: str
    price: float
    volume: int
    timestamp: datetime
    exchange: str
    level_type: str  # 'bid', 'ask', 'mid'

@dataclass
class DarkPoolPrint:
    """Dark pool print (trade) data"""
    symbol: str
    price: float
    size: int
    timestamp: datetime
    exchange: str
    side: str  # 'BUY', 'SELL'
    print_type: str  # 'dark_pool', 'block_trade'

class ChartExchangeAPI:
    """ChartExchange API v1 client for dark pool data"""
    
    def __init__(self, api_key: str, tier: int = 1):
        self.api_key = api_key
        self.tier = tier
        self.base_url = "https://chartexchange.com/api/v1"
        self.session = requests.Session()
        
        # Rate limiting
        self.rate_limits = {
            1: 60,    # 60 requests/minute
            2: 250,   # 250 requests/minute  
            3: 1000   # 1000 requests/minute
        }
        self.request_times = []
        
        logger.info(f"ChartExchange API initialized - Tier {tier} ({self.rate_limits[tier]} req/min)")
    
    def _wait_for_rate_limit(self):
        """Wait if we're approaching rate limit"""
        if not self.request_times:
            return
            
        # Clean old requests (older than 1 minute)
        cutoff = time.time() - 60
        self.request_times = [t for t in self.request_times if t > cutoff]
        
        # Check if we're at limit
        max_requests = self.rate_limits[self.tier]
        if len(self.request_times) >= max_requests:
            sleep_time = 60 - (time.time() - self.request_times[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping {sleep_time:.1f} seconds")
                time.sleep(sleep_time)
                self.request_times = []
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """Make authenticated API request"""
        self._wait_for_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        params['api_key'] = self.api_key
        
        try:
            logger.info(f"ChartExchange API: Requesting {endpoint}")
            response = self.session.get(url, params=params, timeout=30)
            
            # Track request time
            self.request_times.append(time.time())
            
            logger.info(f"ChartExchange API: Status {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    logger.info(f"ChartExchange API: Received {len(data)} results")
                elif isinstance(data, dict):
                    results = data.get('results', [])
                    logger.info(f"ChartExchange API: Received {len(results)} results")
                else:
                    logger.info(f"ChartExchange API: Received {type(data)} data")
                return data
            elif response.status_code == 401:
                logger.error("ChartExchange API: Authentication failed - check API key")
                return None
            elif response.status_code == 429:
                logger.warning("ChartExchange API: Rate limit exceeded")
                return None
            else:
                logger.error(f"ChartExchange API: Error {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"ChartExchange API: Request failed - {e}")
            return None
    
    def get_institutional_flow_data(self, symbol: str, days_back: int = 7) -> Dict[str, Any]:
        """Get institutional flow data from available ChartExchange endpoints"""
        logger.info(f"🎯 Getting institutional flow data for {symbol} from ChartExchange API")
        
        flow_data = {
            'symbol': symbol,
            'exchange_volume': [],
            'short_volume': [],
            'short_interest': [],
            'failure_to_deliver': [],
            'timestamp': datetime.now()
        }
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            'symbol': symbol.upper(),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'page_size': 100,
            'ordering': '-date'
        }
        
        # Get Exchange Volume (institutional vs retail)
        try:
            endpoint = "/data/stocks/exchange-volume/"
            data = self._make_request(endpoint, params)
            if data and isinstance(data, list):
                flow_data['exchange_volume'] = data
                logger.info(f"✅ Found {len(data)} exchange volume records")
        except Exception as e:
            logger.warning(f"Exchange volume error: {e}")
        
        # Get Short Volume (short selling activity)
        try:
            endpoint = "/data/stocks/short-volume/"
            data = self._make_request(endpoint, params)
            if data and isinstance(data, list):
                flow_data['short_volume'] = data
                logger.info(f"✅ Found {len(data)} short volume records")
        except Exception as e:
            logger.warning(f"Short volume error: {e}")
        
        # Get Short Interest (institutional positioning)
        try:
            endpoint = "/data/stocks/short-interest/"
            data = self._make_request(endpoint, params)
            if data and isinstance(data, list):
                flow_data['short_interest'] = data
                logger.info(f"✅ Found {len(data)} short interest records")
        except Exception as e:
            logger.warning(f"Short interest error: {e}")
        
        # Get Failure to Deliver (settlement issues)
        try:
            endpoint = "/data/stocks/failure-to-deliver/"
            data = self._make_request(endpoint, params)
            if data and isinstance(data, list):
                flow_data['failure_to_deliver'] = data
                logger.info(f"✅ Found {len(data)} FTD records")
        except Exception as e:
            logger.warning(f"FTD error: {e}")
        
        logger.info(f"🎯 Retrieved institutional flow data for {symbol}")
        return flow_data
    
    def get_dark_pool_levels(self, symbol: str, days_back: int = 1) -> List[DarkPoolLevel]:
        """Get dark pool levels for a symbol"""
        endpoint = "/data/dark-pool-levels/"
        
        # Format symbol correctly (US:SPY format)
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            'symbol': formatted_symbol,
            'date': end_date.strftime('%Y-%m-%d'),  # Required field
            'decimals': '2',  # Required field
            'page_size': 100,
            'ordering': '-premium'
        }
        
        data = self._make_request(endpoint, params)
        if not data:
            return []
            
        # Convert API response to DarkPoolLevel objects
        levels = []
        for d in data:
            try:
                level = DarkPoolLevel(
                    symbol=symbol.upper(),
                    price=float(d.get('level', 0)),
                    volume=int(d.get('volume', 0)),
                    timestamp=datetime.strptime(d.get('date', ''), '%Y-%m-%d'),
                    exchange='XADF',
                    level_type='mid'
                )
                levels.append(level)
            except (KeyError, ValueError) as e:
                logger.debug(f"Error parsing dark pool level: {e}")
                continue
        
        return levels
    
    def get_dark_pool_prints(self, symbol: str, days_back: int = 1) -> List[DarkPoolPrint]:
        """Get dark pool prints (trades) for a symbol"""
        endpoint = f"/data/dark-pool-prints/"
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Format symbol correctly (US:SPY format)
        formatted_symbol = f"US:{symbol.upper()}" if not symbol.startswith('US:') else symbol.upper()
        
        params = {
            'symbol': formatted_symbol,
            'date': end_date.strftime('%Y-%m-%d'),  # Required field
            'decimals': '2',  # Required field
            'page_size': 100,
            'ordering': '-time'
        }
        
        data = self._make_request(endpoint, params)
        if not data:
            return []
        
        prints = []
        for d in data:
            try:
                print_obj = DarkPoolPrint(
                    symbol=symbol.upper(),
                    price=float(d.get('price', 0)),
                    size=int(d.get('size', 0)),
                    timestamp=datetime.strptime(d.get('time', ''), '%Y-%m-%d %H:%M:%S.%f'),
                    exchange=d.get('exchange', 'XADF'),
                    side=d.get('side', 'unknown'),
                    print_type='dark_pool'
                )
                prints.append(print_obj)
            except (KeyError, ValueError) as e:
                logger.debug(f"Error parsing dark pool print: {e}")
                continue
        
        logger.info(f"ChartExchange API: Found {len(prints)} dark pool prints for {symbol}")
        return prints
    
    def get_dark_pool_summary(self, symbol: str, days_back: int = 1) -> Optional[Dict]:
        """Get dark pool prints summary for a symbol"""
        endpoint = f"/data/dark-pool-prints/summary/"
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            'symbol': symbol.upper(),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
        
        data = self._make_request(endpoint, params)
        if not data:
            return None
        
        logger.info(f"ChartExchange API: Retrieved dark pool summary for {symbol}")
        return data
    
    def test_connection(self) -> bool:
        """Test API connection"""
        endpoint = "/ref/stocks/symbol/"
        params = {'page_size': 1}
        
        data = self._make_request(endpoint, params)
        if data:
            logger.info("✅ ChartExchange API connection successful")
            return True
        else:
            logger.error("❌ ChartExchange API connection failed")
            return False

def test_chartexchange_api():
    """Test ChartExchange API with real data"""
    print("🚀 Testing ChartExchange API")
    print("=" * 50)
    
    # You'll need to set your API key here
    api_key = "YOUR_API_KEY_HERE"  # Replace with your actual API key
    
    if api_key == "YOUR_API_KEY_HERE":
        print("❌ Please set your ChartExchange API key in the script")
        return
    
    api = ChartExchangeAPI(api_key, tier=1)
    
    # Test connection
    if not api.test_connection():
        print("❌ API connection failed")
        return
    
    # Test dark pool data for SPY
    print("\n📊 Testing Dark Pool Levels for SPY...")
    levels = api.get_dark_pool_levels('SPY', days_back=1)
    
    if levels:
        print(f"✅ Found {len(levels)} dark pool levels")
        for level in levels[:3]:  # Show first 3
            print(f"  {level.timestamp.strftime('%H:%M:%S')} - ${level.price:.2f} @ {level.volume:,} ({level.level_type})")
    else:
        print("❌ No dark pool levels found")
    
    print("\n📊 Testing Dark Pool Prints for SPY...")
    prints = api.get_dark_pool_prints('SPY', days_back=1)
    
    if prints:
        print(f"✅ Found {len(prints)} dark pool prints")
        for print_data in prints[:3]:  # Show first 3
            print(f"  {print_data.timestamp.strftime('%H:%M:%S')} - {print_data.side} {print_data.size:,} @ ${print_data.price:.2f}")
    else:
        print("❌ No dark pool prints found")
    
    print("\n📊 Testing Dark Pool Summary for SPY...")
    summary = api.get_dark_pool_summary('SPY', days_back=1)
    
    if summary:
        print(f"✅ Retrieved dark pool summary")
        print(f"  Summary data: {json.dumps(summary, indent=2)[:200]}...")
    else:
        print("❌ No dark pool summary found")

if __name__ == "__main__":
    test_chartexchange_api()
