"""
Intelligence Aggregator
Orchestrates parallel data gathering from multiple public sources
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import json

from .sources import (
    NewsSourceScraper,
    BlockTradeScraper,
    DarkPoolScraper,
    OptionActivityScraper,
    SocialSentimentScraper,
    TechnicalDataScraper
)
from .correlator import IntelligenceCorrelator
from .synthesizer import IntelligenceSynthesizer

logger = logging.getLogger(__name__)

class IntelligenceAggregator:
    """
    Multi-source intelligence gathering engine
    
    Gathers data from:
    - News sites (CNBC, Yahoo Finance, Reuters, Bloomberg)
    - Block trade feeds (public dashboards, summaries)
    - Dark pool data (commentary, ratios, reports)
    - Options activity (flow reports, unusual activity)
    - Social sentiment (Reddit, TradingView, Twitter)
    - Technical dashboards (public indicators, breakdowns)
    
    Then cross-references, pattern-matches, and synthesizes insights
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Initialize scrapers
        self.news_scraper = NewsSourceScraper(config.get('news', {}))
        self.block_trade_scraper = BlockTradeScraper(config.get('block_trades', {}))
        self.dark_pool_scraper = DarkPoolScraper(config.get('dark_pool', {}))
        self.options_scraper = OptionActivityScraper(config.get('options', {}))
        self.social_scraper = SocialSentimentScraper(config.get('social', {}))
        self.technical_scraper = TechnicalDataScraper(config.get('technical', {}))
        
        # Initialize correlator and synthesizer
        self.correlator = IntelligenceCorrelator(config.get('correlation', {}))
        self.synthesizer = IntelligenceSynthesizer(config.get('synthesis', {}))
        
        # Data cache
        self.intelligence_cache = defaultdict(list)
        self.last_update = {}
        
        logger.info("IntelligenceAggregator initialized - ready for parallel research at machine speed")
    
    async def gather_market_intelligence(self, ticker: Optional[str] = None, 
                                         scope: str = 'full') -> Dict[str, Any]:
        """
        Gather comprehensive market intelligence
        
        Args:
            ticker: Specific ticker (None for market-wide)
            scope: 'full', 'quick', 'targeted'
        
        Returns:
            Synthesized intelligence report
        """
        try:
            start_time = datetime.now()
            logger.info(f"Starting {scope} intelligence gathering for {ticker or 'MARKET'}")
            
            # Parallel data gathering
            tasks = []
            
            # News intelligence
            tasks.append(self._gather_news_intelligence(ticker))
            
            # Block trade intelligence
            tasks.append(self._gather_block_trade_intelligence(ticker))
            
            # Dark pool intelligence
            tasks.append(self._gather_dark_pool_intelligence(ticker))
            
            # Options intelligence
            tasks.append(self._gather_options_intelligence(ticker))
            
            # Social intelligence
            tasks.append(self._gather_social_intelligence(ticker))
            
            # Technical intelligence
            tasks.append(self._gather_technical_intelligence(ticker))
            
            # Execute all in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Organize results
            intelligence_data = {
                'news': results[0] if not isinstance(results[0], Exception) else {},
                'block_trades': results[1] if not isinstance(results[1], Exception) else {},
                'dark_pool': results[2] if not isinstance(results[2], Exception) else {},
                'options': results[3] if not isinstance(results[3], Exception) else {},
                'social': results[4] if not isinstance(results[4], Exception) else {},
                'technical': results[5] if not isinstance(results[5], Exception) else {},
                'timestamp': datetime.now(),
                'ticker': ticker,
                'scope': scope
            }
            
            # Cross-reference and correlate
            correlations = await self.correlator.correlate_intelligence(intelligence_data)
            intelligence_data['correlations'] = correlations
            
            # Synthesize insights
            synthesis = await self.synthesizer.synthesize_intelligence(intelligence_data)
            intelligence_data['synthesis'] = synthesis
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Intelligence gathering completed in {duration:.2f}s - "
                       f"{len(correlations.get('patterns', []))} patterns found")
            
            return intelligence_data
            
        except Exception as e:
            logger.error(f"Error gathering intelligence: {e}")
            return {'error': str(e), 'timestamp': datetime.now()}
    
    async def _gather_news_intelligence(self, ticker: Optional[str]) -> Dict[str, Any]:
        """
        Gather news intelligence from multiple sources
        """
        try:
            logger.info("Gathering news intelligence...")
            
            # Parallel scraping of news sources
            tasks = [
                self.news_scraper.scrape_cnbc(ticker),
                self.news_scraper.scrape_yahoo_finance(ticker),
                self.news_scraper.scrape_reuters(ticker),
                self.news_scraper.scrape_bloomberg(ticker),
                self.news_scraper.scrape_marketwatch(ticker),
                self.news_scraper.scrape_seeking_alpha(ticker)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine and deduplicate
            all_news = []
            for result in results:
                if not isinstance(result, Exception) and result:
                    all_news.extend(result.get('articles', []))
            
            # Sort by timestamp and relevance
            all_news.sort(key=lambda x: x.get('timestamp', datetime.now()), reverse=True)
            
            return {
                'articles': all_news[:50],  # Top 50 most recent
                'sources_scraped': len([r for r in results if not isinstance(r, Exception)]),
                'total_articles': len(all_news),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error gathering news intelligence: {e}")
            return {}
    
    async def _gather_block_trade_intelligence(self, ticker: Optional[str]) -> Dict[str, Any]:
        """
        Gather block trade intelligence from public dashboards
        """
        try:
            logger.info("Gathering block trade intelligence...")
            
            # Scrape block trade data from public sources
            tasks = [
                self.block_trade_scraper.scrape_unusual_whales(),
                self.block_trade_scraper.scrape_finviz_blocks(),
                self.block_trade_scraper.scrape_trade_alerts(),
                self.block_trade_scraper.scrape_market_chameleon()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine block trades
            all_blocks = []
            for result in results:
                if not isinstance(result, Exception) and result:
                    all_blocks.extend(result.get('blocks', []))
            
            # Filter by ticker if specified
            if ticker:
                all_blocks = [b for b in all_blocks if b.get('ticker') == ticker]
            
            return {
                'block_trades': all_blocks,
                'sources_scraped': len([r for r in results if not isinstance(r, Exception)]),
                'total_blocks': len(all_blocks),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error gathering block trade intelligence: {e}")
            return {}
    
    async def _gather_dark_pool_intelligence(self, ticker: Optional[str]) -> Dict[str, Any]:
        """
        Gather dark pool intelligence from commentary and reports
        """
        try:
            logger.info("Gathering dark pool intelligence...")
            
            # Scrape dark pool data
            tasks = [
                self.dark_pool_scraper.scrape_finra_dark_pool(),
                self.dark_pool_scraper.scrape_dark_pool_indices(),
                self.dark_pool_scraper.scrape_quiver_quant_dark_pool()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine dark pool data
            dark_pool_data = {}
            for result in results:
                if not isinstance(result, Exception) and result:
                    dark_pool_data.update(result)
            
            return {
                'dark_pool_data': dark_pool_data,
                'sources_scraped': len([r for r in results if not isinstance(r, Exception)]),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error gathering dark pool intelligence: {e}")
            return {}
    
    async def _gather_options_intelligence(self, ticker: Optional[str]) -> Dict[str, Any]:
        """
        Gather options activity intelligence
        """
        try:
            logger.info("Gathering options intelligence...")
            
            # Scrape options flow data
            tasks = [
                self.options_scraper.scrape_unusual_whales_options(),
                self.options_scraper.scrape_flow_algo(),
                self.options_scraper.scrape_cheddar_flow(),
                self.options_scraper.scrape_sweep_alerts()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine options data
            all_options = []
            for result in results:
                if not isinstance(result, Exception) and result:
                    all_options.extend(result.get('flows', []))
            
            # Filter by ticker if specified
            if ticker:
                all_options = [o for o in all_options if o.get('ticker') == ticker]
            
            return {
                'options_flows': all_options,
                'sources_scraped': len([r for r in results if not isinstance(r, Exception)]),
                'total_flows': len(all_options),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error gathering options intelligence: {e}")
            return {}
    
    async def _gather_social_intelligence(self, ticker: Optional[str]) -> Dict[str, Any]:
        """
        Gather social sentiment intelligence
        """
        try:
            logger.info("Gathering social intelligence...")
            
            # Scrape social feeds
            tasks = [
                self.social_scraper.scrape_wallstreetbets(ticker),
                self.social_scraper.scrape_tradingview(ticker),
                self.social_scraper.scrape_stocktwits(ticker),
                self.social_scraper.scrape_twitter_finance(ticker)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine social data
            social_data = {
                'reddit': results[0] if not isinstance(results[0], Exception) else {},
                'tradingview': results[1] if not isinstance(results[1], Exception) else {},
                'stocktwits': results[2] if not isinstance(results[2], Exception) else {},
                'twitter': results[3] if not isinstance(results[3], Exception) else {}
            }
            
            return {
                'social_data': social_data,
                'sources_scraped': len([r for r in results if not isinstance(r, Exception)]),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error gathering social intelligence: {e}")
            return {}
    
    async def _gather_technical_intelligence(self, ticker: Optional[str]) -> Dict[str, Any]:
        """
        Gather technical analysis intelligence
        """
        try:
            logger.info("Gathering technical intelligence...")
            
            # Scrape technical data from public dashboards
            tasks = [
                self.technical_scraper.scrape_finviz_technicals(ticker),
                self.technical_scraper.scrape_tradingview_technicals(ticker),
                self.technical_scraper.scrape_barchart_signals(ticker),
                self.technical_scraper.scrape_investing_com_technicals(ticker)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine technical data
            technical_data = {}
            for result in results:
                if not isinstance(result, Exception) and result:
                    technical_data.update(result)
            
            return {
                'technical_data': technical_data,
                'sources_scraped': len([r for r in results if not isinstance(r, Exception)]),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error gathering technical intelligence: {e}")
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get aggregator status"""
        return {
            'scrapers_available': {
                'news': self.news_scraper is not None,
                'block_trades': self.block_trade_scraper is not None,
                'dark_pool': self.dark_pool_scraper is not None,
                'options': self.options_scraper is not None,
                'social': self.social_scraper is not None,
                'technical': self.technical_scraper is not None
            },
            'cache_size': len(self.intelligence_cache),
            'last_update': self.last_update
        }



