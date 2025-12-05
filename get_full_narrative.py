#!/usr/bin/env python3
"""
🧠 GET FULL NARRATIVE - TAVILY-POWERED INTELLIGENCE
===================================================
Deep research using specialized agents + Tavily API.

NOT generic news. SPECIFIC intelligence from:
- Fed Agent: What the Fed is REALLY saying
- Trump Agent: Policy risk analysis
- Institutional Agent: Smart money positioning
- Macro Agent: Economic regime
- Technical Agent: Price action context
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
    print("🧠 FULL NARRATIVE INTELLIGENCE (Tavily-Powered)")
    print("=" * 80)
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n")
    
    # Check for Tavily key
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        print("❌ TAVILY_API_KEY not set!")
        print("   Set it in .env or export TAVILY_API_KEY=...")
        return
    
    print(f"✅ Tavily API key found\n")
    
    # === GATHER CONTEXT ===
    print("🔧 Gathering market context...\n")
    
    # 1. Get current price
    current_price = None
    try:
        import yfinance as yf
        ticker = yf.Ticker("SPY")
        hist = ticker.history(period='1d', interval='1m')
        if not hist.empty:
            current_price = float(hist['Close'].iloc[-1])
            print(f"   💰 SPY Price: ${current_price:.2f}")
    except Exception as e:
        print(f"   ⚠️ Price fetch failed: {e}")
    
    # 2. Get Fed Watch data
    fed_sentiment = "NEUTRAL"
    fed_cut_prob = 50.0
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
        fed_cut_prob = 87.0  # Use known good value
        fed_sentiment = "DOVISH"
        print(f"   📋 Using fallback: {fed_cut_prob:.1f}% cut → {fed_sentiment}")
    
    # 3. Get Trump risk
    trump_risk = "LOW"
    trump_news = None
    try:
        from live_monitoring.agents.trump_pulse import TrumpPulse
        trump_pulse = TrumpPulse()
        situation = trump_pulse.get_current_situation()
        sentiment = getattr(situation, 'overall_sentiment', 'UNKNOWN')
        if sentiment in ["BEARISH", "VOLATILE"]:
            trump_risk = "HIGH"
        elif sentiment == "NEUTRAL":
            trump_risk = "MEDIUM"
        print(f"   🎯 Trump: {trump_risk} risk")
    except Exception as e:
        print(f"   ⚠️ Trump Pulse failed: {e}")
        trump_risk = "HIGH"  # Conservative default
    
    # 4. Get DP levels
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
                    if vol >= 500000:
                        dp_levels.append({'price': price, 'volume': vol})
                
                dp_levels = sorted(dp_levels, key=lambda x: x['volume'], reverse=True)[:10]
                print(f"   🔒 DP Levels: {len(dp_levels)} battlegrounds")
    except Exception as e:
        print(f"   ⚠️ DP levels failed: {e}")
    
    print("\n" + "=" * 80)
    print("🤖 RUNNING SPECIALIZED AGENTS")
    print("=" * 80 + "\n")
    
    # Initialize engine
    try:
        from live_monitoring.agents.narrative import NarrativeIntelligenceEngine
        
        engine = NarrativeIntelligenceEngine(tavily_key=tavily_key)
        print(f"✅ Engine initialized with {len(engine.agents)} agents\n")
        
        # Get full narrative
        narrative = engine.get_full_narrative(
            symbol="SPY",
            current_price=current_price,
            dp_levels=dp_levels,
            fed_sentiment=fed_sentiment,
            fed_cut_prob=fed_cut_prob,
            trump_risk=trump_risk,
            trump_news=trump_news,
        )
        
        print("\n" + "=" * 80)
        print("📰 SYNTHESIZED NARRATIVE")
        print("=" * 80 + "\n")
        
        print(f"📢 HEADLINE:")
        print(f"   {narrative.headline}\n")
        
        print(f"📖 FULL STORY:")
        print(f"   {narrative.full_story}\n")
        
        if narrative.key_points:
            print(f"📌 KEY POINTS:")
            for i, point in enumerate(narrative.key_points[:5], 1):
                print(f"   {i}. {point}")
            print()
        
        print(f"📊 ANALYSIS:")
        print(f"   • Bias: {narrative.overall_bias}")
        print(f"   • Confidence: {narrative.confidence:.0%}")
        print(f"   • Risk Level: {narrative.risk_level}\n")
        
        if narrative.trade_thesis:
            print(f"💰 TRADE THESIS:")
            print(f"   {narrative.trade_thesis}\n")
        
        if narrative.entry_trigger:
            print(f"🎯 ENTRY TRIGGER:")
            print(f"   {narrative.entry_trigger}\n")
        
        if narrative.risk_factors:
            print(f"⚠️ RISK FACTORS:")
            for risk in narrative.risk_factors[:3]:
                print(f"   • {risk}")
            print()
        
        print("=" * 80)
        print("🤖 AGENT SUMMARIES")
        print("=" * 80 + "\n")
        
        if narrative.fed_summary:
            print(f"🏦 FED AGENT:")
            print(f"   {narrative.fed_summary}\n")
        
        if narrative.trump_summary:
            print(f"🎯 TRUMP AGENT:")
            print(f"   {narrative.trump_summary}\n")
        
        if narrative.institutional_summary:
            print(f"🏛️ INSTITUTIONAL AGENT:")
            print(f"   {narrative.institutional_summary}\n")
        
        if narrative.macro_summary:
            print(f"📊 MACRO AGENT:")
            print(f"   {narrative.macro_summary}\n")
        
        if narrative.technical_summary:
            print(f"📈 TECHNICAL AGENT:")
            print(f"   {narrative.technical_summary}\n")
        
        if narrative.sources:
            print(f"📚 SOURCES ({len(narrative.sources)}):")
            for src in narrative.sources[:5]:
                print(f"   • {src}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ DONE - This is DEEP intelligence, not generic news")
    print("=" * 80)


if __name__ == "__main__":
    main()

