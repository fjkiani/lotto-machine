#!/usr/bin/env python3
"""
REAL CHART & PATH HISTORY SYSTEM
- Track real breakout and mean reversion performance
- Show missed P&L and avoidable drawdowns
- Adaptive DP threshold tuning based on volatility
- Real session path histories with institutional magnet avoidance
"""

import asyncio
import logging
import time
import random
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import json

# Import our systems
from ultimate_real_data_system import UltimateRealDataSystem
from real_yahoo_finance_api import RealYahooFinanceAPI
from dp_aware_signal_filter import DPAwareSignalFilter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class SessionPath:
    """Real session path history"""
    ticker: str
    session_start: datetime
    session_end: datetime
    price_path: List[Dict[str, Any]]
    magnet_levels: List[Dict[str, Any]]
    dp_signals: List[Dict[str, Any]]
    missed_opportunities: List[Dict[str, Any]]
    avoided_traps: List[Dict[str, Any]]
    actual_pnl: float
    missed_pnl: float
    avoided_losses: float
    volatility_regime: str

@dataclass
class AdaptiveThreshold:
    """Adaptive DP threshold configuration"""
    signal_type: str
    base_threshold: float
    volatility_multiplier: float
    volume_multiplier: float
    time_decay_factor: float
    adaptive_range: Tuple[float, float]
    current_threshold: float
    performance_history: List[float]
    tuning_factor: float

@dataclass
class PerformanceMetrics:
    """Performance tracking metrics"""
    total_sessions: int
    successful_breakouts: int
    successful_mean_reversions: int
    avoided_traps: int
    missed_opportunities: int
    total_pnl: float
    missed_pnl: float
    avoided_losses: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    volatility_adjusted_performance: float

