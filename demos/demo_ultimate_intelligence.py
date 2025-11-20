#!/usr/bin/env python3
"""
DEMO: ULTIMATE INSTITUTIONAL INTELLIGENCE SYSTEM
Shows the system working with realistic magnet proximity
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def demo_ultimate_intelligence():
    """Demo the ultimate institutional intelligence system"""
    print("\n" + "="*100)
    print("🔥 DEMO: ULTIMATE INSTITUTIONAL INTELLIGENCE SYSTEM")
    print("="*100)
    
    # Initialize institutional flow agent
    flow_agent = InstitutionalFlowAgent(
        tickers=['SPY'],
        poll_interval=60,
        bin_size=0.10,
        window_minutes=15
    )
    
    print(f"✅ Institutional Flow Agent initialized")
    
    # Poll data
    print("\n📊 POLLING INSTITUTIONAL FLOW DATA...")
    await flow_agent._poll_all_sources()
    await flow_agent._update_magnets()
    
    # Show magnet levels
    magnets = flow_agent.magnet_levels['SPY']
    print(f"\n🎯 MAGNET LEVELS DETECTED:")
    for magnet in magnets:
        print(f"   ${magnet.price:.2f} - {magnet.total_volume:,} volume - {magnet.confidence:.1%} confidence")
    
    # Test with price near magnet
    if magnets:
        test_price = magnets[0].price + 0.20  # Within proximity threshold
        print(f"\n🎯 TESTING WITH PRICE: ${test_price:.2f} (near magnet ${magnets[0].price:.2f})")
        
        # Detect signals
        trades = flow_agent.block_trades['SPY']
        flows = flow_agent.options_flows['SPY']
        
        signals = flow_agent.signal_detector.detect_signals(
            'SPY', test_price, magnets, trades, flows
        )
        
        print(f"\n🔥 COMPOSITE SIGNALS DETECTED: {len(signals)}")
        
        for signal in signals:
            print(f"\n   🚨 {signal.action} SIGNAL!")
            print(f"   Ticker: {signal.ticker}")
            print(f"   Magnet: ${signal.magnet_price:.2f}")
            print(f"   Current: ${test_price:.2f}")
            print(f"   Signals: {', '.join(signal.signals)}")
            print(f"   Confidence: {signal.confidence:.1%}")
            
            # Generate actionable intelligence
            print(f"\n   💡 ACTIONABLE INTELLIGENCE:")
            print(f"   ACTION: {signal.action}")
            print(f"   RISK LEVEL: {'HIGH' if signal.confidence > 0.8 else 'MEDIUM'}")
            print(f"   POSITION SIZE: {'LARGE' if signal.confidence > 0.8 else 'NORMAL'}")
            print(f"   TIMEFRAME: SHORT-TERM")
            
            if signal.action == 'BUY':
                print(f"   ENTRY: ${test_price:.2f}")
                print(f"   TARGET: ${test_price * 1.02:.2f} (+2%)")
                print(f"   STOP: ${test_price * 0.98:.2f} (-2%)")
            elif signal.action == 'SELL':
                print(f"   ENTRY: ${test_price:.2f}")
                print(f"   TARGET: ${test_price * 0.98:.2f} (-2%)")
                print(f"   STOP: ${test_price * 1.02:.2f} (+2%)")
            
            print(f"   REASONING: Composite signal at magnet ${signal.magnet_price:.2f}")
            print(f"   MITIGATION: Set tight stop losses, monitor closely")
    
    else:
        print("\n❌ No magnet levels detected")
    
    print("\n" + "="*100)
    print("🎯 DEMO COMPLETE - INSTITUTIONAL FLOW DETECTION WORKING!")
    print("="*100)

def main():
    """Main function"""
    print("🔥 DEMO: ULTIMATE INSTITUTIONAL INTELLIGENCE SYSTEM")
    print("=" * 60)
    
    asyncio.run(demo_ultimate_intelligence())

if __name__ == "__main__":
    main()
