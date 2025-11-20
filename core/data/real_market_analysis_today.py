#!/usr/bin/env python3
"""
REAL MARKET ANALYSIS - TODAY'S MOVEMENTS
Analyzes how today played out using real data and dark pool detection
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

class RealMarketAnalysis:
    """Real market analysis for today's movements"""
    
    def __init__(self):
        self.system = UltimateRealDataSystem()
        self.yahoo_api = RealYahooFinanceAPI()
        
    async def analyze_todays_market(self) -> Dict[str, Any]:
        """Analyze today's market movements using real data"""
        try:
            logger.info(f"🚀 ANALYZING TODAY'S MARKET MOVEMENTS")
            
            # Key tickers to analyze
            tickers = ['SPY', 'QQQ', 'DIA', 'IWM', 'AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN']
            
            analysis_results = []
            
            for ticker in tickers:
                logger.info(f"\n🔍 ANALYZING {ticker}")
                
                # Get comprehensive real data
                analysis = await self.system.analyze_ticker_comprehensive(ticker)
                
                if analysis.get('error'):
                    logger.warning(f"Error analyzing {ticker}: {analysis['error']}")
                    continue
                
                # Enhance with market context
                enhanced_analysis = self._enhance_with_market_context(analysis)
                analysis_results.append(enhanced_analysis)
                
                # Display results
                self._display_ticker_analysis(enhanced_analysis)
                
                # Rate limiting
                await asyncio.sleep(1)
            
            # Generate market summary
            market_summary = self._generate_market_summary(analysis_results)
            
            return {
                'analysis_time': datetime.now(),
                'tickers_analyzed': len(analysis_results),
                'results': analysis_results,
                'market_summary': market_summary
            }
            
        except Exception as e:
            logger.error(f"Error analyzing today's market: {e}")
            return {'error': str(e)}
    
    def _enhance_with_market_context(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance analysis with market context"""
        try:
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return analysis
            
            # Analyze price movement
            change_percent = current_quote.change_percent
            volume = current_quote.volume
            
            # Determine movement strength
            if abs(change_percent) > 3:
                movement_strength = 'EXTREME'
            elif abs(change_percent) > 2:
                movement_strength = 'STRONG'
            elif abs(change_percent) > 1:
                movement_strength = 'MODERATE'
            else:
                movement_strength = 'WEAK'
            
            # Analyze volume
            if volume > 100_000_000:
                volume_strength = 'EXTREME'
            elif volume > 50_000_000:
                volume_strength = 'HIGH'
            elif volume > 20_000_000:
                volume_strength = 'MODERATE'
            else:
                volume_strength = 'LOW'
            
            # Determine if we could have caught this move
            could_catch_move = self._could_catch_move(analysis, change_percent, volume)
            
            # Add enhanced data
            analysis['movement_strength'] = movement_strength
            analysis['volume_strength'] = volume_strength
            analysis['could_catch_move'] = could_catch_move
            analysis['movement_analysis'] = self._analyze_movement_pattern(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error enhancing market context: {e}")
            return analysis
    
    def _could_catch_move(self, analysis: Dict[str, Any], change_percent: float, volume: int) -> Dict[str, Any]:
        """Determine if we could have caught this move"""
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
            
            # Determine catch probability
            if had_signals and had_magnets and had_options:
                catch_probability = 'HIGH'
            elif had_signals and had_magnets:
                catch_probability = 'MEDIUM'
            elif had_magnets:
                catch_probability = 'LOW'
            else:
                catch_probability = 'NONE'
            
            # Analyze what we missed
            missed_indicators = []
            if not had_signals:
                missed_indicators.append('composite_signals')
            if not had_options:
                missed_indicators.append('options_flows')
            if not had_magnets:
                missed_indicators.append('magnet_levels')
            
            return {
                'catch_probability': catch_probability,
                'had_signals': had_signals,
                'had_magnets': had_magnets,
                'had_options': had_options,
                'missed_indicators': missed_indicators,
                'volume_threshold_met': volume > 20_000_000,
                'price_threshold_met': abs(change_percent) > 1.0
            }
            
        except Exception as e:
            logger.error(f"Error determining catch probability: {e}")
            return {'catch_probability': 'UNKNOWN'}
    
    def _analyze_movement_pattern(self, analysis: Dict[str, Any]) -> str:
        """Analyze the movement pattern"""
        try:
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return 'no_data'
            
            change_percent = current_quote.change_percent
            volume = current_quote.volume
            
            # Pattern analysis
            if change_percent > 2 and volume > 50_000_000:
                return 'BREAKOUT_WITH_VOLUME'
            elif change_percent > 1 and volume > 30_000_000:
                return 'STRONG_TREND'
            elif abs(change_percent) < 0.5:
                return 'CONSOLIDATION'
            elif change_percent < -2 and volume > 50_000_000:
                return 'BREAKDOWN_WITH_VOLUME'
            else:
                return 'NORMAL_MOVEMENT'
                
        except Exception as e:
            logger.error(f"Error analyzing movement pattern: {e}")
            return 'unknown'
    
    def _display_ticker_analysis(self, analysis: Dict[str, Any]):
        """Display analysis for a ticker"""
        try:
            print(f"\n{'='*80}")
            print(f"📊 TICKER: {analysis['ticker']}")
            print(f"💰 PRICE: ${analysis['current_price']:.2f}")
            print(f"📈 CHANGE: {analysis['current_quote'].change:.2f} ({analysis['current_quote'].change_percent:.2f}%)")
            print(f"📊 VOLUME: {analysis['current_quote'].volume:,}")
            print(f"🎯 MOVEMENT STRENGTH: {analysis['movement_strength']}")
            print(f"📊 VOLUME STRENGTH: {analysis['volume_strength']}")
            print(f"🔍 MOVEMENT PATTERN: {analysis['movement_analysis']}")
            
            # Catch analysis
            catch_analysis = analysis['could_catch_move']
            print(f"\n🎯 COULD WE CATCH THIS MOVE?")
            print(f"   Probability: {catch_analysis['catch_probability']}")
            print(f"   Had Signals: {catch_analysis['had_signals']}")
            print(f"   Had Magnets: {catch_analysis['had_magnets']}")
            print(f"   Had Options: {catch_analysis['had_options']}")
            
            if catch_analysis['missed_indicators']:
                print(f"   Missed: {', '.join(catch_analysis['missed_indicators'])}")
            
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
            logger.error(f"Error displaying ticker analysis: {e}")
    
    def _generate_market_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate market summary"""
        try:
            total_tickers = len(results)
            
            # Count movement strengths
            movement_counts = {}
            volume_counts = {}
            catch_counts = {}
            
            for result in results:
                movement = result.get('movement_strength', 'unknown')
                volume = result.get('volume_strength', 'unknown')
                catch = result.get('could_catch_move', {}).get('catch_probability', 'unknown')
                
                movement_counts[movement] = movement_counts.get(movement, 0) + 1
                volume_counts[volume] = volume_counts.get(volume, 0) + 1
                catch_counts[catch] = catch_counts.get(catch, 0) + 1
            
            # Calculate averages
            total_change = sum(r['current_quote'].change_percent for r in results if r.get('current_quote'))
            total_volume = sum(r['current_quote'].volume for r in results if r.get('current_quote'))
            
            avg_change = total_change / total_tickers if total_tickers > 0 else 0
            avg_volume = total_volume / total_tickers if total_tickers > 0 else 0
            
            # Find biggest movers
            biggest_gainers = sorted(results, key=lambda x: x['current_quote'].change_percent, reverse=True)[:3]
            biggest_losers = sorted(results, key=lambda x: x['current_quote'].change_percent)[:3]
            
            return {
                'total_tickers': total_tickers,
                'avg_change_percent': avg_change,
                'avg_volume': avg_volume,
                'movement_distribution': movement_counts,
                'volume_distribution': volume_counts,
                'catch_probability_distribution': catch_counts,
                'biggest_gainers': biggest_gainers,
                'biggest_losers': biggest_losers
            }
            
        except Exception as e:
            logger.error(f"Error generating market summary: {e}")
            return {'error': str(e)}

async def main():
    """Main function"""
    print("🔥 REAL MARKET ANALYSIS - TODAY'S MOVEMENTS")
    print("=" * 60)
    
    analyzer = RealMarketAnalysis()
    
    try:
        results = await analyzer.analyze_todays_market()
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        print(f"\n{'='*100}")
        print(f"🎯 TODAY'S MARKET ANALYSIS SUMMARY")
        print(f"{'='*100}")
        
        summary = results['market_summary']
        
        print(f"\n📊 OVERALL MARKET:")
        print(f"   Tickers Analyzed: {summary['total_tickers']}")
        print(f"   Average Change: {summary['avg_change_percent']:.2f}%")
        print(f"   Average Volume: {summary['avg_volume']:,.0f}")
        
        print(f"\n🎯 MOVEMENT DISTRIBUTION:")
        for movement, count in summary['movement_distribution'].items():
            print(f"   {movement}: {count} tickers")
        
        print(f"\n📊 VOLUME DISTRIBUTION:")
        for volume, count in summary['volume_distribution'].items():
            print(f"   {volume}: {count} tickers")
        
        print(f"\n🔍 CATCH PROBABILITY DISTRIBUTION:")
        for catch, count in summary['catch_probability_distribution'].items():
            print(f"   {catch}: {count} tickers")
        
        print(f"\n📈 BIGGEST GAINERS:")
        for i, gainer in enumerate(summary['biggest_gainers']):
            print(f"   {i+1}. {gainer['ticker']} - {gainer['current_quote'].change_percent:.2f}%")
        
        print(f"\n📉 BIGGEST LOSERS:")
        for i, loser in enumerate(summary['biggest_losers']):
            print(f"   {i+1}. {loser['ticker']} - {loser['current_quote'].change_percent:.2f}%")
        
        print(f"\n✅ REAL MARKET ANALYSIS COMPLETE!")
        print(f"🎯 ANALYZED TODAY'S REAL MOVEMENTS!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

