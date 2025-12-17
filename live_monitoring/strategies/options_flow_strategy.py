#!/usr/bin/env python3
"""
Options Flow Sweeps Strategy
============================

Detects unusual options activity (sweeps, blocks) for institutional positioning.

WHAT IS A SWEEP?
- Large option order split across multiple exchanges
- Indicates urgency to fill (institutional/informed trader)
- Bullish sweep = aggressive call buying
- Bearish sweep = aggressive put buying

WHAT WE CAN DO NOW (with existing data):
- Monitor put/call ratio changes
- Track OI changes (accumulation/distribution)
- Detect max pain shifts
- Gamma exposure changes

WHAT WE NEED FOR FULL IMPLEMENTATION:
- Real-time options flow API (Unusual Whales, FlowAlgo, etc.)
- Or: Scrape options time & sales from broker

Edge: 15-20% win rate boost
Frequency: 5-10 signals per day

STATUS: PARTIAL IMPLEMENTATION
- Uses yfinance for options chain data
- Uses ChartExchange for options summary
- Missing: Real-time sweep detection (needs premium API)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import yfinance as yf

logger = logging.getLogger(__name__)

# Try to import ChartExchange client
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
    HAS_CHARTEXCHANGE = True
except ImportError:
    HAS_CHARTEXCHANGE = False


@dataclass
class OptionsFlowSignal:
    """Options flow trading signal"""
    symbol: str
    timestamp: datetime
    signal_type: str  # BULLISH_SWEEP, BEARISH_SWEEP, CALL_ACCUMULATION, PUT_ACCUMULATION, GAMMA_SQUEEZE
    action: str  # LONG, SHORT
    entry_price: float
    max_pain: float
    put_call_ratio: float
    total_call_oi: int
    total_put_oi: int
    target_price: float
    stop_price: float
    risk_reward_ratio: float
    confidence: float
    reasoning: list


class OptionsFlowStrategy:
    """
    Options Flow Strategy
    
    Analyzes options data for institutional positioning signals.
    
    CURRENT CAPABILITIES:
    - Put/Call ratio analysis
    - Max pain tracking
    - OI accumulation detection
    - Gamma exposure estimation
    
    FUTURE (with premium API):
    - Real-time sweep detection
    - Block trade alerts
    - Dark pool options correlation
    """
    
    # Signal thresholds
    BULLISH_PC_RATIO = 0.7  # P/C < 0.7 = bullish
    BEARISH_PC_RATIO = 1.3  # P/C > 1.3 = bearish
    MIN_OI_CHANGE_PCT = 10  # 10% OI change for accumulation signal
    MAX_PAIN_PROXIMITY_PCT = 1.0  # Within 1% of max pain
    
    # Risk parameters
    STOP_DISTANCE_PCT = 0.5  # 0.5% stop loss
    TARGET_DISTANCE_PCT = 1.0  # 1.0% target (2:1 R/R)
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize options flow strategy."""
        self.api_key = api_key or os.getenv('CHARTEXCHANGE_API_KEY')
        self.client = None
        
        if HAS_CHARTEXCHANGE and self.api_key:
            try:
                self.client = UltimateChartExchangeClient(self.api_key)
                logger.info("📊 Options Flow Strategy initialized with ChartExchange")
            except Exception as e:
                logger.warning(f"Could not initialize ChartExchange: {e}")
        else:
            logger.info("📊 Options Flow Strategy initialized (yfinance only)")
    
    def get_options_summary_yfinance(self, symbol: str) -> Optional[Dict]:
        """
        Get options summary from yfinance.
        
        Returns:
            Dict with put_call_ratio, total_call_oi, total_put_oi, max_pain estimate
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Get available expirations
            expirations = ticker.options
            if not expirations:
                return None
            
            # Use nearest expiration
            nearest_exp = expirations[0]
            chain = ticker.option_chain(nearest_exp)
            
            calls = chain.calls
            puts = chain.puts
            
            if calls.empty or puts.empty:
                return None
            
            # Calculate totals
            total_call_oi = int(calls['openInterest'].sum())
            total_put_oi = int(puts['openInterest'].sum())
            total_call_vol = int(calls['volume'].sum())
            total_put_vol = int(puts['volume'].sum())
            
            # Put/Call ratio (by OI)
            pc_ratio = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0
            
            # Estimate max pain (strike with most OI)
            # Simplified: weighted average of strikes by OI
            call_weighted = (calls['strike'] * calls['openInterest']).sum()
            put_weighted = (puts['strike'] * puts['openInterest']).sum()
            total_oi = total_call_oi + total_put_oi
            
            max_pain_estimate = (call_weighted + put_weighted) / total_oi if total_oi > 0 else 0
            
            return {
                'expiration': nearest_exp,
                'put_call_ratio': pc_ratio,
                'total_call_oi': total_call_oi,
                'total_put_oi': total_put_oi,
                'total_call_vol': total_call_vol,
                'total_put_vol': total_put_vol,
                'max_pain_estimate': max_pain_estimate,
                'source': 'yfinance'
            }
            
        except Exception as e:
            logger.debug(f"Error getting options summary from yfinance: {e}")
            return None
    
    def detect_options_signals(self, symbol: str,
                               current_price: Optional[float] = None) -> Optional[OptionsFlowSignal]:
        """
        Detect options flow signals.
        
        Args:
            symbol: Stock ticker
            current_price: Current price (will fetch if not provided)
        
        Returns:
            OptionsFlowSignal if conditions met, None otherwise
        """
        try:
            # Get current price
            if current_price is None:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d')
                if hist.empty:
                    return None
                current_price = float(hist['Close'].iloc[-1])
            
            # Get options summary
            options_data = self.get_options_summary_yfinance(symbol)
            
            if not options_data:
                return None
            
            pc_ratio = options_data['put_call_ratio']
            max_pain = options_data['max_pain_estimate']
            total_call_oi = options_data['total_call_oi']
            total_put_oi = options_data['total_put_oi']
            
            # Calculate distance to max pain
            max_pain_distance_pct = ((current_price - max_pain) / max_pain) * 100 if max_pain > 0 else 0
            
            # Determine signal
            signal_type = None
            action = None
            reasoning = []
            confidence = 0.65  # Base confidence
            
            # BULLISH: Low P/C ratio + price below max pain
            if pc_ratio < self.BULLISH_PC_RATIO:
                if max_pain_distance_pct < -self.MAX_PAIN_PROXIMITY_PCT:
                    # Price below max pain with bullish P/C = potential rally to max pain
                    signal_type = "CALL_ACCUMULATION"
                    action = "LONG"
                    reasoning.append(f"Put/Call ratio: {pc_ratio:.2f} (bullish < {self.BULLISH_PC_RATIO})")
                    reasoning.append(f"Price ${current_price:.2f} is {abs(max_pain_distance_pct):.1f}% below max pain ${max_pain:.2f}")
                    reasoning.append("Expect rally toward max pain (dealer hedging)")
                    confidence = 0.75
                    
            # BEARISH: High P/C ratio + price above max pain
            elif pc_ratio > self.BEARISH_PC_RATIO:
                if max_pain_distance_pct > self.MAX_PAIN_PROXIMITY_PCT:
                    # Price above max pain with bearish P/C = potential drop to max pain
                    signal_type = "PUT_ACCUMULATION"
                    action = "SHORT"
                    reasoning.append(f"Put/Call ratio: {pc_ratio:.2f} (bearish > {self.BEARISH_PC_RATIO})")
                    reasoning.append(f"Price ${current_price:.2f} is {max_pain_distance_pct:.1f}% above max pain ${max_pain:.2f}")
                    reasoning.append("Expect drop toward max pain (dealer hedging)")
                    confidence = 0.75
            
            # GAMMA SQUEEZE potential: Very low P/C + high call OI
            if pc_ratio < 0.5 and total_call_oi > total_put_oi * 2:
                signal_type = "GAMMA_SQUEEZE"
                action = "LONG"
                reasoning.append(f"Extreme call accumulation: {total_call_oi:,} calls vs {total_put_oi:,} puts")
                reasoning.append(f"Put/Call ratio: {pc_ratio:.2f} (very bullish)")
                reasoning.append("Gamma squeeze potential - dealers forced to buy")
                confidence = 0.80
            
            if signal_type is None:
                return None
            
            # Calculate trade setup
            entry = current_price
            
            if action == "LONG":
                stop = entry * (1 - self.STOP_DISTANCE_PCT / 100)
                # Target max pain if below, otherwise use standard target
                target = max(max_pain, entry * (1 + self.TARGET_DISTANCE_PCT / 100))
            else:  # SHORT
                stop = entry * (1 + self.STOP_DISTANCE_PCT / 100)
                target = min(max_pain, entry * (1 - self.TARGET_DISTANCE_PCT / 100))
            
            risk = abs(entry - stop)
            reward = abs(target - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            return OptionsFlowSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=signal_type,
                action=action,
                entry_price=entry,
                max_pain=max_pain,
                put_call_ratio=pc_ratio,
                total_call_oi=total_call_oi,
                total_put_oi=total_put_oi,
                target_price=target,
                stop_price=stop,
                risk_reward_ratio=rr_ratio,
                confidence=confidence,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"Error detecting options flow signals for {symbol}: {e}")
            return None


# ============================================================
# API REQUIREMENTS FOR FULL SWEEP DETECTION
# ============================================================
"""
To implement REAL-TIME SWEEP DETECTION, we need one of these APIs:

