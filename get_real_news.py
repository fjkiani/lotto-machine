#!/usr/bin/env python3
"""
🔥 GET REAL NEWS CONTEXT - Using Perplexity AI

This script gets ACTUAL market narrative using Perplexity:
- What's driving the market today?
- Key catalysts and events
- Sentiment analysis with real context
- Compare with institutional flow for divergences
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
sys.path.append(str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_env():
    """Load environment variables from .env file"""
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:
        logger.warning(f"Could not load .env: {e}")
    return env_vars


def get_perplexity_news(query: str, api_key: str) -> dict:
    """
    Get news context from Perplexity AI
    
    Returns actual narrative, not just headlines!
    """
    import requests
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "user",
                "content": query,
            }
        ],
        "search_recency_filter": "day",
        "return_citations": True,
        "return_related_questions": True,
    }
    
    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        
        if resp.status_code != 200:
            logger.error(f"Perplexity API error: {resp.status_code} - {resp.text[:200]}")
            return {"error": f"API error: {resp.status_code}"}
        
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        
        return {
            "answer": message.get("content", ""),
            "citations": data.get("citations", []),
            "related_queries": data.get("related_questions", []),
        }
        
    except Exception as e:
        logger.error(f"Error calling Perplexity: {e}")
        return {"error": str(e)}


def get_market_narrative():
    """Get comprehensive market narrative"""
    
    # Load API keys
    load_env()
    api_key = os.getenv('PERPLEXITY_API_KEY')
    
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not found!")
        return None
    
    print("=" * 80)
    print("🔥 GETTING REAL MARKET NARRATIVE FROM PERPLEXITY")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Query 1: What's driving the market today?
    print("\n📰 QUERY 1: What's driving SPY and the stock market today?")
    print("-" * 60)
    
    result1 = get_perplexity_news(
        "What is driving SPY and the US stock market today? What are the main catalysts, news events, and sentiment? Be specific about price action and key drivers.",
        api_key
    )
    
    if "error" not in result1:
        print(f"\n{result1['answer'][:2000]}")
        if result1.get('citations'):
            print(f"\n📎 Sources: {len(result1['citations'])} citations")
    else:
        print(f"❌ Error: {result1['error']}")
    
    # Query 2: Risk sentiment
    print("\n" + "=" * 80)
    print("📊 QUERY 2: Is this a risk-on or risk-off day?")
    print("-" * 60)
    
    result2 = get_perplexity_news(
        "Is today a risk-on or risk-off day for US equities? What's the overall sentiment - bullish, bearish, or neutral? Consider Fed policy, economic data, and market internals.",
        api_key
    )
    
    if "error" not in result2:
        print(f"\n{result2['answer'][:1500]}")
    else:
        print(f"❌ Error: {result2['error']}")
    
    # Query 3: Key events and catalysts
    print("\n" + "=" * 80)
    print("📅 QUERY 3: Key market events today/this week?")
    print("-" * 60)
    
    result3 = get_perplexity_news(
        "What are the key economic events, Fed speeches, or earnings reports affecting the stock market today and this week?",
        api_key
    )
    
    if "error" not in result3:
        print(f"\n{result3['answer'][:1500]}")
    else:
        print(f"❌ Error: {result3['error']}")
    
    # Combine results for sentiment analysis
    all_text = ""
    for r in [result1, result2, result3]:
        if "error" not in r:
            all_text += r.get("answer", "") + " "
    
    # Simple sentiment extraction
    text_lower = all_text.lower()
    
    bullish_words = ["rally", "surge", "gain", "bullish", "optimism", "record", "rise", "up", "higher", "positive"]
    bearish_words = ["selloff", "crash", "drop", "bearish", "fear", "decline", "down", "lower", "negative", "concern"]
    
    bullish_count = sum(1 for w in bullish_words if w in text_lower)
    bearish_count = sum(1 for w in bearish_words if w in text_lower)
    
    if bullish_count > bearish_count + 3:
        sentiment = "BULLISH"
    elif bearish_count > bullish_count + 3:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"
    
    print("\n" + "=" * 80)
    print("🎯 NARRATIVE SUMMARY")
    print("=" * 80)
    print(f"""
   Overall Sentiment: {sentiment}
   Bullish signals: {bullish_count}
   Bearish signals: {bearish_count}
   
   This is the REAL context from current news and analysis.
   Use this to compare with institutional dark pool flow!
    """)
    
    return {
        "market_drivers": result1,
        "risk_sentiment": result2,
        "key_events": result3,
        "overall_sentiment": sentiment,
        "bullish_signals": bullish_count,
        "bearish_signals": bearish_count
    }


def get_divergence_analysis():
    """
    Complete divergence analysis:
    1. Get real news narrative from Perplexity
    2. Get institutional flow from ChartExchange
    3. Detect divergences
    """
    
    load_env()
    
    print("\n" + "=" * 80)
    print("🔥 COMPLETE DIVERGENCE ANALYSIS")
    print("=" * 80)
    
    # Step 1: Get news narrative
    narrative = get_market_narrative()
    if not narrative:
        return
    
    news_sentiment = narrative.get("overall_sentiment", "NEUTRAL")
    
    # Step 2: Get institutional flow
    print("\n" + "=" * 80)
    print("🏦 INSTITUTIONAL FLOW (Dark Pool)")
    print("=" * 80)
    
    try:
        import yfinance as yf
        sys.path.append(str(Path(__file__).parent / 'configs'))
        sys.path.append(str(Path(__file__).parent / 'core' / 'data'))
        
        from chartexchange_config import get_api_key
        from ultimate_chartexchange_client import UltimateChartExchangeClient
        
        api_key = get_api_key()
        client = UltimateChartExchangeClient(api_key=api_key, tier=3)
        
        symbol = "SPY"
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Skip weekends
        while datetime.strptime(yesterday, "%Y-%m-%d").weekday() >= 5:
            yesterday = (datetime.strptime(yesterday, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Get DP data
        dp_levels = client.get_dark_pool_levels(symbol, yesterday)
        
        dp_vol = 0
        if dp_levels:
            for level in dp_levels:
                if isinstance(level, dict) and 'volume' in level:
                    dp_vol += int(level['volume'])
        
        # Get total volume
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="1d")
        total_vol = int(hist['Volume'].iloc[-1]) if not hist.empty else 0
        price = float(hist['Close'].iloc[-1]) if not hist.empty else 0
        
        dp_pct = (dp_vol / total_vol * 100) if total_vol > 0 else 0
        
        # Determine institutional bias
        if dp_pct > 45:
            inst_bias = "ACCUMULATING"
        elif dp_pct < 25:
            inst_bias = "DISTRIBUTING"
        else:
            inst_bias = "NEUTRAL"
        
        print(f"""
   Symbol: {symbol}
   Price: ${price:.2f}
   Dark Pool Volume: {dp_vol:,}
   Dark Pool %: {dp_pct:.1f}%
   Institutional Bias: {inst_bias}
        """)
        
        # Step 3: Detect divergence
        print("=" * 80)
        print("🎯 DIVERGENCE CHECK")
        print("=" * 80)
        
        divergence_detected = False
        signal = "HOLD"
        reasoning = []
        
        # Check for divergence
        if news_sentiment == "BEARISH" and inst_bias == "ACCUMULATING":
            divergence_detected = True
            signal = "BUY"
            reasoning.append("🔥 DIVERGENCE: News is BEARISH but institutions are ACCUMULATING!")
            reasoning.append("→ Institutions buying while headlines scream panic")
            reasoning.append("→ Classic 'buy the dip' opportunity")
        
        elif news_sentiment == "BULLISH" and inst_bias == "DISTRIBUTING":
            divergence_detected = True
            signal = "SELL"
            reasoning.append("🔥 DIVERGENCE: News is BULLISH but institutions are DISTRIBUTING!")
            reasoning.append("→ Institutions selling while headlines pump optimism")
            reasoning.append("→ Classic 'sell the rip' opportunity")
        
        elif news_sentiment == "NEUTRAL" and inst_bias == "ACCUMULATING":
            divergence_detected = True
            signal = "BUY"
            reasoning.append("👀 STEALTH ACCUMULATION: Quiet news but institutions loading up")
            reasoning.append("→ Smart money positioning before a move")
        
        elif news_sentiment == "NEUTRAL" and inst_bias == "DISTRIBUTING":
            divergence_detected = True
            signal = "SELL"
            reasoning.append("👀 STEALTH DISTRIBUTION: Quiet news but institutions unloading")
            reasoning.append("→ Smart money exiting before a drop")
        
        else:
            reasoning.append("📊 No divergence - news and institutions aligned")
            reasoning.append(f"   News: {news_sentiment}, Institutions: {inst_bias}")
        
        print(f"""
   News Sentiment: {news_sentiment}
   Institutional Bias: {inst_bias}
   
   ═══════════════════════════════════════════════════════════════
   DIVERGENCE DETECTED: {'YES' if divergence_detected else 'NO'}
   SIGNAL: {signal}
   ═══════════════════════════════════════════════════════════════
        """)
        
        for r in reasoning:
            print(f"   {r}")
        
        if divergence_detected:
            stop = price * 0.98 if signal == "BUY" else price * 1.02
            target = price * 1.02 if signal == "BUY" else price * 0.98
            print(f"""
   📊 TRADE SETUP:
      Entry: ${price:.2f}
      Stop Loss: ${stop:.2f}
      Target: ${target:.2f}
            """)
        
    except Exception as e:
        logger.error(f"Error getting institutional flow: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        get_divergence_analysis()
    else:
        get_market_narrative()





