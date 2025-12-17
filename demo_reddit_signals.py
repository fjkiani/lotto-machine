#!/usr/bin/env python3
"""
🔥 REDDIT SIGNAL DEMO - Show Actual Signal Generation
======================================================

Demonstrates all 12 signal types with real examples.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

from live_monitoring.exploitation.reddit_exploiter import (
    RedditExploiter, RedditSignalType, RedditRealTimeMonitor, WSBAnalyzer
)
from live_monitoring.orchestrator.checkers.reddit_checker import RedditChecker
from live_monitoring.orchestrator.alert_manager import AlertManager

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_signal_header():
    """Print header"""
    print("\n" + "="*80)
    print("🔥 REDDIT EXPLOITER - SIGNAL DEMONSTRATION")
    print("="*80 + "\n")


def demo_signal_types():
    """Show all signal types"""
    print("\n📊 ALL 12 SIGNAL TYPES:")
    print("-" * 80)
    
    signals = [
        ("FADE_HYPE", "SHORT", "Extreme bullish sentiment (>0.4) + >60% bullish"),
        ("FADE_FEAR", "LONG", "Extreme bearish sentiment (<-0.3) + >50% bearish"),
        ("WSB_YOLO_WAVE", "SHORT", "WSB meme mode (YOLO score >50, >70% WSB)"),
        ("WSB_CAPITULATION", "LONG", "WSB giving up (>70% WSB + sentiment <-0.3)"),
        ("MOMENTUM_SURGE", "LONG/SHORT", "Mention spike >100% + improving sentiment"),
        ("VELOCITY_SURGE", "AVOID", "Mention velocity >3x normal (pump warning)"),
        ("SENTIMENT_SHIFT_ALERT", "WATCH", "7-day sentiment trend shift >0.15"),
        ("SENTIMENT_FLIP", "WATCH", "Sentiment trend reversal (IMPROVING/DECLINING)"),
        ("BULLISH_DIVERGENCE", "LONG", "Price down >2% but sentiment improving"),
        ("BEARISH_DIVERGENCE", "SHORT", "Price up >2% but sentiment declining"),
        ("STEALTH_ACCUMULATION", "LONG", "Low mentions (<50) but price rising >5%"),
        ("PUMP_WARNING", "AVOID", "Mention spike >200% + WSB >60%"),
    ]
    
    for i, (signal_type, action, description) in enumerate(signals, 1):
        print(f"{i:2d}. {signal_type:25s} | {action:10s} | {description}")
    
    print("-" * 80 + "\n")


def demo_analyze_ticker(exploiter: RedditExploiter, symbol: str):
    """Analyze a ticker and show signals"""
    print(f"\n{'='*80}")
    print(f"📱 ANALYZING: {symbol}")
    print(f"{'='*80}\n")
    
    try:
        analysis = exploiter.analyze_ticker(symbol, days=3)
        
        if not analysis:
            print(f"❌ No Reddit data found for {symbol}")
            return
        
        print(f"✅ Analysis Complete!")
        print(f"\n📊 METRICS:")
        print(f"   Total Mentions: {analysis.total_mentions}")
        print(f"   Mentions Today: {analysis.mentions_today}")
        print(f"   Mentions 24h Ago: {analysis.mentions_24h_ago}")
        print(f"   Mention Change: {analysis.mention_change_pct:+.1f}%")
        print(f"\n💭 SENTIMENT:")
        print(f"   Avg Sentiment: {analysis.avg_sentiment:+.3f}")
        print(f"   Bullish %: {analysis.bullish_pct:.1f}%")
        print(f"   Bearish %: {analysis.bearish_pct:.1f}%")
        print(f"   Sentiment Trend: {analysis.sentiment_trend}")
        print(f"\n🎰 WSB ANALYSIS:")
        print(f"   WSB Dominance: {analysis.wsb_dominance:.1f}%")
        print(f"   Top Subreddits: {', '.join(list(analysis.top_subreddits.keys())[:3])}")
        
        print(f"\n🎯 SIGNAL GENERATED:")
        if analysis.signal_type:
            signal_type = analysis.signal_type.value
            print(f"   Type: {signal_type}")
            print(f"   Action: {analysis.action}")
            print(f"   Strength: {analysis.signal_strength:.0f}%")
            
            if analysis.reasoning:
                print(f"\n💡 REASONING:")
                for reason in analysis.reasoning[:5]:
                    print(f"   • {reason}")
            
            if analysis.warnings:
                print(f"\n⚠️  WARNINGS:")
                for warning in analysis.warnings:
                    print(f"   • {warning}")
        else:
            print(f"   No signal generated (strength: {analysis.signal_strength:.0f}%)")
        
        # Velocity check
        velocity = exploiter.calculate_mention_velocity(symbol)
        if velocity['is_surging']:
            print(f"\n⚡ VELOCITY SURGE DETECTED:")
            print(f"   Velocity 1h: {velocity['velocity_1h']:.1f} mentions/hr")
            print(f"   Velocity 24h: {velocity['velocity_24h']:.1f} mentions/hr")
            print(f"   Surge Multiplier: {velocity['surge_multiplier']:.1f}x")
        
        # Price correlation
        price_corr = exploiter.correlate_with_price(symbol, analysis)
        if price_corr['current_price'] > 0:
            print(f"\n💰 PRICE CORRELATION:")
            print(f"   Current Price: ${price_corr['current_price']:.2f}")
            print(f"   Price Change 7d: {price_corr['price_change_7d']:+.1f}%")
            print(f"   Correlation: {price_corr['confirmation']}")
            if price_corr['divergence']:
                print(f"   ⚠️  DIVERGENCE: {price_corr['divergence_type']}")
        
        # Sample posts
        if analysis.sample_posts:
            print(f"\n💬 SAMPLE POSTS:")
            for post in analysis.sample_posts[:3]:
                print(f"   {post}")
        
    except Exception as e:
        print(f"❌ Error analyzing {symbol}: {e}")
        import traceback
        traceback.print_exc()


def demo_hot_tickers(exploiter: RedditExploiter):
    """Show hot ticker discovery"""
    print(f"\n{'='*80}")
    print(f"🔥 HOT TICKER DISCOVERY")
    print(f"{'='*80}\n")
    
    try:
        hot_tickers = exploiter.discover_hot_tickers(min_sentiment_extreme=0.3, max_tickers=10)
        
        if not hot_tickers:
            print("❌ No hot tickers found")
            return
        
        print(f"✅ Found {len(hot_tickers)} hot tickers:\n")
        
        for i, ticker in enumerate(hot_tickers[:10], 1):
            print(f"{i:2d}. {ticker.symbol:6s} | "
                  f"Mentions: {ticker.mention_count:4d} | "
                  f"Sentiment: {ticker.avg_sentiment:+.2f} | "
                  f"Bullish: {ticker.bullish_pct:5.1f}% | "
                  f"WSB: {ticker.wsb_mentions:3d} | "
                  f"Momentum: {ticker.momentum_score:.0f}")
        
    except Exception as e:
        print(f"❌ Error discovering hot tickers: {e}")
        import traceback
        traceback.print_exc()


def demo_emerging_tickers(exploiter: RedditExploiter):
    """Show emerging ticker discovery"""
    print(f"\n{'='*80}")
    print(f"🌱 EMERGING TICKER DISCOVERY")
    print(f"{'='*80}\n")
    
    try:
        emerging = exploiter.discover_emerging_tickers(min_mentions=20, max_mentions=100)
        
        if not emerging:
            print("❌ No emerging tickers found")
            return
        
        print(f"✅ Found {len(emerging)} emerging tickers:\n")
        
        for i, ticker in enumerate(emerging[:10], 1):
            print(f"{i:2d}. {ticker['symbol']:6s} | "
                  f"Mentions: {ticker['mention_count']:4d} | "
                  f"Velocity: {ticker['velocity']:.1f}x | "
                  f"Sentiment: {ticker['sentiment']:+.2f} | "
                  f"Momentum: {ticker['momentum_score']:.0f} | "
                  f"Reason: {ticker['discovery_reason']}")
        
    except Exception as e:
        print(f"❌ Error discovering emerging tickers: {e}")
        import traceback
        traceback.print_exc()


def demo_wsb_analyzer():
    """Show WSB analyzer"""
    print(f"\n{'='*80}")
    print(f"🎰 WSB ANALYZER DEMO")
    print(f"{'='*80}\n")
    
    from live_monitoring.exploitation.reddit_exploiter import RedditMention
    
    analyzer = WSBAnalyzer()
    
    # Create mock WSB mentions
    mentions = [
        RedditMention('wallstreetbets', datetime.now(), 0.8, 'user1', 
                     '🚀🚀🚀 TO THE MOON! 💎💎💎 DIAMOND HANDS! YOLO!', '', 'comment'),
        RedditMention('wallstreetbets', datetime.now(), 0.7, 'user2', 
                     'ALL IN! TENDIES TIME!', '', 'comment'),
        RedditMention('wallstreetbets', datetime.now(), 0.6, 'user3', 
                     'APES STRONG TOGETHER!', '', 'comment'),
        RedditMention('stocks', datetime.now(), 0.3, 'user4', 
                     'Normal analysis post', '', 'comment'),
    ]
    
    analysis = analyzer.analyze_wsb_activity(mentions)
    
    print(f"📊 WSB Analysis Results:")
    print(f"   WSB Dominance: {analysis['wsb_dominance']:.1f}%")
    print(f"   YOLO Score: {analysis['yolo_score']:.0f}/100")
    print(f"   Rocket Emoji Count: {analysis['rocket_emoji']}")
    print(f"   Diamond Hands Count: {analysis['diamond_hands']}")
    print(f"   Meme Mode: {'YES' if analysis['is_meme_mode'] else 'NO'}")
    print(f"   Risk Level: {analysis['risk_level']}")


def demo_contrarian_signals(exploiter: RedditExploiter):
    """Show contrarian signals"""
    print(f"\n{'='*80}")
    print(f"🎯 CONTRARIAN SIGNALS")
    print(f"{'='*80}\n")
    
    try:
        signals = exploiter.get_contrarian_signals(min_strength=60, max_tickers=10)
        
        if not signals:
            print("❌ No contrarian signals found")
            return
        
        print(f"✅ Found {len(signals)} contrarian signals:\n")
        
        for i, signal in enumerate(signals[:10], 1):
            signal_type = signal.signal_type.value if signal.signal_type else "NONE"
            print(f"{i:2d}. {signal.symbol:6s} | "
                  f"{signal_type:25s} | "
                  f"{signal.action:8s} | "
                  f"Strength: {signal.signal_strength:.0f}% | "
                  f"Sentiment: {signal.avg_sentiment:+.2f}")
            
            if signal.reasoning:
                print(f"    └─ {signal.reasoning[0]}")
        
    except Exception as e:
        print(f"❌ Error getting contrarian signals: {e}")
        import traceback
        traceback.print_exc()


def demo_rate_limit_status(exploiter: RedditExploiter):
    """Show rate limit status"""
    print(f"\n{'='*80}")
    print(f"⏱️  RATE LIMIT STATUS")
    print(f"{'='*80}\n")
    
    status = exploiter.get_rate_limit_status()
    
    print(f"📊 Current Status:")
    print(f"   Requests Last Minute: {status['requests_last_minute']}")
    print(f"   Rate Limit: {status['rate_limit']}/min")
    print(f"   Remaining: {status['remaining']}")
    print(f"   Utilization: {status['utilization_pct']:.1f}%")
    print(f"   Can Make Request: {'YES' if status['can_make_request'] else 'NO'}")


def main():
    """Main demo function"""
    print_signal_header()
    
    # Get API key (try multiple env var names)
    api_key = (
        os.getenv('CHARTEXCHANGE_API_KEY') or 
        os.getenv('CHART_EXCHANGE_API_KEY') or
        os.getenv('CHARTEXCHANGE_API') or
        os.getenv('CHARTEXCHANGE_KEY')
    )
    
    if not api_key:
        print("❌ ERROR: No API key found!")
        print("   Tried: CHARTEXCHANGE_API_KEY, CHART_EXCHANGE_API_KEY, CHARTEXCHANGE_API, CHARTEXCHANGE_KEY")
        print("   Check your .env file")
        return
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}\n")
    
    # Initialize exploiter
    print("🔧 Initializing Reddit Exploiter...")
    exploiter = RedditExploiter(api_key=api_key)
    print("✅ Initialized!\n")
    
    # Show all signal types
    demo_signal_types()
    
    # Show rate limit status
    demo_rate_limit_status(exploiter)
    
    # Demo WSB analyzer
    demo_wsb_analyzer()
    
    # Analyze specific tickers
    test_tickers = ['TSLA', 'NVDA', 'GME', 'SPY', 'QQQ']
    
    print(f"\n{'='*80}")
    print(f"📱 ANALYZING TEST TICKERS")
    print(f"{'='*80}")
    print(f"Testing: {', '.join(test_tickers)}\n")
    
    for ticker in test_tickers:
        demo_analyze_ticker(exploiter, ticker)
    
    # Hot ticker discovery
    demo_hot_tickers(exploiter)
    
    # Emerging ticker discovery
    demo_emerging_tickers(exploiter)
    
    # Contrarian signals
    demo_contrarian_signals(exploiter)
    
    print(f"\n{'='*80}")
    print(f"✅ DEMO COMPLETE!")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()

