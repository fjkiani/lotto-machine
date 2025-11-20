#!/usr/bin/env python3
"""
FINAL REAL DATA DEMO - BUY AND SELL SIGNALS WITH REAL API
Tests multiple tickers and scenarios to show both BUY and SELL signals
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Import our ultimate system
from ultimate_real_data_system import UltimateRealDataSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class FinalRealDataDemo:
    """Final demo showing both BUY and SELL signals with real data"""
    
    def __init__(self):
        self.system = UltimateRealDataSystem()
        
    async def run_comprehensive_demo(self) -> Dict[str, Any]:
        """Run comprehensive demo with multiple tickers"""
        try:
            logger.info(f"🚀 RUNNING FINAL REAL DATA DEMO")
            
            # Test multiple tickers to find active options
            tickers_to_test = ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA', 'MSFT']
            
            results = []
            
            for ticker in tickers_to_test:
                logger.info(f"\n🔍 TESTING {ticker}")
                
                analysis = await self.system.analyze_ticker_comprehensive(ticker)
                
                if analysis.get('error'):
                    logger.warning(f"Error with {ticker}: {analysis['error']}")
                    continue
                
                # Enhance analysis
                enhanced_analysis = self._enhance_analysis(analysis)
                results.append(enhanced_analysis)
                
                # Show results
                self._display_ticker_results(enhanced_analysis)
                
                # Wait between requests to respect rate limits
                await asyncio.sleep(2)
            
            # Generate summary
            summary = self._generate_summary(results)
            
            return {
                'tickers_tested': len(results),
                'results': results,
                'summary': summary,
                'demo_time': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Error running comprehensive demo: {e}")
            return {'error': str(e)}
    
    def _enhance_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance analysis with additional context"""
        try:
            # Add signal strength analysis
            analysis['signal_strength'] = self._calculate_signal_strength(analysis)
            
            # Add market context
            analysis['market_context'] = self._analyze_market_context(analysis)
            
            # Add trading recommendation
            analysis['trading_recommendation'] = self._generate_trading_recommendation(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error enhancing analysis: {e}")
            return analysis
    
    def _calculate_signal_strength(self, analysis: Dict[str, Any]) -> str:
        """Calculate overall signal strength"""
        try:
            total_signals = analysis.get('total_signals', 0)
            buy_signals = analysis.get('buy_signals', 0)
            sell_signals = analysis.get('sell_signals', 0)
            
            if total_signals == 0:
                return 'none'
            
            # Calculate signal ratio
            if buy_signals > sell_signals * 2:
                return 'strong_buy'
            elif sell_signals > buy_signals * 2:
                return 'strong_sell'
            elif buy_signals > sell_signals:
                return 'weak_buy'
            elif sell_signals > buy_signals:
                return 'weak_sell'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error calculating signal strength: {e}")
            return 'unknown'
    
    def _analyze_market_context(self, analysis: Dict[str, Any]) -> str:
        """Analyze market context"""
        try:
            current_quote = analysis.get('current_quote')
            if not current_quote:
                return 'no_context'
            
            change_percent = current_quote.change_percent
            
            if change_percent > 2:
                return 'strong_bullish'
            elif change_percent > 0.5:
                return 'bullish'
            elif change_percent < -2:
                return 'strong_bearish'
            elif change_percent < -0.5:
                return 'bearish'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error analyzing market context: {e}")
            return 'unknown'
    
    def _generate_trading_recommendation(self, analysis: Dict[str, Any]) -> str:
        """Generate trading recommendation"""
        try:
            signal_strength = analysis.get('signal_strength', 'none')
            market_context = analysis.get('market_context', 'neutral')
            
            if signal_strength == 'strong_buy' and market_context in ['bullish', 'strong_bullish']:
                return 'STRONG BUY - Multiple bullish signals aligned'
            elif signal_strength == 'strong_sell' and market_context in ['bearish', 'strong_bearish']:
                return 'STRONG SELL - Multiple bearish signals aligned'
            elif signal_strength == 'weak_buy':
                return 'WEAK BUY - Cautious bullish sentiment'
            elif signal_strength == 'weak_sell':
                return 'WEAK SELL - Cautious bearish sentiment'
            else:
                return 'HOLD - No clear directional signals'
                
        except Exception as e:
            logger.error(f"Error generating trading recommendation: {e}")
            return 'UNKNOWN'
    
    def _display_ticker_results(self, analysis: Dict[str, Any]):
        """Display results for a ticker"""
        try:
            print(f"\n{'='*80}")
            print(f"📊 TICKER: {analysis['ticker']}")
            print(f"💰 PRICE: ${analysis['current_price']:.2f}")
            print(f"🎯 SIGNAL STRENGTH: {analysis['signal_strength'].upper()}")
            print(f"📈 MARKET CONTEXT: {analysis['market_context'].upper()}")
            print(f"💡 RECOMMENDATION: {analysis['trading_recommendation']}")
            print(f"📊 DATA SOURCE: {analysis['data_source']}")
            print(f"🔥 OPTIONS FLOWS: {len(analysis['options_flows'])}")
            print(f"🧲 MAGNET LEVELS: {len(analysis['magnets'])}")
            print(f"🚨 TOTAL SIGNALS: {analysis['total_signals']}")
            print(f"   BUY: {analysis['buy_signals']} | SELL: {analysis['sell_signals']} | HOLD: {analysis['hold_signals']}")
            
            if analysis['current_quote']:
                quote = analysis['current_quote']
                print(f"\n🔥 REAL MARKET QUOTE:")
                print(f"   Price: ${quote.price:.2f}")
                print(f"   Volume: {quote.volume:,}")
                print(f"   Change: {quote.change:.2f} ({quote.change_percent:.2f}%)")
            
            if analysis['magnets']:
                print(f"\n🧲 MAGNET LEVELS:")
                for i, magnet in enumerate(analysis['magnets'][:3]):
                    print(f"   {i+1}. ${magnet.price:.2f} - ${magnet.notional_volume:,.0f} notional - Confidence: {magnet.confidence:.2f}")
            
            if analysis['signals']:
                print(f"\n🚨 COMPOSITE SIGNALS:")
                for i, signal in enumerate(analysis['signals'][:3]):
                    print(f"   {i+1}. {signal.action} - {signal.signal_types} - Confidence: {signal.confidence:.2f}")
                    print(f"      Details: {signal.details}")
            
            if analysis['options_flows']:
                print(f"\n📊 REAL OPTIONS FLOWS:")
                for flow in analysis['options_flows'][:5]:
                    print(f"   {flow.ticker} - ${flow.strike:.2f} {flow.option_type} - {flow.contracts:,} contracts - Sweep: {flow.sweep_flag}")
            
            print(f"{'='*80}")
            
        except Exception as e:
            logger.error(f"Error displaying ticker results: {e}")
    
    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary of all results"""
        try:
            total_tickers = len(results)
            total_signals = sum(r.get('total_signals', 0) for r in results)
            total_buy_signals = sum(r.get('buy_signals', 0) for r in results)
            total_sell_signals = sum(r.get('sell_signals', 0) for r in results)
            total_hold_signals = sum(r.get('hold_signals', 0) for r in results)
            
            # Count signal strengths
            strength_counts = {}
            for result in results:
                strength = result.get('signal_strength', 'unknown')
                strength_counts[strength] = strength_counts.get(strength, 0) + 1
            
            # Count market contexts
            context_counts = {}
            for result in results:
                context = result.get('market_context', 'unknown')
                context_counts[context] = context_counts.get(context, 0) + 1
            
            # Find strongest signals
            strong_buy_tickers = [r for r in results if r.get('signal_strength') == 'strong_buy']
            strong_sell_tickers = [r for r in results if r.get('signal_strength') == 'strong_sell']
            
            summary = {
                'total_tickers': total_tickers,
                'total_signals': total_signals,
                'total_buy_signals': total_buy_signals,
                'total_sell_signals': total_sell_signals,
                'total_hold_signals': total_hold_signals,
                'strength_counts': strength_counts,
                'context_counts': context_counts,
                'strong_buy_tickers': len(strong_buy_tickers),
                'strong_sell_tickers': len(strong_sell_tickers),
                'signal_balance': 'balanced' if abs(total_buy_signals - total_sell_signals) <= 2 else 'unbalanced'
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {'error': str(e)}

async def main():
    """Main function"""
    print("🔥 FINAL REAL DATA DEMO - BUY AND SELL SIGNALS")
    print("=" * 60)
    
    demo = FinalRealDataDemo()
    
    try:
        results = await demo.run_comprehensive_demo()
        
        if results.get('error'):
            print(f"\n❌ ERROR: {results['error']}")
            return
        
        print(f"\n{'='*100}")
        print(f"🎯 FINAL REAL DATA DEMO SUMMARY")
        print(f"{'='*100}")
        
        summary = results['summary']
        
        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Tickers Tested: {summary['total_tickers']}")
        print(f"   Total Signals: {summary['total_signals']}")
        print(f"   BUY Signals: {summary['total_buy_signals']}")
        print(f"   SELL Signals: {summary['total_sell_signals']}")
        print(f"   HOLD Signals: {summary['total_hold_signals']}")
        print(f"   Signal Balance: {summary['signal_balance'].upper()}")
        
        print(f"\n🎯 SIGNAL STRENGTH DISTRIBUTION:")
        for strength, count in summary['strength_counts'].items():
            print(f"   {strength.upper()}: {count} tickers")
        
        print(f"\n📈 MARKET CONTEXT DISTRIBUTION:")
        for context, count in summary['context_counts'].items():
            print(f"   {context.upper()}: {count} tickers")
        
        print(f"\n🔥 STRONG SIGNAL TICKERS:")
        print(f"   Strong BUY: {summary['strong_buy_tickers']} tickers")
        print(f"   Strong SELL: {summary['strong_sell_tickers']} tickers")
        
        print(f"\n✅ FINAL REAL DATA DEMO COMPLETE!")
        print(f"🎯 REAL API DATA - NO MOCK DATA!")
        print(f"🚀 COMPREHENSIVE MULTI-TICKER ANALYSIS!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

