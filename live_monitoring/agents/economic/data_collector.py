"""
Economic Intelligence - Data Collector

Fetches REAL historical economic data from:
1. FRED API (Federal Reserve Economic Data) - FREE!
2. Perplexity (for Fed Watch history)
3. yfinance (for market reactions)
4. ChartExchange (for Dark Pool context)

This is where we get the TRAINING DATA.
"""

import os
import sys
import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import yfinance as yf

from .models import EconomicRelease, EventType, DarkPoolContext

logger = logging.getLogger(__name__)


# FRED Series IDs for economic indicators
FRED_SERIES = {
    EventType.NFP: "PAYEMS",  # Total Nonfarm Payrolls
    EventType.UNEMPLOYMENT: "UNRATE",  # Unemployment Rate
    EventType.CPI: "CPIAUCSL",  # Consumer Price Index
    EventType.CORE_CPI: "CPILFESL",  # Core CPI (less food & energy)
    EventType.PPI: "PPIACO",  # Producer Price Index
    EventType.PCE: "PCE",  # Personal Consumption Expenditures
    EventType.CORE_PCE: "PCEPILFE",  # Core PCE
    EventType.GDP: "GDP",  # Gross Domestic Product
    EventType.RETAIL_SALES: "RSAFS",  # Retail Sales
    EventType.JOBLESS_CLAIMS: "ICSA",  # Initial Jobless Claims
    EventType.HOUSING_STARTS: "HOUST",  # Housing Starts
    EventType.ISM_MANUFACTURING: "MANEMP",  # Manufacturing Employment
}


