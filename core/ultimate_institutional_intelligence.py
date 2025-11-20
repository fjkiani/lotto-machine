#!/usr/bin/env python3
"""
ULTIMATE INSTITUTIONAL INTELLIGENCE SYSTEM
Combines institutional flow detection with actionable intelligence
REAL-TIME MAGNET + COMPOSITE SIGNALS = ACTIONABLE TRADES
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.intelligence.institutional_flow_agent import InstitutionalFlowAgent
from src.intelligence.feeds import DataFeedManager
from src.intelligence.analytics import RealTimeAnalytics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class UltimateIntelligenceSystem:
    """Ultimate intelligence system combining institutional flow with actionable intelligence"""
    
    def __init__(self, tickers: List[str] = None):
        self.tickers = tickers or ['SPY']
        
        # Initialize institutional flow agent
        self.flow_agent = InstitutionalFlowAgent(
            tickers=self.tickers,
            poll_interval=60,  # 1 minute polling
            bin_size=0.10,
            window_minutes=15
        )
        
        # Initialize other components
        self.feed_manager = None
        self.analytics = None
        
        logger.info(f"UltimateIntelligenceSystem initialized for {self.tickers}")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            # Initialize feed manager
            self.feed_manager = DataFeedManager({})
            await self.feed_manager.initialize()
            
            # Initialize analytics
            self.analytics = RealTimeAnalytics({
                'monitored_tickers': self.tickers,
                'trade_size_threshold': 5.0,
                'price_zscore_threshold': 2.0,
                'volume_zscore_threshold': 2.0
            })
            await self.analytics.initialize()
            
            logger.info("UltimateIntelligenceSystem fully initialized")
            
        except Exception as e:
            logger.error(f"Error initializing UltimateIntelligenceSystem: {e}")
            raise
    
    async def run_analysis(self) -> Dict[str, Any]:
        """Run complete institutional intelligence analysis"""
        try:
            print("\n" + "="*100)
            print("🔥 ULTIMATE INSTITUTIONAL INTELLIGENCE SYSTEM")
            print("="*100)
            
            # 1. Poll institutional flow data
            print("\n📊 STEP 1: POLLING INSTITUTIONAL FLOW DATA")
            print("-" * 50)
            
            await self.flow_agent._poll_all_sources()
            await self.flow_agent._update_magnets()
            
            # 2. Get market data
            print("\n📈 STEP 2: GATHERING MARKET DATA")
            print("-" * 50)
            
            indices = await self.feed_manager.get_yahoo_finance(self.tickers)
            current_prices = {idx['ticker']: idx['price'] for idx in indices}
            
            print(f"✅ Current prices: {current_prices}")
            
            # 3. Detect composite signals
            print("\n🎯 STEP 3: DETECTING COMPOSITE SIGNALS")
            print("-" * 50)
            
            all_signals = []
            for ticker in self.tickers:
                current_price = current_prices.get(ticker, 660.0)
                magnets = self.flow_agent.magnet_levels[ticker]
                trades = self.flow_agent.block_trades[ticker]
                flows = self.flow_agent.options_flows[ticker]
                
                signals = self.flow_agent.signal_detector.detect_signals(
                    ticker, current_price, magnets, trades, flows
                )
                
                all_signals.extend(signals)
                
                print(f"✅ {ticker}: {len(signals)} composite signals detected")
            
            # 4. Generate actionable intelligence
            print("\n🧠 STEP 4: GENERATING ACTIONABLE INTELLIGENCE")
            print("-" * 50)
            
            actionable_intelligence = self._generate_actionable_intelligence(
                all_signals, current_prices, indices
            )
            
            # 5. Display results
            print("\n" + "="*100)
            print("🎯 ULTIMATE INSTITUTIONAL INTELLIGENCE REPORT")
            print("="*100)
            
            self._display_results(actionable_intelligence, all_signals, current_prices)
            
            return actionable_intelligence
            
        except Exception as e:
            logger.error(f"Error in run_analysis: {e}")
            return {}
    
    def _generate_actionable_intelligence(self, 
                                        signals: List, 
                                        current_prices: Dict[str, float],
                                        indices: List[Dict]) -> Dict[str, Any]:
        """Generate actionable intelligence from composite signals"""
        
        intelligence = {
            'timestamp': datetime.now(),
            'signals': signals,
            'current_prices': current_prices,
            'trading_decisions': [],
            'risk_assessment': [],
            'opportunities': []
        }
        
        # Generate trading decisions
        for signal in signals:
            decision = {
                'ticker': signal.ticker,
                'action': signal.action,
                'confidence': signal.confidence,
                'magnet_price': signal.magnet_price,
                'current_price': current_prices.get(signal.ticker, 0),
                'signals': signal.signals,
                'reasoning': f"Composite signal at magnet ${signal.magnet_price:.2f} with {', '.join(signal.signals)}",
                'risk_level': 'high' if signal.confidence > 0.8 else 'medium',
                'timeframe': 'short_term',
                'position_size': 'large' if signal.confidence > 0.8 else 'normal'
            }
            intelligence['trading_decisions'].append(decision)
        
        # Generate risk assessment
        if signals:
            intelligence['risk_assessment'].append({
                'type': 'composite_signals',
                'severity': 'high',
                'description': f'{len(signals)} composite signals detected - high institutional activity',
                'mitigation': 'Monitor closely, set tight stop losses'
            })
        
        # Generate opportunities
        for signal in signals:
            intelligence['opportunities'].append({
                'type': 'magnet_opportunity',
                'ticker': signal.ticker,
                'description': f'Magnet level ${signal.magnet_price:.2f} with {signal.action} signal',
                'action': signal.action,
                'confidence': signal.confidence,
                'timeframe': 'short_term'
            })
        
        return intelligence
    
    def _display_results(self, 
                        intelligence: Dict[str, Any], 
                        signals: List, 
                        current_prices: Dict[str, float]):
        """Display comprehensive results"""
        
        print(f"\n📊 MARKET STATE:")
        for ticker, price in current_prices.items():
            print(f"   {ticker}: ${price:.2f}")
        
        print(f"\n🎯 TRADING DECISIONS:")
        if intelligence['trading_decisions']:
            for decision in intelligence['trading_decisions']:
                print(f"   ACTION: {decision['action']}")
                print(f"   Ticker: {decision['ticker']}")
                print(f"   Confidence: {decision['confidence']:.1%}")
                print(f"   Magnet: ${decision['magnet_price']:.2f}")
                print(f"   Current: ${decision['current_price']:.2f}")
                print(f"   Reasoning: {decision['reasoning']}")
                print(f"   Risk Level: {decision['risk_level']}")
                print(f"   Position Size: {decision['position_size']}")
                print()
        else:
            print("   No trading decisions generated")
        
        print(f"\n⚠️ RISK FACTORS:")
        if intelligence['risk_assessment']:
            for risk in intelligence['risk_assessment']:
                print(f"   {risk['type'].upper()}: {risk['description']}")
                print(f"   Mitigation: {risk['mitigation']}")
                print()
        else:
            print("   No significant risk factors identified")
        
        print(f"\n💰 OPPORTUNITIES:")
        if intelligence['opportunities']:
            for opportunity in intelligence['opportunities']:
                print(f"   {opportunity['type'].upper()}: {opportunity['description']}")
                print(f"   Action: {opportunity['action']}")
                print(f"   Confidence: {opportunity['confidence']:.1%}")
                print(f"   Timeframe: {opportunity['timeframe']}")
                print()
        else:
            print("   No opportunities identified")
        
        print(f"\n🔥 COMPOSITE SIGNALS:")
        if signals:
            for signal in signals:
                print(f"   {signal.ticker} - {signal.action} at ${signal.magnet_price:.2f}")
                print(f"   Signals: {', '.join(signal.signals)}")
                print(f"   Confidence: {signal.confidence:.1%}")
                print()
        else:
            print("   No composite signals detected")
        
        print("\n" + "="*100)
        print("🎯 ULTIMATE INSTITUTIONAL INTELLIGENCE COMPLETE")
        print("="*100)
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if self.feed_manager:
                await self.feed_manager.cleanup()
            if self.analytics:
                await self.analytics.cleanup()
            logger.info("UltimateIntelligenceSystem cleanup complete")
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")

async def main():
    """Main function"""
    print("🔥 ULTIMATE INSTITUTIONAL INTELLIGENCE SYSTEM")
    print("=" * 60)
    
    # Initialize system
    system = UltimateIntelligenceSystem(['SPY'])
    
    try:
        await system.initialize()
        
        # Run analysis
        result = await system.run_analysis()
        
        if result:
            print("\n✅ Ultimate intelligence analysis completed successfully!")
            print("\n🎯 INSTITUTIONAL FLOW + ACTIONABLE INTELLIGENCE = PROFIT!")
        else:
            print("\n❌ Ultimate intelligence analysis failed!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await system.cleanup()

if __name__ == "__main__":
    asyncio.run(main())

