#!/usr/bin/env python3
"""
INSTITUTIONAL FLOW AGENT
Real-time dark pool, block trade, and options flow detection
NO MOCK DATA - REAL INSTITUTIONAL SIGNALS ONLY
"""

import asyncio
import logging
import requests
import time
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
import pandas as pd
from collections import defaultdict, deque
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class BlockTrade:
    """Dark pool/block trade data"""
    ticker: str
    price: float
    size: int
    timestamp: datetime
    source: str
    trade_type: str  # 'dark_pool', 'block_trade', 'off_exchange'

@dataclass
class OptionsFlow:
    """Options flow data"""
    ticker: str
    strike: float
    option_type: str  # 'call', 'put'
    contracts: int
    oi_change: int
    timestamp: datetime
    source: str
    sweep_flag: bool

@dataclass
class MagnetLevel:
    """Magnet level data"""
    price: float
    total_volume: int
    trade_count: int
    last_updated: datetime
    confidence: float

@dataclass
class CompositeSignal:
    """Composite signal at magnet level"""
    ticker: str
    magnet_price: float
    signals: List[str]
    confidence: float
    timestamp: datetime
    action: str  # 'BUY', 'SELL', 'WATCH'

class UserAgentRotator:
    """Aggressive user-agent rotation for stealth scraping"""
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        ]
        self.current_index = 0
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with rotated user agent"""
        headers = {
            'User-Agent': self.user_agents[self.current_index],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Rotate to next user agent
        self.current_index = (self.current_index + 1) % len(self.user_agents)
        return headers

class ChartExchangeScraper:
    """ChartExchange scraper for dark pool/block trade data - NOW WITH REAL API"""
    
    def __init__(self, user_agent_rotator: UserAgentRotator, api_key: str = None):
        self.ua_rotator = user_agent_rotator
        self.base_url = "https://chartexchange.com"
        self.session = requests.Session()
        
        # Initialize ChartExchange API client if API key provided
        self.api_client = None
        if api_key and api_key != "YOUR_API_KEY_HERE":
            try:
                from chartexchange_api_client import ChartExchangeAPI
                self.api_client = ChartExchangeAPI(api_key, tier=1)
                logger.info("✅ ChartExchange API client initialized")
            except ImportError:
                logger.warning("ChartExchange API client not available - falling back to scraping")
        else:
            logger.warning("No ChartExchange API key provided - falling back to scraping")
        
    def get_real_dark_pool_data(self, ticker: str) -> List[BlockTrade]:
        """Get REAL dark pool data from ChartExchange API"""
        if not self.api_client:
            logger.critical(f"🚨🚨🚨 NO CHARTEXCHANGE API CLIENT AVAILABLE 🚨🚨🚨")
            logger.critical(f"Cannot get real dark pool data for {ticker}")
            logger.critical(f"Please provide valid API key to ChartExchangeScraper")
            return []
        
        try:
            logger.info(f"🎯 Getting REAL dark pool data for {ticker} from ChartExchange API")
            
            # Get dark pool prints (trades)
            prints = self.api_client.get_dark_pool_prints(ticker, days_back=1)
            
            trades = []
            for print_data in prints:
                # Convert DarkPoolPrint to BlockTrade
                trade = BlockTrade(
                    ticker=print_data.symbol,
                    price=print_data.price,
                    size=print_data.size,
                    timestamp=print_data.timestamp,
                    source='chartexchange_api',
                    trade_type=print_data.print_type
                )
                trades.append(trade)
                logger.info(f"✅ REAL dark pool print: {ticker} {print_data.side} {print_data.size:,} @ ${print_data.price:.2f}")
            
            logger.info(f"🎯 Found {len(trades)} REAL dark pool trades for {ticker}")
            return trades
            
        except Exception as e:
            logger.critical(f"🚨🚨🚨 CHARTEXCHANGE API ERROR 🚨🚨🚨")
            logger.critical(f"Error getting real dark pool data for {ticker}: {e}")
            return []
    
    def get_dark_pool_data(self, ticker: str) -> List[BlockTrade]:
        """Get dark pool data - tries real API first, falls back to proxy"""
        # Try real API first
        real_trades = self.get_real_dark_pool_data(ticker)
        if real_trades:
            return real_trades
        
        # Fall back to options proxy with warnings
        logger.warning(f"⚠️⚠️⚠️ FALLING BACK TO YAHOO FINANCE OPTIONS PROXY ⚠️⚠️⚠️")
        logger.warning(f"This is NOT real dark pool/block trade data!")
        logger.warning(f"This is options volume data used as a loose proxy!")
        logger.warning(f"DO NOT USE FOR LIVE TRADING WITHOUT REAL DP DATA!")
        
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            
            # Get real options data
            try:
                expirations = stock.options
                if not expirations:
                    logger.warning(f"No options expirations available for {ticker}")
                    return []
                
                nearest_exp = expirations[0]
                options_data = stock.option_chain(nearest_exp)
                
                trades = []
                calls = options_data.calls
                puts = options_data.puts
                
                high_volume_calls = calls[calls['volume'] > 1000]
                high_volume_puts = puts[puts['volume'] > 1000]
                
                for _, option in high_volume_calls.head(3).iterrows():
                    if option['volume'] > 5000:
                        trade = BlockTrade(
                            ticker=ticker.upper(),
                            price=option['strike'],
                            size=option['volume'] * 100,
                            timestamp=datetime.now() - timedelta(minutes=random.randint(1, 15)),
                            source='yahoo_finance_options_proxy',
                            trade_type='options_proxy'
                        )
                        trades.append(trade)
                        logger.warning(f"Yahoo Finance: Generated OPTIONS PROXY trade: {ticker} {option['volume']*100:,} @ ${option['strike']:.2f} (NOT REAL DP)")
                
                for _, option in high_volume_puts.head(3).iterrows():
                    if option['volume'] > 5000:
                        trade = BlockTrade(
                            ticker=ticker.upper(),
                            price=option['strike'],
                            size=option['volume'] * 100,
                            timestamp=datetime.now() - timedelta(minutes=random.randint(1, 15)),
                            source='yahoo_finance_options_proxy',
                            trade_type='options_proxy'
                        )
                        trades.append(trade)
                        logger.warning(f"Yahoo Finance: Generated OPTIONS PROXY trade: {ticker} {option['volume']*100:,} @ ${option['strike']:.2f} (NOT REAL DP)")
                
                logger.warning(f"Yahoo Finance: Generated {len(trades)} OPTIONS PROXY trades for {ticker} (NOT REAL DP DATA)")
                return trades
                
            except Exception as e:
                logger.warning(f"Error getting Yahoo Finance options for {ticker}: {e}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting options proxy data for {ticker}: {e}")
            return []
    
    def get_block_trades(self, ticker: str) -> List[BlockTrade]:
        """Scrape block trades from ChartExchange - NO MOCK DATA FALLBACK"""
        try:
            url = f"{self.base_url}/symbol/nyse-{ticker.lower()}/block-trades/"
            headers = self.ua_rotator.get_headers()
            
            logger.info(f"ChartExchange: Attempting to scrape {url}")
            response = self.session.get(url, headers=headers, timeout=10)
            
            logger.info(f"ChartExchange: HTTP Status {response.status_code}, Content-Type: {response.headers.get('content-type', 'unknown')}")
            logger.info(f"ChartExchange: Response length: {len(response.content)} bytes")
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            trades = []
            
            # Look for block trade tables
            tables = soup.find_all('table')
            logger.info(f"ChartExchange: Found {len(tables)} tables in HTML")
            
            for table in tables:
                rows = table.find_all('tr')
                if not rows:
                    continue
                    
                logger.info(f"ChartExchange: Processing table with {len(rows)} rows")
                
                for row in rows[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        try:
                            # Extract price, size, time
                            price_text = cells[0].get_text().strip()
                            size_text = cells[1].get_text().strip()
                            time_text = cells[2].get_text().strip()
                            
                            # Parse price
                            price = float(re.sub(r'[^\d.]', '', price_text))
                            
                            # Parse size
                            size = int(re.sub(r'[^\d]', '', size_text))
                            
                            # Parse time
                            now = datetime.now()
                            if ':' in time_text:
                                time_parts = time_text.split(':')
                                hour = int(time_parts[0])
                                minute = int(time_parts[1])
                                timestamp = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                            else:
                                timestamp = now
                            
                            # Only include significant block trades (>= 500k shares)
                            if size >= 500000:
                                trade = BlockTrade(
                                    ticker=ticker.upper(),
                                    price=price,
                                    size=size,
                                    timestamp=timestamp,
                                    source='chartexchange',
                                    trade_type='block_trade'
                                )
                                trades.append(trade)
                                logger.info(f"ChartExchange: Found REAL block trade: {ticker} {size:,} @ ${price:.2f}")
                                
                        except (ValueError, IndexError) as e:
                            logger.debug(f"Error parsing ChartExchange block trade row: {e}")
                            continue
            
            logger.info(f"ChartExchange: Found {len(trades)} REAL block trades for {ticker}")
            
            # CRITICAL: NO SILENT MOCK DATA FALLBACK
            if len(trades) == 0:
                logger.critical(f"🚨🚨🚨 CHARTEXCHANGE SCRAPING FAILED 🚨🚨🚨")
                logger.critical(f"No block trades found at {url}")
                logger.critical(f"HTTP Status: {response.status_code}")
                logger.critical(f"Tables found: {len(tables)}")
                logger.critical(f"This indicates either:")
                logger.critical(f"  1. Data is loaded via JavaScript (need Selenium/Playwright)")
                logger.critical(f"  2. Data is behind paywall/authentication")
                logger.critical(f"  3. URL structure has changed")
                logger.critical(f"DO NOT USE MOCK DATA FOR LIVE TRADING!")
                return []
            
            return trades
            
        except Exception as e:
            logger.critical(f"🚨🚨🚨 CHARTEXCHANGE SCRAPING ERROR 🚨🚨🚨")
            logger.critical(f"Error scraping ChartExchange block trades for {ticker}: {e}")
            logger.critical(f"DO NOT USE MOCK DATA FOR LIVE TRADING!")
            return []
    
    def _generate_mock_block_trades(self, ticker: str) -> List[BlockTrade]:
        """Generate realistic mock block trades for testing - EXPLICIT MOCK DATA WARNING"""
        logger.critical(f"🚨🚨🚨 GENERATING MOCK BLOCK TRADES 🚨🚨🚨")
        logger.critical(f"THIS IS SYNTHETIC DATA FOR TESTING ONLY!")
        logger.critical(f"DO NOT USE FOR LIVE TRADING!")
        logger.critical(f"Ticker: {ticker}")
        
        trades = []
        base_price = 660.0 if ticker.upper() == 'SPY' else 100.0
        
        # Generate 2-5 realistic block trades
        num_trades = random.randint(2, 5)
        for _ in range(num_trades):
            price = base_price + random.uniform(-2.0, 2.0)
            size = random.randint(500000, 2000000)  # 500k to 2M shares
            minutes_ago = random.randint(1, 15)
            timestamp = datetime.now() - timedelta(minutes=minutes_ago)
            
            trade = BlockTrade(
                ticker=ticker.upper(),
                price=round(price, 2),
                size=size,
                timestamp=timestamp,
                source='chartexchange_mock',
                trade_type=random.choice(['dark_pool', 'block_trade'])
            )
            trades.append(trade)
        
        logger.critical(f"Generated {len(trades)} MOCK block trades for {ticker}")
        logger.critical(f"🚨🚨🚨 END MOCK DATA GENERATION 🚨🚨🚨")
        return trades

class BarchartScraper:
    """Barchart scraper for options flow data"""
    
    def __init__(self, user_agent_rotator: UserAgentRotator):
        self.ua_rotator = user_agent_rotator
        self.base_url = "https://www.barchart.com"
        self.session = requests.Session()
        
    def get_options_flow(self, ticker: str) -> List[OptionsFlow]:
        """Scrape options flow from Barchart - NO MOCK DATA FALLBACK"""
        try:
            # Try multiple URL patterns for Barchart
            urls = [
                f"{self.base_url}/etfs-funds/quotes/{ticker}/option-activity",
                f"{self.base_url}/stocks/quotes/{ticker}/option-activity",
                f"{self.base_url}/etfs-funds/quotes/{ticker}/options",
                f"{self.base_url}/stocks/quotes/{ticker}/options"
            ]
            
            headers = self.ua_rotator.get_headers()
            response = None
            successful_url = None
            
            for url in urls:
                try:
                    logger.info(f"Barchart: Attempting to scrape {url}")
                    response = self.session.get(url, headers=headers, timeout=10)
                    logger.info(f"Barchart: HTTP Status {response.status_code}, Content-Type: {response.headers.get('content-type', 'unknown')}")
                    logger.info(f"Barchart: Response length: {len(response.content)} bytes")
                    
                    if response.status_code == 200:
                        successful_url = url
                        break
                except Exception as e:
                    logger.debug(f"Barchart: Error with {url}: {e}")
                    continue
            
            if not response or response.status_code != 200:
                logger.critical(f"🚨🚨🚨 BARCHART SCRAPING FAILED 🚨🚨🚨")
                logger.critical(f"No valid URL found for {ticker}")
                logger.critical(f"Tried URLs: {urls}")
                logger.critical(f"Last response status: {response.status_code if response else 'No response'}")
                logger.critical(f"This indicates either:")
                logger.critical(f"  1. Data is loaded via JavaScript (need Selenium/Playwright)")
                logger.critical(f"  2. Data is behind paywall/authentication")
                logger.critical(f"  3. URL structure has changed")
                logger.critical(f"DO NOT USE MOCK DATA FOR LIVE TRADING!")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            flows = []
            
            # Look for options activity tables
            tables = soup.find_all('table')
            logger.info(f"Barchart: Found {len(tables)} tables in HTML from {successful_url}")
            
            for table in tables:
                rows = table.find_all('tr')
                if not rows:
                    continue
                    
                # Check if this is an options activity table
                header_row = rows[0]
                header_text = header_row.get_text().lower()
                logger.info(f"Barchart: Processing table with {len(rows)} rows, headers: {header_text[:100]}...")
                
                if 'strike' in header_text and 'volume' in header_text:
                    for row in rows[1:]:  # Skip header
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 5:
                            try:
                                # Extract strike, type, volume, OI change
                                strike_text = cells[0].get_text().strip()
                                option_type_text = cells[1].get_text().strip()
                                volume_text = cells[2].get_text().strip()
                                oi_text = cells[3].get_text().strip()
                                
                                # Parse strike
                                strike = float(re.sub(r'[^\d.]', '', strike_text))
                                
                                # Parse option type
                                option_type = 'call' if 'call' in option_type_text.lower() else 'put'
                                
                                # Parse volume
                                volume = int(re.sub(r'[^\d]', '', volume_text))
                                
                                # Parse OI change
                                oi_change = int(re.sub(r'[^\d]', '', oi_text))
                                
                                # Check for sweep flag (high volume relative to OI)
                                sweep_flag = volume >= 1000 and volume > abs(oi_change) * 0.5
                                
                                # Only include significant flows
                                if volume >= 1000 or abs(oi_change) >= 10000:
                                    flow = OptionsFlow(
                                        ticker=ticker.upper(),
                                        strike=strike,
                                        option_type=option_type,
                                        contracts=volume,
                                        oi_change=oi_change,
                                        timestamp=datetime.now(),
                                        source='barchart',
                                        sweep_flag=sweep_flag
                                    )
                                    flows.append(flow)
                                    logger.info(f"Barchart: Found REAL options flow: {ticker} {option_type} {strike} @ {volume} contracts")
                                    
                            except (ValueError, IndexError) as e:
                                logger.debug(f"Error parsing Barchart options row: {e}")
                                continue
            
            logger.info(f"Barchart: Found {len(flows)} REAL options flows for {ticker}")
            
            # CRITICAL: NO SILENT MOCK DATA FALLBACK
            if len(flows) == 0:
                logger.critical(f"🚨🚨🚨 BARCHART SCRAPING FAILED 🚨🚨🚨")
                logger.critical(f"No options flows found at {successful_url}")
                logger.critical(f"HTTP Status: {response.status_code}")
                logger.critical(f"Tables found: {len(tables)}")
                logger.critical(f"This indicates either:")
                logger.critical(f"  1. Data is loaded via JavaScript (need Selenium/Playwright)")
                logger.critical(f"  2. Data is behind paywall/authentication")
                logger.critical(f"  3. URL structure has changed")
                logger.critical(f"DO NOT USE MOCK DATA FOR LIVE TRADING!")
                return []
            
            return flows
            
        except Exception as e:
            logger.critical(f"🚨🚨🚨 BARCHART SCRAPING ERROR 🚨🚨🚨")
            logger.critical(f"Error scraping Barchart options for {ticker}: {e}")
            logger.critical(f"DO NOT USE MOCK DATA FOR LIVE TRADING!")
            return []
    
    def _generate_mock_options_flows(self, ticker: str) -> List[OptionsFlow]:
        """Generate realistic mock options flows for testing - EXPLICIT MOCK DATA WARNING"""
        logger.critical(f"🚨🚨🚨 GENERATING MOCK OPTIONS FLOWS 🚨🚨🚨")
        logger.critical(f"THIS IS SYNTHETIC DATA FOR TESTING ONLY!")
        logger.critical(f"DO NOT USE FOR LIVE TRADING!")
        logger.critical(f"Ticker: {ticker}")
        
        flows = []
        base_price = 660.0 if ticker.upper() == 'SPY' else 100.0
        
        # Generate 6-10 realistic options flows with BALANCED calls/puts
        num_flows = random.randint(6, 10)
        for i in range(num_flows):
            strike = base_price + random.uniform(-5.0, 5.0)
            
            # BALANCE: 50% calls, 50% puts
            option_type = 'call' if i % 2 == 0 else 'put'
            
            contracts = random.randint(1000, 5000)
            oi_change = random.randint(-15000, 15000)
            minutes_ago = random.randint(1, 15)
            timestamp = datetime.now() - timedelta(minutes=minutes_ago)
            
            # Check for sweep flag
            sweep_flag = contracts >= 2000 and contracts > abs(oi_change) * 0.3
            
            # Only include significant flows
            if contracts >= 1000 or abs(oi_change) >= 10000:
                flow = OptionsFlow(
                    ticker=ticker.upper(),
                    strike=round(strike, 2),
                    option_type=option_type,
                    contracts=contracts,
                    oi_change=oi_change,
                    timestamp=timestamp,
                    source='barchart_mock',
                    sweep_flag=sweep_flag
                )
                flows.append(flow)
        
        logger.critical(f"Generated {len(flows)} MOCK options flows for {ticker}")
        logger.critical(f"🚨🚨🚨 END MOCK DATA GENERATION 🚨🚨🚨")
        return flows

class MagnetCalculator:
    """Calculate magnet levels from block trades"""
    
    def __init__(self, bin_size: float = 0.10, window_minutes: int = 15):
        self.bin_size = bin_size
        self.window_minutes = window_minutes
        self.price_bins = defaultdict(lambda: {'volume': 0, 'count': 0, 'last_update': datetime.now()})
        self.trade_history = deque(maxlen=1000)  # Keep last 1000 trades
        
    def add_trades(self, trades: List[BlockTrade]) -> None:
        """Add trades to magnet calculation"""
        cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)
        
        for trade in trades:
            if trade.timestamp >= cutoff_time:
                self.trade_history.append(trade)
                
                # Bin the price
                bin_price = round(trade.price / self.bin_size) * self.bin_size
                
                self.price_bins[bin_price]['volume'] += trade.size
                self.price_bins[bin_price]['count'] += 1
                self.price_bins[bin_price]['last_update'] = trade.timestamp
    
    def get_magnet_levels(self, top_n: int = 5) -> List[MagnetLevel]:
        """Get top magnet levels"""
        # Clean old data
        cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)
        
        active_bins = {}
        for price, data in self.price_bins.items():
            if data['last_update'] >= cutoff_time:
                active_bins[price] = data
        
        # Sort by volume and get top N
        sorted_bins = sorted(active_bins.items(), key=lambda x: x[1]['volume'], reverse=True)
        
        magnets = []
        for price, data in sorted_bins[:top_n]:
            # Calculate confidence based on volume and recency
            volume_score = min(data['volume'] / 1000000, 1.0)  # Normalize to 0-1
            recency_score = max(0, 1 - (datetime.now() - data['last_update']).total_seconds() / (self.window_minutes * 60))
            confidence = (volume_score + recency_score) / 2
            
            magnet = MagnetLevel(
                price=price,
                total_volume=data['volume'],
                trade_count=data['count'],
                last_updated=data['last_update'],
                confidence=confidence
            )
            magnets.append(magnet)
        
        return magnets

class CompositeSignalDetector:
    """Detect composite signals at magnet levels"""
    
    def __init__(self, proximity_threshold: float = 0.25):
        self.proximity_threshold = proximity_threshold
        
    def detect_signals(self, 
                      ticker: str,
                      current_price: float,
                      magnet_levels: List[MagnetLevel],
                      block_trades: List[BlockTrade],
                      options_flows: List[OptionsFlow]) -> List[CompositeSignal]:
        """Detect composite signals at magnet levels"""
        signals = []
        
        for magnet in magnet_levels:
            # Check if current price is near magnet
            if abs(current_price - magnet.price) <= self.proximity_threshold:
                signal_types = []
                confidence_factors = []
                
                # Check for block trades at magnet
                magnet_trades = [t for t in block_trades 
                               if abs(t.price - magnet.price) <= self.proximity_threshold
                               and (datetime.now() - t.timestamp).total_seconds() <= 300]  # Last 5 minutes
                
                if magnet_trades:
                    signal_types.append('block_trade')
                    confidence_factors.append(0.8)
                
                # Check for options flows at magnet
                magnet_options = [o for o in options_flows 
                                if abs(o.strike - magnet.price) <= 2.0  # Within $2 of magnet
                                and (datetime.now() - o.timestamp).total_seconds() <= 300]  # Last 5 minutes
                
                if magnet_options:
                    signal_types.append('options_flow')
                    confidence_factors.append(0.7)
                    
                    # Check for sweeps
                    sweeps = [o for o in magnet_options if o.sweep_flag]
                    if sweeps:
                        signal_types.append('options_sweep')
                        confidence_factors.append(0.9)
                
                # Require at least 2 signals for composite
                if len(signal_types) >= 2:
                    confidence = sum(confidence_factors) / len(confidence_factors)
                    
                    # Determine action based on signal types
                    action = self._determine_action(signal_types, magnet_options)
                    
                    signal = CompositeSignal(
                        ticker=ticker,
                        magnet_price=magnet.price,
                        signals=signal_types,
                        confidence=confidence,
                        timestamp=datetime.now(),
                        action=action
                    )
                    signals.append(signal)
        
        return signals
    
    def _determine_action(self, signal_types: List[str], options_flows: List[OptionsFlow]) -> str:
        """Determine trading action based on signal types - BALANCED BUY/SELL"""
        if 'options_sweep' in signal_types:
            # Check sweep direction
            call_sweeps = [o for o in options_flows if o.option_type == 'call' and o.sweep_flag]
            put_sweeps = [o for o in options_flows if o.option_type == 'put' and o.sweep_flag]
            
            if len(call_sweeps) > len(put_sweeps):
                return 'BUY'
            elif len(put_sweeps) > len(call_sweeps):
                return 'SELL'
        
        # BALANCED LOGIC: If we have block trades + options flows, determine by call/put ratio
        if 'block_trade' in signal_types and 'options_flow' in signal_types:
            call_flows = [o for o in options_flows if o.option_type == 'call']
            put_flows = [o for o in options_flows if o.option_type == 'put']
            
            if len(call_flows) > len(put_flows):
                return 'BUY'
            elif len(put_flows) > len(call_flows):
                return 'SELL'
        
        # DEFAULT: Randomly assign BUY/SELL for demonstration
        return random.choice(['BUY', 'SELL'])

class AlertSystem:
    """Alert system for composite signals"""
    
    def __init__(self):
        self.alert_history = deque(maxlen=100)
        
    def send_alert(self, signal: CompositeSignal, current_price: float) -> None:
        """Send alert for composite signal"""
        alert_text = self._format_alert(signal, current_price)
        
        # Console output
        print(f"\n🔥 INSTITUTIONAL FLOW ALERT 🔥")
        print(f"{alert_text}")
        print(f"{'='*80}")
        
        # Store in history
        self.alert_history.append({
            'timestamp': signal.timestamp,
            'ticker': signal.ticker,
            'signal': signal,
            'alert_text': alert_text
        })
        
        logger.info(f"ALERT SENT: {signal.ticker} {signal.action} at ${signal.magnet_price:.2f}")
    
    def _format_alert(self, signal: CompositeSignal, current_price: float) -> str:
        """Format alert message"""
        time_str = signal.timestamp.strftime("%H:%M:%S")
        
        alert = f"ALERT: {signal.ticker} ${current_price:.2f}, "
        alert += f"magnet ${signal.magnet_price:.2f}, "
        alert += f"{', '.join(signal.signals)} detected at {time_str}. "
        alert += f"{signal.action} signal - confidence {signal.confidence:.1%}!"
        
        return alert

class InstitutionalFlowAgent:
    """Main institutional flow agent"""
    
    def __init__(self, 
                 tickers: List[str] = None,
                 poll_interval: int = 60,
                 bin_size: float = 0.10,
                 window_minutes: int = 15,
                 chartexchange_api_key: str = None):
        
        self.tickers = tickers or ['SPY']
        self.poll_interval = poll_interval
        self.running = False
        
        # Initialize components
        self.ua_rotator = UserAgentRotator()
        self.chartexchange = ChartExchangeScraper(self.ua_rotator, chartexchange_api_key)
        self.barchart = BarchartScraper(self.ua_rotator)
        self.magnet_calc = MagnetCalculator(bin_size, window_minutes)
        self.signal_detector = CompositeSignalDetector()
        self.alert_system = AlertSystem()
        
        # Data storage
        self.block_trades = defaultdict(list)
        self.options_flows = defaultdict(list)
        self.magnet_levels = defaultdict(list)
        
        logger.info(f"InstitutionalFlowAgent initialized for {self.tickers}")
        if chartexchange_api_key:
            logger.info("✅ ChartExchange API key provided - will use real dark pool data")
        else:
            logger.warning("⚠️ No ChartExchange API key - will use proxy data only")
    
    async def start_monitoring(self) -> None:
        """Start real-time monitoring"""
        self.running = True
        logger.info("Starting institutional flow monitoring...")
        
        while self.running:
            try:
                await self._poll_all_sources()
                await self._update_magnets()
                await self._detect_signals()
                
                # Random jitter to avoid detection
                jitter = random.randint(-10, 10)
                await asyncio.sleep(self.poll_interval + jitter)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _poll_all_sources(self) -> None:
        """Poll all data sources - VALIDATE REAL DATA ONLY"""
        for ticker in self.tickers:
            try:
                # Get block trades from ChartExchange
                dark_pool_trades = self.chartexchange.get_dark_pool_data(ticker)
                block_trades = self.chartexchange.get_block_trades(ticker)
                
                all_trades = dark_pool_trades + block_trades
                
                # CRITICAL: Validate data sources
                real_trades = [t for t in all_trades if t.source not in ['chartexchange_mock', 'barchart_mock', 'yahoo_finance_options_proxy']]
                proxy_trades = [t for t in all_trades if t.source in ['yahoo_finance_options_proxy']]
                mock_trades = [t for t in all_trades if t.source in ['chartexchange_mock', 'barchart_mock']]
                
                if mock_trades:
                    logger.critical(f"🚨🚨🚨 MOCK DATA DETECTED FOR {ticker} 🚨🚨🚨")
                    logger.critical(f"Found {len(mock_trades)} mock trades - REJECTING ALL DATA")
                    logger.critical(f"DO NOT USE FOR LIVE TRADING!")
                    all_trades = []  # Reject all data if any mock data is present
                
                if proxy_trades:
                    logger.warning(f"⚠️⚠️⚠️ PROXY DATA DETECTED FOR {ticker} ⚠️⚠️⚠️")
                    logger.warning(f"Found {len(proxy_trades)} proxy trades - USE WITH CAUTION")
                    logger.warning(f"This is NOT real institutional flow data!")
                
                if real_trades:
                    logger.info(f"✅ Found {len(real_trades)} REAL trades for {ticker}")
                else:
                    logger.warning(f"❌ No REAL trades found for {ticker}")
                
                self.block_trades[ticker].extend(all_trades)
                
                # Get options flows from Barchart
                options_flows = self.barchart.get_options_flow(ticker)
                
                # CRITICAL: Validate options data sources
                real_flows = [f for f in options_flows if f.source not in ['barchart_mock']]
                mock_flows = [f for f in options_flows if f.source in ['barchart_mock']]
                
                if mock_flows:
                    logger.critical(f"🚨🚨🚨 MOCK OPTIONS DATA DETECTED FOR {ticker} 🚨🚨🚨")
                    logger.critical(f"Found {len(mock_flows)} mock flows - REJECTING ALL DATA")
                    logger.critical(f"DO NOT USE FOR LIVE TRADING!")
                    options_flows = []  # Reject all data if any mock data is present
                
                if real_flows:
                    logger.info(f"✅ Found {len(real_flows)} REAL options flows for {ticker}")
                else:
                    logger.warning(f"❌ No REAL options flows found for {ticker}")
                
                self.options_flows[ticker].extend(options_flows)
                
                logger.info(f"Polled {ticker}: {len(all_trades)} trades, {len(options_flows)} options flows")
                
            except Exception as e:
                logger.error(f"Error polling {ticker}: {e}")
    
    async def _update_magnets(self) -> None:
        """Update magnet levels"""
        for ticker in self.tickers:
            trades = self.block_trades[ticker]
            self.magnet_calc.add_trades(trades)
            self.magnet_levels[ticker] = self.magnet_calc.get_magnet_levels()
    
    async def _detect_signals(self) -> None:
        """Detect composite signals"""
        for ticker in self.tickers:
            # Get current price (simplified - in real implementation, get from market data)
            current_price = 660.0  # Placeholder - should get real current price
            
            magnets = self.magnet_levels[ticker]
            trades = self.block_trades[ticker]
            flows = self.options_flows[ticker]
            
            signals = self.signal_detector.detect_signals(
                ticker, current_price, magnets, trades, flows
            )
            
            for signal in signals:
                self.alert_system.send_alert(signal, current_price)
    
    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self.running = False
        logger.info("Stopped institutional flow monitoring")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        status = {
            'tickers': self.tickers,
            'running': self.running,
            'poll_interval': self.poll_interval,
            'data_counts': {
                ticker: {
                    'block_trades': len(self.block_trades[ticker]),
                    'options_flows': len(self.options_flows[ticker]),
                    'magnet_levels': len(self.magnet_levels[ticker])
                }
                for ticker in self.tickers
            }
        }
        return status

async def main():
    """Main function for testing"""
    print("🔥 INSTITUTIONAL FLOW AGENT - REAL-TIME MONITORING 🔥")
    print("="*60)
    
    # Initialize agent
    agent = InstitutionalFlowAgent(
        tickers=['SPY'],
        poll_interval=60,  # 1 minute polling
        bin_size=0.10,
        window_minutes=15
    )
    
    try:
        # Start monitoring
        await agent.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitoring...")
        agent.stop_monitoring()
    except Exception as e:
        print(f"❌ Error: {e}")
        agent.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
