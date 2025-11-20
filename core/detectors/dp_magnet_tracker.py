#!/usr/bin/env python3
"""
DP MAGNET TRACKER
- Track price approaching institutional DP levels
- Calculate approach velocity and ETA
- Detect bounces, breaks, and rejections
- Predictive alerting BEFORE price hits
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class MagnetAlert:
    """Alert for approaching DP magnet"""
    timestamp: datetime
    price: float
    magnet_level: float
    magnet_volume: int
    distance: float
    distance_pct: float
    approach_velocity: float  # $/minute
    eta_minutes: Optional[float]
    alert_type: str  # APPROACHING, AT_LEVEL, BOUNCING, BREAKING, REJECTING
    strength: float  # 0-1 based on volume
    
@dataclass
class LevelInteraction:
    """Record of price interacting with DP level"""
    timestamp: datetime
    level: float
    level_volume: int
    price_before: float
    price_at: float
    price_after: float
    volume_spike: bool
    momentum_before: float
    momentum_after: float
    interaction_type: str  # BOUNCE, BREAK, REJECT, STALL
    success: bool  # Did it bounce/break as expected?

class DPMagnetTracker:
    """Track DP magnet interactions and predict approaches"""
    
    def __init__(self, dp_levels: List[Tuple[float, int]]):
        """
        Initialize tracker with DP levels
        
        Args:
            dp_levels: List of (price, volume) tuples
        """
        # Sort levels by volume (most significant first)
        self.dp_levels = sorted(dp_levels, key=lambda x: x[1], reverse=True)
        
        # Track active magnets (within 2% of price)
        self.active_magnets = []
        
        # History of level interactions
        self.interaction_history = []
        
        # Price history for velocity calculation
        self.price_history = []
        self.max_history = 10  # Keep last 10 bars
        
        # Alert thresholds
        self.approach_threshold = 0.02  # 2% = approaching
        self.at_level_threshold = 0.003  # 0.3% = at level
        self.bounce_window = 3  # 3 bars to confirm bounce
        
        logger.info(f"🧲 Magnet Tracker initialized with {len(self.dp_levels)} levels")
    
    def update(self, timestamp: datetime, price: float, volume: int, 
               momentum: float) -> List[MagnetAlert]:
        """
        Update tracker with new price bar
        
        Returns:
            List of MagnetAlert objects
        """
        # Add to price history
        self.price_history.append({
            'timestamp': timestamp,
            'price': price,
            'volume': volume,
            'momentum': momentum
        })
        
        # Keep only recent history
        if len(self.price_history) > self.max_history:
            self.price_history.pop(0)
        
        # Find active magnets
        self.active_magnets = self._find_active_magnets(price)
        
        # Generate alerts
        alerts = []
        for level, level_volume in self.active_magnets:
            alert = self._analyze_magnet(timestamp, price, volume, momentum, 
                                         level, level_volume)
            if alert:
                alerts.append(alert)
        
        return alerts
    
    def _find_active_magnets(self, price: float) -> List[Tuple[float, int]]:
        """Find DP levels within approach threshold"""
        active = []
        for level, volume in self.dp_levels:
            distance_pct = abs(level - price) / price
            if distance_pct <= self.approach_threshold:
                active.append((level, volume))
        return active
    
    def _calculate_approach_velocity(self) -> float:
        """Calculate price velocity ($/minute)"""
        if len(self.price_history) < 2:
            return 0.0
        
        # Linear regression over recent history
        prices = np.array([h['price'] for h in self.price_history])
        times = np.arange(len(prices))
        
        # Fit line: price = slope * time + intercept
        if len(prices) > 1:
            slope = np.polyfit(times, prices, 1)[0]
            return slope
        return 0.0
    
    def _calculate_eta(self, price: float, level: float, velocity: float) -> Optional[float]:
        """Calculate ETA to level in minutes"""
        if abs(velocity) < 0.01:  # Too slow to calculate
            return None
        
        distance = level - price
        
        # Check if moving toward level
        if (distance > 0 and velocity > 0) or (distance < 0 and velocity < 0):
            eta = abs(distance / velocity)
            return eta if eta < 100 else None  # Cap at 100 minutes
        
        return None  # Moving away
    
    def _detect_bounce(self, price: float, level: float, momentum: float) -> bool:
        """Detect if price is bouncing off level"""
        if len(self.price_history) < self.bounce_window:
            return False
        
        # Check if we touched the level and reversed
        recent = self.price_history[-self.bounce_window:]
        
        # For support: prices should be rising after touching
        if level < price:
            touched = any(abs(h['price'] - level) / level < 0.002 for h in recent)
            rising = momentum > 0 and recent[-1]['price'] > recent[0]['price']
            return touched and rising
        
        # For resistance: prices should be falling after touching
        else:
            touched = any(abs(h['price'] - level) / level < 0.002 for h in recent)
            falling = momentum < 0 and recent[-1]['price'] < recent[0]['price']
            return touched and falling
        
        return False
    
    def _detect_break(self, price: float, level: float, momentum: float) -> bool:
        """Detect if price is breaking through level"""
        if len(self.price_history) < 2:
            return False
        
        # Check if we crossed the level with strong momentum
        prev_price = self.price_history[-2]['price']
        
        # Breaking above resistance
        if prev_price < level and price > level:
            return momentum > 0.005  # Strong upward momentum
        
        # Breaking below support
        if prev_price > level and price < level:
            return momentum < -0.005  # Strong downward momentum
        
        return False
    
    def _detect_rejection(self, price: float, level: float, momentum: float) -> bool:
        """Detect if price is rejecting from level"""
        if len(self.price_history) < 3:
            return False
        
        # Check if we approached level but reversed before touching
        recent = self.price_history[-3:]
        
        # For resistance: approached but rejected down
        if level > price:
            closest = min(recent, key=lambda h: abs(h['price'] - level))
            closest_dist = abs(closest['price'] - level) / level
            
            if closest_dist < 0.005:  # Got within 0.5%
                return momentum < 0 and price < closest['price']
        
        # For support: approached but rejected up
        else:
            closest = min(recent, key=lambda h: abs(h['price'] - level))
            closest_dist = abs(closest['price'] - level) / level
            
            if closest_dist < 0.005:  # Got within 0.5%
                return momentum > 0 and price > closest['price']
        
        return False
    
    def _analyze_magnet(self, timestamp: datetime, price: float, volume: int,
                       momentum: float, level: float, level_volume: int) -> Optional[MagnetAlert]:
        """Analyze interaction with a specific magnet"""
        distance = level - price
        distance_pct = distance / price
        
        # Calculate approach velocity
        velocity = self._calculate_approach_velocity()
        eta = self._calculate_eta(price, level, velocity)
        
        # Determine alert type
        alert_type = None
        
        # At level (within 0.3%)
        if abs(distance_pct) < self.at_level_threshold:
            if self._detect_bounce(price, level, momentum):
                alert_type = "BOUNCING"
            elif self._detect_break(price, level, momentum):
                alert_type = "BREAKING"
            elif abs(momentum) < 0.001:
                alert_type = "STALLING"
            else:
                alert_type = "AT_LEVEL"
        
        # Approaching (within 2%)
        elif abs(distance_pct) < self.approach_threshold:
            if self._detect_rejection(price, level, momentum):
                alert_type = "REJECTING"
            else:
                alert_type = "APPROACHING"
        
        if not alert_type:
            return None
        
        # Calculate strength based on volume
        max_volume = max(v for _, v in self.dp_levels)
        strength = min(level_volume / max_volume, 1.0)
        
        return MagnetAlert(
            timestamp=timestamp,
            price=price,
            magnet_level=level,
            magnet_volume=level_volume,
            distance=distance,
            distance_pct=distance_pct,
            approach_velocity=velocity,
            eta_minutes=eta,
            alert_type=alert_type,
            strength=strength
        )
    
    def record_interaction(self, timestamp: datetime, level: float, 
                          level_volume: int, interaction_type: str,
                          success: bool):
        """Record a level interaction for learning"""
        if len(self.price_history) < 3:
            return
        
        interaction = LevelInteraction(
            timestamp=timestamp,
            level=level,
            level_volume=level_volume,
            price_before=self.price_history[-3]['price'],
            price_at=self.price_history[-2]['price'],
            price_after=self.price_history[-1]['price'],
            volume_spike=self.price_history[-2]['volume'] > self.price_history[-3]['volume'] * 1.5,
            momentum_before=self.price_history[-3]['momentum'],
            momentum_after=self.price_history[-1]['momentum'],
            interaction_type=interaction_type,
            success=success
        )
        
        self.interaction_history.append(interaction)
        
        logger.info(f"📝 Recorded {interaction_type} at ${level:.2f} - Success: {success}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics on level interactions"""
        if not self.interaction_history:
            return {}
        
        total = len(self.interaction_history)
        bounces = sum(1 for i in self.interaction_history if i.interaction_type == "BOUNCE")
        breaks = sum(1 for i in self.interaction_history if i.interaction_type == "BREAK")
        rejections = sum(1 for i in self.interaction_history if i.interaction_type == "REJECT")
        
        successful = sum(1 for i in self.interaction_history if i.success)
        
        return {
            'total_interactions': total,
            'bounces': bounces,
            'breaks': breaks,
            'rejections': rejections,
            'success_rate': successful / total if total > 0 else 0,
            'bounce_success': sum(1 for i in self.interaction_history 
                                 if i.interaction_type == "BOUNCE" and i.success) / bounces if bounces > 0 else 0,
            'break_success': sum(1 for i in self.interaction_history 
                                if i.interaction_type == "BREAK" and i.success) / breaks if breaks > 0 else 0
        }



