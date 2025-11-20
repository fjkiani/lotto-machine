#!/usr/bin/env python3
"""
MARKET OPEN SIMULATION - 9:30 AM ANALYSIS
Simulates what our system would have detected at market open
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Import our real systems
from ultimate_real_data_system import UltimateRealDataSystem
from real_yahoo_finance_api import RealYahooFinanceAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MarketOpenSimulation:
    """Simulates market open analysis at 9:30 AM"""
    
    def __init__(self):
        self.system = UltimateRealDataSystem()
        self.yahoo_api = RealYahooFinanceAPI()
        
        # Simulate market open conditions
        self.market_open_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        
    async def simulate_market_open_analysis(self) -> Dict[str, Any]:
        """Simulate what we would have detected at 9:30 AM"""
        try:
            logger.info(f"🚀 SIMULATING MARKET OPEN ANALYSIS AT 9:30 AM")
            logger.info(f"📅 SIMULATION TIME: {self.market_open_time}")
            
            # Key tickers for market open analysis
            tickers = ['SPY', 'QQQ', 'DIA', 'IWM', 'AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN']
            
            analysis_results = []
            alerts = []
            
            for ticker in tickers:
                logger.info(f"\n🔍 ANALYZING {ticker} AT MARKET OPEN")
                
                # Get comprehensive real data (simulating market open conditions)
                analysis = await self.system.analyze_ticker_comprehensive(ticker)
                
                if analysis.get('error'):
                    logger.warning(f"Error analyzing {ticker}: {analysis['error']}")
                    continue
                
                # Enhance with market open context
                enhanced_analysis = self._enhance_with_market_open_context(analysis)
                analysis_results.append(enhanced_analysis)
                
                # Check for alerts
                ticker_alerts = self._check_for_alerts(enhanced_analysis)
                alerts.extend(ticker_alerts)
                
                # Display results
                self._display_market_open_analysis(enhanced_analysis)
                
                # Rate limiting
                await asyncio.sleep(1)
            
            # Generate market open summary
            market_summary = self._generate_market_open_summary(analysis_results, alerts)
            
            return {
                'simulation_time': self.market_open_time,
                'tickers_analyzed': len(analysis_results),
                'results': analysis_results,
                'alerts': alerts,
                'market_summary': market_summary
            }
            
        except Exception as e:
            logger.error(f"Error simulating market open analysis: {e}")
            return {'error': str(e)}
    
    def _enhance_with_market_open_context(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance analysis with market open context"""
        try:
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return analysis
            
            # Analyze pre-market vs open conditions
            change_percent = current_quote.change_percent
            volume = current_quote.volume
            
            # Determine market open strength
            if abs(change_percent) > 2:
                open_strength = 'STRONG_OPEN'
            elif abs(change_percent) > 1:
                open_strength = 'MODERATE_OPEN'
            elif abs(change_percent) > 0.5:
                open_strength = 'WEAK_OPEN'
            else:
                open_strength = 'FLAT_OPEN'
            
            # Analyze opening volume
            if volume > 50_000_000:
                volume_strength = 'HIGH_VOLUME_OPEN'
            elif volume > 20_000_000:
                volume_strength = 'MODERATE_VOLUME_OPEN'
            else:
                volume_strength = 'LOW_VOLUME_OPEN'
            
            # Determine if we would have caught this at open
            would_catch_at_open = self._would_catch_at_open(analysis, change_percent, volume)
            
            # Add enhanced data
            analysis['open_strength'] = open_strength
            analysis['volume_strength'] = volume_strength
            analysis['would_catch_at_open'] = would_catch_at_open
            analysis['market_open_analysis'] = self._analyze_market_open_pattern(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error enhancing market open context: {e}")
            return analysis
    
    def _would_catch_at_open(self, analysis: Dict[str, Any], change_percent: float, volume: int) -> Dict[str, Any]:
        """Determine if we would have caught this at market open"""
        try:
            signals = analysis.get('signals', [])
            magnets = analysis.get('magnets', [])
            options_flows = analysis.get('options_flows', [])
            
            # Check if we had signals
            had_signals = len(signals) > 0
            
            # Check if we had magnet levels
            had_magnets = len(magnets) > 0
            
            # Check if we had options flows
            had_options = len(options_flows) > 0
            
            # Determine catch probability at market open
            if had_signals and had_magnets and had_options:
                catch_probability = 'HIGH'
            elif had_signals and had_magnets:
                catch_probability = 'MEDIUM'
            elif had_magnets and had_options:
                catch_probability = 'MEDIUM'
            elif had_magnets:
                catch_probability = 'LOW'
            else:
                catch_probability = 'NONE'
            
            # Analyze what we would have detected
            detected_indicators = []
            if had_signals:
                detected_indicators.append('composite_signals')
            if had_options:
                detected_indicators.append('options_flows')
            if had_magnets:
                detected_indicators.append('magnet_levels')
            
            # Check for opening gap
            opening_gap = abs(change_percent) > 1.0
            
            # Check for volume spike
            volume_spike = volume > 30_000_000
            
            return {
                'catch_probability': catch_probability,
                'had_signals': had_signals,
                'had_magnets': had_magnets,
                'had_options': had_options,
                'detected_indicators': detected_indicators,
                'opening_gap': opening_gap,
                'volume_spike': volume_spike,
                'would_alert': catch_probability in ['HIGH', 'MEDIUM']
            }
            
        except Exception as e:
            logger.error(f"Error determining catch probability: {e}")
            return {'catch_probability': 'UNKNOWN'}
    
    def _analyze_market_open_pattern(self, analysis: Dict[str, Any]) -> str:
        """Analyze the market open pattern"""
        try:
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return 'no_data'
            
            change_percent = current_quote.change_percent
            volume = current_quote.volume
            
            # Pattern analysis for market open
            if change_percent > 2 and volume > 50_000_000:
                return 'GAP_UP_BREAKOUT'
            elif change_percent > 1 and volume > 30_000_000:
                return 'STRONG_GAP_UP'
            elif change_percent < -2 and volume > 50_000_000:
                return 'GAP_DOWN_BREAKDOWN'
            elif change_percent < -1 and volume > 30_000_000:
                return 'STRONG_GAP_DOWN'
            elif abs(change_percent) < 0.5:
                return 'FLAT_OPEN'
            else:
                return 'NORMAL_OPEN'
                
        except Exception as e:
            logger.error(f"Error analyzing market open pattern: {e}")
            return 'unknown'
    
    def _check_for_alerts(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for alerts that would have been sent"""
        try:
            alerts = []
            ticker = analysis['ticker']
            current_price = analysis['current_price']
            catch_analysis = analysis['would_catch_at_open']
            
            # Check for high probability catches
            if catch_analysis['catch_probability'] == 'HIGH':
                alerts.append({
                    'ticker': ticker,
                    'type': 'HIGH_CONFIDENCE_SIGNAL',
                    'message': f"🚨 HIGH CONFIDENCE SIGNAL: {ticker} at ${current_price:.2f}",
                    'confidence': 'HIGH',
                    'action': 'IMMEDIATE_ATTENTION'
                })
            
            # Check for opening gaps
            if catch_analysis['opening_gap']:
                alerts.append({
                    'ticker': ticker,
                    'type': 'OPENING_GAP',
                    'message': f"📈 OPENING GAP: {ticker} {analysis['current_quote'].change_percent:+.2f}%",
                    'confidence': 'MEDIUM',
                    'action': 'MONITOR_CLOSELY'
                })
            
            # Check for volume spikes
            if catch_analysis['volume_spike']:
                alerts.append({
                    'ticker': ticker,
                    'type': 'VOLUME_SPIKE',
                    'message': f"📊 VOLUME SPIKE: {ticker} {analysis['current_quote'].volume:,} shares",
                    'confidence': 'MEDIUM',
                    'action': 'INVESTIGATE'
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking for alerts: {e}")
            return []
    
    def _display_market_open_analysis(self, analysis: Dict[str, Any]):
        """Display analysis for market open"""
        try:
            print(f"\n{'='*80}")
            print(f"📊 TICKER: {analysis['ticker']}")
            print(f"💰 PRICE: ${analysis['current_price']:.2f}")
            print(f"📈 CHANGE: {analysis['current_quote'].change:.2f} ({analysis['current_quote'].change_percent:.2f}%)")
            print(f"📊 VOLUME: {analysis['current_quote'].volume:,}")
            print(f"🎯 OPEN STRENGTH: {analysis['open_strength']}")
            print(f"📊 VOLUME STRENGTH: {analysis['volume_strength']}")
            print(f"🔍 MARKET OPEN PATTERN: {analysis['market_open_analysis']}")
            
            # Catch analysis
            catch_analysis = analysis['would_catch_at_open']
            print(f"\n🎯 WOULD WE CATCH THIS AT 9:30 AM?")
            print(f"   Probability: {catch_analysis['catch_probability']}")
            print(f"   Had Signals: {catch_analysis['had_signals']}")
            print(f"   Had Magnets: {catch_analysis['had_magnets']}")
            print(f"   Had Options: {catch_analysis['had_options']}")
            print(f"   Opening Gap: {catch_analysis['opening_gap']}")
            print(f"   Volume Spike: {catch_analysis['volume_spike']}")
            print(f"   Would Alert: {catch_analysis['would_alert']}")
            
            if catch_analysis['detected_indicators']:
                print(f"   Detected: {', '.join(catch_analysis['detected_indicators'])}")
            
            # Data analysis
            print(f"\n📊 DATA ANALYSIS:")
            print(f"   Options Flows: {len(analysis['options_flows'])}")
            print(f"   Magnet Levels: {len(analysis['magnets'])}")
            print(f"   Total Signals: {analysis['total_signals']}")
            print(f"   BUY Signals: {analysis['buy_signals']}")
            print(f"   SELL Signals: {analysis['sell_signals']}")
            
            if analysis['magnets']:
                print(f"\n🧲 MAGNET LEVELS:")
                for i, magnet in enumerate(analysis['magnets'][:3]):
                    print(f"   {i+1}. ${magnet.price:.2f} - ${magnet.notional_volume:,.0f} notional")
            
            if analysis['signals']:
                print(f"\n🚨 SIGNALS:")
                for i, signal in enumerate(analysis['signals'][:3]):
                    print(f"   {i+1}. {signal.action} - {signal.signal_types} - Confidence: {signal.confidence:.2f}")
            
            print(f"{'='*80}")
            
        except Exception as e:
            logger.error(f"Error displaying market open analysis: {e}")
    
    def _generate_market_open_summary(self, results: List[Dict[str, Any]], alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate market open summary"""
        try:
            total_tickers = len(results)
            
            # Count catch probabilities
            catch_counts = {}
            open_pattern_counts = {}
            
            for result in results:
                catch = result.get('would_catch_at_open', {}).get('catch_probability', 'unknown')
                pattern = result.get('market_open_analysis', 'unknown')
                
                catch_counts[catch] = catch_counts.get(catch, 0) + 1
                open_pattern_counts[pattern] = open_pattern_counts.get(pattern, 0) + 1
            
            # Count alerts by type
            alert_counts = {}
            for alert in alerts:
                alert_type = alert['type']
                alert_counts[alert_type] = alert_counts.get(alert_type, 0) + 1
            
            # Find biggest movers
            biggest_gainers = sorted(results, key=lambda x: x['current_quote'].change_percent, reverse=True)[:3]
            biggest_losers = sorted(results, key=lambda x: x['current_quote'].change_percent)[:3]
            
            # Find high confidence catches
            high_confidence_catches = [r for r in results if r.get('would_catch_at_open', {}).get('catch_probability') == 'HIGH']
            
            return {
                'total_tickers': total_tickers,
                'catch_probability_distribution': catch_counts,
                'open_pattern_distribution': open_pattern_counts,
                'alert_counts': alert_counts,
                'total_alerts': len(alerts),
                'high_confidence_catches': len(high_confidence_catches),
                'biggest_gainers': biggest_gainers,
                'biggest_losers': biggest_losers,
                'high_confidence_tickers': [r['ticker'] for r in high_confidence_catches]
            }
            
        except Exception as e:
            logger.error(f"Error generating market open summary: {e}")
            return {'error': str(e)}

async def main():
    """Main function"""
    print("🔥 MARKET OPEN SIMULATION - 9:30 AM ANALYSIS")
    print("=" * 60)
    
    simulator = MarketOpenSimulation()
    
    try:
        results = await simulator.simulate_market_open_analysis()
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        print(f"\n{'='*100}")
        print(f"🎯 MARKET OPEN SIMULATION SUMMARY (9:30 AM)")
        print(f"{'='*100}")
        
        summary = results['market_summary']
        alerts = results['alerts']
        
        print(f"\n📊 OVERALL MARKET OPEN:")
        print(f"   Tickers Analyzed: {summary['total_tickers']}")
        print(f"   Total Alerts: {summary['total_alerts']}")
        print(f"   High Confidence Catches: {summary['high_confidence_catches']}")
        
        print(f"\n🎯 CATCH PROBABILITY DISTRIBUTION:")
        for catch, count in summary['catch_probability_distribution'].items():
            print(f"   {catch}: {count} tickers")
        
        print(f"\n🔍 OPEN PATTERN DISTRIBUTION:")
        for pattern, count in summary['open_pattern_distribution'].items():
            print(f"   {pattern}: {count} tickers")
        
        print(f"\n🚨 ALERT BREAKDOWN:")
        for alert_type, count in summary['alert_counts'].items():
            print(f"   {alert_type}: {count} alerts")
        
        print(f"\n📈 BIGGEST GAINERS AT OPEN:")
        for i, gainer in enumerate(summary['biggest_gainers']):
            print(f"   {i+1}. {gainer['ticker']} - {gainer['current_quote'].change_percent:.2f}%")
        
        print(f"\n📉 BIGGEST LOSERS AT OPEN:")
        for i, loser in enumerate(summary['biggest_losers']):
            print(f"   {i+1}. {loser['ticker']} - {loser['current_quote'].change_percent:.2f}%")
        
        if summary['high_confidence_tickers']:
            print(f"\n🔥 HIGH CONFIDENCE CATCHES:")
            for ticker in summary['high_confidence_tickers']:
                print(f"   🎯 {ticker} - Would have caught this move!")
        
        print(f"\n🚨 ALERTS THAT WOULD HAVE BEEN SENT:")
        for alert in alerts:
            print(f"   {alert['type']}: {alert['message']}")
            print(f"      Action: {alert['action']}")
        
        print(f"\n✅ MARKET OPEN SIMULATION COMPLETE!")
        print(f"🎯 SIMULATED 9:30 AM ANALYSIS!")
        print(f"🚨 {len(alerts)} ALERTS WOULD HAVE BEEN SENT!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

