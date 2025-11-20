"""
Anomaly Clustering System
Groups related anomalies into composite events
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Deque
from collections import deque
import numpy as np

from .models import AnomalyEvent, ClusterEvent

logger = logging.getLogger(__name__)

class AnomalyCluster:
    """
    Clusters related anomalies into composite events
    
    If 2+ events cluster within 5 minutes, escalate as "high probability" event
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Clustering parameters
        self.cluster_window_minutes = config.get('cluster_window_minutes', 5)
        self.min_events_for_cluster = config.get('min_events_for_cluster', 2)
        self.max_events_for_cluster = config.get('max_events_for_cluster', 10)
        
        # Conviction thresholds
        self.conviction_thresholds = {
            'low': config.get('low_conviction_threshold', 0.3),
            'medium': config.get('medium_conviction_threshold', 0.6),
            'high': config.get('high_conviction_threshold', 0.8),
            'critical': config.get('critical_conviction_threshold', 0.9)
        }
        
        # Event type weights for clustering
        self.event_weights = {
            'block_trade': config.get('block_trade_weight', 1.0),
            'dark_volume_spike': config.get('dark_volume_weight', 0.8),
            'options_sweep': config.get('options_sweep_weight', 1.2),
            'options_oi_spike': config.get('options_oi_weight', 1.0),
            'price_spike': config.get('price_spike_weight', 0.9),
            'volume_spike': config.get('volume_spike_weight', 0.7),
            'price_volume_spike': config.get('price_volume_spike_weight', 1.1),
            'news_magnet': config.get('news_magnet_weight', 1.3)
        }
        
        logger.info("AnomalyCluster initialized")
    
    async def check_clustering(self, ticker: str, new_anomalies: List[AnomalyEvent], 
                             recent_anomalies: Deque[AnomalyEvent]) -> Optional[ClusterEvent]:
        """
        Check if new anomalies cluster with recent ones
        """
        try:
            if not new_anomalies:
                return None
            
            # Get recent anomalies for this ticker within cluster window
            current_time = datetime.now()
            cluster_window = timedelta(minutes=self.cluster_window_minutes)
            
            relevant_anomalies = []
            
            # Add new anomalies
            for anomaly in new_anomalies:
                if anomaly.ticker == ticker:
                    relevant_anomalies.append(anomaly)
            
            # Add recent anomalies within time window
            for anomaly in recent_anomalies:
                if (anomaly.ticker == ticker and 
                    current_time - anomaly.timestamp <= cluster_window):
                    relevant_anomalies.append(anomaly)
            
            # Check if we have enough events for clustering
            if len(relevant_anomalies) < self.min_events_for_cluster:
                return None
            
            # Calculate cluster score
            cluster_score = self._calculate_cluster_score(relevant_anomalies)
            
            # Determine conviction level
            conviction_level = self._determine_conviction_level(cluster_score)
            
            # Create cluster event
            cluster_event = ClusterEvent(
                timestamp=current_time,
                ticker=ticker,
                events=relevant_anomalies,
                cluster_score=cluster_score,
                conviction_level=conviction_level,
                details={
                    'event_count': len(relevant_anomalies),
                    'time_window_minutes': self.cluster_window_minutes,
                    'event_types': list(set(event.anomaly_type for event in relevant_anomalies)),
                    'avg_severity': np.mean([event.severity for event in relevant_anomalies]),
                    'max_severity': max(event.severity for event in relevant_anomalies),
                    'weighted_score': cluster_score
                }
            )
            
            logger.info(f"Cluster event detected for {ticker}: {conviction_level} conviction, "
                       f"{len(relevant_anomalies)} events, score: {cluster_score:.3f}")
            
            return cluster_event
            
        except Exception as e:
            logger.error(f"Error in clustering check: {e}")
            return None
    
    def _calculate_cluster_score(self, anomalies: List[AnomalyEvent]) -> float:
        """
        Calculate weighted cluster score based on anomaly types and severities
        """
        try:
            if not anomalies:
                return 0.0
            
            # Base score from individual anomaly severities
            base_score = sum(anomaly.severity for anomaly in anomalies)
            
            # Apply weights based on anomaly types
            weighted_score = 0.0
            for anomaly in anomalies:
                weight = self.event_weights.get(anomaly.anomaly_type, 1.0)
                weighted_score += anomaly.severity * weight
            
            # Normalize by number of events
            normalized_score = weighted_score / len(anomalies)
            
            # Bonus for multiple different event types
            unique_types = len(set(anomaly.anomaly_type for anomaly in anomalies))
            diversity_bonus = min(0.3, unique_types * 0.1)
            
            # Bonus for high-severity events
            high_severity_count = sum(1 for anomaly in anomalies if anomaly.severity > 0.7)
            severity_bonus = min(0.2, high_severity_count * 0.05)
            
            final_score = normalized_score + diversity_bonus + severity_bonus
            
            return min(1.0, final_score)  # Cap at 1.0
            
        except Exception as e:
            logger.error(f"Error calculating cluster score: {e}")
            return 0.0
    
    def _determine_conviction_level(self, cluster_score: float) -> str:
        """
        Determine conviction level based on cluster score
        """
        if cluster_score >= self.conviction_thresholds['critical']:
            return 'critical'
        elif cluster_score >= self.conviction_thresholds['high']:
            return 'high'
        elif cluster_score >= self.conviction_thresholds['medium']:
            return 'medium'
        else:
            return 'low'
    
    def get_cluster_summary(self, cluster_event: ClusterEvent) -> str:
        """
        Generate human-readable summary of cluster event
        """
        try:
            event_types = cluster_event.details['event_types']
            event_count = cluster_event.details['event_count']
            avg_severity = cluster_event.details['avg_severity']
            
            summary = (f"{cluster_event.conviction_level.upper()} CONVICTION CLUSTER: "
                      f"{event_count} events detected for {cluster_event.ticker} "
                      f"within {self.cluster_window_minutes} minutes. "
                      f"Event types: {', '.join(event_types)}. "
                      f"Average severity: {avg_severity:.2f}. "
                      f"Cluster score: {cluster_event.cluster_score:.3f}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating cluster summary: {e}")
            return f"Cluster event for {cluster_event.ticker} with {len(cluster_event.events)} events"
    
    def should_escalate(self, cluster_event: ClusterEvent) -> bool:
        """
        Determine if cluster event should be escalated
        """
        return cluster_event.conviction_level in ['high', 'critical']
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get clustering system status
        """
        return {
            'cluster_window_minutes': self.cluster_window_minutes,
            'min_events_for_cluster': self.min_events_for_cluster,
            'max_events_for_cluster': self.max_events_for_cluster,
            'conviction_thresholds': self.conviction_thresholds,
            'event_weights': self.event_weights
        }
