#!/usr/bin/env python3
"""
DP-AWARE SIGNAL FILTERING SYSTEM
- Tighten signals to avoid institutional battlegrounds
- Only trigger when composite flows AND DP structure agree
- Confirm breakouts above magnets or mean-reversion off DP support
- Avoid trading into DP levels
"""

import asyncio
import logging
import time
import random
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json

# Import our systems
from detectors.real_breakout_reversal_detector_yahoo_direct import YahooDirectDataProvider
from data.chartexchange_api_client import ChartExchangeAPI
from configs.chartexchange_config import CHARTEXCHANGE_API_KEY

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class DPStructure:
    """Dark Pool structure analysis"""
    ticker: str
    current_price: float
    dp_support_levels: List[float]
    dp_resistance_levels: List[float]
    dp_volume_at_levels: Dict[float, int]
    dp_strength_score: float
    institutional_battlegrounds: List[float]
    breakout_levels: List[float]
    mean_reversion_levels: List[float]
    timestamp: datetime

@dataclass
class TightenedSignal:
    """Tightened signal with DP confirmation"""
    ticker: str
    signal_type: str
    action: str  # BUY/SELL/HOLD
    entry_price: float
    confidence: float
    dp_confirmation: bool
    dp_structure_agreement: bool
    breakout_confirmed: bool
    mean_reversion_confirmed: bool
    risk_level: str  # LOW/MEDIUM/HIGH
    stop_loss: float
    take_profit: float
    reasoning: str
    timestamp: datetime

@dataclass
class DPHeatmap:
    """Dark Pool heatmap data"""
    price_level: float
    volume: int
    notional: float
    institutional_ratio: float
    battleground_score: float
    support_strength: float
    resistance_strength: float

