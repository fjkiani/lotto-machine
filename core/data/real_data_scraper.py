#!/usr/bin/env python3
"""
REAL DATA SCRAPER - NO MOCK DATA
Uses Playwright/Selenium with stealth techniques to get REAL institutional flow data
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, Page
from fake_useragent import UserAgent
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class RealBlockTrade:
    """Real block trade data from scraping"""
    ticker: str
    price: float
    size: int
    timestamp: datetime
    source: str
    trade_type: str

@dataclass
class RealOptionsFlow:
    """Real options flow data from scraping"""
    ticker: str
    strike: float
    option_type: str
    contracts: int
    oi_change: int
    timestamp: datetime
    source: str
    sweep_flag: bool

class StealthBrowserManager:
    """Manages stealth browser instances for real data scraping"""
    
    def __init__(self):
        self.ua = UserAgent()
        self.browser = None
        self.page = None
        
    async def create_stealth_browser(self) -> Browser:
        """Create stealth browser with randomized fingerprints"""
        playwright = await async_playwright().start()
        
        # Randomize browser fingerprint
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--user-agent=' + self.ua.random
            ]
        )
        
        return browser
    
    async def create_stealth_page(self, browser: Browser) -> Page:
        """Create stealth page with randomized settings"""
        context = await browser.new_context(
            user_agent=self.ua.random,
            viewport={'width': random.randint(1200, 1920), 'height': random.randint(800, 1080)},
            locale='en-US',
            timezone_id='America/New_York'
        )
        
        page = await context.new_page()
        
        # Stealth JavaScript injection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            window.chrome = {
                runtime: {},
            };
        """)
        
        return page
    
    def create_selenium_driver(self) -> webdriver.Chrome:
        """Create undetected Chrome driver"""
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f'--user-agent={self.ua.random}')
        
        driver = uc.Chrome(options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver

class RealChartExchangeScraper:
    """Real ChartExchange scraper with stealth techniques"""
    
    def __init__(self):
        self.browser_manager = StealthBrowserManager()
        self.base_url = "https://chartexchange.com"
        
    async def get_real_dark_pool_data(self, ticker: str) -> List[RealBlockTrade]:
        """Get REAL dark pool data from ChartExchange"""
        try:
            logger.info(f"🔍 SCRAPING REAL DATA: ChartExchange dark pool for {ticker}")
            
            browser = await self.browser_manager.create_stealth_browser()
            page = await self.browser_manager.create_stealth_page(browser)
            
            # Try multiple URL patterns
            urls = [
                f"{self.base_url}/symbol/nyse-{ticker.lower()}/exchange-volume/",
                f"{self.base_url}/symbol/{ticker.lower()}/exchange-volume/",
                f"{self.base_url}/symbol/nyse-{ticker.lower()}/volume/"
            ]
            
            trades = []
            
            for url in urls:
                try:
                    logger.info(f"🌐 Trying URL: {url}")
                    
                    # Navigate with stealth
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                    
                    # Wait for page to load
                    await page.wait_for_timeout(random.randint(2000, 5000))
                    
                    # Check if we hit captcha
                    captcha_text = await page.query_selector("text=Please verify you are not a robot")
                    if captcha_text:
                        logger.warning(f"🚫 CAPTCHA detected at {url}")
                        continue
                    
                    # Look for dark pool/off-exchange data
                    tables = await page.query_selector_all('table')
                    
                    for table in tables:
                        try:
                            # Get table text to check if it's dark pool data
                            table_text = await table.inner_text()
                            
                            if 'off exchange' in table_text.lower() or 'dark pool' in table_text.lower():
                                logger.info(f"✅ Found dark pool table at {url}")
                                
                                # Extract rows
                                rows = await table.query_selector_all('tr')
                                
                                for row in rows[1:]:  # Skip header
                                    cells = await row.query_selector_all('td, th')
                                    
                                    if len(cells) >= 3:
                                        try:
                                            # Extract data
                                            price_text = await cells[0].inner_text()
                                            volume_text = await cells[1].inner_text()
                                            time_text = await cells[2].inner_text()
                                            
                                            # Parse price
                                            price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
                                            
                                            # Parse volume
                                            volume = int(''.join(c for c in volume_text if c.isdigit()))
                                            
                                            # Parse time
                                            now = datetime.now()
                                            if ':' in time_text:
                                                time_parts = time_text.split(':')
                                                hour = int(time_parts[0])
                                                minute = int(time_parts[1])
                                                timestamp = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                                            else:
                                                timestamp = now
                                            
                                            # Only include significant trades
                                            if volume >= 500000:
                                                trade = RealBlockTrade(
                                                    ticker=ticker.upper(),
                                                    price=price,
                                                    size=volume,
                                                    timestamp=timestamp,
                                                    source='chartexchange_real',
                                                    trade_type='dark_pool'
                                                )
                                                trades.append(trade)
                                                logger.info(f"📊 REAL TRADE: {ticker} ${price:.2f} - {volume:,} shares")
                                                
                                        except Exception as e:
                                            logger.debug(f"Error parsing row: {e}")
                                            continue
                                            
                        except Exception as e:
                            logger.debug(f"Error processing table: {e}")
                            continue
                    
                    # If we found data, break
                    if trades:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error with URL {url}: {e}")
                    continue
            
            await browser.close()
            
            logger.info(f"🎯 REAL DATA RESULT: {len(trades)} dark pool trades for {ticker}")
            return trades
            
        except Exception as e:
            logger.error(f"Error scraping ChartExchange for {ticker}: {e}")
            return []

class RealBarchartScraper:
    """Real Barchart scraper with Selenium"""
    
    def __init__(self):
        self.browser_manager = StealthBrowserManager()
        self.base_url = "https://www.barchart.com"
        
    def get_real_options_flow(self, ticker: str) -> List[RealOptionsFlow]:
        """Get REAL options flow from Barchart"""
        try:
            logger.info(f"🔍 SCRAPING REAL DATA: Barchart options for {ticker}")
            
            driver = self.browser_manager.create_selenium_driver()
            flows = []
            
            try:
                # Try multiple URL patterns
                urls = [
                    f"{self.base_url}/etfs-funds/quotes/{ticker}/options",
                    f"{self.base_url}/stocks/quotes/{ticker}/options"
                ]
                
                for url in urls:
                    try:
                        logger.info(f"🌐 Trying URL: {url}")
                        
                        driver.get(url)
                        
                        # Wait for page to load
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.TAG_NAME, "table"))
                        )
                        
                        # Random delay
                        time.sleep(random.randint(2, 5))
                        
                        # Look for options tables
                        tables = driver.find_elements(By.TAG_NAME, "table")
                        
                        for table in tables:
                            try:
                                # Get table text
                                table_text = table.text.lower()
                                
                                if 'strike' in table_text and 'volume' in table_text:
                                    logger.info(f"✅ Found options table at {url}")
                                    
                                    # Extract rows
                                    rows = table.find_elements(By.TAG_NAME, "tr")
                                    
                                    for row in rows[1:]:  # Skip header
                                        cells = row.find_elements(By.TAG_NAME, "td")
                                        
                                        if len(cells) >= 4:
                                            try:
                                                # Extract data
                                                strike_text = cells[0].text
                                                option_type_text = cells[1].text
                                                volume_text = cells[2].text
                                                oi_text = cells[3].text
                                                
                                                # Parse strike
                                                strike = float(''.join(c for c in strike_text if c.isdigit() or c == '.'))
                                                
                                                # Parse option type
                                                option_type = 'call' if 'call' in option_type_text.lower() else 'put'
                                                
                                                # Parse volume
                                                volume = int(''.join(c for c in volume_text if c.isdigit()))
                                                
                                                # Parse OI change
                                                oi_change = int(''.join(c for c in oi_text if c.isdigit() or c == '-'))
                                                
                                                # Check for sweep flag
                                                sweep_flag = volume >= 2000 and volume > abs(oi_change) * 0.3
                                                
                                                # Only include significant flows
                                                if volume >= 1000 or abs(oi_change) >= 10000:
                                                    flow = RealOptionsFlow(
                                                        ticker=ticker.upper(),
                                                        strike=strike,
                                                        option_type=option_type,
                                                        contracts=volume,
                                                        oi_change=oi_change,
                                                        timestamp=datetime.now(),
                                                        source='barchart_real',
                                                        sweep_flag=sweep_flag
                                                    )
                                                    flows.append(flow)
                                                    logger.info(f"📊 REAL OPTIONS: {ticker} ${strike:.2f} {option_type} - {volume:,} contracts")
                                                    
                                            except Exception as e:
                                                logger.debug(f"Error parsing options row: {e}")
                                                continue
                                                
                            except Exception as e:
                                logger.debug(f"Error processing options table: {e}")
                                continue
                        
                        # If we found data, break
                        if flows:
                            break
                            
                    except Exception as e:
                        logger.warning(f"Error with URL {url}: {e}")
                        continue
                        
            finally:
                driver.quit()
            
            logger.info(f"🎯 REAL DATA RESULT: {len(flows)} options flows for {ticker}")
            return flows
            
        except Exception as e:
            logger.error(f"Error scraping Barchart for {ticker}: {e}")
            return []

