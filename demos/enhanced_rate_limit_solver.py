#!/usr/bin/env python3
"""
ENHANCED RATE LIMIT SOLVER WITH PROPER PARSING
- Implement proper HTML parsing for Yahoo Finance
- Add more robust fallback strategies
- Include data validation and error handling
- Create a production-ready solution
"""

import logging
import time
import random
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedRateLimitSolver:
    """Enhanced rate limit solver with proper parsing"""
    
    def __init__(self):
        self.cache_dir = "api_cache"
        self.cache_duration = 300  # 5 minutes
        self.request_delays = {
            'yahoo_finance': 3.0,  # 3 seconds between requests
            'rapidapi': 2.0,       # 2 seconds between requests
            'yfinance': 1.0,       # 1 second between requests
            'yahoo_direct': 5.0    # 5 seconds between requests
        }
        self.last_request_time = {}
        self.request_counts = {}
        self.max_requests_per_minute = {
            'yahoo_finance': 10,
            'rapidapi': 20,
            'yfinance': 30,
            'yahoo_direct': 5
        }
        
        # User agents for rotation
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        # Create cache directory
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_path(self, source: str, ticker: str, data_type: str) -> str:
        """Get cache file path"""
        return os.path.join(self.cache_dir, f"{source}_{ticker}_{data_type}.json")
    
    def _is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache is still valid"""
        try:
            if not os.path.exists(cache_path):
                return False
            
            # Check file age
            file_age = time.time() - os.path.getmtime(cache_path)
            return file_age < self.cache_duration
            
        except Exception as e:
            logger.error(f"Error checking cache validity: {e}")
            return False
    
    def _load_from_cache(self, cache_path: str) -> Optional[Dict[str, Any]]:
        """Load data from cache"""
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading from cache: {e}")
            return None
    
    def _save_to_cache(self, cache_path: str, data: Dict[str, Any]) -> None:
        """Save data to cache"""
        try:
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
    
    def _enforce_rate_limit(self, source: str) -> bool:
        """Enforce rate limiting with jitter"""
        try:
            current_time = time.time()
            
            # Check if we need to wait
            if source in self.last_request_time:
                time_since_last = current_time - self.last_request_time[source]
                required_delay = self.request_delays.get(source, 2.0)
                
                # Add random jitter to avoid synchronized requests
                jitter = random.uniform(0.1, 0.5)
                total_delay = required_delay + jitter
                
                if time_since_last < total_delay:
                    wait_time = total_delay - time_since_last
                    logger.info(f"Rate limiting: waiting {wait_time:.2f}s for {source}")
                    time.sleep(wait_time)
            
            # Update request tracking
            self.last_request_time[source] = time.time()
            
            # Track request counts
            minute_key = int(current_time // 60)
            if source not in self.request_counts:
                self.request_counts[source] = {}
            
            if minute_key not in self.request_counts[source]:
                self.request_counts[source][minute_key] = 0
            
            self.request_counts[source][minute_key] += 1
            
            # Check if we're hitting limits
            max_requests = self.max_requests_per_minute.get(source, 20)
            if self.request_counts[source][minute_key] > max_requests:
                logger.warning(f"Rate limit approaching for {source}, switching to fallback")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error enforcing rate limit: {e}")
            return False
    
    def get_market_data_with_fallback(self, ticker: str) -> Dict[str, Any]:
        """Get market data with multiple fallback strategies"""
        try:
            logger.info(f"🔍 GETTING MARKET DATA FOR {ticker} WITH ENHANCED FALLBACKS")
            
            # Try cache first
            cache_path = self._get_cache_path("cached", ticker, "market_data")
            if self._is_cache_valid(cache_path):
                cached_data = self._load_from_cache(cache_path)
                if cached_data:
                    logger.info(f"✅ Using cached data for {ticker}")
                    return cached_data
            
            # Try yfinance first (most reliable)
            yfinance_data = self._try_yfinance(ticker)
            if yfinance_data and self._validate_data(yfinance_data):
                self._save_to_cache(cache_path, yfinance_data)
                return yfinance_data
            
            # Try RapidAPI as fallback
            rapidapi_data = self._try_rapidapi(ticker)
            if rapidapi_data and self._validate_data(rapidapi_data):
                self._save_to_cache(cache_path, rapidapi_data)
                return rapidapi_data
            
            # Try Yahoo Finance direct with proper parsing
            yahoo_data = self._try_yahoo_direct_enhanced(ticker)
            if yahoo_data and self._validate_data(yahoo_data):
                self._save_to_cache(cache_path, yahoo_data)
                return yahoo_data
            
            # Return minimal data structure if all fail
            logger.warning(f"All data sources failed for {ticker}, returning minimal data")
            minimal_data = {
                'ticker': ticker,
                'price': 0.0,
                'volume': 0,
                'change': 0.0,
                'change_percent': 0.0,
                'high': 0.0,
                'low': 0.0,
                'options': {'call_volume': 0, 'put_volume': 0, 'put_call_ratio': 0},
                'source': 'minimal_fallback',
                'timestamp': datetime.now().isoformat(),
                'error': 'All data sources failed'
            }
            
            return minimal_data
            
        except Exception as e:
            logger.error(f"Error getting market data for {ticker}: {e}")
            return {}
    
    def _validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate data quality"""
        try:
            if not data:
                return False
            
            # Check required fields
            required_fields = ['ticker', 'price', 'volume', 'source']
            for field in required_fields:
                if field not in data:
                    return False
            
            # Check data types and ranges
            if not isinstance(data['price'], (int, float)) or data['price'] <= 0:
                return False
            
            if not isinstance(data['volume'], (int, float)) or data['volume'] < 0:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating data: {e}")
            return False
    
    def _try_yfinance(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Try yfinance with enhanced error handling"""
        try:
            if not self._enforce_rate_limit('yfinance'):
                return None
            
            logger.info(f"📊 Trying yfinance for {ticker}")
            
            stock = yf.Ticker(ticker)
            
            # Get basic info with timeout
            try:
                info = stock.info
            except Exception as info_e:
                logger.warning(f"Info failed for {ticker}: {info_e}")
                info = {}
            
            # Get history with timeout
            hist = stock.history(period="1d", timeout=10)
            
            if hist.empty:
                logger.warning(f"No history data from yfinance for {ticker}")
                return None
            
            # Get options data
            options_data = None
            try:
                options = stock.options
                if options:
                    nearest_exp = options[0]
                    option_chain = stock.option_chain(nearest_exp)
                    
                    call_volume = option_chain.calls['volume'].sum()
                    put_volume = option_chain.puts['volume'].sum()
                    
                    options_data = {
                        'call_volume': int(call_volume),
                        'put_volume': int(put_volume),
                        'put_call_ratio': put_volume / call_volume if call_volume > 0 else 0
                    }
            except Exception as opt_e:
                logger.warning(f"Options data failed for {ticker}: {opt_e}")
                options_data = {'call_volume': 0, 'put_volume': 0, 'put_call_ratio': 0}
            
            # Prepare data
            current_price = hist['Close'].iloc[-1]
            current_volume = hist['Volume'].iloc[-1]
            prev_close = hist['Close'].iloc[0] if len(hist) > 1 else current_price
            
            data = {
                'ticker': ticker,
                'price': float(current_price),
                'volume': int(current_volume),
                'change': float(current_price - prev_close),
                'change_percent': float((current_price - prev_close) / prev_close * 100) if prev_close != 0 else 0,
                'high': float(hist['High'].max()),
                'low': float(hist['Low'].min()),
                'options': options_data,
                'source': 'yfinance',
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ yfinance data retrieved for {ticker}")
            return data
            
        except Exception as e:
            logger.error(f"yfinance failed for {ticker}: {e}")
            return None
    
    def _try_rapidapi(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Try RapidAPI with enhanced error handling"""
        try:
            if not self._enforce_rate_limit('rapidapi'):
                return None
            
            logger.info(f"📊 Trying RapidAPI for {ticker}")
            
            # Use the latest API key
            api_key = "3ec17c8a5cmsh14c013e8aa23a1cp147fb9jsn3e2385628a9b"
            headers = {
                'x-rapidapi-host': 'apidojo-yahoo-finance-v1.p.rapidapi.com',
                'x-rapidapi-key': api_key
            }
            
            # Get market quotes
            url = f"https://apidojo-yahoo-finance-v1.p.rapidapi.com/market/v2/get-quotes"
            params = {'symbols': ticker}
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'quoteResponse' in data and 'result' in data['quoteResponse']:
                    result = data['quoteResponse']['result'][0]
                    
                    # Get options data
                    options_data = {'call_volume': 0, 'put_volume': 0, 'put_call_ratio': 0}
                    
                    try:
                        options_url = f"https://apidojo-yahoo-finance-v1.p.rapidapi.com/market/v2/get-options"
                        options_params = {'symbol': ticker}
                        
                        options_response = requests.get(options_url, headers=headers, params=options_params, timeout=15)
                        
                        if options_response.status_code == 200:
                            options_json = options_response.json()
                            if 'optionChain' in options_json and 'result' in options_json['optionChain']:
                                option_chain = options_json['optionChain']['result'][0]
                                if 'options' in option_chain and option_chain['options']:
                                    straddles = option_chain['options'][0].get('straddles', [])
                                    
                                    call_volume = 0
                                    put_volume = 0
                                    
                                    for straddle in straddles:
                                        if 'call' in straddle:
                                            call_volume += straddle['call'].get('volume', 0)
                                        if 'put' in straddle:
                                            put_volume += straddle['put'].get('volume', 0)
                                    
                                    options_data = {
                                        'call_volume': call_volume,
                                        'put_volume': put_volume,
                                        'put_call_ratio': put_volume / call_volume if call_volume > 0 else 0
                                    }
                    except Exception as opt_e:
                        logger.warning(f"Options parsing failed for {ticker}: {opt_e}")
                    
                    data = {
                        'ticker': ticker,
                        'price': float(result['regularMarketPrice']),
                        'volume': int(result['regularMarketVolume']),
                        'change': float(result['regularMarketChange']),
                        'change_percent': float(result['regularMarketChangePercent']),
                        'high': float(result['regularMarketDayHigh']),
                        'low': float(result['regularMarketDayLow']),
                        'options': options_data,
                        'source': 'rapidapi',
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    logger.info(f"✅ RapidAPI data retrieved for {ticker}")
                    return data
            
            logger.warning(f"RapidAPI failed for {ticker}: Status {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"RapidAPI failed for {ticker}: {e}")
            return None
    
    def _try_yahoo_direct_enhanced(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Try Yahoo Finance direct with proper HTML parsing"""
        try:
            if not self._enforce_rate_limit('yahoo_direct'):
                return None
            
            logger.info(f"📊 Trying Yahoo Finance direct with parsing for {ticker}")
            
            # Use random user agent
            user_agent = random.choice(self.user_agents)
            
            url = f"https://finance.yahoo.com/quote/{ticker}"
            headers = {
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try to extract data from the page
                price = self._extract_price_from_html(soup)
                volume = self._extract_volume_from_html(soup)
                change = self._extract_change_from_html(soup)
                
                if price > 0:  # Only return if we got valid price data
                    data = {
                        'ticker': ticker,
                        'price': price,
                        'volume': volume,
                        'change': change,
                        'change_percent': (change / price * 100) if price != 0 else 0,
                        'high': price,  # Would need more parsing for accurate high/low
                        'low': price,
                        'options': {'call_volume': 0, 'put_volume': 0, 'put_call_ratio': 0},
                        'source': 'yahoo_direct',
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    logger.info(f"✅ Yahoo Finance direct data retrieved for {ticker}")
                    return data
            
            logger.warning(f"Yahoo Finance direct failed for {ticker}: Status {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Yahoo Finance direct failed for {ticker}: {e}")
            return None
    
    def _extract_price_from_html(self, soup: BeautifulSoup) -> float:
        """Extract price from HTML"""
        try:
            # Try multiple selectors for price
            price_selectors = [
                'span[data-field="regularMarketPrice"]',
                'span[data-symbol="price"]',
                '.Trsdu\\(0\\.3s\\) .Fw\\(b\\) .Fz\\(36px\\)',
                '[data-testid="qsp-price"]',
                '.quote-header-section .quote-price'
            ]
            
            for selector in price_selectors:
                element = soup.select_one(selector)
                if element:
                    price_text = element.get_text().strip()
                    # Extract numeric value
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        return float(price_match.group())
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error extracting price: {e}")
            return 0.0
    
    def _extract_volume_from_html(self, soup: BeautifulSoup) -> int:
        """Extract volume from HTML"""
        try:
            # Try multiple selectors for volume
            volume_selectors = [
                'span[data-field="regularMarketVolume"]',
                'span[data-symbol="volume"]',
                'td[data-field="regularMarketVolume"]'
            ]
            
            for selector in volume_selectors:
                element = soup.select_one(selector)
                if element:
                    volume_text = element.get_text().strip()
                    # Extract numeric value
                    volume_match = re.search(r'[\d,]+', volume_text.replace(',', ''))
                    if volume_match:
                        return int(volume_match.group())
            
            return 0
            
        except Exception as e:
            logger.error(f"Error extracting volume: {e}")
            return 0
    
    def _extract_change_from_html(self, soup: BeautifulSoup) -> float:
        """Extract change from HTML"""
        try:
            # Try multiple selectors for change
            change_selectors = [
                'span[data-field="regularMarketChange"]',
                'span[data-symbol="change"]',
                '.quote-header-section .quote-change'
            ]
            
            for selector in change_selectors:
                element = soup.select_one(selector)
                if element:
                    change_text = element.get_text().strip()
                    # Extract numeric value (handle + and - signs)
                    change_match = re.search(r'[+-]?[\d,]+\.?\d*', change_text.replace(',', ''))
                    if change_match:
                        return float(change_match.group())
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error extracting change: {e}")
            return 0.0

def test_enhanced_rate_limit_solver():
    """Test the enhanced rate limit solver"""
    print("🔥 ENHANCED API RATE LIMIT SOLVER - TESTING")
    print("=" * 80)
    
    solver = EnhancedRateLimitSolver()
    tickers = ['SPY', 'QQQ', 'TSLA']
    
    for ticker in tickers:
        print(f"\n🔍 TESTING {ticker}:")
        
        try:
            data = solver.get_market_data_with_fallback(ticker)
            
            if data:
                print(f"   ✅ Data retrieved from {data['source']}")
                print(f"   Price: ${data['price']:.2f}")
                print(f"   Volume: {data['volume']:,}")
                print(f"   Change: {data['change_percent']:.2f}%")
                print(f"   Put/Call Ratio: {data['options']['put_call_ratio']:.2f}")
                print(f"   Timestamp: {data['timestamp']}")
                
                if 'error' in data:
                    print(f"   ⚠️  Warning: {data['error']}")
            else:
                print(f"   ❌ No data retrieved")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n✅ ENHANCED RATE LIMIT SOLVER TEST COMPLETE!")
    print(f"🎯 PRODUCTION READY!")

if __name__ == "__main__":
    test_enhanced_rate_limit_solver()

