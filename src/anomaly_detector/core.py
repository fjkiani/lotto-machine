"""
Core Anomaly Detection Engine
Main orchestrator for real-time anomaly detection
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import numpy as np

from .baselines import RollingBaseline
from .classifiers import (
    BlockTradeClassifier,
    DarkVolumeClassifier,
    OptionsFlowClassifier, 
    PriceVolumeClassifier,
    NewsMagnetClassifier
)
from .clustering import AnomalyCluster
from .alerting import AlertRouter
from .feedback import AdaptiveFeedback

logger = logging.getLogger(__name__)

from .models import MarketTick, NewsEvent, OptionsFlow, AnomalyEvent, ClusterEvent

class AnomalyDetector:
    """
    Main anomaly detection engine
    
    Core loop:
    1. Process incoming market data
    2. Update rolling baselines
    3. Run anomaly classifiers
    4. Cluster related anomalies
    5. Route alerts based on conviction
    6. Learn from feedback
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tickers = config.get('tickers', ['SPY', 'QQQ', 'IWM', 'DIA'])
        
        # Initialize components
        self.baselines = {ticker: RollingBaseline(ticker, config) for ticker in self.tickers}
        
        self.classifiers = {
            'block_trade': BlockTradeClassifier(config),
            'dark_volume': DarkVolumeClassifier(config), 
            'options_flow': OptionsFlowClassifier(config),
            'price_volume': PriceVolumeClassifier(config),
            'news_magnet': NewsMagnetClassifier(config)
        }
        
        self.clusterer = AnomalyCluster(config)
        self.alert_router = AlertRouter(config)
        self.feedback = AdaptiveFeedback(config)
        
        # Data buffers
        self.tick_buffer = deque(maxlen=10000)  # Last 10k ticks
        self.news_buffer = deque(maxlen=1000)   # Last 1k news events
        self.options_buffer = deque(maxlen=5000) # Last 5k options events
        
        # Anomaly tracking
        self.recent_anomalies = deque(maxlen=1000)
        self.cluster_events = deque(maxlen=500)
        
        logger.info(f"AnomalyDetector initialized for tickers: {self.tickers}")
    
    async def process_market_tick(self, tick: MarketTick) -> Optional[ClusterEvent]:
        """
        Process a single market tick and return any cluster events
        """
        try:
            # Add to buffer
            self.tick_buffer.append(tick)
            
            # Update rolling baselines
            baseline = self.baselines.get(tick.ticker)
            if baseline:
                baseline.update_tick(tick)
            
            # Run anomaly classifiers
            anomalies = []
            
            for classifier_name, classifier in self.classifiers.items():
                if classifier_name == 'news_magnet':
                    continue  # Skip news classifier for tick data
                
                anomaly = await classifier.detect_anomaly(tick, baseline)
                if anomaly:
                    anomalies.append(anomaly)
                    self.recent_anomalies.append(anomaly)
            
            # Check for clustering
            if anomalies:
                cluster_event = await self.clusterer.check_clustering(
                    tick.ticker, 
                    anomalies,
                    self.recent_anomalies
                )
                
                if cluster_event:
                    self.cluster_events.append(cluster_event)
                    
                    # Route alert if conviction is high enough
                    if cluster_event.conviction_level in ['high', 'critical']:
                        await self.alert_router.route_alert(cluster_event)
                    
                    return cluster_event
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing market tick: {e}")
            return None
    
    async def process_news_event(self, news: NewsEvent) -> Optional[ClusterEvent]:
        """
        Process news event and check for news-magnet anomalies
        """
        try:
            self.news_buffer.append(news)
            
            # Run news magnet classifier
            news_classifier = self.classifiers['news_magnet']
            anomaly = await news_classifier.detect_anomaly(news, None)
            
            if anomaly:
                self.recent_anomalies.append(anomaly)
                
                # Check for clustering with recent anomalies
                cluster_event = await self.clusterer.check_clustering(
                    news.ticker or 'MARKET',
                    [anomaly],
                    self.recent_anomalies
                )
                
                if cluster_event:
                    self.cluster_events.append(cluster_event)
                    
                    if cluster_event.conviction_level in ['high', 'critical']:
                        await self.alert_router.route_alert(cluster_event)
                    
                    return cluster_event
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing news event: {e}")
            return None
    
    async def process_options_flow(self, options: OptionsFlow) -> Optional[ClusterEvent]:
        """
        Process options flow data
        """
        try:
            self.options_buffer.append(options)
            
            # Run options flow classifier
            options_classifier = self.classifiers['options_flow']
            anomaly = await options_classifier.detect_anomaly(options, None)
            
            if anomaly:
                self.recent_anomalies.append(anomaly)
                
                # Check for clustering
                cluster_event = await self.clusterer.check_clustering(
                    options.ticker,
                    [anomaly],
                    self.recent_anomalies
                )
                
                if cluster_event:
                    self.cluster_events.append(cluster_event)
                    
                    if cluster_event.conviction_level in ['high', 'critical']:
                        await self.alert_router.route_alert(cluster_event)
                    
                    return cluster_event
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing options flow: {e}")
            return None
    
    async def update_feedback(self, cluster_event: ClusterEvent, market_move: float):
        """
        Update adaptive feedback based on actual market moves
        """
        try:
            await self.feedback.update_feedback(cluster_event, market_move)
            
            # Recalibrate thresholds if needed
            if self.feedback.should_recalibrate():
                await self._recalibrate_thresholds()
                
        except Exception as e:
            logger.error(f"Error updating feedback: {e}")
    
    async def _recalibrate_thresholds(self):
        """
        Recalibrate anomaly detection thresholds based on feedback
        """
        try:
            recalibration_data = self.feedback.get_recalibration_data()
            
            for classifier_name, classifier in self.classifiers.items():
                if hasattr(classifier, 'recalibrate'):
                    await classifier.recalibrate(recalibration_data.get(classifier_name, {}))
            
            logger.info("Thresholds recalibrated based on feedback")
            
        except Exception as e:
            logger.error(f"Error recalibrating thresholds: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current system status
        """
        return {
            'tickers_monitored': self.tickers,
            'recent_anomalies_count': len(self.recent_anomalies),
            'cluster_events_count': len(self.cluster_events),
            'tick_buffer_size': len(self.tick_buffer),
            'news_buffer_size': len(self.news_buffer),
            'options_buffer_size': len(self.options_buffer),
            'baseline_status': {
                ticker: baseline.get_status() 
                for ticker, baseline in self.baselines.items()
            },
            'feedback_status': self.feedback.get_status()
        }
    
    async def start_monitoring(self):
        """
        Start the main monitoring loop
        """
        logger.info("Starting anomaly detection monitoring...")
        
        # This would typically connect to real-time data feeds
        # For now, we'll set up the infrastructure
        
        while True:
            try:
                # Main monitoring loop would go here
                # In a real implementation, this would:
                # 1. Connect to market data feeds
                # 2. Process incoming ticks
                # 3. Handle news feeds
                # 4. Monitor options flow
                
                await asyncio.sleep(0.1)  # 100ms loop
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1)
    
    async def stop_monitoring(self):
        """
        Stop the monitoring loop
        """
        logger.info("Stopping anomaly detection monitoring...")
        # Cleanup logic would go here