class RealDataManager:
    """Manages real data scraping with intelligent polling"""
    
    def __init__(self):
        self.chartexchange_scraper = RealChartExchangeScraper()
        self.barchart_scraper = RealBarchartScraper()
        self.last_poll_time = {}
        self.poll_interval = 300  # 5 minutes minimum
        
    async def get_real_institutional_data(self, ticker: str) -> Dict[str, Any]:
        """Get REAL institutional data with intelligent polling"""
        try:
            current_time = datetime.now()
            
            # Check if we should poll (respect rate limits)
            if ticker in self.last_poll_time:
                time_since_last = (current_time - self.last_poll_time[ticker]).total_seconds()
                if time_since_last < self.poll_interval:
                    logger.info(f"⏰ Rate limiting: {ticker} - {self.poll_interval - time_since_last:.0f}s remaining")
                    return {'block_trades': [], 'options_flows': []}
            
            logger.info(f"🚀 POLLING REAL DATA for {ticker}")
            
            # Get real data
            block_trades = await self.chartexchange_scraper.get_real_dark_pool_data(ticker)
            options_flows = self.barchart_scraper.get_real_options_flow(ticker)
            
            # Update last poll time
            self.last_poll_time[ticker] = current_time
            
            return {
                'block_trades': block_trades,
                'options_flows': options_flows,
                'poll_time': current_time,
                'data_source': 'REAL'
            }
            
        except Exception as e:
            logger.error(f"Error getting real data for {ticker}: {e}")
            return {'block_trades': [], 'options_flows': [], 'error': str(e)}

