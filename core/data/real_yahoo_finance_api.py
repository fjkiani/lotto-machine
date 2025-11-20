#!/usr/bin/env python3
"""
REAL YAHOO FINANCE API INTEGRATION
Uses the real RapidAPI key for Yahoo Finance data
"""

import asyncio
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class RealOptionsFlow:
    """Real options flow data from Yahoo Finance API"""
    ticker: str
    strike: float
    option_type: str
    contracts: int
    oi_change: int
    timestamp: datetime
    source: str
    sweep_flag: bool
    bid: float
    ask: float
    last_price: float

@dataclass
class RealMarketQuote:
    """Real market quote from Yahoo Finance API"""
    ticker: str
    price: float
    volume: int
    change: float
    change_percent: float
    timestamp: datetime
    source: str

class RealYahooFinanceAPI:
    """Real Yahoo Finance API client using RapidAPI"""
    
    def __init__(self):
        self.api_key = "3ec17c8a5cmsh14c013e8aa23a1cp147fb9jsn3e2385628a9b"
        self.base_url = "https://apidojo-yahoo-finance-v1.p.rapidapi.com"
        self.headers = {
            'x-rapidapi-host': 'apidojo-yahoo-finance-v1.p.rapidapi.com',
            'x-rapidapi-key': self.api_key
        }
        self.last_request_time = {}
        self.min_interval = 1  # 1 second between requests
        
    def _can_request(self, endpoint: str) -> bool:
        """Check if we can make a request"""
        current_time = time.time()
        
        if endpoint not in self.last_request_time:
            return True
        
        time_since_last = current_time - self.last_request_time[endpoint]
        
        if time_since_last >= self.min_interval:
            return True
        
        logger.info(f"⏰ Rate limiting {endpoint}: {self.min_interval - time_since_last:.1f}s remaining")
        return False
    
    def _record_request(self, endpoint: str):
        """Record a request"""
        self.last_request_time[endpoint] = time.time()
    
    def get_market_quotes(self, symbols: List[str]) -> List[RealMarketQuote]:
        """Get real market quotes using market/v2/get-quotes endpoint"""
        try:
            if not self._can_request('market_quotes'):
                return []
            
            logger.info(f"🔍 GETTING REAL MARKET QUOTES: {symbols}")
            
            # Convert symbols to comma-separated string
            symbols_str = ','.join(symbols)
            
            url = f"{self.base_url}/market/v2/get-quotes"
            params = {
                'symbols': symbols_str,
                'region': 'US'
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            self._record_request('market_quotes')
            
            data = response.json()
            quotes = []
            
            if 'quoteResponse' in data and 'result' in data['quoteResponse']:
                for quote_data in data['quoteResponse']['result']:
                    try:
                        quote = RealMarketQuote(
                            ticker=quote_data.get('symbol', ''),
                            price=quote_data.get('regularMarketPrice', 0),
                            volume=quote_data.get('regularMarketVolume', 0),
                            change=quote_data.get('regularMarketChange', 0),
                            change_percent=quote_data.get('regularMarketChangePercent', 0),
                            timestamp=datetime.now(),
                            source='yahoo_finance_api'
                        )
                        quotes.append(quote)
                        logger.info(f"📊 REAL QUOTE: {quote.ticker} - ${quote.price:.2f} - Volume: {quote.volume:,}")
                        
                    except Exception as e:
                        logger.warning(f"Error parsing quote: {e}")
                        continue
            
            logger.info(f"🎯 REAL MARKET QUOTES: {len(quotes)} quotes retrieved")
            return quotes
            
        except Exception as e:
            logger.error(f"Error getting market quotes: {e}")
            return []
    
    def get_options_data(self, symbol: str) -> List[RealOptionsFlow]:
        """Get real options data using stock/v3/get-options endpoint"""
        try:
            if not self._can_request('options'):
                return []
            
            logger.info(f"🔍 GETTING REAL OPTIONS DATA: {symbol}")
            
            url = f"{self.base_url}/stock/v3/get-options"
            params = {
                'symbol': symbol,
                'region': 'US'
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            
            self._record_request('options')
            
            data = response.json()
            flows = []
            
            if 'optionChain' in data and 'result' in data['optionChain']:
                option_chain = data['optionChain']['result'][0]
                logger.info(f"📊 OPTION CHAIN KEYS: {list(option_chain.keys())}")
                
                # Process straddles (calls and puts are in straddles)
                if 'options' in option_chain:
                    options = option_chain['options']
                    logger.info(f"📊 OPTIONS TYPE: {type(options)}, LENGTH: {len(options)}")
                    if options and 'straddles' in options[0]:
                        straddles = options[0]['straddles']
                        logger.info(f"📊 STRADDLES COUNT: {len(straddles)}")
                    else:
                        logger.warning("No straddles found in options")
                        return flows
                    
                    for i, straddle in enumerate(straddles):
                        try:
                            # Process call
                            if 'call' in straddle:
                                call_data = straddle['call']
                                volume = call_data.get('volume', 0)
                                if i < 5:  # Debug first 5
                                    logger.info(f"📊 CALL {i}: Volume {volume}")
                                if volume > 100:  # Lower threshold for after hours
                                    flow = RealOptionsFlow(
                                        ticker=symbol.upper(),
                                        strike=call_data.get('strike', 0),
                                        option_type='call',
                                        contracts=volume,
                                        oi_change=call_data.get('openInterest', 0),
                                        timestamp=datetime.now(),
                                        source='yahoo_finance_api',
                                        sweep_flag=volume > 1000,
                                        bid=call_data.get('bid', 0),
                                        ask=call_data.get('ask', 0),
                                        last_price=call_data.get('lastPrice', 0)
                                    )
                                    flows.append(flow)
                                    logger.info(f"📊 REAL CALL: {symbol} ${flow.strike:.2f} - {flow.contracts:,} contracts")
                            
                            # Process put
                            if 'put' in straddle:
                                put_data = straddle['put']
                                volume = put_data.get('volume', 0)
                                if volume > 100:  # Lower threshold for after hours
                                    flow = RealOptionsFlow(
                                        ticker=symbol.upper(),
                                        strike=put_data.get('strike', 0),
                                        option_type='put',
                                        contracts=volume,
                                        oi_change=put_data.get('openInterest', 0),
                                        timestamp=datetime.now(),
                                        source='yahoo_finance_api',
                                        sweep_flag=volume > 1000,
                                        bid=put_data.get('bid', 0),
                                        ask=put_data.get('ask', 0),
                                        last_price=put_data.get('lastPrice', 0)
                                    )
                                    flows.append(flow)
                                    logger.info(f"📊 REAL PUT: {symbol} ${flow.strike:.2f} - {flow.contracts:,} contracts")
                                
                        except Exception as e:
                            logger.warning(f"Error parsing straddle: {e}")
                            continue
            
            logger.info(f"🎯 REAL OPTIONS DATA: {len(flows)} options flows for {symbol}")
            return flows
            
        except Exception as e:
            logger.error(f"Error getting options data for {symbol}: {e}")
            return []
    
    def get_market_movers(self) -> Dict[str, List[RealMarketQuote]]:
        """Get market movers using market/v2/get-movers endpoint"""
        try:
            if not self._can_request('movers'):
                return {}
            
            logger.info(f"🔍 GETTING REAL MARKET MOVERS")
            
            url = f"{self.base_url}/market/v2/get-movers"
            params = {
                'region': 'US'
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            self._record_request('movers')
            
            data = response.json()
            movers = {}
            
            if 'finance' in data and 'result' in data['finance']:
                result = data['finance']['result']
                
                # Process gainers
                if 'gainers' in result:
                    gainers = []
                    for gainer_data in result['gainers']:
                        try:
                            quote = RealMarketQuote(
                                ticker=gainer_data.get('symbol', ''),
                                price=gainer_data.get('regularMarketPrice', 0),
                                volume=gainer_data.get('regularMarketVolume', 0),
                                change=gainer_data.get('regularMarketChange', 0),
                                change_percent=gainer_data.get('regularMarketChangePercent', 0),
                                timestamp=datetime.now(),
                                source='yahoo_finance_api'
                            )
                            gainers.append(quote)
                            
                        except Exception as e:
                            logger.warning(f"Error parsing gainer: {e}")
                            continue
                    
                    movers['gainers'] = gainers
                    logger.info(f"📈 REAL GAINERS: {len(gainers)} stocks")
                
                # Process losers
                if 'losers' in result:
                    losers = []
                    for loser_data in result['losers']:
                        try:
                            quote = RealMarketQuote(
                                ticker=loser_data.get('symbol', ''),
                                price=loser_data.get('regularMarketPrice', 0),
                                volume=loser_data.get('regularMarketVolume', 0),
                                change=loser_data.get('regularMarketChange', 0),
                                change_percent=loser_data.get('regularMarketChangePercent', 0),
                                timestamp=datetime.now(),
                                source='yahoo_finance_api'
                            )
                            losers.append(quote)
                            
                        except Exception as e:
                            logger.warning(f"Error parsing loser: {e}")
                            continue
                    
                    movers['losers'] = losers
                    logger.info(f"📉 REAL LOSERS: {len(losers)} stocks")
            
            logger.info(f"🎯 REAL MARKET MOVERS: {len(movers)} categories")
            return movers
            
        except Exception as e:
            logger.error(f"Error getting market movers: {e}")
            return {}

class RealDataManagerWithAPI:
    """Real data manager using the actual Yahoo Finance API"""
    
    def __init__(self):
        self.yahoo_api = RealYahooFinanceAPI()
        
    async def get_comprehensive_data(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive real data for a ticker"""
        try:
            logger.info(f"🚀 GETTING COMPREHENSIVE REAL DATA FOR {ticker}")
            
            # Get market quotes
            quotes = self.yahoo_api.get_market_quotes([ticker])
            current_price = quotes[0].price if quotes else 0
            
            # Get options data
            options_flows = self.yahoo_api.get_options_data(ticker)
            
            # Get market movers for context
            movers = self.yahoo_api.get_market_movers()
            
            return {
                'ticker': ticker,
                'current_price': current_price,
                'quotes': quotes,
                'options_flows': options_flows,
                'market_movers': movers,
                'data_source': 'YAHOO_FINANCE_API_REAL',
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error getting comprehensive data for {ticker}: {e}")
            return {'error': str(e)}

async def test_real_yahoo_finance_api():
    """Test the real Yahoo Finance API"""
    print("\n" + "="*100)
    print("🔥 REAL YAHOO FINANCE API TEST - USING REAL API KEY")
    print("="*100)
    
    manager = RealDataManagerWithAPI()
    
    # Test with SPY
    ticker = 'SPY'
    
    print(f"\n🔍 TESTING REAL YAHOO FINANCE API FOR {ticker}")
    print("-" * 60)
    
    try:
        data = await manager.get_comprehensive_data(ticker)
        
        if data.get('error'):
            print(f"\n❌ ERROR: {data['error']}")
            return
        
        print(f"\n📊 REAL YAHOO FINANCE API RESULTS:")
        print(f"   Ticker: {data['ticker']}")
        print(f"   Current Price: ${data['current_price']:.2f}")
        print(f"   Data Source: {data['data_source']}")
        print(f"   Quotes: {len(data['quotes'])}")
        print(f"   Options Flows: {len(data['options_flows'])}")
        print(f"   Market Movers: {len(data['market_movers'])}")
        
        if data['quotes']:
            print(f"\n🔥 REAL MARKET QUOTES:")
            for quote in data['quotes'][:3]:
                print(f"   {quote.ticker} - ${quote.price:.2f} - Volume: {quote.volume:,} - Change: {quote.change_percent:.2f}%")
        
        if data['options_flows']:
            print(f"\n🔥 REAL OPTIONS FLOWS:")
            for flow in data['options_flows'][:5]:
                print(f"   {flow.ticker} - ${flow.strike:.2f} {flow.option_type} - {flow.contracts:,} contracts - Sweep: {flow.sweep_flag}")
        
        if data['market_movers']:
            print(f"\n🔥 REAL MARKET MOVERS:")
            for category, movers in data['market_movers'].items():
                print(f"   {category.upper()}: {len(movers)} stocks")
                for mover in movers[:2]:
                    print(f"     {mover.ticker} - ${mover.price:.2f} - Change: {mover.change_percent:.2f}%")
        
        print(f"\n✅ REAL YAHOO FINANCE API TEST COMPLETE!")
        print(f"🎯 USING REAL API KEY - NO MOCK DATA!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    print("🔥 REAL YAHOO FINANCE API TEST")
    print("=" * 50)
    
    asyncio.run(test_real_yahoo_finance_api())

if __name__ == "__main__":
    main()