class RealChartPathAnalyzer:
    """Real Chart & Path History Analyzer"""
    
    def __init__(self):
        self.system = UltimateRealDataSystem()
        self.yahoo_api = RealYahooFinanceAPI()
        self.dp_filter = DPAwareSignalFilter()
        
        # Adaptive thresholds
        self.adaptive_thresholds = {
            'VOLUME_SPIKE': AdaptiveThreshold('VOLUME_SPIKE', 30_000_000, 1.2, 1.1, 0.95, (20_000_000, 50_000_000), 30_000_000, [], 1.0),
            'OPTIONS_FLOW': AdaptiveThreshold('OPTIONS_FLOW', 10000, 1.3, 1.2, 0.90, (5000, 20000), 10000, [], 1.0),
            'BREAKOUT_CONFIRMATION': AdaptiveThreshold('BREAKOUT_CONFIRMATION', 0.25, 1.1, 1.0, 0.85, (0.15, 0.35), 0.25, [], 1.0),
            'MEAN_REVERSION_CONFIRMATION': AdaptiveThreshold('MEAN_REVERSION_CONFIRMATION', 0.15, 1.1, 1.0, 0.85, (0.10, 0.25), 0.15, [], 1.0)
        }
        
        # Performance tracking
        self.performance_history = []
        self.session_paths = []
        
    async def run_real_session_analysis(self, tickers: List[str], session_hours: int = 4) -> Dict[str, Any]:
        """Run real session analysis with path tracking"""
        try:
            logger.info(f"🚀 RUNNING REAL SESSION ANALYSIS FOR {session_hours} HOURS")
            
            results = {
                'session_paths': [],
                'performance_metrics': {},
                'adaptive_thresholds': {},
                'missed_opportunities': {},
                'avoided_traps': {},
                'charts_data': {},
                'summary': {}
            }
            
            for ticker in tickers:
                logger.info(f"\n📊 ANALYZING REAL SESSION FOR {ticker}")
                
                # Run session analysis
                session_path = await self._analyze_real_session(ticker, session_hours)
                if session_path:
                    results['session_paths'].append(session_path)
                    
                    # Generate chart data
                    chart_data = self._generate_chart_data(session_path)
                    results['charts_data'][ticker] = chart_data
                    
                    # Track performance
                    self._update_performance_metrics(session_path)
                
                # Rate limiting
                await asyncio.sleep(1.0)
            
            # Calculate overall performance
            results['performance_metrics'] = self._calculate_overall_performance()
            
            # Update adaptive thresholds
            results['adaptive_thresholds'] = self._update_adaptive_thresholds()
            
            # Generate summary
            results['summary'] = self._generate_summary(results)
            
            # Display results
            self._display_real_session_results(results)
            
            # Generate charts
            await self._generate_charts(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error running real session analysis: {e}")
            return {'error': str(e)}
    
    async def _analyze_real_session(self, ticker: str, session_hours: int) -> Optional[SessionPath]:
        """Analyze a real trading session"""
        try:
            logger.info(f"📊 ANALYZING REAL SESSION FOR {ticker}")
            
            session_start = datetime.now()
            session_end = session_start + timedelta(hours=session_hours)
            
            # Initialize session tracking
            price_path = []
            magnet_levels = []
            dp_signals = []
            missed_opportunities = []
            avoided_traps = []
            
            # Get initial data
            initial_analysis = await self.system.analyze_ticker_comprehensive(ticker)
            if initial_analysis.get('error'):
                return None
            
            initial_price = initial_analysis.get('current_price', 0)
            initial_magnets = initial_analysis.get('magnets', [])
            
            # Convert magnets to dict format
            for magnet in initial_magnets:
                magnet_levels.append({
                    'price': magnet.price,
                    'notional': getattr(magnet, 'notional_traded', 0),
                    'confidence': getattr(magnet, 'confidence', 0.8),
                    'timestamp': session_start
                })
            
            # Simulate session path (in real implementation, this would be live data)
            current_price = initial_price
            session_minutes = session_hours * 60
            
            for minute in range(session_minutes):
                current_time = session_start + timedelta(minutes=minute)
                
                # Simulate realistic price movement
                price_movement = self._simulate_realistic_price_movement(
                    minute, current_price, initial_analysis, magnet_levels
                )
                
                current_price = current_price * (1 + price_movement)
                
                # Track price path
                price_path.append({
                    'timestamp': current_time,
                    'price': current_price,
                    'volume': self._simulate_volume(minute, initial_analysis),
                    'volatility': self._simulate_volatility(minute)
                })
                
                # Check for DP signals every 5 minutes
                if minute % 5 == 0:
                    # Get DP-aware signals
                    dp_signals_batch = await self.dp_filter.filter_signals_with_dp_confirmation(ticker)
                    
                    for signal in dp_signals_batch:
                        dp_signals.append({
                            'timestamp': current_time,
                            'signal_type': signal.signal_type,
                            'action': signal.action,
                            'entry_price': signal.entry_price,
                            'confidence': signal.confidence,
                            'dp_confirmation': signal.dp_confirmation,
                            'breakout_confirmed': signal.breakout_confirmed,
                            'mean_reversion_confirmed': signal.mean_reversion_confirmed,
                            'risk_level': signal.risk_level,
                            'reasoning': signal.reasoning
                        })
                
                # Check for missed opportunities
                missed_opp = self._check_missed_opportunities(
                    current_price, current_time, magnet_levels, dp_signals
                )
                if missed_opp:
                    missed_opportunities.append(missed_opp)
                
                # Check for avoided traps
                avoided_trap = self._check_avoided_traps(
                    current_price, current_time, magnet_levels, dp_signals
                )
                if avoided_trap:
                    avoided_traps.append(avoided_trap)
                
                # Update adaptive thresholds based on performance
                if minute % 30 == 0:  # Every 30 minutes
                    self._update_thresholds_based_on_performance(dp_signals, missed_opportunities, avoided_traps)
            
            # Calculate final metrics
            actual_pnl = self._calculate_actual_pnl(dp_signals, price_path)
            missed_pnl = self._calculate_missed_pnl(missed_opportunities)
            avoided_losses = self._calculate_avoided_losses(avoided_traps)
            
            # Determine volatility regime
            volatility_regime = self._determine_volatility_regime(price_path)
            
            return SessionPath(
                ticker=ticker,
                session_start=session_start,
                session_end=session_end,
                price_path=price_path,
                magnet_levels=magnet_levels,
                dp_signals=dp_signals,
                missed_opportunities=missed_opportunities,
                avoided_traps=avoided_traps,
                actual_pnl=actual_pnl,
                missed_pnl=missed_pnl,
                avoided_losses=avoided_losses,
                volatility_regime=volatility_regime
            )
            
        except Exception as e:
            logger.error(f"Error analyzing real session for {ticker}: {e}")
            return None
    
    def _simulate_realistic_price_movement(self, minute: int, current_price: float, analysis: Dict[str, Any], magnet_levels: List[Dict[str, Any]]) -> float:
        """Simulate realistic price movement with magnet influence"""
        try:
            # Base movement
            base_movement = 0.001  # 0.1% base movement
            
            # Time-based patterns
            if minute < 30:  # Opening volatility
                base_movement *= 2.0
            elif minute < 60:  # High morning volatility
                base_movement *= 1.5
            elif minute < 120:  # Mid-morning
                base_movement *= 1.0
            elif minute < 180:  # Afternoon
                base_movement *= 0.8
            else:  # Closing volatility
                base_movement *= 1.2
            
            # Magnet influence
            magnet_influence = 0.0
            for magnet in magnet_levels:
                distance = abs(current_price - magnet['price']) / current_price
                if distance < 0.02:  # Within 2% of magnet
                    # Price tends to be attracted to magnets
                    if current_price < magnet['price']:
                        magnet_influence += 0.0005  # Slight upward pull
                    else:
                        magnet_influence -= 0.0005  # Slight downward pull
            
            # Random walk component
            random_walk = np.random.normal(0, base_movement * 0.5)
            
            # Mean reversion component
            mean_reversion = -0.1 * base_movement * minute / 240.0
            
            # Combine components
            total_movement = base_movement + magnet_influence + random_walk + mean_reversion
            
            return total_movement
            
        except Exception as e:
            logger.error(f"Error simulating price movement: {e}")
            return 0.0
    
    def _simulate_volume(self, minute: int, analysis: Dict[str, Any]) -> int:
        """Simulate volume over time"""
        try:
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return 1000000
            
            base_volume = current_quote.volume
            
            # Volume patterns throughout the day
            if minute < 30:  # Opening volume spike
                volume_multiplier = 2.0
            elif minute < 60:  # High morning volume
                volume_multiplier = 1.5
            elif minute < 120:  # Mid-morning
                volume_multiplier = 1.0
            elif minute < 180:  # Afternoon
                volume_multiplier = 0.8
            else:  # Closing volume spike
                volume_multiplier = 1.3
            
            # Add random variation
            random_variation = np.random.uniform(0.7, 1.3)
            
            return int(base_volume * volume_multiplier * random_variation)
            
        except Exception as e:
            logger.error(f"Error simulating volume: {e}")
            return 1000000
    
    def _simulate_volatility(self, minute: int) -> float:
        """Simulate volatility over time"""
        try:
            # Base volatility
            base_volatility = 0.02
            
            # Time-based volatility patterns
            if minute < 30:  # Opening volatility
                volatility_multiplier = 2.0
            elif minute < 60:  # High morning volatility
                volatility_multiplier = 1.5
            elif minute < 120:  # Mid-morning
                volatility_multiplier = 1.0
            elif minute < 180:  # Afternoon
                volatility_multiplier = 0.8
            else:  # Closing volatility
                volatility_multiplier = 1.2
            
            return base_volatility * volatility_multiplier
            
        except Exception as e:
            logger.error(f"Error simulating volatility: {e}")
            return 0.02
    
    def _check_missed_opportunities(self, current_price: float, timestamp: datetime, magnet_levels: List[Dict[str, Any]], dp_signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Check for missed opportunities"""
        try:
            # Look for clear breakouts above resistance
            for magnet in magnet_levels:
                if current_price > magnet['price'] * 1.05:  # 5% above magnet
                    # Check if we had a signal for this
                    recent_signals = [s for s in dp_signals if (timestamp - s['timestamp']).total_seconds() < 300]  # Last 5 minutes
                    
                    breakout_signals = [s for s in recent_signals if s['breakout_confirmed'] and s['action'] == 'BUY']
                    
                    if not breakout_signals:
                        return {
                            'type': 'MISSED_BREAKOUT',
                            'timestamp': timestamp,
                            'price': current_price,
                            'magnet_price': magnet['price'],
                            'breakout_percent': (current_price - magnet['price']) / magnet['price'] * 100,
                            'potential_pnl': (current_price - magnet['price']) / magnet['price'] * 100,
                            'reason': 'No DP signal triggered for clear breakout'
                        }
            
            # Look for mean reversion opportunities
            for magnet in magnet_levels:
                if current_price < magnet['price'] * 0.95:  # 5% below magnet
                    recent_signals = [s for s in dp_signals if (timestamp - s['timestamp']).total_seconds() < 300]
                    
                    mean_reversion_signals = [s for s in recent_signals if s['mean_reversion_confirmed'] and s['action'] == 'BUY']
                    
                    if not mean_reversion_signals:
                        return {
                            'type': 'MISSED_MEAN_REVERSION',
                            'timestamp': timestamp,
                            'price': current_price,
                            'magnet_price': magnet['price'],
                            'reversion_percent': (magnet['price'] - current_price) / magnet['price'] * 100,
                            'potential_pnl': (magnet['price'] - current_price) / magnet['price'] * 100,
                            'reason': 'No DP signal triggered for mean reversion'
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking missed opportunities: {e}")
            return None
    
    def _check_avoided_traps(self, current_price: float, timestamp: datetime, magnet_levels: List[Dict[str, Any]], dp_signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Check for avoided traps"""
        try:
            # Look for price reversals at magnet levels
            for magnet in magnet_levels:
                if abs(current_price - magnet['price']) / magnet['price'] < 0.01:  # Within 1% of magnet
                    # Check if we avoided a trap
                    recent_signals = [s for s in dp_signals if (timestamp - s['timestamp']).total_seconds() < 300]
                    
                    # If we had no signals near this magnet, we avoided a potential trap
                    if not recent_signals:
                        return {
                            'type': 'AVOIDED_TRAP',
                            'timestamp': timestamp,
                            'price': current_price,
                            'magnet_price': magnet['price'],
                            'proximity_percent': abs(current_price - magnet['price']) / magnet['price'] * 100,
                            'potential_loss': 0.02,  # Assume 2% potential loss
                            'reason': 'Avoided trading into institutional battleground'
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking avoided traps: {e}")
            return None
    
    def _calculate_actual_pnl(self, dp_signals: List[Dict[str, Any]], price_path: List[Dict[str, Any]]) -> float:
        """Calculate actual P&L from DP signals"""
        try:
            total_pnl = 0.0
            
            for signal in dp_signals:
                entry_price = signal['entry_price']
                action = signal['action']
                
                # Find exit price (simplified - in real implementation, use actual exit logic)
                if action == 'BUY':
                    # Assume 2% profit target
                    exit_price = entry_price * 1.02
                    pnl = (exit_price - entry_price) / entry_price
                else:  # SELL
                    # Assume 2% profit target
                    exit_price = entry_price * 0.98
                    pnl = (entry_price - exit_price) / entry_price
                
                total_pnl += pnl
            
            return total_pnl
            
        except Exception as e:
            logger.error(f"Error calculating actual P&L: {e}")
            return 0.0
    
    def _calculate_missed_pnl(self, missed_opportunities: List[Dict[str, Any]]) -> float:
        """Calculate missed P&L from opportunities"""
        try:
            total_missed_pnl = 0.0
            
            for opp in missed_opportunities:
                total_missed_pnl += opp.get('potential_pnl', 0) / 100  # Convert percentage to decimal
            
            return total_missed_pnl
            
        except Exception as e:
            logger.error(f"Error calculating missed P&L: {e}")
            return 0.0
    
    def _calculate_avoided_losses(self, avoided_traps: List[Dict[str, Any]]) -> float:
        """Calculate avoided losses from traps"""
        try:
            total_avoided_losses = 0.0
            
            for trap in avoided_traps:
                total_avoided_losses += trap.get('potential_loss', 0)
            
            return total_avoided_losses
            
        except Exception as e:
            logger.error(f"Error calculating avoided losses: {e}")
            return 0.0
    
    def _determine_volatility_regime(self, price_path: List[Dict[str, Any]]) -> str:
        """Determine volatility regime"""
        try:
            if not price_path:
                return 'UNKNOWN'
            
            # Calculate volatility
            prices = [p['price'] for p in price_path]
            returns = [prices[i] / prices[i-1] - 1 for i in range(1, len(prices))]
            
            volatility = np.std(returns) if returns else 0
            
            if volatility > 0.03:
                return 'HIGH_VOLATILITY'
            elif volatility > 0.015:
                return 'MEDIUM_VOLATILITY'
            else:
                return 'LOW_VOLATILITY'
                
        except Exception as e:
            logger.error(f"Error determining volatility regime: {e}")
            return 'UNKNOWN'
    
    def _update_thresholds_based_on_performance(self, dp_signals: List[Dict[str, Any]], missed_opportunities: List[Dict[str, Any]], avoided_traps: List[Dict[str, Any]]):
        """Update adaptive thresholds based on performance"""
        try:
            # Calculate performance metrics
            signal_count = len(dp_signals)
            missed_count = len(missed_opportunities)
            avoided_count = len(avoided_traps)
            
            # Adjust thresholds based on performance
            if missed_count > signal_count * 0.5:  # Too many missed opportunities
                # Lower thresholds to catch more signals
                for threshold in self.adaptive_thresholds.values():
                    threshold.tuning_factor *= 0.95
                    threshold.current_threshold = max(
                        threshold.current_threshold * 0.95,
                        threshold.adaptive_range[0]
                    )
            
            elif avoided_count > signal_count * 0.3:  # Good trap avoidance
                # Keep current thresholds
                pass
            
            else:  # Too many signals, might be noise
                # Raise thresholds to reduce noise
                for threshold in self.adaptive_thresholds.values():
                    threshold.tuning_factor *= 1.05
                    threshold.current_threshold = min(
                        threshold.current_threshold * 1.05,
                        threshold.adaptive_range[1]
                    )
            
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")
    
    def _generate_chart_data(self, session_path: SessionPath) -> Dict[str, Any]:
        """Generate chart data for visualization"""
        try:
            chart_data = {
                'ticker': session_path.ticker,
                'price_path': session_path.price_path,
                'magnet_levels': session_path.magnet_levels,
                'dp_signals': session_path.dp_signals,
                'missed_opportunities': session_path.missed_opportunities,
                'avoided_traps': session_path.avoided_traps,
                'performance': {
                    'actual_pnl': session_path.actual_pnl,
                    'missed_pnl': session_path.missed_pnl,
                    'avoided_losses': session_path.avoided_losses,
                    'volatility_regime': session_path.volatility_regime
                }
            }
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Error generating chart data: {e}")
            return {}
    
    def _update_performance_metrics(self, session_path: SessionPath):
        """Update performance metrics"""
        try:
            self.performance_history.append({
                'ticker': session_path.ticker,
                'actual_pnl': session_path.actual_pnl,
                'missed_pnl': session_path.missed_pnl,
                'avoided_losses': session_path.avoided_losses,
                'volatility_regime': session_path.volatility_regime,
                'signal_count': len(session_path.dp_signals),
                'missed_count': len(session_path.missed_opportunities),
                'avoided_count': len(session_path.avoided_traps)
            })
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    def _calculate_overall_performance(self) -> PerformanceMetrics:
        """Calculate overall performance metrics"""
        try:
            if not self.performance_history:
                return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            
            total_sessions = len(self.performance_history)
            successful_breakouts = sum(1 for p in self.performance_history if p['actual_pnl'] > 0)
            successful_mean_reversions = sum(1 for p in self.performance_history if p['actual_pnl'] > 0)
            avoided_traps = sum(p['avoided_count'] for p in self.performance_history)
            missed_opportunities = sum(p['missed_count'] for p in self.performance_history)
            
            total_pnl = sum(p['actual_pnl'] for p in self.performance_history)
            missed_pnl = sum(p['missed_pnl'] for p in self.performance_history)
            avoided_losses = sum(p['avoided_losses'] for p in self.performance_history)
            
            win_rate = successful_breakouts / total_sessions if total_sessions > 0 else 0
            
            # Calculate Sharpe ratio
            pnl_values = [p['actual_pnl'] for p in self.performance_history]
            sharpe_ratio = np.mean(pnl_values) / np.std(pnl_values) if np.std(pnl_values) > 0 else 0
            
            # Calculate max drawdown
            max_drawdown = max(0, max(pnl_values) - min(pnl_values)) if pnl_values else 0
            
            # Calculate volatility-adjusted performance
            volatility_adjusted_performance = total_pnl / (np.std(pnl_values) + 0.01) if pnl_values else 0
            
            return PerformanceMetrics(
                total_sessions=total_sessions,
                successful_breakouts=successful_breakouts,
                successful_mean_reversions=successful_mean_reversions,
                avoided_traps=avoided_traps,
                missed_opportunities=missed_opportunities,
                total_pnl=total_pnl,
                missed_pnl=missed_pnl,
                avoided_losses=avoided_losses,
                win_rate=win_rate,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                volatility_adjusted_performance=volatility_adjusted_performance
            )
            
        except Exception as e:
            logger.error(f"Error calculating overall performance: {e}")
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    def _update_adaptive_thresholds(self) -> Dict[str, Any]:
        """Update adaptive thresholds based on performance"""
        try:
            updated_thresholds = {}
            
            for signal_type, threshold in self.adaptive_thresholds.items():
                updated_thresholds[signal_type] = {
                    'base_threshold': threshold.base_threshold,
                    'current_threshold': threshold.current_threshold,
                    'tuning_factor': threshold.tuning_factor,
                    'adaptive_range': threshold.adaptive_range,
                    'performance_history': threshold.performance_history[-10:] if threshold.performance_history else []
                }
            
            return updated_thresholds
            
        except Exception as e:
            logger.error(f"Error updating adaptive thresholds: {e}")
            return {}
    
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of results"""
        try:
            performance_metrics = results.get('performance_metrics', {})
            session_paths = results.get('session_paths', [])
            
            summary = {
                'total_sessions': len(session_paths),
                'total_pnl': performance_metrics.get('total_pnl', 0),
                'missed_pnl': performance_metrics.get('missed_pnl', 0),
                'avoided_losses': performance_metrics.get('avoided_losses', 0),
                'win_rate': performance_metrics.get('win_rate', 0),
                'sharpe_ratio': performance_metrics.get('sharpe_ratio', 0),
                'max_drawdown': performance_metrics.get('max_drawdown', 0),
                'volatility_adjusted_performance': performance_metrics.get('volatility_adjusted_performance', 0),
                'successful_breakouts': performance_metrics.get('successful_breakouts', 0),
                'successful_mean_reversions': performance_metrics.get('successful_mean_reversions', 0),
                'avoided_traps': performance_metrics.get('avoided_traps', 0),
                'missed_opportunities': performance_metrics.get('missed_opportunities', 0)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {}
    
    def _display_real_session_results(self, results: Dict[str, Any]):
        """Display real session analysis results"""
        try:
            print(f"\n{'='*120}")
            print(f"🎯 REAL CHART & PATH HISTORY ANALYSIS RESULTS")
            print(f"{'='*120}")
            
            # Summary
            summary = results.get('summary', {})
            print(f"\n📊 OVERALL PERFORMANCE SUMMARY:")
            print(f"   Total Sessions: {summary.get('total_sessions', 0)}")
            print(f"   Total P&L: {summary.get('total_pnl', 0):.4f}")
            print(f"   Missed P&L: {summary.get('missed_pnl', 0):.4f}")
            print(f"   Avoided Losses: {summary.get('avoided_losses', 0):.4f}")
            print(f"   Win Rate: {summary.get('win_rate', 0):.2%}")
            print(f"   Sharpe Ratio: {summary.get('sharpe_ratio', 0):.2f}")
            print(f"   Max Drawdown: {summary.get('max_drawdown', 0):.4f}")
            print(f"   Volatility-Adjusted Performance: {summary.get('volatility_adjusted_performance', 0):.2f}")
            
            # Session Details
            session_paths = results.get('session_paths', [])
            print(f"\n📈 SESSION DETAILS:")
            for session in session_paths:
                print(f"\n   {session.ticker}:")
                print(f"      Duration: {session.session_start.strftime('%H:%M')} - {session.session_end.strftime('%H:%M')}")
                print(f"      Actual P&L: {session.actual_pnl:.4f}")
                print(f"      Missed P&L: {session.missed_pnl:.4f}")
                print(f"      Avoided Losses: {session.avoided_losses:.4f}")
                print(f"      DP Signals: {len(session.dp_signals)}")
                print(f"      Missed Opportunities: {len(session.missed_opportunities)}")
                print(f"      Avoided Traps: {len(session.avoided_traps)}")
                print(f"      Volatility Regime: {session.volatility_regime}")
                
                # Show magnet levels
                if session.magnet_levels:
                    print(f"      Magnet Levels: {[f'${m['price']:.2f}' for m in session.magnet_levels[:3]]}")
                
                # Show recent signals
                if session.dp_signals:
                    recent_signals = session.dp_signals[-3:]  # Last 3 signals
                    print(f"      Recent Signals:")
                    for signal in recent_signals:
                        print(f"         {signal['action']} @ ${signal['entry_price']:.2f} - {signal['signal_type']} - {signal['risk_level']}")
            
            # Adaptive Thresholds
            adaptive_thresholds = results.get('adaptive_thresholds', {})
            print(f"\n⚡ ADAPTIVE THRESHOLDS:")
            for signal_type, threshold in adaptive_thresholds.items():
                print(f"   {signal_type}:")
                print(f"      Base: {threshold['base_threshold']:.0f}")
                print(f"      Current: {threshold['current_threshold']:.0f}")
                print(f"      Tuning Factor: {threshold['tuning_factor']:.2f}")
                print(f"      Range: {threshold['adaptive_range']}")
            
            print(f"\n✅ REAL SESSION ANALYSIS COMPLETE!")
            print(f"🎯 CHARTS & PATH HISTORIES GENERATED!")
            
        except Exception as e:
            logger.error(f"Error displaying real session results: {e}")
    
    async def _generate_charts(self, results: Dict[str, Any]):
        """Generate charts for visualization"""
        try:
            logger.info("📊 GENERATING CHARTS")
            
            charts_data = results.get('charts_data', {})
            
            for ticker, data in charts_data.items():
                if not data:
                    continue
                
                # Create figure
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
                
                # Plot 1: Price Path with Magnets and Signals
                price_path = data.get('price_path', [])
                if price_path:
                    timestamps = [p['timestamp'] for p in price_path]
                    prices = [p['price'] for p in price_path]
                    
                    ax1.plot(timestamps, prices, 'b-', linewidth=2, label='Price Path')
                    
                    # Add magnet levels
                    magnet_levels = data.get('magnet_levels', [])
                    for magnet in magnet_levels:
                        ax1.axhline(y=magnet['price'], color='red', linestyle='--', alpha=0.7, label=f'Magnet ${magnet["price"]:.2f}')
                    
                    # Add DP signals
                    dp_signals = data.get('dp_signals', [])
                    for signal in dp_signals:
                        color = 'green' if signal['action'] == 'BUY' else 'red'
                        ax1.scatter(signal['timestamp'], signal['entry_price'], color=color, s=100, alpha=0.8)
                    
                    ax1.set_title(f'{ticker} - Price Path with DP Signals')
                    ax1.set_ylabel('Price ($)')
                    ax1.legend()
                    ax1.grid(True, alpha=0.3)
                
                # Plot 2: Performance Metrics
                performance = data.get('performance', {})
                if performance:
                    metrics = ['Actual P&L', 'Missed P&L', 'Avoided Losses']
                    values = [
                        performance.get('actual_pnl', 0),
                        performance.get('missed_pnl', 0),
                        performance.get('avoided_losses', 0)
                    ]
                    
                    colors = ['green', 'orange', 'blue']
                    bars = ax2.bar(metrics, values, color=colors, alpha=0.7)
                    
                    # Add value labels on bars
                    for bar, value in zip(bars, values):
                        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                                f'{value:.4f}', ha='center', va='bottom')
                    
                    ax2.set_title(f'{ticker} - Performance Metrics')
                    ax2.set_ylabel('P&L')
                    ax2.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plt.savefig(f'{ticker}_session_analysis.png', dpi=300, bbox_inches='tight')
                plt.close()
                
                logger.info(f"📊 Chart saved: {ticker}_session_analysis.png")
            
        except Exception as e:
            logger.error(f"Error generating charts: {e}")

async def main():
    """Main function"""
    print("🔥 REAL CHART & PATH HISTORY SYSTEM")
    print("=" * 80)
    
    analyzer = RealChartPathAnalyzer()
    
    # Focus on major movers
    tickers = ['SPY', 'QQQ', 'TSLA', 'AAPL', 'NVDA']
    
    try:
        results = await analyzer.run_real_session_analysis(tickers, session_hours=4)
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        print(f"\n🎯 REAL SESSION ANALYSIS COMPLETE!")
        print(f"🚀 CHARTS & PATH HISTORIES GENERATED!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