async def test_real_data_scraping():
    """Test real data scraping"""
    print("\n" + "="*100)
    print("🔥 REAL DATA SCRAPING TEST - NO MOCK DATA")
    print("="*100)
    
    manager = RealDataManager()
    
    # Test with SPY
    ticker = 'SPY'
    
    print(f"\n🔍 TESTING REAL DATA SCRAPING FOR {ticker}")
    print("-" * 60)
    
    try:
        data = await manager.get_real_institutional_data(ticker)
        
        print(f"\n📊 REAL DATA RESULTS:")
        print(f"   Block Trades: {len(data.get('block_trades', []))}")
        print(f"   Options Flows: {len(data.get('options_flows', []))}")
        print(f"   Data Source: {data.get('data_source', 'UNKNOWN')}")
        
        if data.get('block_trades'):
            print(f"\n🔥 REAL BLOCK TRADES:")
            for trade in data['block_trades'][:3]:  # Show first 3
                print(f"   {trade.ticker} - ${trade.price:.2f} - {trade.size:,} shares - {trade.trade_type}")
        
        if data.get('options_flows'):
            print(f"\n🔥 REAL OPTIONS FLOWS:")
            for flow in data['options_flows'][:3]:  # Show first 3
                print(f"   {flow.ticker} - ${flow.strike:.2f} {flow.option_type} - {flow.contracts:,} contracts")
        
        if data.get('error'):
            print(f"\n❌ ERROR: {data['error']}")
        
        print(f"\n✅ REAL DATA SCRAPING TEST COMPLETE!")
        print(f"🎯 NO MOCK DATA - ONLY REAL INSTITUTIONAL FLOW!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    print("🔥 REAL DATA SCRAPING TEST")
    print("=" * 50)
    
    asyncio.run(test_real_data_scraping())

if __name__ == "__main__":
    main()