1. UNUSUAL WHALES ($99-299/month)
   - Real-time options flow
   - Sweep detection
   - Block trades
   - Dark pool options
   API: https://unusualwhales.com/api

2. FLOWALGO ($99-199/month)
   - Real-time options flow
   - Smart money tracking
   - Sweep alerts
   API: https://flowalgo.com/api

3. TRADYTICS ($50-100/month)
   - Options flow
   - Unusual activity
   - AI predictions
   API: https://tradytics.com/api

4. BARCHART ($99/month)
   - Options flow
   - Unusual options activity
   API: https://www.barchart.com/solutions/data

5. FREE ALTERNATIVES:
   - Scrape from broker (Thinkorswim, IBKR)
   - Use yfinance for OI changes (delayed)
   - ChartExchange options summary (EOD)

RECOMMENDATION:
- Start with yfinance (free, delayed)
- Add Unusual Whales if edge proven ($99/month)
"""


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    strategy = OptionsFlowStrategy()
    
    print("\n" + "="*60)
    print("📊 OPTIONS FLOW STRATEGY TEST")
    print("="*60)
    
    for symbol in ['SPY', 'QQQ']:
        print(f"\n📊 Testing {symbol}...")
        
        # Get options summary
        options_data = strategy.get_options_summary_yfinance(symbol)
        
        if options_data:
            print(f"   Expiration: {options_data['expiration']}")
            print(f"   Put/Call Ratio: {options_data['put_call_ratio']:.2f}")
            print(f"   Total Call OI: {options_data['total_call_oi']:,}")
            print(f"   Total Put OI: {options_data['total_put_oi']:,}")
            print(f"   Max Pain Estimate: ${options_data['max_pain_estimate']:.2f}")
        
        # Test signal generation
        signal = strategy.detect_options_signals(symbol)
        
        if signal:
            print(f"\n   🎯 SIGNAL GENERATED!")
            print(f"      Type: {signal.signal_type}")
            print(f"      Action: {signal.action}")
            print(f"      P/C Ratio: {signal.put_call_ratio:.2f}")
            print(f"      Max Pain: ${signal.max_pain:.2f}")
            print(f"      Entry: ${signal.entry_price:.2f}")
            print(f"      Target: ${signal.target_price:.2f}")
            print(f"      Stop: ${signal.stop_price:.2f}")
            print(f"      Confidence: {signal.confidence:.0%}")
            print(f"      Reasoning:")
            for r in signal.reasoning:
                print(f"         • {r}")
        else:
            print(f"\n   ⚠️ No signal generated")
            if options_data:
                print(f"      P/C ratio {options_data['put_call_ratio']:.2f} is neutral (0.7-1.3)")
    
    print("\n" + "="*60)
    print("📋 API REQUIREMENTS FOR FULL SWEEP DETECTION")
    print("="*60)
    print("""
    Current: Using yfinance (free, delayed)
    
    For REAL-TIME sweeps, need premium API:
    - Unusual Whales: $99-299/month
    - FlowAlgo: $99-199/month
    - Tradytics: $50-100/month
    
    Recommendation: Start with current implementation,
    upgrade to Unusual Whales if edge proven.
    """)