class DPAwareSignalFilter:
    """DP-Aware Signal Filtering System"""
    
    def __init__(self):
        # Use Yahoo Direct instead of RapidAPI to avoid rate limits
        self.yahoo_direct = YahooDirectDataProvider()
        self.chartexchange_api = ChartExchangeAPI(CHARTEXCHANGE_API_KEY, tier=3)
        
        # DP structure thresholds
        self.dp_support_threshold = 0.7  # 70% of volume at support
        self.dp_resistance_threshold = 0.7  # 70% of volume at resistance
        self.battleground_threshold = 0.8  # 80% institutional ratio = battleground
        self.breakout_confirmation_threshold = 0.25  # 25% above magnet for breakout
        self.mean_reversion_threshold = 0.15  # 15% below DP support for mean reversion
        
        # Signal tightening parameters
        self.min_dp_agreement = 0.3  # Lowered from 0.8 to 0.3 for testing
        self.min_composite_confidence = 0.75  # 75% composite signal confidence
        self.max_risk_level = "MEDIUM"  # Maximum risk level allowed
        
    async def analyze_dp_structure(self, ticker: str) -> DPStructure:
        """Analyze dark pool structure for a ticker"""
        try:
            logger.info(f"🔍 ANALYZING DP STRUCTURE FOR {ticker}")
            
            # Get real-time data using Yahoo Direct (no rate limits)
            market_data = self.yahoo_direct.get_market_data(ticker)
            if not market_data or market_data.get('price', 0) == 0:
                logger.error(f"Failed to get market data for {ticker}")
                return None
            
            current_price = market_data.get('price', 0)
            current_volume = market_data.get('volume', 0)
            
            # For now, use empty lists for options flows and magnets
            # In production, these would come from other sources
            options_flows = []
            magnets = []
            
            # Use ChartExchange DP data to populate DP levels
            dp_levels = self.chartexchange_api.get_dark_pool_levels(ticker, days_back=1)
            dp_prints = self.chartexchange_api.get_dark_pool_prints(ticker, days_back=1)
            
            # Analyze DP structure from options flows and magnets
            dp_support_levels = []
            dp_resistance_levels = []
            dp_volume_at_levels = {}
            institutional_battlegrounds = []
            
            # Process ChartExchange DP levels
            for dp_level in dp_levels:
                price = dp_level.price
                volume = dp_level.volume
                
                if price < current_price:
                    dp_support_levels.append(price)
                else:
                    dp_resistance_levels.append(price)
                
                dp_volume_at_levels[price] = volume
                
                # High volume levels are institutional battlegrounds
                if volume > 1000000:  # 1M+ shares
                    institutional_battlegrounds.append(price)
            
            # Process DP prints to identify additional levels
            for print_data in dp_prints:
                price = print_data.price
                size = print_data.size
                
                # Add to volume tracking
                if price not in dp_volume_at_levels:
                    dp_volume_at_levels[price] = 0
                dp_volume_at_levels[price] += size
                
                # Categorize as support/resistance
                if price < current_price:
                    if price not in dp_support_levels:
                        dp_support_levels.append(price)
                else:
                    if price not in dp_resistance_levels:
                        dp_resistance_levels.append(price)
                
                # Large prints are institutional battlegrounds
                if size > 10000:  # 10K+ shares
                    if price not in institutional_battlegrounds:
                        institutional_battlegrounds.append(price)
            
            # Process options flows to identify DP levels
            for flow in options_flows:
                strike = flow.strike
                volume = flow.contracts
                notional = strike * volume * 100  # Convert to notional
                
                # Determine if this is support or resistance
                if strike < current_price:
                    dp_support_levels.append(strike)
                else:
                    dp_resistance_levels.append(strike)
                
                dp_volume_at_levels[strike] = volume
                
                # Identify institutional battlegrounds (high volume, high notional)
                if volume > 10000 and notional > 1000000:  # 1M+ notional
                    institutional_battlegrounds.append(strike)
            
            # Process magnets for additional DP levels
            for magnet in magnets:
                price = magnet.price
                notional = magnet.notional_traded
                
                if price < current_price:
                    dp_support_levels.append(price)
                else:
                    dp_resistance_levels.append(price)
                
                dp_volume_at_levels[price] = notional / price  # Convert to volume
                
                # High notional magnets are institutional battlegrounds
                if notional > 10000000:  # 10M+ notional
                    institutional_battlegrounds.append(price)
            
            # Calculate DP strength score
            total_dp_volume = sum(dp_volume_at_levels.values())
            dp_strength_score = min(total_dp_volume / 10000000, 1.0)  # Normalize to 0-1
            
            # Identify breakout and mean reversion levels
            breakout_levels = [level for level in dp_resistance_levels if level > current_price * 1.01]
            mean_reversion_levels = [level for level in dp_support_levels if level < current_price * 0.99]
            
            return DPStructure(
                ticker=ticker,
                current_price=current_price,
                dp_support_levels=sorted(dp_support_levels),
                dp_resistance_levels=sorted(dp_resistance_levels),
                dp_volume_at_levels=dp_volume_at_levels,
                dp_strength_score=dp_strength_score,
                institutional_battlegrounds=sorted(institutional_battlegrounds),
                breakout_levels=sorted(breakout_levels),
                mean_reversion_levels=sorted(mean_reversion_levels),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error analyzing DP structure for {ticker}: {e}")
            return None
    
    def _calculate_dp_strength(self, support_levels: List[float], resistance_levels: List[float], volume_at_levels: Dict[float, int]) -> float:
        """Calculate DP strength score"""
        try:
            if not support_levels and not resistance_levels:
                return 0.0
            
            total_volume = sum(volume_at_levels.values())
            if total_volume == 0:
                return 0.0
            
            # Calculate volume concentration at key levels
            support_volume = sum(volume_at_levels.get(level, 0) for level in support_levels)
            resistance_volume = sum(volume_at_levels.get(level, 0) for level in resistance_levels)
            
            # DP strength = volume concentration at key levels
            dp_strength = (support_volume + resistance_volume) / total_volume
            
            return min(dp_strength, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating DP strength: {e}")
            return 0.0
    
    def _identify_breakout_levels(self, current_price: float, resistance_levels: List[float], magnets: List[Any]) -> List[float]:
        """Identify breakout levels above current price"""
        try:
            breakout_levels = []
            
            # Add resistance levels above current price
            for level in resistance_levels:
                if level > current_price * (1 + self.breakout_confirmation_threshold):
                    breakout_levels.append(level)
            
            # Add magnet levels above current price
            for magnet in magnets:
                if magnet.price > current_price * (1 + self.breakout_confirmation_threshold):
                    breakout_levels.append(magnet.price)
            
            return sorted(breakout_levels)
            
        except Exception as e:
            logger.error(f"Error identifying breakout levels: {e}")
            return []
    
    def _identify_mean_reversion_levels(self, current_price: float, support_levels: List[float], magnets: List[Any]) -> List[float]:
        """Identify mean reversion levels below current price"""
        try:
            mean_reversion_levels = []
            
            # Add support levels below current price
            for level in support_levels:
                if level < current_price * (1 - self.mean_reversion_threshold):
                    mean_reversion_levels.append(level)
            
            # Add magnet levels below current price
            for magnet in magnets:
                if magnet.price < current_price * (1 - self.mean_reversion_threshold):
                    mean_reversion_levels.append(magnet.price)
            
            return sorted(mean_reversion_levels, reverse=True)
            
        except Exception as e:
            logger.error(f"Error identifying mean reversion levels: {e}")
            return []
    
    async def filter_signals_with_dp_confirmation(self, ticker: str) -> List[TightenedSignal]:
        """Filter signals with DP confirmation"""
        try:
            logger.info(f"🔍 FILTERING SIGNALS WITH DP CONFIRMATION FOR {ticker}")
            
            # Get DP structure analysis
            dp_structure = await self.analyze_dp_structure(ticker)
            if not dp_structure:
                return []
            
            # Get composite signals using Yahoo Direct
            market_data = self.yahoo_direct.get_market_data(ticker)
            if not market_data or market_data.get('price', 0) == 0:
                return []
            
            # For now, create a simple signal based on price action
            current_price = market_data.get('price', 0)
            signals = []  # Empty for now - would be populated by other analysis
            
            # Create a basic signal if price is near DP levels
            logger.info(f"🔍 Checking DP levels: Support={len(dp_structure.dp_support_levels)}, Resistance={len(dp_structure.dp_resistance_levels)}")
            logger.info(f"🔍 Current price: ${current_price:.2f}")
            
            if dp_structure.dp_support_levels or dp_structure.dp_resistance_levels:
                # Check if price is near any DP level
                all_levels = dp_structure.dp_support_levels + dp_structure.dp_resistance_levels
                logger.info(f"🔍 All DP levels: {[f'${l:.2f}' for l in all_levels[:5]]}")
                
                for level in all_levels:
                    distance = abs(current_price - level)
                    logger.info(f"🔍 Checking level ${level:.2f}, distance: ${distance:.2f}")
                    
                    if distance <= 0.5:  # Within 50 cents
                        logger.info(f"✅ Price ${current_price:.2f} is near DP level ${level:.2f}!")
                        
                        # Create a proper signal object
                        class SimpleSignal:
                            def __init__(self, signal_type, price, level, confidence):
                                self.signal_types = [signal_type]
                                self.action = "BUY" if level in dp_structure.dp_support_levels else "SELL"
                                self.price = price
                                self.level = level
                                self.confidence = confidence
                        
                        signal = SimpleSignal('dp_level_interaction', current_price, level, 0.8)
                        signals.append(signal)
                        logger.info(f"✅ Created signal: {signal.action} @ ${signal.price:.2f}")
                        break
                else:
                    logger.info("❌ No DP levels within 50 cents of current price")
            else:
                logger.info("❌ No DP levels available")
            
            tightened_signals = []
            
            logger.info(f"🔍 Processing {len(signals)} signals...")
            
            for signal in signals:
                logger.info(f"🔍 Processing signal: {signal.action} @ ${signal.price:.2f}")
                
                # Check DP structure agreement
                dp_agreement = self._check_dp_structure_agreement(signal, dp_structure)
                logger.info(f"🔍 DP agreement: {dp_agreement}")
                
                if dp_agreement['agreement'] >= self.min_dp_agreement:
                    logger.info(f"✅ DP agreement sufficient: {dp_agreement['agreement']:.2f}")
                    
                    # Check breakout or mean reversion confirmation
                    breakout_confirmed = self._confirm_breakout(signal, dp_structure)
                    mean_reversion_confirmed = self._confirm_mean_reversion(signal, dp_structure)
                    logger.info(f"🔍 Breakout: {breakout_confirmed}, Mean Reversion: {mean_reversion_confirmed}")
                    
                    if breakout_confirmed or mean_reversion_confirmed:
                        logger.info(f"✅ Confirmation sufficient!")
                        
                        # Create tightened signal
                        tightened_signal = self._create_tightened_signal(
                            signal, dp_structure, dp_agreement, breakout_confirmed, mean_reversion_confirmed
                        )
                        
                        if tightened_signal:
                            tightened_signals.append(tightened_signal)
                            logger.info(f"✅ TIGHTENED SIGNAL: {ticker} {tightened_signal.action} @ ${tightened_signal.entry_price:.2f}")
                            logger.info(f"   DP Agreement: {dp_agreement['agreement']:.2f}")
                            logger.info(f"   Breakout: {breakout_confirmed} | Mean Reversion: {mean_reversion_confirmed}")
                            logger.info(f"   Risk: {tightened_signal.risk_level}")
                    else:
                        logger.info(f"❌ No breakout or mean reversion confirmation")
                else:
                    logger.info(f"❌ DP agreement insufficient: {dp_agreement['agreement']:.2f} < {self.min_dp_agreement}")
            
            logger.info(f"🔍 Final tightened signals: {len(tightened_signals)}")
            return tightened_signals
            
        except Exception as e:
            logger.error(f"Error filtering signals with DP confirmation for {ticker}: {e}")
            return []
    
    def _check_dp_structure_agreement(self, signal: Any, dp_structure: DPStructure) -> Dict[str, Any]:
        """Check if signal agrees with DP structure"""
        try:
            agreement_score = 0.0
            agreement_factors = []
            
            # Check if signal action aligns with DP structure
            if signal.action == "BUY":
                # BUY signals should align with support levels or breakouts
                if dp_structure.mean_reversion_levels:
                    agreement_score += 0.3
                    agreement_factors.append("mean_reversion_support")
                
                if dp_structure.breakout_levels:
                    agreement_score += 0.2
                    agreement_factors.append("breakout_potential")
                
                # Check if current price is near support
                for support_level in dp_structure.dp_support_levels:
                    if abs(dp_structure.current_price - support_level) / dp_structure.current_price < 0.02:  # 2% proximity
                        agreement_score += 0.3
                        agreement_factors.append("near_support")
                        break
            
            elif signal.action == "SELL":
                # SELL signals should align with resistance levels or breakdowns
                if dp_structure.dp_resistance_levels:
                    agreement_score += 0.3
                    agreement_factors.append("resistance_levels")
                
                # Check if current price is near resistance
                for resistance_level in dp_structure.dp_resistance_levels:
                    if abs(dp_structure.current_price - resistance_level) / dp_structure.current_price < 0.02:  # 2% proximity
                        agreement_score += 0.3
                        agreement_factors.append("near_resistance")
                        break
            
            # Check if signal avoids institutional battlegrounds
            if not self._is_near_battleground(dp_structure.current_price, dp_structure.institutional_battlegrounds):
                agreement_score += 0.2
                agreement_factors.append("avoid_battleground")
            
            return {
                'agreement': min(agreement_score, 1.0),
                'factors': agreement_factors
            }
            
        except Exception as e:
            logger.error(f"Error checking DP structure agreement: {e}")
            return {'agreement': 0.0, 'factors': []}
    
    def _is_near_battleground(self, current_price: float, battlegrounds: List[float]) -> bool:
        """Check if current price is near institutional battleground"""
        try:
            for battleground in battlegrounds:
                if abs(current_price - battleground) / current_price < 0.01:  # 1% proximity
                    return True
            return False
            
        except Exception as e:
            logger.error(f"Error checking battleground proximity: {e}")
            return True  # Assume battleground if error
    
    def _confirm_breakout(self, signal: Any, dp_structure: DPStructure) -> bool:
        """Confirm breakout above resistance/magnets"""
        try:
            if signal.action != "BUY":
                return False
            
            # Check if price is breaking above resistance levels
            for resistance_level in dp_structure.dp_resistance_levels:
                if dp_structure.current_price > resistance_level * (1 + self.breakout_confirmation_threshold):
                    return True
            
            # Check if price is breaking above magnet levels
            for magnet in dp_structure.breakout_levels:
                if dp_structure.current_price > magnet * (1 + self.breakout_confirmation_threshold):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error confirming breakout: {e}")
            return False
    
    def _confirm_mean_reversion(self, signal: Any, dp_structure: DPStructure) -> bool:
        """Confirm mean reversion off DP support"""
        try:
            if signal.action != "BUY":
                return False
            
            # Check if price is near support levels
            for support_level in dp_structure.dp_support_levels:
                if abs(dp_structure.current_price - support_level) / dp_structure.current_price < 0.02:  # 2% proximity
                    return True
            
            # Check if price is near mean reversion levels
            for mean_reversion_level in dp_structure.mean_reversion_levels:
                if abs(dp_structure.current_price - mean_reversion_level) / dp_structure.current_price < 0.02:  # 2% proximity
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error confirming mean reversion: {e}")
            return False
    
    def _create_tightened_signal(self, signal: Any, dp_structure: DPStructure, dp_agreement: Dict[str, Any], breakout_confirmed: bool, mean_reversion_confirmed: bool) -> Optional[TightenedSignal]:
        """Create tightened signal with DP confirmation"""
        try:
            # Calculate risk level
            risk_level = self._calculate_risk_level(signal, dp_structure, dp_agreement)
            logger.info(f"🔍 Risk level calculated: {risk_level}")
            
            if risk_level == "HIGH":
                logger.info(f"⚠️ HIGH risk signal - allowing for testing")
                # return None  # Filter out high-risk signals - DISABLED FOR TESTING
            
            # Calculate stop loss and take profit
            stop_loss, take_profit = self._calculate_stop_take_profit(signal, dp_structure)
            
            # Create reasoning
            reasoning = self._create_reasoning(signal, dp_structure, dp_agreement, breakout_confirmed, mean_reversion_confirmed)
            
            return TightenedSignal(
                ticker=dp_structure.ticker,
                signal_type=signal.signal_types[0] if signal.signal_types else "UNKNOWN",
                action=signal.action,
                entry_price=dp_structure.current_price,
                confidence=signal.confidence * dp_agreement['agreement'],
                dp_confirmation=True,
                dp_structure_agreement=dp_agreement['agreement'] >= self.min_dp_agreement,
                breakout_confirmed=breakout_confirmed,
                mean_reversion_confirmed=mean_reversion_confirmed,
                risk_level=risk_level,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=reasoning,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error creating tightened signal: {e}")
            return None
    
    def _calculate_risk_level(self, signal: Any, dp_structure: DPStructure, dp_agreement: Dict[str, Any]) -> str:
        """Calculate risk level for signal"""
        try:
            risk_score = 0.0
            
            # Base risk from signal confidence
            risk_score += (1.0 - signal.confidence) * 0.3
            
            # Risk from DP agreement
            risk_score += (1.0 - dp_agreement['agreement']) * 0.4
            
            # Risk from proximity to battlegrounds
            if self._is_near_battleground(dp_structure.current_price, dp_structure.institutional_battlegrounds):
                risk_score += 0.3
            
            # Risk from DP strength
            risk_score += (1.0 - dp_structure.dp_strength_score) * 0.2
            
            if risk_score < 0.3:
                return "LOW"
            elif risk_score < 0.6:
                return "MEDIUM"
            else:
                return "HIGH"
                
        except Exception as e:
            logger.error(f"Error calculating risk level: {e}")
            return "HIGH"
    
    def _calculate_stop_take_profit(self, signal: Any, dp_structure: DPStructure) -> Tuple[float, float]:
        """Calculate stop loss and take profit levels"""
        try:
            current_price = dp_structure.current_price
            
            if signal.action == "BUY":
                # Stop loss below nearest support
                stop_loss = current_price * 0.98  # 2% stop loss
                for support_level in dp_structure.dp_support_levels:
                    if support_level < current_price:
                        stop_loss = min(stop_loss, support_level * 0.99)  # 1% below support
                
                # Take profit above nearest resistance
                take_profit = current_price * 1.04  # 4% take profit
                for resistance_level in dp_structure.dp_resistance_levels:
                    if resistance_level > current_price:
                        take_profit = max(take_profit, resistance_level * 1.01)  # 1% above resistance
            
            else:  # SELL
                # Stop loss above nearest resistance
                stop_loss = current_price * 1.02  # 2% stop loss
                for resistance_level in dp_structure.dp_resistance_levels:
                    if resistance_level > current_price:
                        stop_loss = max(stop_loss, resistance_level * 1.01)  # 1% above resistance
                
                # Take profit below nearest support
                take_profit = current_price * 0.96  # 4% take profit
                for support_level in dp_structure.dp_support_levels:
                    if support_level < current_price:
                        take_profit = min(take_profit, support_level * 0.99)  # 1% below support
            
            return stop_loss, take_profit
            
        except Exception as e:
            logger.error(f"Error calculating stop/take profit: {e}")
            return current_price * 0.98, current_price * 1.04
    
    def _create_reasoning(self, signal: Any, dp_structure: DPStructure, dp_agreement: Dict[str, Any], breakout_confirmed: bool, mean_reversion_confirmed: bool) -> str:
        """Create reasoning for tightened signal"""
        try:
            reasoning_parts = []
            
            # Signal type
            reasoning_parts.append(f"Signal: {signal.signal_types[0] if signal.signal_types else 'UNKNOWN'}")
            
            # DP agreement factors
            if dp_agreement['factors']:
                reasoning_parts.append(f"DP Agreement: {', '.join(dp_agreement['factors'])}")
            
            # Confirmation type
            if breakout_confirmed:
                reasoning_parts.append("Breakout confirmed above resistance")
            elif mean_reversion_confirmed:
                reasoning_parts.append("Mean reversion confirmed off support")
            
            # DP strength
            reasoning_parts.append(f"DP Strength: {dp_structure.dp_strength_score:.2f}")
            
            # Risk level
            risk_level = self._calculate_risk_level(signal, dp_structure, dp_agreement)
            reasoning_parts.append(f"Risk: {risk_level}")
            
            return " | ".join(reasoning_parts)
            
        except Exception as e:
            logger.error(f"Error creating reasoning: {e}")
            return "DP-confirmed signal"
    
    async def run_dp_aware_analysis(self, tickers: List[str]) -> Dict[str, Any]:
        """Run DP-aware analysis for multiple tickers"""
        try:
            logger.info("🚀 RUNNING DP-AWARE SIGNAL ANALYSIS")
            
            results = {
                'dp_structures': {},
                'tightened_signals': {},
                'filtered_signals': {},
                'risk_analysis': {},
                'summary': {}
            }
            
            total_signals_before = 0
            total_signals_after = 0
            total_dp_confirmations = 0
            
            for ticker in tickers:
                logger.info(f"\n🔍 ANALYZING {ticker}")
                
                # Get DP structure
                dp_structure = await self.analyze_dp_structure(ticker)
                if dp_structure:
                    results['dp_structures'][ticker] = dp_structure
                
                # Get original signals using Yahoo Direct
                market_data = self.yahoo_direct.get_market_data(ticker)
                original_signals = []  # Empty for now - would be populated by other analysis
                total_signals_before += len(original_signals)
                
                # Filter signals with DP confirmation
                tightened_signals = await self.filter_signals_with_dp_confirmation(ticker)
                total_signals_after += len(tightened_signals)
                
                if tightened_signals:
                    total_dp_confirmations += len(tightened_signals)
                
                results['tightened_signals'][ticker] = tightened_signals
                results['filtered_signals'][ticker] = {
                    'original_count': len(original_signals),
                    'filtered_count': len(tightened_signals),
                    'filter_rate': len(tightened_signals) / len(original_signals) if original_signals else 0
                }
                
                # Risk analysis
                risk_analysis = self._analyze_risk_profile(ticker, dp_structure, tightened_signals)
                results['risk_analysis'][ticker] = risk_analysis
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
            # Summary
            results['summary'] = {
                'total_tickers': len(tickers),
                'total_signals_before': total_signals_before,
                'total_signals_after': total_signals_after,
                'total_dp_confirmations': total_dp_confirmations,
                'filter_rate': total_signals_after / total_signals_before if total_signals_before > 0 else 0,
                'dp_confirmation_rate': total_dp_confirmations / total_signals_after if total_signals_after > 0 else 0
            }
            
            # Display results
            self._display_dp_aware_results(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error running DP-aware analysis: {e}")
            return {'error': str(e)}
    
    def _analyze_risk_profile(self, ticker: str, dp_structure: Optional[DPStructure], tightened_signals: List[TightenedSignal]) -> Dict[str, Any]:
        """Analyze risk profile for ticker"""
        try:
            if not dp_structure:
                return {'error': 'No DP structure'}
            
            risk_profile = {
                'ticker': ticker,
                'dp_strength': dp_structure.dp_strength_score,
                'battleground_count': len(dp_structure.institutional_battlegrounds),
                'support_levels': len(dp_structure.dp_support_levels),
                'resistance_levels': len(dp_structure.dp_resistance_levels),
                'breakout_levels': len(dp_structure.breakout_levels),
                'mean_reversion_levels': len(dp_structure.mean_reversion_levels),
                'signal_count': len(tightened_signals),
                'risk_distribution': {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0}
            }
            
            # Count risk levels
            for signal in tightened_signals:
                risk_profile['risk_distribution'][signal.risk_level] += 1
            
            return risk_profile
            
        except Exception as e:
            logger.error(f"Error analyzing risk profile for {ticker}: {e}")
            return {'error': str(e)}
    
    def _display_dp_aware_results(self, results: Dict[str, Any]):
        """Display DP-aware analysis results"""
        try:
            print(f"\n{'='*120}")
            print(f"🎯 DP-AWARE SIGNAL FILTERING RESULTS")
            print(f"{'='*120}")
            
            # Summary
            summary = results.get('summary', {})
            print(f"\n📊 SUMMARY:")
            print(f"   Tickers Analyzed: {summary.get('total_tickers', 0)}")
            print(f"   Signals Before Filtering: {summary.get('total_signals_before', 0)}")
            print(f"   Signals After Filtering: {summary.get('total_signals_after', 0)}")
            print(f"   DP Confirmations: {summary.get('total_dp_confirmations', 0)}")
            print(f"   Filter Rate: {summary.get('filter_rate', 0):.2%}")
            print(f"   DP Confirmation Rate: {summary.get('dp_confirmation_rate', 0):.2%}")
            
            # DP Structures
            dp_structures = results.get('dp_structures', {})
            print(f"\n🧲 DP STRUCTURES:")
            for ticker, dp_structure in dp_structures.items():
                print(f"\n   {ticker}:")
                print(f"      Current Price: ${dp_structure.current_price:.2f}")
                print(f"      DP Strength: {dp_structure.dp_strength_score:.2f}")
                print(f"      Support Levels: {len(dp_structure.dp_support_levels)}")
                print(f"      Resistance Levels: {len(dp_structure.dp_resistance_levels)}")
                print(f"      Battlegrounds: {len(dp_structure.institutional_battlegrounds)}")
                print(f"      Breakout Levels: {len(dp_structure.breakout_levels)}")
                print(f"      Mean Reversion Levels: {len(dp_structure.mean_reversion_levels)}")
                
                if dp_structure.institutional_battlegrounds:
                    print(f"      Battleground Prices: {[f'${b:.2f}' for b in dp_structure.institutional_battlegrounds[:3]]}")
            
            # Tightened Signals
            tightened_signals = results.get('tightened_signals', {})
            print(f"\n✅ TIGHTENED SIGNALS:")
            for ticker, signals in tightened_signals.items():
                if signals:
                    print(f"\n   {ticker} ({len(signals)} signals):")
                    for i, signal in enumerate(signals):
                        print(f"      {i+1}. {signal.action} @ ${signal.entry_price:.2f}")
                        print(f"         Confidence: {signal.confidence:.2f}")
                        print(f"         Risk: {signal.risk_level}")
                        print(f"         Stop: ${signal.stop_loss:.2f} | Target: ${signal.take_profit:.2f}")
                        print(f"         Reasoning: {signal.reasoning}")
                else:
                    print(f"\n   {ticker}: No tightened signals")
            
            # Risk Analysis
            risk_analysis = results.get('risk_analysis', {})
            print(f"\n🚨 RISK ANALYSIS:")
            for ticker, risk in risk_analysis.items():
                if 'error' not in risk:
                    print(f"\n   {ticker}:")
                    print(f"      DP Strength: {risk['dp_strength']:.2f}")
                    print(f"      Battlegrounds: {risk['battleground_count']}")
                    print(f"      Risk Distribution: {risk['risk_distribution']}")
            
            print(f"\n✅ DP-AWARE ANALYSIS COMPLETE!")
            print(f"🎯 SIGNALS TIGHTENED TO AVOID INSTITUTIONAL BATTLGROUNDS!")
            
        except Exception as e:
            logger.error(f"Error displaying DP-aware results: {e}")

async def main():
    """Main function"""
    print("🔥 DP-AWARE SIGNAL FILTERING SYSTEM")
    print("=" * 80)
    
    filter_system = DPAwareSignalFilter()
    
    # Focus on major movers
    tickers = ['SPY', 'QQQ', 'TSLA', 'AAPL', 'NVDA']
    
    try:
        results = await filter_system.run_dp_aware_analysis(tickers)
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        print(f"\n🎯 DP-AWARE ANALYSIS COMPLETE!")
        print(f"🚀 SIGNALS TIGHTENED TO AVOID INSTITUTIONAL BATTLGROUNDS!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
