#!/usr/bin/env python3
"""
📊 Show Actual Signal Data Structures
======================================

Shows the actual Python objects and data structures for signals.
"""

from datetime import datetime
from dataclasses import asdict
from live_monitoring.exploitation.reddit_exploiter import (
    RedditTickerAnalysis, RedditSignalType, HotTickerDiscovery, RedditMention
)


def show_signal_structure():
    """Show what a RedditTickerAnalysis object looks like"""
    
    print("\n" + "="*80)
    print("📊 REDDIT SIGNAL DATA STRUCTURE")
    print("="*80 + "\n")
    
    # Create example signal
    analysis = RedditTickerAnalysis(
        symbol="TSLA",
        timestamp=datetime.now(),
        total_mentions=1250,
        mentions_today=450,
        mentions_24h_ago=280,
        mention_change_pct=60.7,
        avg_sentiment=0.65,
        bullish_pct=72.0,
        bearish_pct=15.0,
        sentiment_trend="IMPROVING",
        top_subreddits={'wallstreetbets': 850, 'stocks': 200, 'investing': 150},
        wsb_dominance=68.0,
        signal_type=RedditSignalType.FADE_HYPE,
        signal_strength=85.0,
        action="SHORT",
        reasoning=[
            "Extreme bullish sentiment (+0.65)",
            "Crowd is 72% bullish - too crowded",
            "Contrarian signal: FADE THE HYPE",
            "Mention surge indicates FOMO peak"
        ],
        warnings=[
            "High WSB dominance (68%) - meme risk",
            "Retail FOMO in progress"
        ],
        sample_posts=[
            "[+0.8] r/wallstreetbets: 🚀🚀🚀 TO THE MOON!",
            "[+0.7] r/stocks: This is going to $500!",
            "[+0.6] r/investing: Strong fundamentals"
        ]
    )
    
    print("📱 RedditTickerAnalysis Object:")
    print("-" * 80)
    print(f"Symbol: {analysis.symbol}")
    print(f"Timestamp: {analysis.timestamp}")
    print(f"Signal Type: {analysis.signal_type.value if analysis.signal_type else 'NONE'}")
    print(f"Action: {analysis.action}")
    print(f"Strength: {analysis.signal_strength}%")
    print(f"\n📊 Metrics:")
    print(f"   Total Mentions: {analysis.total_mentions:,}")
    print(f"   Mentions Today: {analysis.mentions_today}")
    print(f"   Mentions 24h Ago: {analysis.mentions_24h_ago}")
    print(f"   Mention Change: {analysis.mention_change_pct:+.1f}%")
    print(f"\n💭 Sentiment:")
    print(f"   Avg Sentiment: {analysis.avg_sentiment:+.3f}")
    print(f"   Bullish %: {analysis.bullish_pct:.1f}%")
    print(f"   Bearish %: {analysis.bearish_pct:.1f}%")
    print(f"   Trend: {analysis.sentiment_trend}")
    print(f"\n🎰 WSB Analysis:")
    print(f"   WSB Dominance: {analysis.wsb_dominance:.1f}%")
    print(f"   Top Subreddits: {dict(list(analysis.top_subreddits.items())[:3])}")
    print(f"\n💡 Reasoning ({len(analysis.reasoning)} items):")
    for i, reason in enumerate(analysis.reasoning, 1):
        print(f"   {i}. {reason}")
    print(f"\n⚠️  Warnings ({len(analysis.warnings)} items):")
    for i, warning in enumerate(analysis.warnings, 1):
        print(f"   {i}. {warning}")
    print(f"\n💬 Sample Posts ({len(analysis.sample_posts)} items):")
    for i, post in enumerate(analysis.sample_posts, 1):
        print(f"   {i}. {post}")
    
    print("\n" + "="*80)
    print("📋 AS DICT (for JSON/API):")
    print("="*80 + "\n")
    
    # Convert to dict
    signal_dict = {
        'symbol': analysis.symbol,
        'timestamp': analysis.timestamp.isoformat(),
        'signal_type': analysis.signal_type.value if analysis.signal_type else None,
        'action': analysis.action,
        'strength': analysis.signal_strength,
        'metrics': {
            'total_mentions': analysis.total_mentions,
            'mentions_today': analysis.mentions_today,
            'mentions_24h_ago': analysis.mentions_24h_ago,
            'mention_change_pct': analysis.mention_change_pct,
            'avg_sentiment': analysis.avg_sentiment,
            'bullish_pct': analysis.bullish_pct,
            'bearish_pct': analysis.bearish_pct,
            'sentiment_trend': analysis.sentiment_trend,
            'wsb_dominance': analysis.wsb_dominance,
        },
        'reasoning': analysis.reasoning,
        'warnings': analysis.warnings,
        'sample_posts': analysis.sample_posts
    }
    
    import json
    print(json.dumps(signal_dict, indent=2, default=str))
    
    print("\n" + "="*80)
    print("🔥 HOT TICKER DISCOVERY STRUCTURE")
    print("="*80 + "\n")
    
    hot_ticker = HotTickerDiscovery(
        symbol="NVDA",
        mention_count=850,
        avg_sentiment=0.55,
        bullish_pct=68.0,
        wsb_mentions=420,
        momentum_score=82.5,
        discovery_reason="Rapid mention growth (2.3x)"
    )
    
    print(f"Symbol: {hot_ticker.symbol}")
    print(f"Mention Count: {hot_ticker.mention_count}")
    print(f"Avg Sentiment: {hot_ticker.avg_sentiment:+.2f}")
    print(f"Bullish %: {hot_ticker.bullish_pct:.1f}%")
    print(f"WSB Mentions: {hot_ticker.wsb_mentions}")
    print(f"Momentum Score: {hot_ticker.momentum_score:.1f}")
    print(f"Discovery Reason: {hot_ticker.discovery_reason}")
    
    print("\n" + "="*80)
    print("✅ STRUCTURE DEMO COMPLETE!")
    print("="*80 + "\n")


if __name__ == '__main__':
    show_signal_structure()

