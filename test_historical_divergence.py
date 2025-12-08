#!/usr/bin/env python3
"""
TEST HISTORICAL DIVERGENCES - Prove the news exploit edge

This test checks HISTORICAL dates where we have DP data
to see if the divergence strategy would have been profitable.

The EDGE:
- High DP % (>40%) + Price Down = BUY (institutions accumulating in panic)
- Low DP % (<25%) + Price Up = SELL (institutions distributing into rally)
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
sys.path.append(str(Path(__file__).parent))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'enrichment'))
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'core'))
sys.path.append(str(Path(__file__).parent / 'core'))
sys.path.append(str(Path(__file__).parent / 'core' / 'data'))
sys.path.append(str(Path(__file__).parent / 'configs'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_divergence_for_date(symbol: str, date_str: str):
    """
    Check for divergence on a specific date and validate next-day result.
    
    Returns dict with:
    - date
    - dp_pct
    - price_change
    - signal (BUY/SELL/HOLD)
    - next_day_change
    - profitable (True/False)
    """
    import yfinance as yf
    from live_monitoring.enrichment.institutional_narrative import load_institutional_context
    
    result = {
        "date": date_str,
        "symbol": symbol,
        "dp_pct": None,
        "price_change": None,
        "signal": "HOLD",
        "confidence": 0.0,
        "next_day_change": None,
        "profitable": None,
        "reasoning": []
    }
    
    try:
        # Get institutional context for the date
        ctx = load_institutional_context(symbol, date_str)
        dp_pct = ctx.get('dark_pool', {}).get('pct')
        price_change = ctx.get('pct_change', 0)
        
        result["dp_pct"] = dp_pct
        result["price_change"] = price_change
        
        if dp_pct is None:
            result["reasoning"].append("No DP data available")
            return result
        
        # Apply divergence logic
        # CASE 1: High DP + Price Down = BUY (accumulation in panic)
        if dp_pct > 40 and price_change < -0.3:
            result["signal"] = "BUY"
            result["confidence"] = 0.70
            result["reasoning"].append(f"HIGH DP ({dp_pct:.1f}%) + Price DOWN ({price_change:.2f}%)")
            result["reasoning"].append("Institutions accumulating while retail panics")
        
        # CASE 2: Low DP + Price Up = SELL (distribution into rally)
        elif dp_pct < 25 and price_change > 0.3:
            result["signal"] = "SELL"
            result["confidence"] = 0.70
            result["reasoning"].append(f"LOW DP ({dp_pct:.1f}%) + Price UP ({price_change:.2f}%)")
            result["reasoning"].append("Institutions distributing while retail FOMOs")
        
        # CASE 3: Very High DP + Flat = Stealth accumulation
        elif dp_pct > 50 and abs(price_change) < 0.3:
            result["signal"] = "BUY"
            result["confidence"] = 0.65
            result["reasoning"].append(f"VERY HIGH DP ({dp_pct:.1f}%) + FLAT price")
            result["reasoning"].append("Stealth accumulation in progress")
        
        # CASE 4: Very Low DP + Flat = Distribution complete
        elif dp_pct < 20 and abs(price_change) < 0.3:
            result["signal"] = "SELL"
            result["confidence"] = 0.65
            result["reasoning"].append(f"VERY LOW DP ({dp_pct:.1f}%) + FLAT price")
            result["reasoning"].append("Distribution complete, breakdown likely")
        
        # CASE 5: High DP + Price Up = Confirmation (no divergence)
        elif dp_pct > 40 and price_change > 0.3:
            result["signal"] = "HOLD"
            result["confidence"] = 0.50
            result["reasoning"].append(f"HIGH DP ({dp_pct:.1f}%) CONFIRMS UP move ({price_change:.2f}%)")
            result["reasoning"].append("No divergence - trend may continue")
        
        # CASE 6: Low DP + Price Down = Confirmation (no divergence)
        elif dp_pct < 25 and price_change < -0.3:
            result["signal"] = "HOLD"
            result["confidence"] = 0.50
            result["reasoning"].append(f"LOW DP ({dp_pct:.1f}%) CONFIRMS DOWN move ({price_change:.2f}%)")
            result["reasoning"].append("No divergence - trend may continue")
        
        else:
            result["signal"] = "HOLD"
            result["confidence"] = 0.40
            result["reasoning"].append(f"Neutral DP ({dp_pct:.1f}%) with price change ({price_change:.2f}%)")
        
        # Now check next day's result
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        next_day = date_obj + timedelta(days=1)
        
        # Skip weekends
        while next_day.weekday() >= 5:
            next_day = next_day + timedelta(days=1)
        
        next_day_str = next_day.strftime("%Y-%m-%d")
        
        # Get next day's price data
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=date_str, end=(next_day + timedelta(days=5)).strftime("%Y-%m-%d"), interval="1d")
        
        if len(hist) >= 2:
            # Find the next trading day after our date
            for i, idx in enumerate(hist.index):
                if idx.strftime("%Y-%m-%d") == date_str:
                    if i + 1 < len(hist):
                        close_today = float(hist['Close'].iloc[i])
                        close_next = float(hist['Close'].iloc[i + 1])
                        next_day_change = ((close_next / close_today) - 1) * 100
                        result["next_day_change"] = next_day_change
                        
                        # Determine if profitable
                        if result["signal"] == "BUY":
                            result["profitable"] = next_day_change > 0
                        elif result["signal"] == "SELL":
                            result["profitable"] = next_day_change < 0
                        else:
                            result["profitable"] = None  # No trade taken
                    break
        
    except Exception as e:
        logger.error(f"Error checking divergence for {symbol} on {date_str}: {e}")
        result["reasoning"].append(f"Error: {str(e)}")
    
    return result


def run_historical_backtest():
    """Run backtest on multiple historical dates"""
    print("=" * 80)
    print("🔥 HISTORICAL DIVERGENCE BACKTEST")
    print("   Testing if news/DP divergences would have been profitable")
    print("=" * 80)
    
    symbol = "SPY"
    
    # Test last 10 trading days
    dates_to_test = []
    current = datetime.now() - timedelta(days=1)  # Start from yesterday
    
    while len(dates_to_test) < 10:
        if current.weekday() < 5:  # Skip weekends
            dates_to_test.append(current.strftime("%Y-%m-%d"))
        current = current - timedelta(days=1)
    
    dates_to_test.reverse()  # Oldest first
    
    print(f"\n📅 Testing {len(dates_to_test)} dates for {symbol}:")
    print(f"   {dates_to_test[0]} to {dates_to_test[-1]}")
    
    results = []
    
    for date_str in dates_to_test:
        print(f"\n   Checking {date_str}...", end=" ")
        result = check_divergence_for_date(symbol, date_str)
        results.append(result)
        
        if result["signal"] != "HOLD":
            emoji = "✅" if result["profitable"] else "❌" if result["profitable"] is False else "⏳"
            print(f"{result['signal']} @ {result['confidence']:.0%} → {emoji}")
        else:
            print("HOLD (no divergence)")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 BACKTEST RESULTS")
    print("=" * 80)
    
    signals = [r for r in results if r["signal"] != "HOLD"]
    profitable = [r for r in signals if r["profitable"] == True]
    unprofitable = [r for r in signals if r["profitable"] == False]
    pending = [r for r in signals if r["profitable"] is None]
    
    print(f"\n   Total Dates Tested: {len(results)}")
    print(f"   Signals Generated: {len(signals)}")
    print(f"   Profitable Trades: {len(profitable)}")
    print(f"   Unprofitable Trades: {len(unprofitable)}")
    print(f"   Pending (no next-day data): {len(pending)}")
    
    if len(signals) > 0:
        completed_signals = [s for s in signals if s["profitable"] is not None]
        if completed_signals:
            win_rate = len(profitable) / len(completed_signals) * 100
            print(f"\n   📈 WIN RATE: {win_rate:.1f}%")
            
            if win_rate >= 55:
                print(f"   🔥 EDGE CONFIRMED! This strategy shows promise!")
            elif win_rate >= 50:
                print(f"   ⚠️  Marginal edge - needs more data/tuning")
            else:
                print(f"   ❌ No edge detected on this sample")
    
    # Show detailed results
    print("\n" + "-" * 80)
    print("📋 DETAILED TRADE LOG:")
    print("-" * 80)
    
    print(f"\n{'Date':<12} {'DP%':<8} {'Δ Price':<10} {'Signal':<8} {'Conf':<8} {'Next Day':<12} {'Result':<8}")
    print("-" * 80)
    
    for r in results:
        dp_str = f"{r['dp_pct']:.1f}%" if r['dp_pct'] else "N/A"
        price_str = f"{r['price_change']:+.2f}%" if r['price_change'] else "N/A"
        next_str = f"{r['next_day_change']:+.2f}%" if r['next_day_change'] else "N/A"
        
        if r["profitable"] is True:
            result_str = "✅ WIN"
        elif r["profitable"] is False:
            result_str = "❌ LOSS"
        elif r["signal"] != "HOLD":
            result_str = "⏳"
        else:
            result_str = "-"
        
        print(f"{r['date']:<12} {dp_str:<8} {price_str:<10} {r['signal']:<8} {r['confidence']:.0%}     {next_str:<12} {result_str:<8}")
    
    return results


def analyze_best_conditions():
    """Analyze which conditions produce the best signals"""
    print("\n" + "=" * 80)
    print("🧠 ANALYZING OPTIMAL CONDITIONS")
    print("=" * 80)
    
    print("""
   📊 DIVERGENCE SIGNAL RULES:
   
   ┌─────────────────────────────────────────────────────────────┐
   │  Dark Pool %    │  Price Move     │  Signal    │  Logic     │
   ├─────────────────────────────────────────────────────────────┤
   │  > 40%          │  DOWN > 0.3%    │  BUY       │  Accumulation │
   │  < 25%          │  UP > 0.3%      │  SELL      │  Distribution │
   │  > 50%          │  FLAT           │  BUY       │  Stealth acc  │
   │  < 20%          │  FLAT           │  SELL      │  Dist done    │
   │  > 40%          │  UP > 0.3%      │  HOLD      │  Confirmation │
   │  < 25%          │  DOWN > 0.3%    │  HOLD      │  Confirmation │
   │  25-40%         │  ANY            │  HOLD      │  Neutral      │
   └─────────────────────────────────────────────────────────────┘
   
   💡 KEY INSIGHT:
   The edge comes from DIVERGENCES - when institutional flow (DP)
   contradicts price action or news sentiment.
   
   🎯 HIGH-PROBABILITY SETUPS:
   1. "Panic Buy" - DP > 45% + Price Down > 1% + Bearish News
   2. "Rally Sell" - DP < 20% + Price Up > 1% + Bullish News  
   3. "Stealth Entry" - DP > 55% + Flat Price + No News
   
   ⚠️  AVOID:
   - Neutral DP (25-40%) - institutions are balanced
   - DP confirms price direction - no divergence edge
   """)


def main():
    """Run historical backtest"""
    
    # Run backtest
    results = run_historical_backtest()
    
    # Analyze conditions
    analyze_best_conditions()
    
    # Final recommendation
    print("\n" + "=" * 80)
    print("🎯 RECOMMENDATION")
    print("=" * 80)
    
    signals = [r for r in results if r["signal"] != "HOLD"]
    if signals:
        print(f"""
   Based on {len(results)} days of data:
   
   1. DIVERGENCE SIGNALS: {len(signals)} opportunities identified
   2. NEXT STEPS:
      a. Add Perplexity API for real-time news sentiment
      b. Run during RTH (9:30-4pm) for live signals
      c. Paper trade divergence signals for 2 weeks
      d. If win rate > 55%, deploy with small capital
   
   3. INTEGRATION WITH LOTTO MACHINE:
      - Add divergence score to signal generator
      - Boost confidence when DP diverges from news
      - Veto signals when DP confirms bearish news
        """)
    else:
        print("""
   ⚠️  No divergence signals in sample period.
   
   This could mean:
   - Market is in consolidation (normal)
   - Need to test over longer period
   - DP data might not be available for all dates
   
   Recommendation: Run test on more dates or wait for market volatility
        """)


if __name__ == "__main__":
    main()




