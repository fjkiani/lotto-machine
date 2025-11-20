"""
Adaptive Feedback System
Learns from anomaly detection performance and recalibrates thresholds
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from dataclasses import dataclass
import numpy as np
import json

from .models import ClusterEvent

logger = logging.getLogger(__name__)

@dataclass
class FeedbackRecord:
    """Record of anomaly detection feedback"""
    timestamp: datetime
    ticker: str
    cluster_event: ClusterEvent
    market_move_1min: float
    market_move_5min: float
    market_move_15min: float
    was_correct: bool
    false_positive: bool
    false_negative: bool

class AdaptiveFeedback:
    """
    Adaptive feedback system that learns from anomaly detection performance
    
    After each anomaly, logs subsequent market moves and recalibrates thresholds
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Feedback tracking
        self.feedback_records = deque(maxlen=1000)  # Last 1000 feedback records
        self.performance_metrics = {
            'total_anomalies': 0,
            'correct_predictions': 0,
            'false_positives': 0,
            'false_negatives': 0,
            'accuracy': 0.0,
            'precision': 0.0,
            'recall': 0.0
        }
        
        # Recalibration parameters
        self.recalibration_threshold = config.get('recalibration_threshold', 0.1)  # 10% accuracy drop
        self.min_samples_for_recalibration = config.get('min_samples_for_recalibration', 50)
        self.recalibration_window_days = config.get('recalibration_window_days', 7)
        
        # Market move thresholds for determining "correct" predictions
        self.market_move_thresholds = {
            '1min': config.get('market_move_threshold_1min', 0.002),  # 0.2%
            '5min': config.get('market_move_threshold_5min', 0.005),  # 0.5%
            '15min': config.get('market_move_threshold_15min', 0.01)   # 1.0%
        }
        
        # Threshold adjustment factors
        self.adjustment_factors = {
            'false_positive_rate': config.get('fp_adjustment_factor', 0.1),
            'false_negative_rate': config.get('fn_adjustment_factor', 0.1),
            'accuracy_drop': config.get('accuracy_adjustment_factor', 0.05)
        }
        
        logger.info("AdaptiveFeedback initialized")
    
    async def update_feedback(self, cluster_event: ClusterEvent, market_move: float) -> None:
        """
        Update feedback based on actual market move
        """
        try:
            # Determine if prediction was correct
            was_correct = self._was_prediction_correct(cluster_event, market_move)
            false_positive = not was_correct and cluster_event.conviction_level in ['high', 'critical']
            false_negative = was_correct and cluster_event.conviction_level in ['low', 'medium']
            
            # Create feedback record
            feedback_record = FeedbackRecord(
                timestamp=datetime.now(),
                ticker=cluster_event.ticker,
                cluster_event=cluster_event,
                market_move_1min=market_move,  # This would be actual 1min move
                market_move_5min=market_move * 1.5,  # Simulated
                market_move_15min=market_move * 2.0,  # Simulated
                was_correct=was_correct,
                false_positive=false_positive,
                false_negative=false_negative
            )
            
            # Add to records
            self.feedback_records.append(feedback_record)
            
            # Update performance metrics
            self._update_performance_metrics(feedback_record)
            
            logger.info(f"Feedback updated for {cluster_event.ticker}: "
                       f"move={market_move:.3f}, correct={was_correct}")
            
        except Exception as e:
            logger.error(f"Error updating feedback: {e}")
    
    def _was_prediction_correct(self, cluster_event: ClusterEvent, market_move: float) -> bool:
        """
        Determine if the anomaly prediction was correct based on market move
        """
        try:
            # Use appropriate threshold based on conviction level
            if cluster_event.conviction_level in ['critical', 'high']:
                threshold = self.market_move_thresholds['5min']
            else:
                threshold = self.market_move_thresholds['15min']
            
            # Consider it correct if market moved significantly
            return abs(market_move) >= threshold
            
        except Exception as e:
            logger.error(f"Error determining prediction correctness: {e}")
            return False
    
    def _update_performance_metrics(self, feedback_record: FeedbackRecord) -> None:
        """
        Update performance metrics based on new feedback
        """
        try:
            self.performance_metrics['total_anomalies'] += 1
            
            if feedback_record.was_correct:
                self.performance_metrics['correct_predictions'] += 1
            
            if feedback_record.false_positive:
                self.performance_metrics['false_positives'] += 1
            
            if feedback_record.false_negative:
                self.performance_metrics['false_negatives'] += 1
            
            # Recalculate metrics
            total = self.performance_metrics['total_anomalies']
            correct = self.performance_metrics['correct_predictions']
            fp = self.performance_metrics['false_positives']
            fn = self.performance_metrics['false_negatives']
            
            if total > 0:
                self.performance_metrics['accuracy'] = correct / total
            
            if (correct + fp) > 0:
                self.performance_metrics['precision'] = correct / (correct + fp)
            
            if (correct + fn) > 0:
                self.performance_metrics['recall'] = correct / (correct + fn)
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    def should_recalibrate(self) -> bool:
        """
        Determine if thresholds should be recalibrated
        """
        try:
            # Check if we have enough samples
            if len(self.feedback_records) < self.min_samples_for_recalibration:
                return False
            
            # Check if accuracy has dropped significantly
            current_accuracy = self.performance_metrics['accuracy']
            if current_accuracy < (1.0 - self.recalibration_threshold):
                return True
            
            # Check if false positive rate is too high
            fp_rate = self.performance_metrics['false_positives'] / self.performance_metrics['total_anomalies']
            if fp_rate > 0.3:  # 30% false positive rate
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking recalibration need: {e}")
            return False
    
    def get_recalibration_data(self) -> Dict[str, Any]:
        """
        Get data for recalibrating thresholds
        """
        try:
            # Analyze recent performance
            recent_records = [
                record for record in self.feedback_records
                if datetime.now() - record.timestamp <= timedelta(days=self.recalibration_window_days)
            ]
            
            if not recent_records:
                return {}
            
            # Calculate performance by anomaly type
            type_performance = {}
            for record in recent_records:
                for event in record.cluster_event.events:
                    anomaly_type = event.anomaly_type
                    if anomaly_type not in type_performance:
                        type_performance[anomaly_type] = {
                            'total': 0,
                            'correct': 0,
                            'false_positives': 0
                        }
                    
                    type_performance[anomaly_type]['total'] += 1
                    if record.was_correct:
                        type_performance[anomaly_type]['correct'] += 1
                    if record.false_positive:
                        type_performance[anomaly_type]['false_positives'] += 1
            
            # Calculate adjustment recommendations
            adjustments = {}
            for anomaly_type, perf in type_performance.items():
                if perf['total'] > 0:
                    accuracy = perf['correct'] / perf['total']
                    fp_rate = perf['false_positives'] / perf['total']
                    
                    # Recommend threshold adjustments
                    if accuracy < 0.6:  # Low accuracy
                        adjustments[anomaly_type] = {
                            'action': 'increase_threshold',
                            'factor': 1.0 + self.adjustment_factors['accuracy_drop']
                        }
                    elif fp_rate > 0.3:  # High false positive rate
                        adjustments[anomaly_type] = {
                            'action': 'increase_threshold',
                            'factor': 1.0 + self.adjustment_factors['false_positive_rate']
                        }
                    elif accuracy > 0.8 and fp_rate < 0.1:  # High accuracy, low FP
                        adjustments[anomaly_type] = {
                            'action': 'decrease_threshold',
                            'factor': 1.0 - self.adjustment_factors['accuracy_drop']
                        }
            
            return {
                'type_performance': type_performance,
                'adjustments': adjustments,
                'overall_metrics': self.performance_metrics,
                'recent_records_count': len(recent_records)
            }
            
        except Exception as e:
            logger.error(f"Error getting recalibration data: {e}")
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get feedback system status
        """
        return {
            'performance_metrics': self.performance_metrics,
            'feedback_records_count': len(self.feedback_records),
            'recalibration_threshold': self.recalibration_threshold,
            'min_samples_for_recalibration': self.min_samples_for_recalibration,
            'market_move_thresholds': self.market_move_thresholds,
            'should_recalibrate': self.should_recalibrate()
        }
