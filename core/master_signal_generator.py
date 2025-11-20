#!/usr/bin/env python3
"""
MASTER SIGNAL GENERATOR
- Score all signals based on institutional strength
- Filter to ONLY high-probability moves
- Generate master signals with clear reasoning
- NO NOISE - only the best fucking opportunities
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class SignalScore:
    """Score breakdown for a signal"""
    timestamp: datetime
    price: float
    action: str
    
    # Core scores (0-1)
    dp_level_strength: float  # Based on DP volume
    volume_confirmation: float  # Volume spike magnitude
    momentum_strength: float  # Momentum alignment
    regime_score: float  # Regime favorability
    magnet_interaction: float  # Bounce/break quality
    
    # Total score
    total_score: float
    
    # Context
    dp_level: float
    dp_volume: int
    interaction_type: str  # BOUNCE, BREAK, REJECTION
    reasoning: str

@dataclass
class MasterSignal:
    """Master signal - ONLY the best opportunities"""
    timestamp: datetime
    action: str  # BUY or SELL
    price: float
    confidence: float  # 0-1
    
    # Why this is a master signal
    primary_reason: str
    supporting_factors: List[str]
    
    # Risk/reward
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    
    # Context
    dp_level: float
    dp_volume: int
    regime: str
    
    # Full scoring breakdown
    score_breakdown: SignalScore

class MasterSignalGenerator:
    """Generate master signals from raw signals"""
    
    def __init__(self):
        # Master signal threshold - only top signals
        self.master_threshold = 0.75  # 75%+ score required
        
        # Scoring weights
        self.weights = {
            'dp_strength': 0.35,      # 35% - most important
            'volume': 0.25,           # 25% - confirmation critical
            'momentum': 0.20,         # 20% - direction matters
            'regime': 0.10,           # 10% - context
            'magnet_interaction': 0.10  # 10% - bounce/break quality
        }
        
        # Battleground threshold (>1M shares)
        self.battleground_volume = 1000000
        
        logger.info("🎯 Master Signal Generator initialized")
        logger.info(f"   Master threshold: {self.master_threshold:.0%}")
    
    def score_signal(self, timestamp: datetime, price: float, action: str,
                    dp_level: float, dp_volume: int, 
                    volume_vs_avg: float, volume_confirmed: bool,
                    momentum: float, momentum_confirmed: bool,
                    regime: str, magnet_alerts: List[str],
                    confidence: float) -> SignalScore:
        """
        Score a signal on 0-1 scale
        """
        # 1. DP Level Strength (0-1)
        # Battlegrounds (>1M) = 1.0, scale down for smaller levels
        if dp_volume >= self.battleground_volume:
            dp_strength = 1.0
        else:
            dp_strength = min(dp_volume / self.battleground_volume, 0.9)
        
        # 2. Volume Confirmation (0-1)
        # Scale based on how much above average
        if volume_vs_avg >= 3.0:
            volume_score = 1.0
        elif volume_vs_avg >= 2.0:
            volume_score = 0.8
        elif volume_vs_avg >= 1.5:
            volume_score = 0.6
        else:
            volume_score = 0.3 if volume_confirmed else 0.0
        
        # 3. Momentum Strength (0-1)
        # Strong momentum = high score
        abs_momentum = abs(momentum)
        if abs_momentum >= 0.01:  # 1%+ momentum
            momentum_score = 1.0
        elif abs_momentum >= 0.005:  # 0.5%+
            momentum_score = 0.7
        elif momentum_confirmed:
            momentum_score = 0.5
        else:
            momentum_score = 0.2
        
        # 4. Regime Score (0-1)
        # BUY signals: favor UPTREND/RANGE
        # SELL signals: favor DOWNTREND/RANGE
        if action == "BUY":
            regime_map = {"UPTREND": 1.0, "RANGE": 0.8, "CHOP": 0.5, "DOWNTREND": 0.3}
        else:
            regime_map = {"DOWNTREND": 1.0, "RANGE": 0.8, "CHOP": 0.5, "UPTREND": 0.3}
        
        regime_score = regime_map.get(regime, 0.5)
        
        # 5. Magnet Interaction (0-1)
        # BOUNCING/BREAKING = high, STALLING/AT_LEVEL = medium, APPROACHING = low
        magnet_score = 0.5  # Default
        interaction_type = "NONE"
        
        if magnet_alerts:
            for alert in magnet_alerts:
                if "BOUNCING" in alert:
                    magnet_score = 1.0
                    interaction_type = "BOUNCE"
                    break
                elif "BREAKING" in alert:
                    magnet_score = 1.0
                    interaction_type = "BREAK"
                    break
                elif "REJECTING" in alert:
                    magnet_score = 0.3
                    interaction_type = "REJECTION"
                elif "STALLING" in alert:
                    magnet_score = 0.4
                    interaction_type = "STALL"
                elif "AT" in alert and "magnet" in alert:
                    magnet_score = 0.5
                    interaction_type = "AT_LEVEL"
        
        # Calculate weighted total
        total = (
            dp_strength * self.weights['dp_strength'] +
            volume_score * self.weights['volume'] +
            momentum_score * self.weights['momentum'] +
            regime_score * self.weights['regime'] +
            magnet_score * self.weights['magnet_interaction']
        )
        
        # Build reasoning
        reasons = []
        if dp_volume >= self.battleground_volume:
            reasons.append(f"BATTLEGROUND (${dp_level:.2f} w/ {dp_volume:,} shares)")
        if volume_vs_avg >= 2.0:
            reasons.append(f"VOLUME SURGE ({volume_vs_avg:.1f}x avg)")
        if abs_momentum >= 0.005:
            reasons.append(f"STRONG MOMENTUM ({momentum:+.2%})")
        if interaction_type in ["BOUNCE", "BREAK"]:
            reasons.append(f"{interaction_type} at DP level")
        
        reasoning = " + ".join(reasons) if reasons else "Standard signal"
        
        return SignalScore(
            timestamp=timestamp,
            price=price,
            action=action,
            dp_level_strength=dp_strength,
            volume_confirmation=volume_score,
            momentum_strength=momentum_score,
            regime_score=regime_score,
            magnet_interaction=magnet_score,
            total_score=total,
            dp_level=dp_level,
            dp_volume=dp_volume,
            interaction_type=interaction_type,
            reasoning=reasoning
        )
    
    def generate_master_signal(self, score: SignalScore, 
                               regime: str) -> Optional[MasterSignal]:
        """
        Generate a master signal if score exceeds threshold
        """
        if score.total_score < self.master_threshold:
            return None
        
        # Calculate stop loss and take profit
        if score.action == "BUY":
            # Stop loss: below DP level
            stop_loss = score.dp_level * 0.997  # 0.3% below
            # Take profit: 2:1 risk/reward minimum
            risk = score.price - stop_loss
            take_profit = score.price + (risk * 2)
        else:
            # SELL logic
            stop_loss = score.dp_level * 1.003  # 0.3% above
            risk = stop_loss - score.price
            take_profit = score.price - (risk * 2)
        
        risk_reward = abs(take_profit - score.price) / abs(score.price - stop_loss)
        
        # Build primary reason
        if score.dp_volume >= self.battleground_volume and score.interaction_type == "BOUNCE":
            primary_reason = f"INSTITUTIONAL BOUNCE at ${score.dp_level:.2f} battleground ({score.dp_volume:,} shares)"
        elif score.dp_volume >= self.battleground_volume and score.interaction_type == "BREAK":
            primary_reason = f"INSTITUTIONAL BREAKOUT through ${score.dp_level:.2f} battleground ({score.dp_volume:,} shares)"
        elif score.interaction_type == "BOUNCE":
            primary_reason = f"Strong bounce off DP level ${score.dp_level:.2f}"
        elif score.interaction_type == "BREAK":
            primary_reason = f"Breakout through DP level ${score.dp_level:.2f}"
        else:
            primary_reason = f"High-probability setup at ${score.dp_level:.2f}"
        
        # Supporting factors
        supporting = []
        if score.volume_confirmation >= 0.8:
            supporting.append(f"Heavy volume confirmation")
        if score.momentum_strength >= 0.7:
            supporting.append(f"Strong directional momentum")
        if score.regime_score >= 0.8:
            supporting.append(f"Favorable regime ({regime})")
        
        return MasterSignal(
            timestamp=score.timestamp,
            action=score.action,
            price=score.price,
            confidence=score.total_score,
            primary_reason=primary_reason,
            supporting_factors=supporting,
            entry_price=score.price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward,
            dp_level=score.dp_level,
            dp_volume=score.dp_volume,
            regime=regime,
            score_breakdown=score
        )
    
    def filter_to_master_signals(self, all_signals: List[dict]) -> List[MasterSignal]:
        """
        Filter all signals down to master signals only
        
        Args:
            all_signals: List of signal dicts with all data
        
        Returns:
            List of MasterSignal objects
        """
        master_signals = []
        
        for sig in all_signals:
            # Score the signal
            score = self.score_signal(
                timestamp=sig['timestamp'],
                price=sig['price'],
                action=sig['action'],
                dp_level=sig.get('dp_level', 0),
                dp_volume=sig.get('dp_volume', 0),
                volume_vs_avg=sig.get('volume_vs_avg', 1.0),
                volume_confirmed=sig.get('volume_confirmed', False),
                momentum=sig.get('momentum', 0),
                momentum_confirmed=sig.get('momentum_confirmed', False),
                regime=sig.get('regime', 'UNKNOWN'),
                magnet_alerts=sig.get('magnet_alerts', []),
                confidence=sig.get('confidence', 0)
            )
            
            # Generate master signal if qualified
            master = self.generate_master_signal(score, sig.get('regime', 'UNKNOWN'))
            
            if master:
                master_signals.append(master)
                
                logger.info(f"🎯 MASTER SIGNAL: {master.action} @ ${master.price:.2f}")
                logger.info(f"   {master.primary_reason}")
                logger.info(f"   Confidence: {master.confidence:.0%} | Score: {score.total_score:.2f}")
                logger.info(f"   Entry: ${master.entry_price:.2f} | Stop: ${master.stop_loss:.2f} | Target: ${master.take_profit:.2f}")
                logger.info(f"   Risk/Reward: 1:{master.risk_reward_ratio:.1f}")
        
        logger.info("")
        logger.info(f"📊 MASTER SIGNAL SUMMARY:")
        logger.info(f"   Total signals evaluated: {len(all_signals)}")
        logger.info(f"   Master signals generated: {len(master_signals)}")
        logger.info(f"   Filter rate: {len(master_signals)/len(all_signals)*100:.1f}% passed")
        
        return master_signals
    
    def get_rejection_summary(self, all_signals: List[dict]) -> dict:
        """Analyze why signals were rejected"""
        rejections = {
            'low_dp_strength': 0,
            'no_volume': 0,
            'weak_momentum': 0,
            'poor_regime': 0,
            'no_magnet_interaction': 0,
            'total_rejected': 0
        }
        
        for sig in all_signals:
            score = self.score_signal(
                timestamp=sig['timestamp'],
                price=sig['price'],
                action=sig['action'],
                dp_level=sig.get('dp_level', 0),
                dp_volume=sig.get('dp_volume', 0),
                volume_vs_avg=sig.get('volume_vs_avg', 1.0),
                volume_confirmed=sig.get('volume_confirmed', False),
                momentum=sig.get('momentum', 0),
                momentum_confirmed=sig.get('momentum_confirmed', False),
                regime=sig.get('regime', 'UNKNOWN'),
                magnet_alerts=sig.get('magnet_alerts', []),
                confidence=sig.get('confidence', 0)
            )
            
            if score.total_score < self.master_threshold:
                rejections['total_rejected'] += 1
                
                # Find weakest factor
                if score.dp_level_strength < 0.5:
                    rejections['low_dp_strength'] += 1
                if score.volume_confirmation < 0.5:
                    rejections['no_volume'] += 1
                if score.momentum_strength < 0.5:
                    rejections['weak_momentum'] += 1
                if score.regime_score < 0.5:
                    rejections['poor_regime'] += 1
                if score.magnet_interaction < 0.5:
                    rejections['no_magnet_interaction'] += 1
        
        return rejections



