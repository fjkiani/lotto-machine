#!/usr/bin/env python3
"""
REAL INSTITUTIONAL FLOW AGENT - NO MOCK DATA
Integrates real data scraping with signal detection
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Import our real data scrapers
from real_data_scraper_v2 import RealDataManagerV2, RealBlockTrade, RealOptionsFlow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

@dataclass
class MagnetLevel:
    """Magnet level for institutional flow detection"""
    price: float
    notional_volume: float
    trade_count: int
    confidence: float

@dataclass
class CompositeSignal:
    """Composite signal from multiple sources"""
    ticker: str
    price: float
    signal_types: List[str]
    confidence: float
    action: str
    timestamp: datetime
    details: str

class RealMagnetCalculator:
    """Calculates magnet levels from REAL data"""
    
    def __init__(self):
        self.price_bin_size = 0.10  # $0.10 increments
        self.time_window = 15  # 15 minutes
        self.top_magnets = 5
        
    def calculate_magnets(self, block_trades: List[RealBlockTrade], 
                         options_flows: List[RealOptionsFlow]) -> List[MagnetLevel]:
        """Calculate magnet levels from REAL data"""
        try:
            logger.info("🧲 CALCULATING MAGNET LEVELS FROM REAL DATA")
            
            # Create price bins
            price_bins = {}
            
            # Process block trades
            for trade in block_trades:
                bin_price = round(trade.price / self.price_bin_size) * self.price_bin_size
                if bin_price not in price_bins:
                    price_bins[bin_price] = {'notional': 0, 'count': 0}
                
                price_bins[bin_price]['notional'] += trade.price * trade.size
                price_bins[bin_price]['count'] += 1
                
                logger.info(f"📊 BLOCK TRADE: ${trade.price:.2f} - {trade.size:,} shares - Bin: ${bin_price:.2f}")
            
            # Process options flows (convert to notional)
            for flow in options_flows:
                # Estimate underlying price impact
                estimated_price = flow.strike + (0.5 if flow.option_type == 'call' else -0.5)
                bin_price = round(estimated_price / self.price_bin_size) * self.price_bin_size
                
                if bin_price not in price_bins:
                    price_bins[bin_price] = {'notional': 0, 'count': 0}
                
                # Convert options contracts to notional (100 shares per contract)
                notional = estimated_price * flow.contracts * 100
                price_bins[bin_price]['notional'] += notional
                price_bins[bin_price]['count'] += 1
                
                logger.info(f"📊 OPTIONS FLOW: ${flow.strike:.2f} {flow.option_type} - {flow.contracts:,} contracts - Bin: ${bin_price:.2f}")
            
            # Sort by notional volume and get top magnets
            sorted_bins = sorted(price_bins.items(), key=lambda x: x[1]['notional'], reverse=True)
            
            magnets = []
            for i, (price, data) in enumerate(sorted_bins[:self.top_magnets]):
                confidence = min(1.0, data['notional'] / 10000000)  # Scale confidence
                
                magnet = MagnetLevel(
                    price=price,
                    notional_volume=data['notional'],
                    trade_count=data['count'],
                    confidence=confidence
                )
                magnets.append(magnet)
                
                logger.info(f"🧲 MAGNET {i+1}: ${price:.2f} - ${data['notional']:,.0f} notional - {data['count']} trades")
            
            logger.info(f"🎯 CALCULATED {len(magnets)} MAGNET LEVELS FROM REAL DATA")
            return magnets
            
        except Exception as e:
            logger.error(f"Error calculating magnets: {e}")
            return []

class RealCompositeSignalDetector:
    """Detects composite signals from REAL data"""
    
    def __init__(self):
        self.block_threshold = 500000  # 500K shares
        self.options_threshold = 1000  # 1K contracts
        self.oi_threshold = 10000  # 10K OI change
        self.proximity_threshold = 0.25  # $0.25 for SPY
        
    def detect_signals(self, current_price: float, magnets: List[MagnetLevel],
                      block_trades: List[RealBlockTrade], 
                      options_flows: List[RealOptionsFlow]) -> List[CompositeSignal]:
        """Detect composite signals from REAL data"""
        try:
            logger.info(f"🔍 DETECTING COMPOSITE SIGNALS AT ${current_price:.2f}")
            
            signals = []
            
            # Check each magnet level
            for magnet in magnets:
                if abs(current_price - magnet.price) <= self.proximity_threshold:
                    logger.info(f"🎯 PRICE NEAR MAGNET: ${current_price:.2f} -> ${magnet.price:.2f}")
                    
                    signal_types = []
                    signal_details = []
                    
                    # Check for block trades at this level
                    nearby_blocks = [t for t in block_trades 
                                   if abs(t.price - magnet.price) <= self.proximity_threshold
                                   and t.size >= self.block_threshold]
                    
                    if nearby_blocks:
                        signal_types.append('block_trade')
                        for block in nearby_blocks:
                            signal_details.append(f"Block: ${block.price:.2f} - {block.size:,} shares")
                        logger.info(f"🔥 BLOCK TRADE SIGNAL: {len(nearby_blocks)} trades")
                    
                    # Check for options flows at this level
                    nearby_options = [o for o in options_flows 
                                    if abs(o.strike - magnet.price) <= self.proximity_threshold
                                    and (o.contracts >= self.options_threshold or abs(o.oi_change) >= self.oi_threshold)]
                    
                    if nearby_options:
                        signal_types.append('options_flow')
                        for option in nearby_options:
                            signal_details.append(f"Options: ${option.strike:.2f} {option.option_type} - {option.contracts:,} contracts")
                        logger.info(f"🔥 OPTIONS FLOW SIGNAL: {len(nearby_options)} flows")
                    
                    # Check for options sweeps
                    sweeps = [o for o in nearby_options if o.sweep_flag]
                    if sweeps:
                        signal_types.append('options_sweep')
                        for sweep in sweeps:
                            signal_details.append(f"Sweep: ${sweep.strike:.2f} {sweep.option_type} - {sweep.contracts:,} contracts")
                        logger.info(f"🔥 OPTIONS SWEEP SIGNAL: {len(sweeps)} sweeps")
                    
                    # Generate composite signal if we have multiple signal types
                    if len(signal_types) >= 2:
                        confidence = min(1.0, len(signal_types) * 0.3 + magnet.confidence * 0.4)
                        action = self._determine_action(signal_types, nearby_options)
                        
                        signal = CompositeSignal(
                            ticker='SPY',
                            price=current_price,
                            signal_types=signal_types,
                            confidence=confidence,
                            action=action,
                            timestamp=datetime.now(),
                            details='; '.join(signal_details)
                        )
                        
                        signals.append(signal)
                        logger.info(f"🚨 COMPOSITE SIGNAL: {action} - {signal_types} - Confidence: {confidence:.2f}")
            
            logger.info(f"🎯 DETECTED {len(signals)} COMPOSITE SIGNALS FROM REAL DATA")
            return signals
            
        except Exception as e:
            logger.error(f"Error detecting signals: {e}")
            return []
    
    def _determine_action(self, signal_types: List[str], options_flows: List[RealOptionsFlow]) -> str:
        """Determine trading action from REAL data"""
        try:
            # Count call vs put flows
            call_flows = [o for o in options_flows if o.option_type == 'call']
            put_flows = [o for o in options_flows if o.option_type == 'put']
            
            call_volume = sum(o.contracts for o in call_flows)
            put_volume = sum(o.contracts for o in put_flows)
            
            logger.info(f"📊 CALL VOLUME: {call_volume:,} | PUT VOLUME: {put_volume:,}")
            
            # Determine action based on options flow
            if call_volume > put_volume * 1.5:
                return 'BUY'
            elif put_volume > call_volume * 1.5:
                return 'SELL'
            else:
                # Balanced - check for sweeps
                call_sweeps = [o for o in call_flows if o.sweep_flag]
                put_sweeps = [o for o in put_flows if o.sweep_flag]
                
                if len(call_sweeps) > len(put_sweeps):
                    return 'BUY'
                elif len(put_sweeps) > len(call_sweeps):
                    return 'SELL'
                else:
                    return 'HOLD'
                    
        except Exception as e:
            logger.error(f"Error determining action: {e}")
            return 'HOLD'

class RealInstitutionalFlowAgent:
    """Main agent that orchestrates REAL data collection and signal detection"""
    
    def __init__(self):
        self.data_manager = RealDataManagerV2()
        self.magnet_calculator = RealMagnetCalculator()
        self.signal_detector = RealCompositeSignalDetector()
        
    async def analyze_ticker(self, ticker: str, current_price: float) -> Dict[str, Any]:
        """Analyze ticker with REAL data"""
        try:
            logger.info(f"🚀 ANALYZING {ticker} AT ${current_price:.2f} WITH REAL DATA")
            
            # Get real data
            data = await self.data_manager.get_real_institutional_data(ticker)
            
            if data.get('rate_limited'):
                logger.warning(f"⏰ Rate limited for {ticker}")
                return {'error': 'Rate limited', 'data_source': 'REAL'}
            
            block_trades = data.get('block_trades', [])
            options_flows = data.get('options_flows', [])
            
            logger.info(f"📊 REAL DATA: {len(block_trades)} block trades, {len(options_flows)} options flows")
            
            # Calculate magnet levels
            magnets = self.magnet_calculator.calculate_magnets(block_trades, options_flows)
            
            # Detect composite signals
            signals = self.signal_detector.detect_signals(current_price, magnets, block_trades, options_flows)
            
            # Generate analysis
            analysis = {
                'ticker': ticker,
                'current_price': current_price,
                'data_source': 'REAL',
                'block_trades': block_trades,
                'options_flows': options_flows,
                'magnets': magnets,
                'signals': signals,
                'analysis_time': datetime.now(),
                'total_signals': len(signals),
                'buy_signals': len([s for s in signals if s.action == 'BUY']),
                'sell_signals': len([s for s in signals if s.action == 'SELL']),
                'hold_signals': len([s for s in signals if s.action == 'HOLD'])
            }
            
            logger.info(f"🎯 ANALYSIS COMPLETE: {len(signals)} signals ({analysis['buy_signals']} BUY, {analysis['sell_signals']} SELL)")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            return {'error': str(e), 'data_source': 'REAL'}

async def test_real_institutional_flow():
    """Test real institutional flow agent"""
    print("\n" + "="*100)
    print("🔥 REAL INSTITUTIONAL FLOW AGENT TEST - NO MOCK DATA")
    print("="*100)
    
    agent = RealInstitutionalFlowAgent()
    
    # Test with SPY at current price
    ticker = 'SPY'
    current_price = 660.30
    
    print(f"\n🔍 TESTING REAL INSTITUTIONAL FLOW FOR {ticker} AT ${current_price:.2f}")
    print("-" * 60)
    
    try:
        analysis = await agent.analyze_ticker(ticker, current_price)
        
        if analysis.get('error'):
            print(f"\n❌ ERROR: {analysis['error']}")
            return
        
        print(f"\n📊 REAL DATA ANALYSIS RESULTS:")
        print(f"   Ticker: {analysis['ticker']}")
        print(f"   Current Price: ${analysis['current_price']:.2f}")
        print(f"   Data Source: {analysis['data_source']}")
        print(f"   Block Trades: {len(analysis['block_trades'])}")
        print(f"   Options Flows: {len(analysis['options_flows'])}")
        print(f"   Magnet Levels: {len(analysis['magnets'])}")
        print(f"   Total Signals: {analysis['total_signals']}")
        print(f"   BUY Signals: {analysis['buy_signals']}")
        print(f"   SELL Signals: {analysis['sell_signals']}")
        print(f"   HOLD Signals: {analysis['hold_signals']}")
        
        if analysis['magnets']:
            print(f"\n🧲 MAGNET LEVELS:")
            for i, magnet in enumerate(analysis['magnets'][:3]):
                print(f"   {i+1}. ${magnet.price:.2f} - ${magnet.notional_volume:,.0f} notional - Confidence: {magnet.confidence:.2f}")
        
        if analysis['signals']:
            print(f"\n🚨 COMPOSITE SIGNALS:")
            for i, signal in enumerate(analysis['signals'][:3]):
                print(f"   {i+1}. {signal.action} - {signal.signal_types} - Confidence: {signal.confidence:.2f}")
                print(f"      Details: {signal.details}")
        
        print(f"\n✅ REAL INSTITUTIONAL FLOW TEST COMPLETE!")
        print(f"🎯 NO MOCK DATA - ONLY REAL INSTITUTIONAL FLOW!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    print("🔥 REAL INSTITUTIONAL FLOW AGENT TEST")
    print("=" * 50)
    
    asyncio.run(test_real_institutional_flow())

if __name__ == "__main__":
    main()

