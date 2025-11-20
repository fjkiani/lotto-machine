"""
Real-Time Intelligence System
Implements Alpha's blueprint for continuous market intelligence

Data Feeds → Ingestion → Analytics → Narrative → Alerts → Feedback
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
import json

from .feeds import DataFeedManager
from .ingestion import ContinuousIngestion
from .analytics import RealTimeAnalytics
from .narrative import NarrativeEngine
from .alerts import AlertManager, FeedbackLoop

logger = logging.getLogger(__name__)

@dataclass
class MarketEvent:
    """Standardized market event"""
    ticker: str
    timestamp: datetime
    source: str
    event_type: str  # 'news', 'trade', 'options', 'block', 'price'
    data: Dict[str, Any]
    raw_text: str

@dataclass
class AnomalyFlag:
    """Anomaly detection flag"""
    ticker: str
    timestamp: datetime
    anomaly_type: str  # 'trade_size', 'price_spike', 'options_sweep', 'dark_pool_surge'
    severity: float  # 0-1
    details: Dict[str, Any]
    conviction_score: float

@dataclass
class CompositeAlert:
    """Composite cluster alert"""
    ticker: str
    timestamp: datetime
    conviction_score: float
    anomaly_types: List[str]
    narrative: str
    suggested_action: str
    risk_level: str

class RealTimeIntelligenceSystem:
    """
    Alpha's Real-Time Intelligence System
    
    Continuous polling → Anomaly detection → Narrative synthesis → Actionable alerts
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Initialize components
        self.feed_manager = DataFeedManager(config.get('feeds', {}))
        self.ingestion = ContinuousIngestion(config.get('ingestion', {}))
        self.analytics = RealTimeAnalytics(config.get('analytics', {}))
        self.narrative_engine = NarrativeEngine(config.get('narrative', {}))
        self.alert_manager = AlertManager(config.get('alerts', {}))
        self.feedback_loop = FeedbackLoop(config.get('feedback', {}))
        
        # System state
        self.is_running = False
        self.polling_interval = config.get('polling_interval', 15)  # seconds
        self.tickers = config.get('monitored_tickers', ['SPY', 'QQQ', 'IWM'])
        
        # Event storage
        self.recent_events = []  # Last 10 minutes
        self.active_anomalies = []
        self.alert_history = []
        
        logger.info("Real-Time Intelligence System initialized - ready for relentless market monitoring")
    
    async def start_system(self):
        """Start the continuous intelligence system"""
        try:
            logger.info("🚀 Starting Real-Time Intelligence System...")
            self.is_running = True
            
            # Start all components
            await self.feed_manager.initialize()
            await self.analytics.initialize()
            await self.narrative_engine.initialize()
            await self.alert_manager.initialize()
            
            # Start continuous polling loop
            await self._continuous_polling_loop()
            
        except Exception as e:
            logger.error(f"Error starting system: {e}")
            self.is_running = False
    
    async def stop_system(self):
        """Stop the system gracefully"""
        logger.info("Stopping Real-Time Intelligence System...")
        self.is_running = False
        
        # Cleanup
        await self.feed_manager.cleanup()
        await self.analytics.cleanup()
        await self.narrative_engine.cleanup()
        await self.alert_manager.cleanup()
    
    async def _continuous_polling_loop(self):
        """Main continuous polling loop - Alpha's relentless monitoring"""
        logger.info(f"Starting continuous polling every {self.polling_interval}s")
        
        while self.is_running:
            try:
                cycle_start = datetime.now()
                
                # 1. DATA FEEDS - Pull all sources
                await self._poll_all_feeds()
                
                # 2. ANALYTICS - Detect anomalies
                await self._detect_anomalies()
                
                # 3. NARRATIVE - Extract "why"
                await self._generate_narratives()
                
                # 4. COMPOSITE CLUSTERING - Conviction scoring
                await self._cluster_anomalies()
                
                # 5. ALERTS - Push actionable alerts
                await self._process_alerts()
                
                # 6. FEEDBACK - Auto-tune thresholds
                await self._update_feedback()
                
                # Calculate cycle time
                cycle_time = (datetime.now() - cycle_start).total_seconds()
                logger.debug(f"Intelligence cycle completed in {cycle_time:.2f}s")
                
                # Wait for next cycle
                await asyncio.sleep(max(0, self.polling_interval - cycle_time))
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(self.polling_interval)
    
    async def _poll_all_feeds(self):
        """Step 1: Pull all data feeds in parallel"""
        try:
            # Parallel polling of all sources
            tasks = []
            
            # News feeds
            tasks.append(self._poll_news_feeds())
            
            # Market data feeds
            tasks.append(self._poll_market_feeds())
            
            # Options feeds
            tasks.append(self._poll_options_feeds())
            
            # Social feeds
            tasks.append(self._poll_social_feeds())
            
            # Execute all in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            new_events = []
            for result in results:
                if not isinstance(result, Exception) and result:
                    new_events.extend(result)
            
            # Add to recent events
            self.recent_events.extend(new_events)
            
            # Keep only last 10 minutes
            cutoff_time = datetime.now() - timedelta(minutes=10)
            self.recent_events = [
                event for event in self.recent_events
                if event.timestamp > cutoff_time
            ]
            
            logger.debug(f"Polled {len(new_events)} new events, {len(self.recent_events)} total recent")
            
        except Exception as e:
            logger.error(f"Error polling feeds: {e}")
    
    async def _poll_news_feeds(self) -> List[MarketEvent]:
        """Poll news sources (Tavily, RSS, Twitter)"""
        try:
            events = []
            
            # Tavily API for rapid news
            tavily_news = await self.feed_manager.get_tavily_news(self.tickers)
            for article in tavily_news:
                events.append(MarketEvent(
                    ticker=article.get('ticker', 'MARKET'),
                    timestamp=datetime.now(),
                    source='tavily',
                    event_type='news',
                    data=article,
                    raw_text=article.get('headline', '')
                ))
            
            # RSS feeds
            rss_news = await self.feed_manager.get_rss_feeds()
            for article in rss_news:
                events.append(MarketEvent(
                    ticker=article.get('ticker', 'MARKET'),
                    timestamp=datetime.now(),
                    source=article.get('source', 'rss'),
                    event_type='news',
                    data=article,
                    raw_text=article.get('title', '')
                ))
            
            # Twitter/X search
            twitter_news = await self.feed_manager.get_twitter_finance(self.tickers)
            for tweet in twitter_news:
                events.append(MarketEvent(
                    ticker=tweet.get('ticker', 'MARKET'),
                    timestamp=datetime.now(),
                    source='twitter',
                    event_type='news',
                    data=tweet,
                    raw_text=tweet.get('text', '')
                ))
            
            return events
            
        except Exception as e:
            logger.error(f"Error polling news feeds: {e}")
            return []
    
    async def _poll_market_feeds(self) -> List[MarketEvent]:
        """Poll market data (broker feeds, Yahoo Finance)"""
        try:
            events = []
            
            # Broker feed (Interactive Brokers, Alpaca, etc.)
            broker_data = await self.feed_manager.get_broker_feed(self.tickers)
            for trade in broker_data:
                events.append(MarketEvent(
                    ticker=trade.get('ticker'),
                    timestamp=trade.get('timestamp', datetime.now()),
                    source='broker',
                    event_type='trade',
                    data=trade,
                    raw_text=f"Trade: {trade.get('size')} @ ${trade.get('price')}"
                ))
            
            # Yahoo Finance backup
            yahoo_data = await self.feed_manager.get_yahoo_finance(self.tickers)
            for quote in yahoo_data:
                events.append(MarketEvent(
                    ticker=quote.get('ticker'),
                    timestamp=datetime.now(),
                    source='yahoo',
                    event_type='quote',
                    data=quote,
                    raw_text=f"Quote: ${quote.get('price')}"
                ))
            
            return events
            
        except Exception as e:
            logger.error(f"Error polling market feeds: {e}")
            return []
    
    async def _poll_options_feeds(self) -> List[MarketEvent]:
        """Poll options flow dashboards"""
        try:
            events = []
            
            # Barchart options flow
            barchart_flows = await self.feed_manager.get_barchart_options(self.tickers)
            for flow in barchart_flows:
                events.append(MarketEvent(
                    ticker=flow.get('ticker'),
                    timestamp=datetime.now(),
                    source='barchart',
                    event_type='options',
                    data=flow,
                    raw_text=f"Options: {flow.get('contracts')} {flow.get('type')} @ ${flow.get('strike')}"
                ))
            
            # TradingView options
            tv_flows = await self.feed_manager.get_tradingview_options(self.tickers)
            for flow in tv_flows:
                events.append(MarketEvent(
                    ticker=flow.get('ticker'),
                    timestamp=datetime.now(),
                    source='tradingview',
                    event_type='options',
                    data=flow,
                    raw_text=f"Options: {flow.get('contracts')} {flow.get('type')} @ ${flow.get('strike')}"
                ))
            
            return events
            
        except Exception as e:
            logger.error(f"Error polling options feeds: {e}")
            return []
    
    async def _poll_social_feeds(self) -> List[MarketEvent]:
        """Poll social sentiment feeds"""
        try:
            events = []
            
            # Reddit finance
            reddit_posts = await self.feed_manager.get_reddit_finance(self.tickers)
            for post in reddit_posts:
                events.append(MarketEvent(
                    ticker=post.get('ticker', 'MARKET'),
                    timestamp=datetime.now(),
                    source='reddit',
                    event_type='social',
                    data=post,
                    raw_text=post.get('title', '')
                ))
            
            return events
            
        except Exception as e:
            logger.error(f"Error polling social feeds: {e}")
            return []
    
    async def _detect_anomalies(self):
        """Step 2: Detect anomalies using rolling baselines"""
        try:
            # Group events by ticker
            ticker_events = {}
            for event in self.recent_events:
                ticker = event.ticker
                if ticker not in ticker_events:
                    ticker_events[ticker] = []
                ticker_events[ticker].append(event)
            
            # Detect anomalies for each ticker
            new_anomalies = []
            for ticker, events in ticker_events.items():
                anomalies = await self.analytics.detect_anomalies(ticker, events)
                new_anomalies.extend(anomalies)
            
            # Add to active anomalies
            self.active_anomalies.extend(new_anomalies)
            
            # Keep only recent anomalies
            cutoff_time = datetime.now() - timedelta(minutes=30)
            self.active_anomalies = [
                anomaly for anomaly in self.active_anomalies
                if anomaly.timestamp > cutoff_time
            ]
            
            if new_anomalies:
                logger.info(f"Detected {len(new_anomalies)} new anomalies")
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
    
    async def _generate_narratives(self):
        """Step 3: Generate narratives using LLM"""
        try:
            if not self.recent_events:
                return
            
            # Batch recent events for LLM analysis
            recent_events_data = [
                {
                    'ticker': event.ticker,
                    'timestamp': event.timestamp.isoformat(),
                    'source': event.source,
                    'type': event.event_type,
                    'text': event.raw_text
                }
                for event in self.recent_events[-50:]  # Last 50 events
            ]
            
            # Generate narrative
            narrative = await self.narrative_engine.generate_narrative(
                events=recent_events_data,
                anomalies=self.active_anomalies[-20:],  # Last 20 anomalies
                time_window_minutes=10
            )
            
            logger.debug(f"Generated narrative: {narrative[:100]}...")
            
        except Exception as e:
            logger.error(f"Error generating narratives: {e}")
    
    async def _cluster_anomalies(self):
        """Step 4: Composite clustering with conviction scoring"""
        try:
            if not self.active_anomalies:
                return
            
            # Group anomalies by ticker and time window
            clusters = await self.analytics.cluster_anomalies(self.active_anomalies)
            
            # Calculate conviction scores
            high_conviction_clusters = []
            for cluster in clusters:
                conviction_score = self._calculate_conviction_score(cluster)
                
                if conviction_score >= 0.7:  # High conviction threshold
                    alert = CompositeAlert(
                        ticker=cluster['ticker'],
                        timestamp=datetime.now(),
                        conviction_score=conviction_score,
                        anomaly_types=cluster['anomaly_types'],
                        narrative=cluster.get('narrative', ''),
                        suggested_action=self._suggest_action(cluster),
                        risk_level=self._assess_risk_level(conviction_score)
                    )
                    high_conviction_clusters.append(alert)
            
            # Process high conviction alerts
            if high_conviction_clusters:
                await self._process_high_conviction_alerts(high_conviction_clusters)
            
        except Exception as e:
            logger.error(f"Error clustering anomalies: {e}")
    
    def _calculate_conviction_score(self, cluster: Dict[str, Any]) -> float:
        """Calculate conviction score for anomaly cluster"""
        try:
            # Base score from number of anomaly types
            anomaly_count = len(cluster.get('anomaly_types', []))
            base_score = min(1.0, anomaly_count / 5.0)  # Max at 5 types
            
            # Boost from recency
            recent_anomalies = [
                a for a in cluster.get('anomalies', [])
                if (datetime.now() - a.timestamp).total_seconds() < 300  # 5 minutes
            ]
            recency_boost = min(0.3, len(recent_anomalies) / 10.0)
            
            # Boost from severity
            avg_severity = sum(a.severity for a in cluster.get('anomalies', [])) / max(1, len(cluster.get('anomalies', [])))
            severity_boost = avg_severity * 0.2
            
            conviction_score = base_score + recency_boost + severity_boost
            return min(1.0, conviction_score)
            
        except Exception as e:
            logger.error(f"Error calculating conviction score: {e}")
            return 0.0
    
    def _suggest_action(self, cluster: Dict[str, Any]) -> str:
        """Suggest trading action based on cluster"""
        try:
            anomaly_types = cluster.get('anomaly_types', [])
            
            if 'price_spike' in anomaly_types and 'options_sweep' in anomaly_types:
                return "SCALP - Momentum play with options confirmation"
            elif 'block_trade' in anomaly_types and 'news' in anomaly_types:
                return "FADE - Institutional reaction to news"
            elif 'dark_pool_surge' in anomaly_types:
                return "VOLATILITY - Off-exchange activity suggests major move"
            else:
                return "MONITOR - Multiple signals detected"
                
        except Exception as e:
            logger.error(f"Error suggesting action: {e}")
            return "MONITOR"
    
    def _assess_risk_level(self, conviction_score: float) -> str:
        """Assess risk level based on conviction score"""
        if conviction_score >= 0.9:
            return "CRITICAL"
        elif conviction_score >= 0.7:
            return "HIGH"
        elif conviction_score >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    async def _process_high_conviction_alerts(self, alerts: List[CompositeAlert]):
        """Process high conviction alerts"""
        try:
            for alert in alerts:
                # Send to alert manager
                await self.alert_manager.send_alert(alert)
                
                # Log for post-mortem
                self.alert_history.append(alert)
                
                logger.warning(f"🚨 HIGH CONVICTION ALERT: {alert.ticker} - {alert.suggested_action}")
            
        except Exception as e:
            logger.error(f"Error processing high conviction alerts: {e}")
    
    async def _process_alerts(self):
        """Step 5: Process and send alerts"""
        try:
            # Process any pending alerts
            await self.alert_manager.process_pending_alerts()
            
        except Exception as e:
            logger.error(f"Error processing alerts: {e}")
    
    async def _update_feedback(self):
        """Step 6: Update feedback and auto-tune thresholds"""
        try:
            # Update feedback loop with recent performance
            await self.feedback_loop.update_thresholds(self.alert_history[-10:])
            
        except Exception as e:
            logger.error(f"Error updating feedback: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            'is_running': self.is_running,
            'polling_interval': self.polling_interval,
            'monitored_tickers': self.tickers,
            'recent_events_count': len(self.recent_events),
            'active_anomalies_count': len(self.active_anomalies),
            'alert_history_count': len(self.alert_history),
            'last_update': datetime.now()
        }
