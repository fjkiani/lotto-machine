#!/usr/bin/env python3
"""
RIGOROUS DP MAGNET INTERACTION ENGINE
- Track approach/interaction with major DP levels ONLY
- Require BOTH price AND institutional flow confirmation
- NEVER act on first touch - wait for confirmed reaction
- Adaptive stops outside battlefield zones
- Regime-aware thresholds
- Complete cycle-by-cycle audit trail
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class DPMagnetLevel:
    """Major DP level (battleground)"""
    price: float
    volume: int
    is_battleground: bool  # >1M shares
    
    # Interaction tracking
    first_touch_time: Optional[datetime] = None
    touch_count: int = 0
    confirmed_bounces: int = 0
    confirmed_breaks: int = 0
    
    # For adaptive stops
    battlefield_zone_pct: float = 0.003  # 0.3% zone around level

@dataclass
class MagnetInteraction:
    """Record of price interacting with DP magnet"""
    timestamp: datetime
    level: DPMagnetLevel
    interaction_type: str  # FIRST_TOUCH, TESTING, BOUNCE, BREAK, REJECTION
    
    # Price action
    price: float
    distance_pct: float
    approach_velocity: float  # $/minute
    
    # Confirmation metrics
    volume_vs_avg: float
    volume_confirmed: bool
    momentum: float
    momentum_confirmed: bool
    
    # Candle characteristics
    candle_type: str  # REVERSAL, CONTINUATION, DOJI, etc
    close_position: float  # Where close is in candle range (0-1)
    
    # Decision
    is_actionable: bool
    reasoning: str

@dataclass
class RigorousSignal:
    """Signal with full confirmation and risk management"""
    timestamp: datetime
    action: str  # BUY or SELL
    entry_price: float
    
    # DP context
    dp_level: float
    dp_volume: int
    interaction_type: str  # BOUNCE or BREAK
    touch_count: int  # How many times we've touched this level
    
    # Confirmation
    volume_vs_avg: float
    momentum: float
    flow_confirmed: bool
    
    # Risk management
    stop_loss: float  # Outside battlefield zone
    take_profit: float
    risk_reward_ratio: float
    
    # Regime context
    regime: str
    regime_confidence: float
    
    # Entry quality
    entry_quality: str  # CLEAN_BREAK, STRONG_BOUNCE, etc
    confidence: float
    
    # Full reasoning
    primary_reason: str
    supporting_factors: List[str]
    warning_factors: List[str]

class RigorousDPEngine:
    """Rigorous DP-aware signal engine with institutional flow confirmation"""
    
    def __init__(self, dp_levels_df):
        """
        Initialize with DP levels
        
        Args:
            dp_levels_df: DataFrame with 'level' and 'volume' columns
        """
        # Only track battlegrounds (>1M shares) and major levels (>500K)
        self.battleground_threshold = 1000000
        self.major_level_threshold = 500000
        
        # Create magnet levels
        self.magnets = []
        for _, row in dp_levels_df.iterrows():
            vol = int(row['volume'])
            if vol >= self.major_level_threshold:
                magnet = DPMagnetLevel(
                    price=float(row['level']),
                    volume=vol,
                    is_battleground=(vol >= self.battleground_threshold)
                )
                self.magnets.append(magnet)
        
        # Sort by volume (most significant first)
        self.magnets.sort(key=lambda m: m.volume, reverse=True)
        
        # Regime-aware thresholds
        self.regime_params = {
            'UPTREND': {
                'distance_threshold': 0.002,  # 0.2% - tighter
                'volume_multiplier': 1.5,
                'momentum_threshold': 0.003,
                'confirmation_required': 'medium'
            },
            'DOWNTREND': {
                'distance_threshold': 0.002,
                'volume_multiplier': 1.5,
                'momentum_threshold': 0.003,
                'confirmation_required': 'medium'
            },
            'RANGE': {
                'distance_threshold': 0.003,  # 0.3% - normal
                'volume_multiplier': 1.8,
                'momentum_threshold': 0.004,
                'confirmation_required': 'high'
            },
            'CHOP': {
                'distance_threshold': 0.004,  # 0.4% - wider
                'volume_multiplier': 2.0,
                'momentum_threshold': 0.005,
                'confirmation_required': 'very_high'
            },
            'INSUFFICIENT_DATA': {
                'distance_threshold': 0.003,
                'volume_multiplier': 2.0,
                'momentum_threshold': 0.005,
                'confirmation_required': 'very_high'
            }
        }
        
        # Price history for velocity calculation
        self.price_history = []
        self.max_history = 10
        
        # Interaction tracking
        self.all_interactions = []
        
        logger.info("🎯 Rigorous DP Engine initialized")
        logger.info(f"   Battlegrounds (>1M): {sum(1 for m in self.magnets if m.is_battleground)}")
        logger.info(f"   Major levels (>500K): {len(self.magnets)}")
    
    def _find_nearest_magnet(self, price: float, regime: str) -> Optional[DPMagnetLevel]:
        """Find nearest major DP level within threshold"""
        params = self.regime_params.get(regime, self.regime_params['RANGE'])
        threshold = params['distance_threshold']
        
        closest = None
        min_distance = float('inf')
        
        for magnet in self.magnets:
            distance_pct = abs(magnet.price - price) / price
            if distance_pct <= threshold and distance_pct < min_distance:
                closest = magnet
                min_distance = distance_pct
        
        return closest
    
    def _calculate_approach_velocity(self) -> float:
        """Calculate price velocity ($/minute)"""
        if len(self.price_history) < 3:
            return 0.0
        
        prices = np.array([h['price'] for h in self.price_history[-5:]])
        times = np.arange(len(prices))
        
        if len(prices) > 1:
            slope = np.polyfit(times, prices, 1)[0]
            return slope
        return 0.0
    
    def _analyze_candle(self, open_price: float, high: float, low: float, close: float) -> tuple:
        """Analyze candle characteristics"""
        candle_range = high - low
        if candle_range < 0.01:
            return "DOJI", 0.5
        
        # Where is close in the range?
        close_position = (close - low) / candle_range if candle_range > 0 else 0.5
        
        # Determine candle type
        body_size = abs(close - open_price)
        body_pct = body_size / candle_range if candle_range > 0 else 0
        
        if close > open_price and close_position > 0.7 and body_pct > 0.5:
            return "STRONG_BULLISH", close_position
        elif close < open_price and close_position < 0.3 and body_pct > 0.5:
            return "STRONG_BEARISH", close_position
        elif close > open_price and close_position > 0.5:
            return "BULLISH", close_position
        elif close < open_price and close_position < 0.5:
            return "BEARISH", close_position
        elif body_pct < 0.3:
            return "DOJI", close_position
        else:
            return "NEUTRAL", close_position
    
    def _check_flow_confirmation(self, volume_vs_avg: float, momentum: float,
                                 regime: str, magnet: DPMagnetLevel,
                                 is_bounce: bool) -> tuple:
        """Check if we have institutional flow confirmation"""
        params = self.regime_params.get(regime, self.regime_params['RANGE'])
        
        # Volume confirmation
        volume_confirmed = volume_vs_avg >= params['volume_multiplier']
        
        # Momentum confirmation (direction matters)
        if is_bounce:
            # For bounce, need positive momentum
            momentum_confirmed = momentum >= params['momentum_threshold']
        else:
            # For break, need strong momentum in break direction
            momentum_confirmed = abs(momentum) >= params['momentum_threshold']
        
        # Flow confirmed = BOTH volume AND momentum
        flow_confirmed = volume_confirmed and momentum_confirmed
        
        return volume_confirmed, momentum_confirmed, flow_confirmed
    
    def process_bar(self, timestamp: datetime, open_price: float, high: float,
                   low: float, close: float, volume: int, avg_volume: float,
                   momentum: float, regime: str) -> Optional[RigorousSignal]:
        """
        Process a single bar and potentially generate signal
        
        Returns:
            RigorousSignal if actionable, None otherwise
        """
        # Add to price history
        self.price_history.append({
            'timestamp': timestamp,
            'price': close,
            'open': open_price,
            'high': high,
            'low': low,
            'volume': volume
        })
        if len(self.price_history) > self.max_history:
            self.price_history.pop(0)
        
        # Find nearest magnet
        magnet = self._find_nearest_magnet(close, regime)
        
        if not magnet:
            return None  # Not near any major DP level
        
        # Calculate metrics
        distance_pct = abs(magnet.price - close) / close
        approach_velocity = self._calculate_approach_velocity()
        volume_vs_avg = volume / avg_volume if avg_volume > 0 else 1.0
        
        # Analyze candle
        candle_type, close_position = self._analyze_candle(open_price, high, low, close)
        
        # Determine interaction type
        is_first_touch = magnet.first_touch_time is None
        
        if is_first_touch:
            magnet.first_touch_time = timestamp
            magnet.touch_count = 1
            interaction_type = "FIRST_TOUCH"
            is_actionable = False
            reasoning = "First touch - waiting for confirmation"
        
        else:
            magnet.touch_count += 1
            
            # Check if this is a bounce or break
            is_near_level = distance_pct <= self.regime_params[regime]['distance_threshold']
            
            if not is_near_level:
                return None  # Moved away from level
            
            # Determine if bouncing or breaking
            if magnet.price < close:
                # Price above magnet = potential support bounce
                is_bounce = True
                volume_conf, momentum_conf, flow_conf = self._check_flow_confirmation(
                    volume_vs_avg, momentum, regime, magnet, is_bounce=True
                )
                
                if flow_conf and candle_type in ["STRONG_BULLISH", "BULLISH"]:
                    interaction_type = "BOUNCE"
                    is_actionable = True
                    magnet.confirmed_bounces += 1
                else:
                    interaction_type = "TESTING"
                    is_actionable = False
            
            else:
                # Price below magnet = potential resistance rejection or break
                is_bounce = False
                volume_conf, momentum_conf, flow_conf = self._check_flow_confirmation(
                    volume_vs_avg, momentum, regime, magnet, is_bounce=False
                )
                
                # Check for clean break (close >0.2% above level)
                clean_break = close > (magnet.price * 1.002)
                
                if flow_conf and clean_break and candle_type in ["STRONG_BULLISH", "BULLISH"]:
                    interaction_type = "BREAK"
                    is_actionable = True
                    magnet.confirmed_breaks += 1
                elif candle_type in ["STRONG_BEARISH", "BEARISH"]:
                    interaction_type = "REJECTION"
                    is_actionable = False
                else:
                    interaction_type = "TESTING"
                    is_actionable = False
            
            reasoning = self._build_reasoning(
                interaction_type, magnet, volume_vs_avg, momentum,
                volume_conf, momentum_conf, flow_conf, candle_type
            )
        
        # Record interaction
        interaction = MagnetInteraction(
            timestamp=timestamp,
            level=magnet,
            interaction_type=interaction_type,
            price=close,
            distance_pct=distance_pct,
            approach_velocity=approach_velocity,
            volume_vs_avg=volume_vs_avg,
            volume_confirmed=volume_conf if not is_first_touch else False,
            momentum=momentum,
            momentum_confirmed=momentum_conf if not is_first_touch else False,
            candle_type=candle_type,
            close_position=close_position,
            is_actionable=is_actionable,
            reasoning=reasoning
        )
        
        self.all_interactions.append(interaction)
        
        # Generate signal if actionable
        if is_actionable:
            return self._generate_signal(interaction, regime)
        
        return None
    
    def _build_reasoning(self, interaction_type: str, magnet: DPMagnetLevel,
                        volume_vs_avg: float, momentum: float,
                        volume_conf: bool, momentum_conf: bool,
                        flow_conf: bool, candle_type: str) -> str:
        """Build detailed reasoning string"""
        reasons = []
        
        if interaction_type == "FIRST_TOUCH":
            return "First touch - waiting for confirmation"
        
        reasons.append(f"{interaction_type} at ${magnet.price:.2f}")
        
        if magnet.is_battleground:
            reasons.append(f"BATTLEGROUND ({magnet.volume:,} shares)")
        else:
            reasons.append(f"Major level ({magnet.volume:,} shares)")
        
        if volume_conf:
            reasons.append(f"Volume {volume_vs_avg:.1f}x avg ✅")
        else:
            reasons.append(f"Volume {volume_vs_avg:.1f}x avg ❌")
        
        if momentum_conf:
            reasons.append(f"Momentum {momentum:+.2%} ✅")
        else:
            reasons.append(f"Momentum {momentum:+.2%} ❌")
        
        reasons.append(f"Candle: {candle_type}")
        
        if flow_conf:
            reasons.append("FLOW CONFIRMED ✅")
        else:
            reasons.append("No flow confirmation ❌")
        
        return " | ".join(reasons)
    
    def _generate_signal(self, interaction: MagnetInteraction, regime: str) -> RigorousSignal:
        """Generate rigorous signal with full risk management"""
        magnet = interaction.level
        
        # Determine action
        if interaction.interaction_type == "BOUNCE":
            action = "BUY"
            # Stop OUTSIDE battlefield zone (below)
            stop_loss = magnet.price * (1 - magnet.battlefield_zone_pct - 0.001)
            # Target: 2:1 R/R minimum
            risk = interaction.price - stop_loss
            take_profit = interaction.price + (risk * 2.0)
            entry_quality = "STRONG_BOUNCE" if magnet.is_battleground else "BOUNCE"
        
        else:  # BREAK
            action = "BUY"
            # Stop OUTSIDE battlefield zone (below breakout level)
            stop_loss = magnet.price * (1 - magnet.battlefield_zone_pct)
            # Target: 2:1 R/R
            risk = interaction.price - stop_loss
            take_profit = interaction.price + (risk * 2.0)
            entry_quality = "CLEAN_BREAK" if magnet.is_battleground else "BREAK"
        
        risk_reward = abs(take_profit - interaction.price) / abs(interaction.price - stop_loss)
        
        # Build primary reason
        if magnet.is_battleground and interaction.interaction_type == "BOUNCE":
            primary = f"INSTITUTIONAL BOUNCE off ${magnet.price:.2f} battleground ({magnet.volume:,} shares)"
        elif magnet.is_battleground and interaction.interaction_type == "BREAK":
            primary = f"CLEAN BREAKOUT through ${magnet.price:.2f} battleground ({magnet.volume:,} shares)"
        elif interaction.interaction_type == "BOUNCE":
            primary = f"Confirmed bounce off ${magnet.price:.2f} major level ({magnet.volume:,} shares)"
        else:
            primary = f"Breakout through ${magnet.price:.2f} major level ({magnet.volume:,} shares)"
        
        # Supporting factors
        supporting = []
        if interaction.volume_vs_avg >= 2.0:
            supporting.append(f"Heavy volume ({interaction.volume_vs_avg:.1f}x avg)")
        if abs(interaction.momentum) >= 0.005:
            supporting.append(f"Strong momentum ({interaction.momentum:+.2%})")
        if interaction.candle_type in ["STRONG_BULLISH", "STRONG_BEARISH"]:
            supporting.append(f"Decisive candle ({interaction.candle_type})")
        if magnet.touch_count >= 2:
            supporting.append(f"Tested {magnet.touch_count}x")
        
        # Warning factors
        warnings = []
        if regime == "CHOP":
            warnings.append("Choppy regime - tighter risk management")
        if interaction.volume_vs_avg < 1.8:
            warnings.append("Moderate volume - watch for follow-through")
        
        # Confidence calculation
        confidence = 0.7  # Base
        if magnet.is_battleground:
            confidence += 0.15
        if interaction.volume_vs_avg >= 2.0:
            confidence += 0.10
        if abs(interaction.momentum) >= 0.005:
            confidence += 0.05
        
        confidence = min(confidence, 0.95)
        
        return RigorousSignal(
            timestamp=interaction.timestamp,
            action=action,
            entry_price=interaction.price,
            dp_level=magnet.price,
            dp_volume=magnet.volume,
            interaction_type=interaction.interaction_type,
            touch_count=magnet.touch_count,
            volume_vs_avg=interaction.volume_vs_avg,
            momentum=interaction.momentum,
            flow_confirmed=True,  # Only generated if flow confirmed
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward,
            regime=regime,
            regime_confidence=0.8,  # TODO: calculate from regime detection
            entry_quality=entry_quality,
            confidence=confidence,
            primary_reason=primary,
            supporting_factors=supporting,
            warning_factors=warnings
        )
    
    def get_interaction_summary(self) -> Dict[str, Any]:
        """Get summary of all magnet interactions"""
        summary = {
            'total_interactions': len(self.all_interactions),
            'first_touches': sum(1 for i in self.all_interactions if i.interaction_type == "FIRST_TOUCH"),
            'testing': sum(1 for i in self.all_interactions if i.interaction_type == "TESTING"),
            'bounces': sum(1 for i in self.all_interactions if i.interaction_type == "BOUNCE"),
            'breaks': sum(1 for i in self.all_interactions if i.interaction_type == "BREAK"),
            'rejections': sum(1 for i in self.all_interactions if i.interaction_type == "REJECTION"),
            'actionable': sum(1 for i in self.all_interactions if i.is_actionable)
        }
        
        return summary

