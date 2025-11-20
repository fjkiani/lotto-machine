"""
Real-Time Analytics Engine
Implements Alpha's anomaly detection blueprint

Rolling Baseline Compute + Anomaly Detection + Composite Clustering
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
import statistics
import math

logger = logging.getLogger(__name__)

class RollingBaseline:
    """Rolling baseline calculator for each ticker"""
    
    def __init__(self, ticker: str, window_sizes: List[int] = [60, 300, 1800]):
        self.ticker = ticker
        self.window_sizes = window_sizes  # 1m, 5m, 30m in seconds
        
        # Rolling data storage
        self.price_data = defaultdict(lambda: deque(maxlen=1000))
        self.volume_data = defaultdict(lambda: deque(maxlen=1000))
        self.trade_size_data = defaultdict(lambda: deque(maxlen=1000))
        
        # Current baselines
        self.baselines = {}
        
        logger.debug(f"RollingBaseline initialized for {ticker}")
    
    def add_tick(self, timestamp: datetime, price: float, volume: int, trade_size: int = None):
        """Add new tick data"""
        try:
            # Store data
            self.price_data[timestamp].append(price)
            self.volume_data[timestamp].append(volume)
            if trade_size:
                self.trade_size_data[timestamp].append(trade_size)
            
            # Update baselines
            self._update_baselines(timestamp)
            
        except Exception as e:
            logger.error(f"Error adding tick for {self.ticker}: {e}")
    
    def _update_baselines(self, current_time: datetime):
        """Update rolling baselines"""
        try:
            for window_size in self.window_sizes:
                cutoff_time = current_time - timedelta(seconds=window_size)
                
                # Filter data within window
                recent_prices = []
                recent_volumes = []
                recent_trade_sizes = []
                
                for timestamp, prices in self.price_data.items():
                    if timestamp >= cutoff_time:
                        recent_prices.extend(prices)
                
                for timestamp, volumes in self.volume_data.items():
                    if timestamp >= cutoff_time:
                        recent_volumes.extend(volumes)
                
                for timestamp, sizes in self.trade_size_data.items():
                    if timestamp >= cutoff_time:
                        recent_trade_sizes.extend(sizes)
                
                # Calculate statistics
                if recent_prices:
                    self.baselines[f'{window_size}_price'] = {
                        'mean': statistics.mean(recent_prices),
                        'std': statistics.stdev(recent_prices) if len(recent_prices) > 1 else 0,
                        'median': statistics.median(recent_prices),
                        'count': len(recent_prices)
                    }
                
                if recent_volumes:
                    self.baselines[f'{window_size}_volume'] = {
                        'mean': statistics.mean(recent_volumes),
                        'std': statistics.stdev(recent_volumes) if len(recent_volumes) > 1 else 0,
                        'median': statistics.median(recent_volumes),
                        'count': len(recent_volumes)
                    }
                
                if recent_trade_sizes:
                    self.baselines[f'{window_size}_trade_size'] = {
                        'mean': statistics.mean(recent_trade_sizes),
                        'std': statistics.stdev(recent_trade_sizes) if len(recent_trade_sizes) > 1 else 0,
                        'median': statistics.median(recent_trade_sizes),
                        'count': len(recent_trade_sizes)
                    }
            
        except Exception as e:
            logger.error(f"Error updating baselines for {self.ticker}: {e}")
    
    def get_price_zscore(self, price: float, window_size: int = 300) -> float:
        """Calculate Z-score for price"""
        try:
            baseline_key = f'{window_size}_price'
            if baseline_key not in self.baselines:
                return 0.0
            
            baseline = self.baselines[baseline_key]
            if baseline['std'] == 0:
                return 0.0
            
            return (price - baseline['mean']) / baseline['std']
            
        except Exception as e:
            logger.error(f"Error calculating price Z-score: {e}")
            return 0.0
    
    def get_volume_zscore(self, volume: int, window_size: int = 300) -> float:
        """Calculate Z-score for volume"""
        try:
            baseline_key = f'{window_size}_volume'
            if baseline_key not in self.baselines:
                return 0.0
            
            baseline = self.baselines[baseline_key]
            if baseline['std'] == 0:
                return 0.0
            
            return (volume - baseline['mean']) / baseline['std']
            
        except Exception as e:
            logger.error(f"Error calculating volume Z-score: {e}")
            return 0.0
    
    def get_trade_size_multiple(self, trade_size: int, window_size: int = 300) -> float:
        """Calculate multiple of median trade size"""
        try:
            baseline_key = f'{window_size}_trade_size'
            if baseline_key not in self.baselines:
                return 1.0
            
            baseline = self.baselines[baseline_key]
            if baseline['median'] == 0:
                return 1.0
            
            return trade_size / baseline['median']
            
        except Exception as e:
            logger.error(f"Error calculating trade size multiple: {e}")
            return 1.0

class RealTimeAnalytics:
    """
    Real-time analytics engine implementing Alpha's anomaly detection
    
    Features:
    - Rolling baseline compute (1m, 5m, 30m windows)
    - Anomaly detection (trade size, price spike, options sweep, dark pool surge)
    - Composite clustering with conviction scoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Rolling baselines per ticker
        self.baselines = {}
        
        # Anomaly detection thresholds
        self.thresholds = {
            'trade_size_multiple': config.get('trade_size_threshold', 5.0),
            'price_zscore': config.get('price_zscore_threshold', 2.0),
            'volume_zscore': config.get('volume_zscore_threshold', 2.0),
            'options_sweep_contracts': config.get('options_sweep_threshold', 1000),
            'dark_pool_ratio': config.get('dark_pool_threshold', 0.4)
        }
        
        # Clustering parameters
        self.cluster_time_window = timedelta(minutes=config.get('cluster_window_minutes', 5))
        self.min_anomalies_for_cluster = config.get('min_anomalies_cluster', 2)
        
        logger.info("RealTimeAnalytics initialized - ready for anomaly detection")
    
    async def initialize(self):
        """Initialize analytics engine"""
        try:
            # Initialize baselines for monitored tickers
            monitored_tickers = self.config.get('monitored_tickers', ['SPY', 'QQQ', 'IWM'])
            for ticker in monitored_tickers:
                self.baselines[ticker] = RollingBaseline(ticker)
            
            logger.info("RealTimeAnalytics initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing RealTimeAnalytics: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        pass
    
    async def detect_anomalies(self, ticker: str, events: List[Any]) -> List[Any]:
        """
        Detect anomalies from events
        
        Anomaly Types:
        1. Trade size > 5x rolling median? Flag.
        2. Price change > 2 std dev in <5min? Flag.
        3. Unusual option sweep (N contracts, penny-wide to ask/bid)? Flag.
        4. Surge in dark pool/off-exchange ratio? Flag.
        """
        try:
            anomalies = []
            
            # Get or create baseline for ticker
            if ticker not in self.baselines:
                self.baselines[ticker] = RollingBaseline(ticker)
            
            baseline = self.baselines[ticker]
            
            # Process each event
            for event in events:
                event_anomalies = []
                
                # 1. Trade Size Anomaly
                if event.event_type == 'trade':
                    trade_size = event.data.get('size', 0)
                    if trade_size > 0:
                        multiple = baseline.get_trade_size_multiple(trade_size)
                        if multiple >= self.thresholds['trade_size_multiple']:
                            event_anomalies.append({
                                'type': 'trade_size',
                                'severity': min(1.0, multiple / 10.0),
                                'details': {
                                    'trade_size': trade_size,
                                    'multiple': multiple,
                                    'threshold': self.thresholds['trade_size_multiple']
                                }
                            })
                
                # 2. Price Spike Anomaly
                if event.event_type in ['trade', 'quote']:
                    price = event.data.get('price', 0)
                    if price > 0:
                        zscore = baseline.get_price_zscore(price)
                        if abs(zscore) >= self.thresholds['price_zscore']:
                            event_anomalies.append({
                                'type': 'price_spike',
                                'severity': min(1.0, abs(zscore) / 5.0),
                                'details': {
                                    'price': price,
                                    'zscore': zscore,
                                    'threshold': self.thresholds['price_zscore']
                                }
                            })
                
                # 3. Volume Spike Anomaly
                if event.event_type in ['trade', 'quote']:
                    volume = event.data.get('volume', 0)
                    if volume > 0:
                        zscore = baseline.get_volume_zscore(volume)
                        if zscore >= self.thresholds['volume_zscore']:
                            event_anomalies.append({
                                'type': 'volume_spike',
                                'severity': min(1.0, zscore / 5.0),
                                'details': {
                                    'volume': volume,
                                    'zscore': zscore,
                                    'threshold': self.thresholds['volume_zscore']
                                }
                            })
                
                # 4. Options Sweep Anomaly
                if event.event_type == 'options':
                    contracts = event.data.get('contracts', 0)
                    if contracts >= self.thresholds['options_sweep_contracts']:
                        event_anomalies.append({
                            'type': 'options_sweep',
                            'severity': min(1.0, contracts / 5000.0),
                            'details': {
                                'contracts': contracts,
                                'threshold': self.thresholds['options_sweep_contracts']
                            }
                        })
                
                # 5. Dark Pool Surge Anomaly
                if event.event_type == 'dark_pool':
                    ratio = event.data.get('off_exchange_ratio', 0)
                    if ratio >= self.thresholds['dark_pool_ratio']:
                        event_anomalies.append({
                            'type': 'dark_pool_surge',
                            'severity': min(1.0, ratio),
                            'details': {
                                'ratio': ratio,
                                'threshold': self.thresholds['dark_pool_ratio']
                            }
                        })
                
                # Create anomaly flags
                for anomaly_data in event_anomalies:
                    from .realtime_system import AnomalyFlag
                    
                    anomaly = AnomalyFlag(
                        ticker=ticker,
                        timestamp=event.timestamp,
                        anomaly_type=anomaly_data['type'],
                        severity=anomaly_data['severity'],
                        details=anomaly_data['details'],
                        conviction_score=anomaly_data['severity']  # Initial conviction
                    )
                    anomalies.append(anomaly)
                
                # Update baseline with event data
                if event.event_type in ['trade', 'quote']:
                    price = event.data.get('price', 0)
                    volume = event.data.get('volume', 0)
                    trade_size = event.data.get('size', 0)
                    
                    if price > 0:
                        baseline.add_tick(event.timestamp, price, volume, trade_size)
            
            logger.debug(f"Detected {len(anomalies)} anomalies for {ticker}")
            return anomalies
            
        except Exception as e:
            logger.error(f"Error detecting anomalies for {ticker}: {e}")
            return []
    
    async def cluster_anomalies(self, anomalies: List[Any]) -> List[Dict[str, Any]]:
        """
        Cluster anomalies by ticker and time window
        
        Composite clustering:
        - Group anomalies by ticker
        - Find clusters within time window
        - Calculate conviction scores
        """
        try:
            clusters = []
            
            # Group anomalies by ticker
            ticker_anomalies = defaultdict(list)
            for anomaly in anomalies:
                ticker_anomalies[anomaly.ticker].append(anomaly)
            
            # Cluster anomalies for each ticker
            for ticker, ticker_anomaly_list in ticker_anomalies.items():
                ticker_clusters = self._cluster_ticker_anomalies(ticker, ticker_anomaly_list)
                clusters.extend(ticker_clusters)
            
            logger.debug(f"Created {len(clusters)} anomaly clusters")
            return clusters
            
        except Exception as e:
            logger.error(f"Error clustering anomalies: {e}")
            return []
    
    def _cluster_ticker_anomalies(self, ticker: str, anomalies: List[Any]) -> List[Dict[str, Any]]:
        """Cluster anomalies for a specific ticker"""
        try:
            clusters = []
            
            # Sort anomalies by timestamp
            anomalies.sort(key=lambda x: x.timestamp)
            
            # Find clusters within time window
            current_cluster = []
            cluster_start_time = None
            
            for anomaly in anomalies:
                if not current_cluster:
                    # Start new cluster
                    current_cluster = [anomaly]
                    cluster_start_time = anomaly.timestamp
                else:
                    # Check if anomaly is within time window
                    time_diff = anomaly.timestamp - cluster_start_time
                    if time_diff <= self.cluster_time_window:
                        # Add to current cluster
                        current_cluster.append(anomaly)
                    else:
                        # Finalize current cluster if it has enough anomalies
                        if len(current_cluster) >= self.min_anomalies_for_cluster:
                            cluster = self._create_cluster(ticker, current_cluster)
                            clusters.append(cluster)
                        
                        # Start new cluster
                        current_cluster = [anomaly]
                        cluster_start_time = anomaly.timestamp
            
            # Finalize last cluster
            if len(current_cluster) >= self.min_anomalies_for_cluster:
                cluster = self._create_cluster(ticker, current_cluster)
                clusters.append(cluster)
            
            return clusters
            
        except Exception as e:
            logger.error(f"Error clustering ticker anomalies for {ticker}: {e}")
            return []
    
    def _create_cluster(self, ticker: str, anomalies: List[Any]) -> Dict[str, Any]:
        """Create a cluster from anomalies"""
        try:
            # Extract anomaly types
            anomaly_types = list(set(anomaly.anomaly_type for anomaly in anomalies))
            
            # Calculate cluster metrics
            total_severity = sum(anomaly.severity for anomaly in anomalies)
            avg_severity = total_severity / len(anomalies)
            
            # Calculate conviction score
            conviction_score = self._calculate_cluster_conviction(anomalies)
            
            # Determine cluster narrative
            narrative = self._generate_cluster_narrative(anomalies, anomaly_types)
            
            cluster = {
                'ticker': ticker,
                'timestamp': anomalies[0].timestamp,
                'anomalies': anomalies,
                'anomaly_types': anomaly_types,
                'anomaly_count': len(anomalies),
                'avg_severity': avg_severity,
                'conviction_score': conviction_score,
                'narrative': narrative,
                'time_span': (anomalies[-1].timestamp - anomalies[0].timestamp).total_seconds()
            }
            
            return cluster
            
        except Exception as e:
            logger.error(f"Error creating cluster: {e}")
            return {}
    
    def _calculate_cluster_conviction(self, anomalies: List[Any]) -> float:
        """Calculate conviction score for anomaly cluster"""
        try:
            # Base score from number of anomalies
            anomaly_count_score = min(1.0, len(anomalies) / 10.0)
            
            # Severity score
            avg_severity = sum(anomaly.severity for anomaly in anomalies) / len(anomalies)
            severity_score = avg_severity * 0.5
            
            # Diversity score (different anomaly types)
            anomaly_types = set(anomaly.anomaly_type for anomaly in anomalies)
            diversity_score = min(0.3, len(anomaly_types) / 5.0)
            
            # Recency score
            now = datetime.now()
            recent_anomalies = [
                a for a in anomalies
                if (now - a.timestamp).total_seconds() < 300  # 5 minutes
            ]
            recency_score = min(0.2, len(recent_anomalies) / 5.0)
            
            conviction_score = anomaly_count_score + severity_score + diversity_score + recency_score
            return min(1.0, conviction_score)
            
        except Exception as e:
            logger.error(f"Error calculating cluster conviction: {e}")
            return 0.0
    
    def _generate_cluster_narrative(self, anomalies: List[Any], anomaly_types: List[str]) -> str:
        """Generate narrative for anomaly cluster"""
        try:
            if len(anomaly_types) == 1:
                return f"Single anomaly type detected: {anomaly_types[0]}"
            
            if 'trade_size' in anomaly_types and 'price_spike' in anomaly_types:
                return "Large institutional trades coinciding with price movement"
            
            if 'options_sweep' in anomaly_types and 'price_spike' in anomaly_types:
                return "Options activity driving price movement"
            
            if 'dark_pool_surge' in anomaly_types:
                return "Elevated off-exchange activity suggesting major move"
            
            if 'volume_spike' in anomaly_types and 'price_spike' in anomaly_types:
                return "High volume price movement indicating strong directional bias"
            
            return f"Multiple anomaly types detected: {', '.join(anomaly_types)}"
            
        except Exception as e:
            logger.error(f"Error generating cluster narrative: {e}")
            return "Anomaly cluster detected"



