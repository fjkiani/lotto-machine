#!/usr/bin/env python3
"""
TEST DIVERGENCE EDGE - FIXED VERSION

Tests if we can exploit news/DP divergences during volatile market days.
The edge is in DIVERGENCES - when institutions act opposite to headlines.
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
    level=logging.WARNING,  # Reduce noise
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_price_history(symbol: str, days: int = 30):
    """Get price history with accurate daily changes"""
    import yfinance as yf
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days + 10)  # Extra buffer
    
    ticker = yf.Ticker(symbol)
    hist = ticker.history(start=start_date.strftime("%Y-%m-%d"), 
                          end=end_date.strftime("%Y-%m-%d"),
                          interval="1d")
    
    if hist.empty:
        return []
    
    results = []
    for i in range(1, len(hist)):
        date_str = hist.index[i].strftime("%Y-%m-%d")
        close = float(hist['Close'].iloc[i])
        prev_close = float(hist['Close'].iloc[i-1])
        pct_change = ((close / prev_close) - 1) * 100
        
        results.append({
            "date": date_str,
            "close": close,
            "prev_close": prev_close,
            "pct_change": pct_change,
            "volume": int(hist['Volume'].iloc[i])
        })
    
    return results


def get_dp_data(symbol: str, date_str: str):
    """Get dark pool data for a specific date"""
    try:
        from configs.chartexchange_config import get_api_key
        from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
        
        api_key = get_api_key()
        client = UltimateChartExchangeClient(api_key=api_key, tier=3)
        
        # Get DP levels
        dp_levels = client.get_dark_pool_levels(symbol, date_str)
        dp_prints = client.get_dark_pool_prints(symbol, date_str)
        
        dp_vol = 0
        if dp_levels:
            for level in dp_levels:
                if isinstance(level, dict) and 'volume' in level:
                    dp_vol += int(level['volume'])
        
        if dp_vol == 0 and dp_prints:
            for print_obj in dp_prints:
                if isinstance(print_obj, dict) and 'size' in print_obj:
                    dp_vol += int(print_obj['size'])
        
        return dp_vol
        
    except Exception as e:
        return None


def check_divergence(price_change: float, dp_pct: float):
    """
    Check for divergence between price action and DP activity.
    
    Returns (signal, confidence, reasoning)
    """
    signal = "HOLD"
    confidence = 0.40
    reasoning = []
    
    if dp_pct is None:
        return signal, confidence, ["No DP data"]
    
    # CASE 1: Price DOWN but HIGH DP = Institutions accumulating (BUY)
    if price_change < -0.5 and dp_pct > 45:
        signal = "BUY"
        confidence = 0.75
        reasoning.append(f"🎯 DIVERGENCE: Price DOWN {price_change:.2f}% but HIGH DP ({dp_pct:.1f}%)")
        reasoning.append("Institutions accumulating during selloff")
    
    # CASE 2: Price UP but LOW DP = Institutions distributing (SELL)
    elif price_change > 0.5 and dp_pct < 25:
        signal = "SELL"
        confidence = 0.75
        reasoning.append(f"🎯 DIVERGENCE: Price UP {price_change:.2f}% but LOW DP ({dp_pct:.1f}%)")
        reasoning.append("Institutions distributing into rally")
    
    # CASE 3: BIG Price DOWN + LOW DP = Confirmation (WAIT for bounce)
    elif price_change < -1.0 and dp_pct < 30:
        signal = "WAIT"
        confidence = 0.60
        reasoning.append(f"Price DOWN {price_change:.2f}% with LOW DP ({dp_pct:.1f}%)")
        reasoning.append("Confirmed selloff - wait for accumulation to start")
    
    # CASE 4: BIG Price UP + HIGH DP = Confirmation (trend may continue)
    elif price_change > 1.0 and dp_pct > 40:
        signal = "HOLD"
        confidence = 0.60
        reasoning.append(f"Price UP {price_change:.2f}% with HIGH DP ({dp_pct:.1f}%)")
        reasoning.append("Confirmed rally - DP supports uptrend")
    
    # CASE 5: Neutral
    else:
        reasoning.append(f"Neutral: Price {price_change:+.2f}% with DP {dp_pct:.1f}%")
        reasoning.append("No clear divergence")
    
    return signal, confidence, reasoning


def run_edge_test():
    """Test the divergence edge on recent data"""
    print("=" * 80)
    print("🔥 DIVERGENCE EDGE TEST")
    print("   Finding exploitable news vs institutional flow divergences")
    print("=" * 80)
    
    symbol = "SPY"
    
    # Get price history
    print(f"\n📈 Fetching {symbol} price history...")
    price_data = get_price_history(symbol, days=30)
    
    if not price_data:
        print("❌ Could not fetch price data")
        return
    
    print(f"   Got {len(price_data)} trading days")
    
    # Find volatile days
    volatile_days = [d for d in price_data if abs(d['pct_change']) > 0.5]
    print(f"   Volatile days (>0.5% move): {len(volatile_days)}")
    
    # Analyze each volatile day
    print("\n" + "=" * 80)
    print("📊 ANALYZING VOLATILE DAYS FOR DIVERGENCES")
    print("=" * 80)
    
    results = []
    
    for day in volatile_days[-10:]:  # Last 10 volatile days
        date_str = day['date']
        price_change = day['pct_change']
        
        print(f"\n📅 {date_str}: {symbol} {price_change:+.2f}%")
        
        # Get DP data
        dp_vol = get_dp_data(symbol, date_str)
        
        if dp_vol and dp_vol > 0:
            # Estimate total volume and DP %
            total_vol = day['volume']
            if total_vol > 0:
                dp_pct = (dp_vol / total_vol) * 100
            else:
                dp_pct = None
        else:
            dp_pct = None
        
        if dp_pct:
            print(f"   DP Volume: {dp_vol:,} ({dp_pct:.1f}%)")
        else:
            print(f"   DP data: Not available")
        
        # Check for divergence
        signal, confidence, reasoning = check_divergence(price_change, dp_pct)
        
        print(f"   Signal: {signal} @ {confidence:.0%}")
        for r in reasoning:
            print(f"   → {r}")
        
        # Check next day result if signal generated
        if signal in ["BUY", "SELL"]:
            # Find next day in price_data
            idx = next((i for i, d in enumerate(price_data) if d['date'] == date_str), None)
            if idx is not None and idx + 1 < len(price_data):
                next_day = price_data[idx + 1]
                next_change = next_day['pct_change']
                
                if signal == "BUY":
                    profitable = next_change > 0
                else:  # SELL
                    profitable = next_change < 0
                
                result_str = "✅ WIN" if profitable else "❌ LOSS"
                print(f"   📈 Next Day: {next_change:+.2f}% → {result_str}")
                
                results.append({
                    "date": date_str,
                    "signal": signal,
                    "next_change": next_change,
                    "profitable": profitable
                })
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 EDGE TEST RESULTS")
    print("=" * 80)
    
    if results:
        wins = sum(1 for r in results if r['profitable'])
        losses = len(results) - wins
        win_rate = (wins / len(results)) * 100
        
        print(f"\n   Total Signals: {len(results)}")
        print(f"   Wins: {wins}")
        print(f"   Losses: {losses}")
        print(f"   WIN RATE: {win_rate:.1f}%")
        
        if win_rate >= 60:
            print(f"\n   🔥 STRONG EDGE DETECTED!")
        elif win_rate >= 55:
            print(f"\n   ✅ Moderate edge - worth trading")
        elif win_rate >= 50:
            print(f"\n   ⚠️  Marginal edge - needs refinement")
        else:
            print(f"\n   ❌ No edge - strategy needs work")
    else:
        print("\n   No divergence signals generated in the sample period")
        print("   → This could mean market is calm (no divergences)")
        print("   → Or DP data not available for volatile days")
    
    return results


def show_current_setup():
    """Show current market setup and potential signals"""
    print("\n" + "=" * 80)
    print("🎰 CURRENT MARKET SETUP")
    print("=" * 80)
    
    import yfinance as yf
    
    symbol = "SPY"
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d", interval="1d")
    
    if hist.empty:
        print("❌ Could not fetch current data")
        return
    
    # Today's data
    today_close = float(hist['Close'].iloc[-1])
    prev_close = float(hist['Close'].iloc[-2])
    today_change = ((today_close / prev_close) - 1) * 100
    today_volume = int(hist['Volume'].iloc[-1])
    
    print(f"\n📊 {symbol} Current State:")
    print(f"   Price: ${today_close:.2f}")
    print(f"   Change: {today_change:+.2f}%")
    print(f"   Volume: {today_volume:,}")
    
    # Get DP data for most recent available date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    dp_vol = get_dp_data(symbol, yesterday)
    
    if dp_vol and today_volume > 0:
        # Use yesterday's DP as proxy
        dp_pct = (dp_vol / today_volume) * 100 if today_volume > 0 else None
        if dp_pct:
            print(f"   DP % (yesterday proxy): {dp_pct:.1f}%")
    
    # Current signal assessment
    print("\n🎯 SIGNAL ASSESSMENT:")
    
    if abs(today_change) < 0.3:
        print("   📊 Market is FLAT - no clear signal")
        print("   → Wait for volatility to generate divergence signals")
    elif today_change < -0.5:
        print("   📉 Market is DOWN - watch for accumulation signal")
        print("   → If DP spikes above 45%, consider BUY")
    elif today_change > 0.5:
        print("   📈 Market is UP - watch for distribution signal")
        print("   → If DP drops below 25%, consider SELL")
    else:
        print("   📊 Market is NEUTRAL - no clear divergence")


def show_strategy_rules():
    """Display the divergence trading rules"""
    print("\n" + "=" * 80)
    print("📋 DIVERGENCE TRADING RULES")
    print("=" * 80)
    
    print("""
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                    NEWS vs DARK POOL DIVERGENCE STRATEGY                 │
   ├──────────────────────────────────────────────────────────────────────────┤
   │                                                                          │
   │  🎯 BUY SIGNALS (Panic Buy):                                             │
   │  ─────────────────────────────────────────────────────────────────────── │
   │  • Headlines: "Market crashes", "Panic selling", "Risk-off"              │
   │  • Price: DOWN > 0.5%                                                    │
   │  • Dark Pool: > 45% (institutions accumulating)                          │
   │  → BUY the dip - institutions buying what retail is selling              │
   │                                                                          │
   │  🎯 SELL SIGNALS (Rally Sell):                                           │
   │  ─────────────────────────────────────────────────────────────────────── │
   │  • Headlines: "Market rallies", "Bullish momentum", "Risk-on"            │
   │  • Price: UP > 0.5%                                                      │
   │  • Dark Pool: < 25% (institutions distributing)                          │
   │  → SELL the rip - institutions selling what retail is buying             │
   │                                                                          │
   │  ⏸️  HOLD (No Divergence):                                               │
   │  ─────────────────────────────────────────────────────────────────────── │
   │  • DP 25-45% = Neutral institutional activity                            │
   │  • DP confirms price direction = No edge                                 │
   │  • Low volatility days = No signal                                       │
   │                                                                          │
   │  📈 ENTRY/EXIT:                                                          │
   │  ─────────────────────────────────────────────────────────────────────── │
   │  • Entry: On divergence detection                                        │
   │  • Stop Loss: 2% from entry                                              │
   │  • Target: 2% from entry (1:1 R/R minimum)                               │
   │  • Position Size: 2% of capital                                          │
   │                                                                          │
   └──────────────────────────────────────────────────────────────────────────┘
   
   💡 KEY INSIGHT: The edge is in DIVERGENCES - when institutional flow
      (measured by dark pool %) contradicts the price action / news sentiment.
   
   ⚠️  This strategy works BEST during volatile days when there's clear
      divergence. Calm markets = no divergence = no signal.
    """)


def main():
    """Run all tests"""
    
    # Show strategy rules
    show_strategy_rules()
    
    # Run edge test
    results = run_edge_test()
    
    # Show current setup
    show_current_setup()
    
    # Next steps
    print("\n" + "=" * 80)
    print("🚀 NEXT STEPS TO EXPLOIT NEWS")
    print("=" * 80)
    print("""
   1. ✅ Dark Pool data is working (ChartExchange API)
   2. ⏳ Add Perplexity API for real-time news sentiment
   3. ⏳ Integrate divergence detection into signal generator
   4. ⏳ Run during RTH (9:30-4pm) for live signals
   5. ⏳ Paper trade divergence signals for 2 weeks
   6. ⏳ If win rate > 55%, deploy with small capital
   
   🎯 The edge is in DIVERGENCES - trade when institutions do the 
      OPPOSITE of what headlines suggest. No divergence = no trade.
    """)


if __name__ == "__main__":
    main()





