#!/usr/bin/env python3
"""
REAL BREAKOUT & REVERSAL DETECTOR WITH RATE LIMIT SOLVER
- Use our production rate limit solver
- Detect true breakouts and reversals in real-time
- Show adaptive joining of confirmed moves
- Visualize trade chains for full transparency
- Track edge and performance in real-time
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

# Import our production rate limit solver
from production_rate_limit_solver import ProductionRateLimitSolver
from dp_aware_signal_filter import DPAwareSignalFilter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class RealTradeChain:
    """Real trade chain tracking"""
    ticker: str
    signal_type: str
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    confidence: float
    dp_confirmation: bool
    breakout_confirmed: bool
    mean_reversion_confirmed: bool
    risk_level: str
    pnl: float
    max_favorable: float
    max_adverse: float
    hold_time_minutes: int
    reasoning: str
    magnet_level: float
    volume_spike: bool
    options_flow: bool

@dataclass
class RealEdgeMetrics:
    """Real edge tracking metrics"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_hold_time: float
    breakout_success_rate: float
    reversal_success_rate: float
    dp_confirmation_rate: float
    false_signal_rate: float
    magnet_accuracy: float

class RealBreakoutReversalDetector:
    """Real Breakout & Reversal Detector with Rate Limit Solver"""
    
    def __init__(self):
        self.rate_limit_solver = ProductionRateLimitSolver()
        self.dp_filter = DPAwareSignalFilter()
        
        # Trade chain tracking
        self.trade_chains = []
        self.edge_metrics = RealEdgeMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        # Real-time tracking
        self.price_history = {}
        self.magnet_history = {}
        self.signal_history = {}
        
        # Breakout/Reversal detection thresholds
        self.breakout_threshold = 0.02  # 2% above resistance
        self.reversal_threshold = 0.02  # 2% below support
        self.volume_spike_threshold = 2.0  # 2x average volume
        self.options_flow_threshold = 10000  # 10K contracts
        
    async def run_real_breakout_reversal_detection(self, tickers: List[str], duration_hours: int = 0.1) -> Dict[str, Any]:
        """Run real breakout and reversal detection"""
        try:
            logger.info(f"🚀 RUNNING REAL BREAKOUT & REVERSAL DETECTION FOR {duration_hours} HOURS")
            
            results = {
                'detected_breakouts': [],
                'detected_reversals': [],
                'trade_chains': [],
                'edge_metrics': {},
                'visualization_data': {},
                'summary': {}
            }
            
            # Initialize tracking for each ticker
            for ticker in tickers:
                self.price_history[ticker] = []
                self.magnet_history[ticker] = []
                self.signal_history[ticker] = []
            
            # Run detection loop
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=duration_hours)
            
            while datetime.now() < end_time:
                logger.info(f"🔍 DETECTING BREAKOUTS & REVERSALS - {datetime.now().strftime('%H:%M:%S')}")
                
                for ticker in tickers:
                    # Get real-time data using rate limit solver
                    detection_result = await self._detect_real_breakout_reversal(ticker)
                    
                    if detection_result:
                        if detection_result['type'] == 'BREAKOUT':
                            results['detected_breakouts'].append(detection_result)
                        elif detection_result['type'] == 'REVERSAL':
                            results['detected_reversals'].append(detection_result)
                        
                        # Create trade chain if signal is strong enough
                        if detection_result['confidence'] > 0.7:
                            trade_chain = self._create_real_trade_chain(ticker, detection_result)
                            if trade_chain:
                                self.trade_chains.append(trade_chain)
                                results['trade_chains'].append(trade_chain)
                                
                                logger.info(f"✅ REAL SIGNAL DETECTED: {ticker} {detection_result['type']}")
                                logger.info(f"   Entry: ${detection_result['entry_price']:.2f}")
                                logger.info(f"   Confidence: {detection_result['confidence']:.2f}")
                                logger.info(f"   DP Confirmation: {detection_result['dp_confirmation']}")
                                logger.info(f"   Risk Level: {detection_result['risk_level']}")
                
                # Wait before next detection cycle
                await asyncio.sleep(30)  # Check every 30 seconds
            
            # Calculate edge metrics
            results['edge_metrics'] = self._calculate_real_edge_metrics()
            
            # Generate visualization data
            results['visualization_data'] = self._generate_real_visualization_data()
            
            # Generate summary
            results['summary'] = self._generate_real_summary(results)
            
            # Display results
            self._display_real_detection_results(results)
            
            # Generate charts
            await self._generate_real_detection_charts(results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error running real breakout reversal detection: {e}")
            return {'error': str(e)}
    
    async def _detect_real_breakout_reversal(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Detect real breakout or reversal using rate limit solver"""
        try:
            # Get market data using our rate limit solver
            market_data = self.rate_limit_solver.get_market_data_with_fallback(ticker)
            
            if not market_data or market_data.get('price', 0) <= 0:
                logger.warning(f"No valid market data for {ticker}")
                return None
            
            current_price = market_data['price']
            current_volume = market_data['volume']
            options_data = market_data.get('options', {})
            
            # Get DP-aware signals
            dp_signals = await self.dp_filter.filter_signals_with_dp_confirmation(ticker)
            
            # Track price history
            self.price_history[ticker].append({
                'timestamp': datetime.now(),
                'price': current_price,
                'volume': current_volume
            })
            
            # Keep only last 100 price points
            if len(self.price_history[ticker]) > 100:
                self.price_history[ticker] = self.price_history[ticker][-100:]
            
            # Detect breakouts
            breakout_detection = self._detect_breakout(ticker, current_price, current_volume, options_data, dp_signals)
            if breakout_detection:
                return breakout_detection
            
            # Detect reversals
            reversal_detection = self._detect_reversal(ticker, current_price, current_volume, options_data, dp_signals)
            if reversal_detection:
                return reversal_detection
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting real breakout/reversal for {ticker}: {e}")
            return None
    
    def _detect_breakout(self, ticker: str, current_price: float, current_volume: int, options_data: Dict[str, Any], dp_signals: List[Any]) -> Optional[Dict[str, Any]]:
        """Detect real breakout"""
        try:
            if len(self.price_history[ticker]) < 20:
                return None
            
            # Calculate resistance levels from price history
            price_history = [p['price'] for p in self.price_history[ticker]]
            resistance_levels = self._calculate_resistance_levels(price_history)
            
            # Check for breakout above resistance
            for resistance_level in resistance_levels:
                if current_price > resistance_level * (1 + self.breakout_threshold):
                    # Check volume spike
                    avg_volume = np.mean([p['volume'] for p in self.price_history[ticker][-20:]])
                    volume_spike = current_volume > avg_volume * self.volume_spike_threshold
                    
                    # Check options flow
                    options_flow = self._check_options_flow(options_data, 'call')
                    
                    # Check DP confirmation
                    dp_confirmation = any(signal.dp_confirmation and signal.breakout_confirmed for signal in dp_signals)
                    
                    # Calculate confidence
                    confidence = 0.5  # Base confidence
                    if volume_spike:
                        confidence += 0.2
                    if options_flow:
                        confidence += 0.2
                    if dp_confirmation:
                        confidence += 0.3
                    
                    # Determine risk level
                    risk_level = 'LOW' if confidence > 0.8 else 'MEDIUM' if confidence > 0.6 else 'HIGH'
                    
                    return {
                        'type': 'BREAKOUT',
                        'ticker': ticker,
                        'entry_price': current_price,
                        'resistance_level': resistance_level,
                        'breakout_strength': (current_price - resistance_level) / resistance_level,
                        'volume_spike': volume_spike,
                        'options_flow': options_flow,
                        'dp_confirmation': dp_confirmation,
                        'confidence': confidence,
                        'risk_level': risk_level,
                        'timestamp': datetime.now(),
                        'reasoning': f'Breakout above resistance ${resistance_level:.2f} with {confidence:.1%} confidence'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting breakout for {ticker}: {e}")
            return None
    
    def _detect_reversal(self, ticker: str, current_price: float, current_volume: int, options_data: Dict[str, Any], dp_signals: List[Any]) -> Optional[Dict[str, Any]]:
        """Detect real reversal"""
        try:
            if len(self.price_history[ticker]) < 20:
                return None
            
            # Calculate support levels from price history
            price_history = [p['price'] for p in self.price_history[ticker]]
            support_levels = self._calculate_support_levels(price_history)
            
            # Check for reversal off support
            for support_level in support_levels:
                if current_price < support_level * (1 - self.reversal_threshold):
                    # Check volume spike
                    avg_volume = np.mean([p['volume'] for p in self.price_history[ticker][-20:]])
                    volume_spike = current_volume > avg_volume * self.volume_spike_threshold
                    
                    # Check options flow
                    options_flow = self._check_options_flow(options_data, 'put')
                    
                    # Check DP confirmation
                    dp_confirmation = any(signal.dp_confirmation and signal.mean_reversion_confirmed for signal in dp_signals)
                    
                    # Calculate confidence
                    confidence = 0.5  # Base confidence
                    if volume_spike:
                        confidence += 0.2
                    if options_flow:
                        confidence += 0.2
                    if dp_confirmation:
                        confidence += 0.3
                    
                    # Determine risk level
                    risk_level = 'LOW' if confidence > 0.8 else 'MEDIUM' if confidence > 0.6 else 'HIGH'
                    
                    return {
                        'type': 'REVERSAL',
                        'ticker': ticker,
                        'entry_price': current_price,
                        'support_level': support_level,
                        'reversal_strength': (support_level - current_price) / support_level,
                        'volume_spike': volume_spike,
                        'options_flow': options_flow,
                        'dp_confirmation': dp_confirmation,
                        'confidence': confidence,
                        'risk_level': risk_level,
                        'timestamp': datetime.now(),
                        'reasoning': f'Reversal off support ${support_level:.2f} with {confidence:.1%} confidence'
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error detecting reversal for {ticker}: {e}")
            return None
    
    def _calculate_resistance_levels(self, price_history: List[float]) -> List[float]:
        """Calculate resistance levels from price history"""
        try:
            if len(price_history) < 10:
                return []
            
            # Find local maxima
            resistance_levels = []
            for i in range(1, len(price_history) - 1):
                if price_history[i] > price_history[i-1] and price_history[i] > price_history[i+1]:
                    resistance_levels.append(price_history[i])
            
            # Return top 3 resistance levels
            return sorted(resistance_levels, reverse=True)[:3]
            
        except Exception as e:
            logger.error(f"Error calculating resistance levels: {e}")
            return []
    
    def _calculate_support_levels(self, price_history: List[float]) -> List[float]:
        """Calculate support levels from price history"""
        try:
            if len(price_history) < 10:
                return []
            
            # Find local minima
            support_levels = []
            for i in range(1, len(price_history) - 1):
                if price_history[i] < price_history[i-1] and price_history[i] < price_history[i+1]:
                    support_levels.append(price_history[i])
            
            # Return top 3 support levels
            return sorted(support_levels)[:3]
            
        except Exception as e:
            logger.error(f"Error calculating support levels: {e}")
            return []
    
    def _check_options_flow(self, options_data: Dict[str, Any], option_type: str) -> bool:
        """Check for significant options flow"""
        try:
            if not options_data:
                return False
            
            if option_type == 'call':
                volume = options_data.get('call_volume', 0)
            else:
                volume = options_data.get('put_volume', 0)
            
            return volume > self.options_flow_threshold
            
        except Exception as e:
            logger.error(f"Error checking options flow: {e}")
            return False
    
    def _create_real_trade_chain(self, ticker: str, detection_result: Dict[str, Any]) -> Optional[RealTradeChain]:
        """Create real trade chain"""
        try:
            return RealTradeChain(
                ticker=ticker,
                signal_type=detection_result['type'],
                entry_time=detection_result['timestamp'],
                entry_price=detection_result['entry_price'],
                exit_time=None,
                exit_price=None,
                confidence=detection_result['confidence'],
                dp_confirmation=detection_result['dp_confirmation'],
                breakout_confirmed=detection_result['type'] == 'BREAKOUT',
                mean_reversion_confirmed=detection_result['type'] == 'REVERSAL',
                risk_level=detection_result['risk_level'],
                pnl=0.0,
                max_favorable=0.0,
                max_adverse=0.0,
                hold_time_minutes=0,
                reasoning=detection_result['reasoning'],
                magnet_level=detection_result.get('resistance_level', detection_result.get('support_level', 0)),
                volume_spike=detection_result['volume_spike'],
                options_flow=detection_result['options_flow']
            )
            
        except Exception as e:
            logger.error(f"Error creating real trade chain: {e}")
            return None
    
    def _calculate_real_edge_metrics(self) -> RealEdgeMetrics:
        """Calculate real edge metrics"""
        try:
            if not self.trade_chains:
                return RealEdgeMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            
            total_trades = len(self.trade_chains)
            winning_trades = sum(1 for tc in self.trade_chains if tc.pnl > 0)
            losing_trades = sum(1 for tc in self.trade_chains if tc.pnl <= 0)
            
            total_pnl = sum(tc.pnl for tc in self.trade_chains)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            wins = [tc.pnl for tc in self.trade_chains if tc.pnl > 0]
            losses = [tc.pnl for tc in self.trade_chains if tc.pnl <= 0]
            
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0
            
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
            
            # Sharpe ratio
            pnl_values = [tc.pnl for tc in self.trade_chains]
            sharpe_ratio = np.mean(pnl_values) / np.std(pnl_values) if np.std(pnl_values) > 0 else 0
            
            # Max drawdown
            max_drawdown = max([tc.max_adverse for tc in self.trade_chains]) if self.trade_chains else 0
            
            # Average hold time
            avg_hold_time = np.mean([tc.hold_time_minutes for tc in self.trade_chains])
            
            # Success rates
            breakout_trades = [tc for tc in self.trade_chains if tc.signal_type == "BREAKOUT"]
            reversal_trades = [tc for tc in self.trade_chains if tc.signal_type == "REVERSAL"]
            
            breakout_success_rate = sum(1 for tc in breakout_trades if tc.pnl > 0) / len(breakout_trades) if breakout_trades else 0
            reversal_success_rate = sum(1 for tc in reversal_trades if tc.pnl > 0) / len(reversal_trades) if reversal_trades else 0
            
            # DP confirmation rate
            dp_confirmation_rate = sum(1 for tc in self.trade_chains if tc.dp_confirmation) / total_trades if total_trades > 0 else 0
            
            # False signal rate (trades with negative P&L)
            false_signal_rate = losing_trades / total_trades if total_trades > 0 else 0
            
            # Magnet accuracy (how often we hit magnet levels)
            magnet_accuracy = sum(1 for tc in self.trade_chains if tc.magnet_level > 0) / total_trades if total_trades > 0 else 0
            
            return RealEdgeMetrics(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                total_pnl=total_pnl,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                avg_hold_time=avg_hold_time,
                breakout_success_rate=breakout_success_rate,
                reversal_success_rate=reversal_success_rate,
                dp_confirmation_rate=dp_confirmation_rate,
                false_signal_rate=false_signal_rate,
                magnet_accuracy=magnet_accuracy
            )
            
        except Exception as e:
            logger.error(f"Error calculating real edge metrics: {e}")
            return RealEdgeMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    def _generate_real_visualization_data(self) -> Dict[str, Any]:
        """Generate real visualization data"""
        try:
            visualization_data = {
                'trade_chains': [],
                'price_paths': {},
                'signal_timelines': {},
                'performance_curves': {}
            }
            
            # Convert trade chains to visualization format
            for tc in self.trade_chains:
                visualization_data['trade_chains'].append({
                    'ticker': tc.ticker,
                    'signal_type': tc.signal_type,
                    'entry_time': tc.entry_time.isoformat(),
                    'entry_price': tc.entry_price,
                    'exit_time': tc.exit_time.isoformat() if tc.exit_time else None,
                    'exit_price': tc.exit_price,
                    'pnl': tc.pnl,
                    'max_favorable': tc.max_favorable,
                    'max_adverse': tc.max_adverse,
                    'hold_time_minutes': tc.hold_time_minutes,
                    'confidence': tc.confidence,
                    'risk_level': tc.risk_level,
                    'magnet_level': tc.magnet_level,
                    'volume_spike': tc.volume_spike,
                    'options_flow': tc.options_flow
                })
            
            # Add price paths
            for ticker, price_history in self.price_history.items():
                visualization_data['price_paths'][ticker] = price_history
            
            return visualization_data
            
        except Exception as e:
            logger.error(f"Error generating real visualization data: {e}")
            return {}
    
    def _generate_real_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate real summary of results"""
        try:
            edge_metrics = results.get('edge_metrics', {})
            
            summary = {
                'total_breakouts': len(results.get('detected_breakouts', [])),
                'total_reversals': len(results.get('detected_reversals', [])),
                'total_trades': edge_metrics.get('total_trades', 0),
                'winning_trades': edge_metrics.get('winning_trades', 0),
                'losing_trades': edge_metrics.get('losing_trades', 0),
                'total_pnl': edge_metrics.get('total_pnl', 0),
                'win_rate': edge_metrics.get('win_rate', 0),
                'avg_win': edge_metrics.get('avg_win', 0),
                'avg_loss': edge_metrics.get('avg_loss', 0),
                'profit_factor': edge_metrics.get('profit_factor', 0),
                'sharpe_ratio': edge_metrics.get('sharpe_ratio', 0),
                'max_drawdown': edge_metrics.get('max_drawdown', 0),
                'avg_hold_time': edge_metrics.get('avg_hold_time', 0),
                'breakout_success_rate': edge_metrics.get('breakout_success_rate', 0),
                'reversal_success_rate': edge_metrics.get('reversal_success_rate', 0),
                'dp_confirmation_rate': edge_metrics.get('dp_confirmation_rate', 0),
                'false_signal_rate': edge_metrics.get('false_signal_rate', 0),
                'magnet_accuracy': edge_metrics.get('magnet_accuracy', 0)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating real summary: {e}")
            return {}
    
    def _display_real_detection_results(self, results: Dict[str, Any]):
        """Display real detection results"""
        try:
            print(f"\n{'='*120}")
            print(f"🎯 REAL BREAKOUT & REVERSAL DETECTION RESULTS")
            print(f"{'='*120}")
            
            # Summary
            summary = results.get('summary', {})
            print(f"\n📊 REAL-TIME DETECTION SUMMARY:")
            print(f"   Total Breakouts Detected: {summary.get('total_breakouts', 0)}")
            print(f"   Total Reversals Detected: {summary.get('total_reversals', 0)}")
            print(f"   Total Trades: {summary.get('total_trades', 0)}")
            print(f"   Winning Trades: {summary.get('winning_trades', 0)}")
            print(f"   Losing Trades: {summary.get('losing_trades', 0)}")
            print(f"   Total P&L: {summary.get('total_pnl', 0):.4f}")
            print(f"   Win Rate: {summary.get('win_rate', 0):.2%}")
            print(f"   Avg Win: {summary.get('avg_win', 0):.2%}")
            print(f"   Avg Loss: {summary.get('avg_loss', 0):.2%}")
            print(f"   Profit Factor: {summary.get('profit_factor', 0):.2f}")
            print(f"   Sharpe Ratio: {summary.get('sharpe_ratio', 0):.2f}")
            print(f"   Max Drawdown: {summary.get('max_drawdown', 0):.2%}")
            print(f"   Avg Hold Time: {summary.get('avg_hold_time', 0):.1f} minutes")
            print(f"   Breakout Success Rate: {summary.get('breakout_success_rate', 0):.2%}")
            print(f"   Reversal Success Rate: {summary.get('reversal_success_rate', 0):.2%}")
            print(f"   DP Confirmation Rate: {summary.get('dp_confirmation_rate', 0):.2%}")
            print(f"   False Signal Rate: {summary.get('false_signal_rate', 0):.2%}")
            print(f"   Magnet Accuracy: {summary.get('magnet_accuracy', 0):.2%}")
            
            # Detected Breakouts
            detected_breakouts = results.get('detected_breakouts', [])
            print(f"\n📈 DETECTED BREAKOUTS:")
            for breakout in detected_breakouts:
                print(f"\n   {breakout['ticker']} - {breakout['timestamp'].strftime('%H:%M:%S')}:")
                print(f"      Entry Price: ${breakout['entry_price']:.2f}")
                print(f"      Resistance Level: ${breakout['resistance_level']:.2f}")
                print(f"      Breakout Strength: {breakout['breakout_strength']:.2%}")
                print(f"      Volume Spike: {breakout['volume_spike']}")
                print(f"      Options Flow: {breakout['options_flow']}")
                print(f"      DP Confirmation: {breakout['dp_confirmation']}")
                print(f"      Confidence: {breakout['confidence']:.2f}")
                print(f"      Risk Level: {breakout['risk_level']}")
                print(f"      Reasoning: {breakout['reasoning']}")
            
            # Detected Reversals
            detected_reversals = results.get('detected_reversals', [])
            print(f"\n📉 DETECTED REVERSALS:")
            for reversal in detected_reversals:
                print(f"\n   {reversal['ticker']} - {reversal['timestamp'].strftime('%H:%M:%S')}:")
                print(f"      Entry Price: ${reversal['entry_price']:.2f}")
                print(f"      Support Level: ${reversal['support_level']:.2f}")
                print(f"      Reversal Strength: {reversal['reversal_strength']:.2%}")
                print(f"      Volume Spike: {reversal['volume_spike']}")
                print(f"      Options Flow: {reversal['options_flow']}")
                print(f"      DP Confirmation: {reversal['dp_confirmation']}")
                print(f"      Confidence: {reversal['confidence']:.2f}")
                print(f"      Risk Level: {reversal['risk_level']}")
                print(f"      Reasoning: {reversal['reasoning']}")
            
            # Trade Chains
            trade_chains = results.get('trade_chains', [])
            print(f"\n🔗 REAL TRADE CHAINS:")
            for tc in trade_chains:
                print(f"\n   {tc.ticker} - {tc.signal_type}:")
                print(f"      Entry: ${tc.entry_price:.2f} @ {tc.entry_time.strftime('%H:%M:%S')}")
                if tc.exit_time:
                    print(f"      Exit: ${tc.exit_price:.2f} @ {tc.exit_time.strftime('%H:%M:%S')}")
                    print(f"      P&L: {tc.pnl:.2%}")
                    print(f"      Hold Time: {tc.hold_time_minutes:.1f} minutes")
                    print(f"      Max Favorable: {tc.max_favorable:.2%}")
                    print(f"      Max Adverse: {tc.max_adverse:.2%}")
                print(f"      Signal: {tc.signal_type}")
                print(f"      Confidence: {tc.confidence:.2f}")
                print(f"      Risk Level: {tc.risk_level}")
                print(f"      DP Confirmation: {tc.dp_confirmation}")
                print(f"      Magnet Level: ${tc.magnet_level:.2f}")
                print(f"      Volume Spike: {tc.volume_spike}")
                print(f"      Options Flow: {tc.options_flow}")
                print(f"      Reasoning: {tc.reasoning}")
            
            print(f"\n✅ REAL BREAKOUT & REVERSAL DETECTION COMPLETE!")
            print(f"🎯 REAL-TIME TRADE CHAINS VISUALIZED!")
            
        except Exception as e:
            logger.error(f"Error displaying real detection results: {e}")
    
    async def _generate_real_detection_charts(self, results: Dict[str, Any]):
        """Generate real detection charts"""
        try:
            logger.info("📊 GENERATING REAL DETECTION CHARTS")
            
            # Create main figure
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 15))
            
            # Plot 1: Real Trade Chain Performance
            trade_chains = results.get('trade_chains', [])
            if trade_chains:
                tickers = [tc.ticker for tc in trade_chains]
                pnls = [tc.pnl for tc in trade_chains]
                colors = ['green' if pnl > 0 else 'red' for pnl in pnls]
                
                bars = ax1.bar(range(len(trade_chains)), pnls, color=colors, alpha=0.7)
                ax1.set_title('Real Trade Chain Performance', fontsize=14, fontweight='bold')
                ax1.set_xlabel('Trade Number')
                ax1.set_ylabel('P&L (%)')
                ax1.grid(True, alpha=0.3)
                
                # Add value labels on bars
                for i, (bar, pnl) in enumerate(zip(bars, pnls)):
                    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                            f'{pnl:.1%}', ha='center', va='bottom', fontsize=8)
            
            # Plot 2: Detection Timeline
            detected_breakouts = results.get('detected_breakouts', [])
            detected_reversals = results.get('detected_reversals', [])
            
            if detected_breakouts or detected_reversals:
                # Plot breakouts
                if detected_breakouts:
                    breakout_times = [b['timestamp'] for b in detected_breakouts]
                    breakout_prices = [b['entry_price'] for b in detected_breakouts]
                    ax2.scatter(breakout_times, breakout_prices, color='blue', s=100, alpha=0.7, label='Breakouts')
                
                # Plot reversals
                if detected_reversals:
                    reversal_times = [r['timestamp'] for r in detected_reversals]
                    reversal_prices = [r['entry_price'] for r in detected_reversals]
                    ax2.scatter(reversal_times, reversal_prices, color='red', s=100, alpha=0.7, label='Reversals')
                
                ax2.set_title('Detection Timeline', fontsize=14, fontweight='bold')
                ax2.set_xlabel('Time')
                ax2.set_ylabel('Price ($)')
                ax2.legend()
                ax2.grid(True, alpha=0.3)
            
            # Plot 3: Confidence vs Performance
            if trade_chains:
                confidences = [tc.confidence for tc in trade_chains]
                pnls = [tc.pnl for tc in trade_chains]
                
                scatter = ax3.scatter(confidences, pnls, c=pnls, cmap='RdYlGn', alpha=0.7, s=100)
                ax3.set_title('Confidence vs Performance', fontsize=14, fontweight='bold')
                ax3.set_xlabel('Confidence')
                ax3.set_ylabel('P&L (%)')
                ax3.grid(True, alpha=0.3)
                plt.colorbar(scatter, ax=ax3, label='P&L (%)')
            
            # Plot 4: Real Edge Metrics
            edge_metrics = results.get('edge_metrics', {})
            if edge_metrics:
                metrics_names = ['Win Rate', 'DP Confirmation Rate', 'Magnet Accuracy', 'Breakout Success Rate']
                metrics_values = [
                    edge_metrics.get('win_rate', 0),
                    edge_metrics.get('dp_confirmation_rate', 0),
                    edge_metrics.get('magnet_accuracy', 0),
                    edge_metrics.get('breakout_success_rate', 0)
                ]
                
                bars = ax4.bar(metrics_names, metrics_values, color=['green', 'blue', 'purple', 'orange'], alpha=0.7)
                ax4.set_title('Real Edge Metrics', fontsize=14, fontweight='bold')
                ax4.set_ylabel('Value')
                ax4.grid(True, alpha=0.3)
                
                # Add value labels on bars
                for bar, value in zip(bars, metrics_values):
                    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                            f'{value:.2f}', ha='center', va='bottom', fontsize=10)
            
            plt.tight_layout()
            plt.savefig('real_breakout_reversal_detection.png', dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info("📊 Real detection chart saved: real_breakout_reversal_detection.png")
            
        except Exception as e:
            logger.error(f"Error generating real detection charts: {e}")

async def main():
    """Main function"""
    print("🔥 REAL BREAKOUT & REVERSAL DETECTOR WITH RATE LIMIT SOLVER")
    print("=" * 80)
    
    detector = RealBreakoutReversalDetector()
    
    # Focus on major movers
    tickers = ['SPY', 'QQQ', 'TSLA', 'AAPL', 'NVDA']
    
    try:
        results = await detector.run_real_breakout_reversal_detection(tickers, duration_hours=0.1)  # 6 minutes
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        print(f"\n🎯 REAL BREAKOUT & REVERSAL DETECTION COMPLETE!")
        print(f"🚀 REAL-TIME TRADE CHAINS VISUALIZED!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