class EconomicDataCollector:
    """
    Collects historical economic data for training.
    
    Sources:
    - FRED API: Economic indicators with history
    - Perplexity: Fed Watch history, market context
    - yfinance: Market reactions (SPY, TLT, VIX)
    - ChartExchange: Dark Pool data
    """
    
    def __init__(self, fred_api_key: str = None, perplexity_api_key: str = None,
                 chartexchange_api_key: str = None):
        """
        Initialize collector with API keys.
        
        Args:
            fred_api_key: FRED API key (free from https://fred.stlouisfed.org/docs/api/api_key.html)
            perplexity_api_key: Perplexity API key
            chartexchange_api_key: ChartExchange API key
        """
        self.fred_key = fred_api_key or os.getenv('FRED_API_KEY')
        self.perplexity_key = perplexity_api_key or os.getenv('PERPLEXITY_API_KEY')
        self.chartexchange_key = chartexchange_api_key or os.getenv('CHARTEXCHANGE_API_KEY')
        
        logger.info("📊 EconomicDataCollector initialized")
        logger.info(f"   FRED API: {'✅' if self.fred_key else '❌ (get free key at fred.stlouisfed.org)'}")
        logger.info(f"   Perplexity: {'✅' if self.perplexity_key else '❌'}")
        logger.info(f"   ChartExchange: {'✅' if self.chartexchange_key else '❌'}")
    
    # ========================================================================
    # FRED API - Economic Data
    # ========================================================================
    
    def fetch_fred_series(self, series_id: str, start_date: str, end_date: str = None) -> List[Dict]:
        """
        Fetch data from FRED API.
        
        Args:
            series_id: FRED series ID (e.g., "PAYEMS" for NFP)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (defaults to today)
        
        Returns:
            List of {date, value} dicts
        """
        if not self.fred_key:
            logger.warning("⚠️ FRED API key not set - using fallback data")
            return []
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        url = f"https://api.stlouisfed.org/fred/series/observations"
        params = {
            'series_id': series_id,
            'api_key': self.fred_key,
            'file_type': 'json',
            'observation_start': start_date,
            'observation_end': end_date
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                observations = data.get('observations', [])
                
                result = []
                for obs in observations:
                    if obs.get('value') and obs['value'] != '.':
                        result.append({
                            'date': obs['date'],
                            'value': float(obs['value'])
                        })
                
                logger.info(f"✅ Fetched {len(result)} observations for {series_id}")
                return result
            else:
                logger.error(f"❌ FRED API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ FRED fetch error: {e}")
            return []
    
    def fetch_economic_releases(self, event_type: EventType, 
                                 start_date: str = "2020-01-01",
                                 end_date: str = None) -> List[EconomicRelease]:
        """
        Fetch historical releases for an event type.
        
        Args:
            event_type: Type of economic event
            start_date: Start date
            end_date: End date
        
        Returns:
            List of EconomicRelease objects
        """
        series_id = FRED_SERIES.get(event_type)
        if not series_id:
            logger.warning(f"No FRED series for {event_type}")
            return []
        
        # Fetch the data
        observations = self.fetch_fred_series(series_id, start_date, end_date)
        
        if not observations:
            return []
        
        releases = []
        
        for i, obs in enumerate(observations):
            # Calculate surprise (vs previous value as proxy for forecast)
            previous = observations[i-1]['value'] if i > 0 else obs['value']
            actual = obs['value']
            
            # For change-based indicators (NFP), calculate month-over-month
            if event_type in [EventType.NFP]:
                change = actual - previous
                forecast_approx = change  # Rough approximation
                surprise_pct = 0
            else:
                forecast_approx = previous  # Use previous as proxy
                surprise_pct = ((actual - forecast_approx) / forecast_approx * 100) if forecast_approx != 0 else 0
            
            release = EconomicRelease(
                date=obs['date'],
                time="08:30",  # Most releases at 8:30 AM
                event_type=event_type,
                event_name=event_type.value.replace('_', ' ').title(),
                actual=actual,
                forecast=forecast_approx,
                previous=previous,
                surprise_pct=surprise_pct,
                surprise_sigma=surprise_pct / 10 if surprise_pct != 0 else 0,  # Rough σ estimate
                source="FRED"
            )
            releases.append(release)
        
        logger.info(f"📊 Created {len(releases)} releases for {event_type.value}")
        return releases
    
    # ========================================================================
    # MARKET REACTIONS - yfinance
    # ========================================================================
    
    def fetch_market_reaction(self, date: str, time: str = "08:30") -> Dict:
        """
        Fetch market reaction (SPY, TLT, VIX) after an economic release.
        
        Args:
            date: Release date (YYYY-MM-DD)
            time: Release time (HH:MM)
        
        Returns:
            Dict with spy_change_1hr, tlt_change_1hr, vix_change_1hr
        """
        result = {
            'spy_change_1hr': 0.0,
            'spy_change_24hr': 0.0,
            'tlt_change_1hr': 0.0,
            'vix_change_1hr': 0.0,
            'volume_spike': 1.0
        }
        
        try:
            # Parse date
            release_date = datetime.strptime(date, '%Y-%m-%d')
            next_day = release_date + timedelta(days=1)
            
            # Fetch daily data (more reliable than intraday)
            spy = yf.download('SPY', start=date, end=next_day.strftime('%Y-%m-%d'), progress=False)
            tlt = yf.download('TLT', start=date, end=next_day.strftime('%Y-%m-%d'), progress=False)
            vix = yf.download('^VIX', start=date, end=next_day.strftime('%Y-%m-%d'), progress=False)
            
            if not spy.empty and len(spy) > 0:
                # Calculate intraday move (open to close as proxy for 1hr)
                open_price = float(spy['Open'].iloc[0])
                close_price = float(spy['Close'].iloc[0])
                result['spy_change_1hr'] = float((close_price - open_price) / open_price * 100) if open_price > 0 else 0.0
                
                # Volume spike
                avg_vol = float(spy['Volume'].mean()) if len(spy) > 0 else 1.0
                vol = float(spy['Volume'].iloc[0])
                result['volume_spike'] = float(vol / avg_vol) if avg_vol > 0 else 1.0
            
            if not tlt.empty and len(tlt) > 0:
                open_price = float(tlt['Open'].iloc[0])
                close_price = float(tlt['Close'].iloc[0])
                result['tlt_change_1hr'] = float((close_price - open_price) / open_price * 100) if open_price > 0 else 0.0
            
            if not vix.empty and len(vix) > 0:
                open_price = float(vix['Open'].iloc[0])
                close_price = float(vix['Close'].iloc[0])
                result['vix_change_1hr'] = float(close_price - open_price)  # VIX in points
            
        except Exception as e:
            logger.debug(f"Market reaction fetch error for {date}: {e}")
        
        return result
    
    def enrich_with_market_data(self, releases: List[EconomicRelease]) -> List[EconomicRelease]:
        """
        Enrich releases with market reaction data.
        
        This is expensive (one API call per release) so use sparingly!
        """
        enriched = []
        total = len(releases)
        
        for i, release in enumerate(releases):
            if (i + 1) % 10 == 0:
                logger.info(f"   Enriching market data: {i+1}/{total}")
            
            market = self.fetch_market_reaction(release.date, release.time)
            
            release.spy_change_1hr = market['spy_change_1hr']
            release.spy_change_24hr = market.get('spy_change_24hr', 0)
            release.tlt_change_1hr = market['tlt_change_1hr']
            release.vix_change_1hr = market['vix_change_1hr']
            release.volume_spike = market['volume_spike']
            
            enriched.append(release)
        
        return enriched
    
    # ========================================================================
    # DARK POOL CONTEXT - ChartExchange
    # ========================================================================
    
    def fetch_dp_context(self, symbol: str, date: str) -> Optional[DarkPoolContext]:
        """
        Fetch Dark Pool context for a date.
        
        Args:
            symbol: Stock symbol (e.g., "SPY")
            date: Date (YYYY-MM-DD)
        
        Returns:
            DarkPoolContext or None
        """
        if not self.chartexchange_key:
            return None
        
        try:
            # Use our existing ChartExchange client
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            
            client = UltimateChartExchangeClient(self.chartexchange_key)
            
            # Get DP levels
            levels = client.get_dark_pool_levels(symbol, date)
            
            # Get DP prints
            prints = client.get_dark_pool_prints(symbol, date)
            
            if not levels:
                return None
            
            # Calculate metrics
            total_dp_vol = sum(l.get('total_vol', 0) for l in levels)
            
            # Buy/sell ratio from prints
            buy_vol = sum(p.get('volume', 0) for p in (prints or []) if p.get('side') == 'buy')
            sell_vol = sum(p.get('volume', 0) for p in (prints or []) if p.get('side') == 'sell')
            total_print_vol = buy_vol + sell_vol
            
            return DarkPoolContext(
                symbol=symbol,
                timestamp=date,
                total_dp_volume=total_dp_vol,
                buy_volume=buy_vol,
                sell_volume=sell_vol,
                buy_ratio=buy_vol / total_print_vol if total_print_vol > 0 else 0.5,
                large_prints_count=len([p for p in (prints or []) if p.get('value', 0) > 1000000]),
                avg_print_size=total_print_vol / len(prints) if prints else 0
            )
            
        except Exception as e:
            logger.debug(f"DP context fetch error for {date}: {e}")
            return None
    
    def enrich_with_dp_data(self, releases: List[EconomicRelease], 
                            symbol: str = "SPY") -> List[EconomicRelease]:
        """
        Enrich releases with Dark Pool context.
        """
        enriched = []
        
        for release in releases:
            dp_context = self.fetch_dp_context(symbol, release.date)
            
            if dp_context:
                release.dp_activity_before = dp_context.dp_pct_of_total
                release.dp_buy_ratio_before = dp_context.buy_ratio
            
            enriched.append(release)
        
        return enriched
    
    # ========================================================================
    # FED WATCH HISTORY - Perplexity
    # ========================================================================
    
    def fetch_fed_watch_history(self, date: str) -> Dict:
        """
        Fetch Fed Watch probabilities for a specific date using Perplexity.
        
        Args:
            date: Date to query (YYYY-MM-DD)
        
        Returns:
            Dict with cut_prob, hold_prob
        """
        if not self.perplexity_key:
            return {'cut_prob': 50, 'hold_prob': 50}
        
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            from enrichment.apis.perplexity_search import PerplexitySearchClient
            
            client = PerplexitySearchClient(api_key=self.perplexity_key)
            
            query = f"""
            What were the CME FedWatch Tool probabilities on {date}?
            Give the probability of:
            1. Rate CUT
            2. Rate HOLD (no change)
            Format: CUT: XX%, HOLD: XX%
            """
            
            result = client.search(query)
            
            if result and 'answer' in result:
                import re
                answer = result['answer'].lower()
                
                cut_match = re.search(r'cut[:\s]+(\d+)', answer)
                hold_match = re.search(r'hold[:\s]+(\d+)', answer)
                
                return {
                    'cut_prob': float(cut_match.group(1)) if cut_match else 50,
                    'hold_prob': float(hold_match.group(1)) if hold_match else 50
                }
            
        except Exception as e:
            logger.debug(f"Fed Watch history error for {date}: {e}")
        
        return {'cut_prob': 50, 'hold_prob': 50}
    
    # ========================================================================
    # COMPREHENSIVE DATA COLLECTION
    # ========================================================================
    
    def collect_comprehensive_data(self, event_types: List[EventType] = None,
                                    start_date: str = "2023-01-01",
                                    include_market: bool = True,
                                    include_dp: bool = False) -> List[EconomicRelease]:
        """
        Collect comprehensive training data.
        
        Args:
            event_types: Event types to collect (defaults to all)
            start_date: Start date for historical data
            include_market: Enrich with market reaction data
            include_dp: Enrich with Dark Pool data (slower)
        
        Returns:
            List of fully enriched EconomicRelease objects
        """
        if event_types is None:
            event_types = [
                EventType.NFP,
                EventType.UNEMPLOYMENT,
                EventType.CPI,
                EventType.CORE_CPI,
                EventType.PPI,
                EventType.PCE,
                EventType.RETAIL_SALES,
                EventType.JOBLESS_CLAIMS
            ]
        
        logger.info(f"📊 Collecting data for {len(event_types)} event types since {start_date}")
        
        all_releases = []
        
        for event_type in event_types:
            logger.info(f"   Fetching {event_type.value}...")
            releases = self.fetch_economic_releases(event_type, start_date)
            all_releases.extend(releases)
        
        logger.info(f"📊 Total releases fetched: {len(all_releases)}")
        
        # Enrich with market data (expensive)
        if include_market and all_releases:
            logger.info("📈 Enriching with market reaction data...")
            all_releases = self.enrich_with_market_data(all_releases)
        
        # Enrich with DP data (very expensive)
        if include_dp and all_releases:
            logger.info("🔒 Enriching with Dark Pool data...")
            all_releases = self.enrich_with_dp_data(all_releases)
        
        logger.info(f"✅ Collection complete: {len(all_releases)} enriched releases")
        return all_releases


# ========================================================================================
# DEMO
# ========================================================================================

def _demo():
    """Demo the data collector."""
    print("=" * 70)
    print("📊 ECONOMIC DATA COLLECTOR DEMO")
    print("=" * 70)
    
    collector = EconomicDataCollector()
    
    # Test FRED fetch
    print("\n📊 Fetching NFP data from FRED...")
    releases = collector.fetch_economic_releases(EventType.NFP, start_date="2024-01-01")
    
    print(f"\n   Found {len(releases)} releases")
    for r in releases[:5]:
        print(f"   {r.date}: {r.actual} (prev: {r.previous})")
    
    # Test market data
    print("\n📈 Fetching market reaction for 2024-12-06...")
    market = collector.fetch_market_reaction("2024-12-06")
    print(f"   SPY: {market['spy_change_1hr']:+.2f}%")
    print(f"   TLT: {market['tlt_change_1hr']:+.2f}%")
    print(f"   VIX: {market['vix_change_1hr']:+.2f}")
    
    print("\n✅ Demo complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    _demo()

