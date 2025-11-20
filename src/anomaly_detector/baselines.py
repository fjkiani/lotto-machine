"""
Rolling Baseline Calculator
Maintains rolling statistics for "normal" market behavior
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BaselineStats:
    """Rolling baseline statistics"""
    # Price stats
    price_mean: float = 0.0
    price_std: float = 0.0
    vwap: float = 0.0
    
    # Volume stats
    volume_mean: float = 0.0
    volume_std: float = 0.0
    volume_per_minute: float = 0.0
    
    # Trade size stats
    trade_size_median: float = 0.0
    trade_size_mean: float = 0.0
    trade_size_std: float = 0.0
    
    # Dark pool stats
    dark_volume_ratio: float = 0.0
    
    # Timestamps
    last_updated: datetime = None
    window_start: datetime = None

class RollingBaseline:
    """
    Maintains rolling baselines for anomaly detection
    
    Updates every minute with 30-minute rolling windows
    """
    
    def __init__(self, ticker: str, config: Dict[str, Any]):
        self.ticker = ticker
        self.config = config
        
        # Window sizes (in minutes)
        self.price_window = config.get('price_window_minutes', 30)
        self.volume_window = config.get('volume_window_minutes', 30)
        self.trade_size_window = config.get('trade_size_window_minutes', 30)
        
        # Data buffers
        self.price_buffer = deque(maxlen=self.price_window * 60)  # 1 tick per second max
        self.volume_buffer = deque(maxlen=self.volume_window * 60)
        self.trade_size_buffer = deque(maxlen=self.trade_size_window * 60)
        self.dark_volume_buffer = deque(maxlen=self.volume_window * 60)
        
        # Current stats
        self.current_stats = BaselineStats()
        
        # Update frequency
        self.last_update = datetime.now()
        self.update_interval = timedelta(minutes=1)  # Update every minute
        
        logger.info(f"RollingBaseline initialized for {ticker}")
    
    def update_tick(self, tick_data) -> None:
        """
        Update baseline with new tick data
        """
        try:
            current_time = datetime.now()
            
            # Add to buffers
            self.price_buffer.append({
                'timestamp': tick_data.timestamp,
                'price': tick_data.price,
                'volume': tick_data.volume
            })
            
            self.volume_buffer.append({
                'timestamp': tick_data.timestamp,
                'volume': tick_data.volume
            })
            
            if tick_data.trade_size:
                self.trade_size_buffer.append({
                    'timestamp': tick_data.timestamp,
                    'trade_size': tick_data.trade_size
                })
            
            if tick_data.is_dark_pool:
                self.dark_volume_buffer.append({
                    'timestamp': tick_data.timestamp,
                    'volume': tick_data.volume
                })
            
            # Update stats if enough time has passed
            if current_time - self.last_update >= self.update_interval:
                self._recalculate_stats()
                self.last_update = current_time
                
        except Exception as e:
            logger.error(f"Error updating tick for {self.ticker}: {e}")
    
    def _recalculate_stats(self) -> None:
        """
        Recalculate rolling statistics
        """
        try:
            current_time = datetime.now()
            
            # Price statistics
            if self.price_buffer:
                recent_prices = [
                    tick['price'] for tick in self.price_buffer
                    if current_time - tick['timestamp'] <= timedelta(minutes=self.price_window)
                ]
                
                if recent_prices:
                    self.current_stats.price_mean = np.mean(recent_prices)
                    self.current_stats.price_std = np.std(recent_prices)
                    
                    # Calculate VWAP
                    total_value = sum(tick['price'] * tick['volume'] for tick in self.price_buffer
                                   if current_time - tick['timestamp'] <= timedelta(minutes=self.price_window))
                    total_volume = sum(tick['volume'] for tick in self.price_buffer
                                     if current_time - tick['timestamp'] <= timedelta(minutes=self.price_window))
                    
                    if total_volume > 0:
                        self.current_stats.vwap = total_value / total_volume
            
            # Volume statistics
            if self.volume_buffer:
                recent_volumes = [
                    tick['volume'] for tick in self.volume_buffer
                    if current_time - tick['timestamp'] <= timedelta(minutes=self.volume_window)
                ]
                
                if recent_volumes:
                    self.current_stats.volume_mean = np.mean(recent_volumes)
                    self.current_stats.volume_std = np.std(recent_volumes)
                    
                    # Volume per minute
                    minute_volumes = self._calculate_minute_volumes()
                    if minute_volumes:
                        self.current_stats.volume_per_minute = np.mean(minute_volumes)
            
            # Trade size statistics
            if self.trade_size_buffer:
                recent_trade_sizes = [
                    tick['trade_size'] for tick in self.trade_size_buffer
                    if current_time - tick['timestamp'] <= timedelta(minutes=self.trade_size_window)
                ]
                
                if recent_trade_sizes:
                    self.current_stats.trade_size_median = np.median(recent_trade_sizes)
                    self.current_stats.trade_size_mean = np.mean(recent_trade_sizes)
                    self.current_stats.trade_size_std = np.std(recent_trade_sizes)
            
            # Dark pool ratio
            if self.dark_volume_buffer and self.volume_buffer:
                dark_volume = sum(tick['volume'] for tick in self.dark_volume_buffer
                                if current_time - tick['timestamp'] <= timedelta(minutes=self.volume_window))
                total_volume = sum(tick['volume'] for tick in self.volume_buffer
                                 if current_time - tick['timestamp'] <= timedelta(minutes=self.volume_window))
                
                if total_volume > 0:
                    self.current_stats.dark_volume_ratio = dark_volume / total_volume
            
            # Update timestamps
            self.current_stats.last_updated = current_time
            self.current_stats.window_start = current_time - timedelta(minutes=self.price_window)
            
        except Exception as e:
            logger.error(f"Error recalculating stats for {self.ticker}: {e}")
    
    def _calculate_minute_volumes(self) -> List[float]:
        """
        Calculate volume per minute for recent data
        """
        try:
            minute_volumes = []
            current_time = datetime.now()
            
            # Group ticks by minute
            minute_groups = {}
            
            for tick in self.volume_buffer:
                if current_time - tick['timestamp'] <= timedelta(minutes=self.volume_window):
                    minute_key = tick['timestamp'].replace(second=0, microsecond=0)
                    if minute_key not in minute_groups:
                        minute_groups[minute_key] = 0
                    minute_groups[minute_key] += tick['volume']
            
            minute_volumes = list(minute_groups.values())
            return minute_volumes
            
        except Exception as e:
            logger.error(f"Error calculating minute volumes: {e}")
            return []
    
    def get_price_zscore(self, price: float) -> float:
        """
        Calculate Z-score for price relative to baseline
        """
        if self.current_stats.price_std == 0:
            return 0.0
        
        return (price - self.current_stats.price_mean) / self.current_stats.price_std
    
    def get_volume_zscore(self, volume: float) -> float:
        """
        Calculate Z-score for volume relative to baseline
        """
        if self.current_stats.volume_std == 0:
            return 0.0
        
        return (volume - self.current_stats.volume_mean) / self.current_stats.volume_std
    
    def get_trade_size_multiple(self, trade_size: float) -> float:
        """
        Calculate multiple of median trade size
        """
        if self.current_stats.trade_size_median == 0:
            return 0.0
        
        return trade_size / self.current_stats.trade_size_median
    
    def is_dark_volume_spike(self, current_dark_ratio: float, threshold: float = 0.4) -> bool:
        """
        Check if dark volume ratio is spiking
        """
        return current_dark_ratio > threshold
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current baseline status
        """
        return {
            'ticker': self.ticker,
            'price_mean': self.current_stats.price_mean,
            'price_std': self.current_stats.price_std,
            'vwap': self.current_stats.vwap,
            'volume_mean': self.current_stats.volume_mean,
            'volume_std': self.current_stats.volume_std,
            'volume_per_minute': self.current_stats.volume_per_minute,
            'trade_size_median': self.current_stats.trade_size_median,
            'trade_size_mean': self.current_stats.trade_size_mean,
            'trade_size_std': self.current_stats.trade_size_std,
            'dark_volume_ratio': self.current_stats.dark_volume_ratio,
            'last_updated': self.current_stats.last_updated.isoformat() if self.current_stats.last_updated else None,
            'window_start': self.current_stats.window_start.isoformat() if self.current_stats.window_start else None,
            'buffer_sizes': {
                'price': len(self.price_buffer),
                'volume': len(self.volume_buffer),
                'trade_size': len(self.trade_size_buffer),
                'dark_volume': len(self.dark_volume_buffer)
            }
        }

