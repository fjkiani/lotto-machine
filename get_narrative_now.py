#!/usr/bin/env python3
"""
📰 GET NARRATIVE NOW - SPECIFIC INTELLIGENCE
============================================
Shows what the narrative intelligence system would tell you right now
using ALL our actual data: DP levels, Fed Watch, Trump intel.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add project root to path
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)

def main():
    print("=" * 80)
    print("📰 SPECIFIC MARKET NARRATIVE (Not Generic Bullshit)")
    print("=" * 80)
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
    
    # === GATHER ALL OUR INTELLIGENCE ===
    print("🔧 Gathering intelligence...\n")
    
    # 1. Get current price
    current_price = None
    try:
        import yfinance as yf
        ticker = yf.Ticker("SPY")
        hist = ticker.history(period='1d', interval='1m')
        if not hist.empty:
            current_price = float(hist['Close'].iloc[-1])
            print(f"   💰 SPY Current Price: ${current_price:.2f}")
    except Exception as e:
        print(f"   ⚠️ Price fetch failed: {e}")
    
    # 2. Get Fed Watch data
    fed_sentiment = "NEUTRAL"
    fed_cut_prob = None
    try:
        from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
        fed_watch = FedWatchMonitor()
        status = fed_watch.get_current_status()
        fed_cut_prob = status.prob_cut
        if fed_cut_prob > 70:
            fed_sentiment = "DOVISH"
        elif fed_cut_prob < 30:
            fed_sentiment = "HAWKISH"
        print(f"   🏦 Fed Watch: {fed_cut_prob:.1f}% cut → {fed_sentiment}")
    except Exception as e:
        print(f"   ⚠️ Fed Watch failed: {e}")
    
    # 3. Get Trump risk
    trump_risk = "LOW"
    trump_news = None
    try:
        from live_monitoring.agents.trump_pulse import TrumpPulse
        from live_monitoring.agents.trump_news_monitor import TrumpNewsMonitor
        
        trump_pulse = TrumpPulse()
        situation = trump_pulse.get_current_situation()
        activity = getattr(situation, 'activity_level', 'N/A')
        sentiment = getattr(situation, 'overall_sentiment', 'UNKNOWN')
        
        if activity == "HIGH" or sentiment in ["BEARISH", "VOLATILE"]:
            trump_risk = "HIGH"
        elif activity == "MEDIUM":
            trump_risk = "MEDIUM"
        print(f"   🎯 Trump: {activity} activity, {sentiment} → {trump_risk} risk")
        
        # Get latest Trump news
        try:
            trump_news_monitor = TrumpNewsMonitor()
            exploits = trump_news_monitor.get_exploitable_news()
            if exploits:
                trump_news = exploits[0].news.headline
                print(f"   📰 Trump News: {trump_news[:50]}...")
        except:
            pass
    except Exception as e:
        print(f"   ⚠️ Trump Pulse failed: {e}")
    
    # 4. Get ACTUAL DP levels (the good shit)
    dp_levels = []
    try:
        from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
        api_key = os.getenv('CHARTEXCHANGE_API_KEY')
        if api_key:
            client = UltimateChartExchangeClient(api_key)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            raw_levels = client.get_dark_pool_levels("SPY", yesterday)
            
            if raw_levels:
                for level in raw_levels:
                    price = float(level.get('level', 0))
                    vol = float(level.get('volume', level.get('total_vol', 0)))
                    if vol >= 500000:  # Only significant levels
                        dp_levels.append({'price': price, 'volume': vol})
                
                dp_levels = sorted(dp_levels, key=lambda x: x['volume'], reverse=True)[:10]
                print(f"   🔒 DP Levels: {len(dp_levels)} battlegrounds loaded")
                
                # Show top 3
                for i, lvl in enumerate(dp_levels[:3]):
                    vol_str = f"{lvl['volume']/1e6:.1f}M" if lvl['volume'] >= 1e6 else f"{lvl['volume']/1e3:.0f}K"
                    print(f"      #{i+1}: ${lvl['price']:.2f} ({vol_str} shares)")
    except Exception as e:
        print(f"   ⚠️ DP levels failed: {e}")
    
    print("\n" + "=" * 80)
    print("📊 SPECIFIC NARRATIVE (Using Our Intelligence)")
    print("=" * 80 + "\n")
    
    # Get SPECIFIC narrative
    try:
        from live_monitoring.agents.signal_brain.narrative import NarrativeEnricher
        narrative = NarrativeEnricher()
        
        context = narrative.get_narrative(
            symbol="SPY",
            fed_sentiment=fed_sentiment,
            trump_risk=trump_risk,
            dp_levels=dp_levels,
            current_price=current_price,
            fed_cut_prob=fed_cut_prob,
            trump_news=trump_news
        )
        
        print(f"📰 THE STORY:")
        print(f"   {context.summary}\n")
        
        print(f"🎯 PRIMARY CATALYST:")
        print(f"   {context.catalyst}\n")
        
        print(f"⚠️ RISK ENVIRONMENT:")
        print(f"   {context.risk_environment}\n")
        
        if context.divergence_detected:
            print(f"🔀 DIVERGENCE DETECTED:")
            print(f"   {context.divergence_detail}\n")
        else:
            print(f"✅ NO DIVERGENCE: Institutions aligned with sentiment\n")
        
        print(f"💯 CONFIDENCE: {context.confidence:.0%}")
        print(f"📚 SOURCES: {', '.join(context.sources)}")
        
    except Exception as e:
        print(f"❌ Error getting narrative: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ DONE - This is SPECIFIC intelligence, not generic news")
    print("=" * 80)

if __name__ == "__main__":
    main()

