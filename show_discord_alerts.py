#!/usr/bin/env python3
"""
📱 Show Discord Alert Examples
===============================

Shows what Discord alerts look like for different signal types.
"""

import json
from datetime import datetime
from live_monitoring.exploitation.reddit_exploiter import (
    RedditTickerAnalysis, RedditSignalType
)


def show_discord_embed(signal_type: str, embed: dict):
    """Show formatted Discord embed"""
    print(f"\n{'='*80}")
    print(f"📱 DISCORD ALERT: {signal_type}")
    print(f"{'='*80}\n")
    print(f"Title: {embed.get('title', 'N/A')}")
    print(f"Color: #{embed.get('color', 0):06x}")
    print(f"Description: {embed.get('description', 'N/A')}")
    print(f"\nFields ({len(embed.get('fields', []))}):")
    for i, field in enumerate(embed.get('fields', []), 1):
        name = field.get('name', 'N/A')
        value = field.get('value', 'N/A')
        inline = field.get('inline', False)
        print(f"   {i}. [{name}] {'(inline)' if inline else ''}")
        # Truncate long values
        if len(value) > 100:
            value = value[:97] + "..."
        print(f"      {value}")
    print(f"\nFooter: {embed.get('footer', {}).get('text', 'N/A')}")
    print(f"Timestamp: {embed.get('timestamp', 'N/A')}")
    print(f"\n{'─'*80}")
    print("JSON Format:")
    print(json.dumps(embed, indent=2, default=str))


def demo_discord_alerts():
    """Show Discord alert examples"""
    
    print("\n" + "="*80)
    print("📱 DISCORD ALERT EXAMPLES")
    print("="*80)
    
    # FADE_HYPE signal
    fade_hype_signal = RedditTickerAnalysis(
        symbol="GME",
        timestamp=datetime.now(),
        total_mentions=1234,
        mentions_today=450,
        mentions_24h_ago=280,
        mention_change_pct=60.7,
        avg_sentiment=0.65,
        bullish_pct=72.0,
        bearish_pct=15.0,
        sentiment_trend="IMPROVING",
        top_subreddits={'wallstreetbets': 850},
        wsb_dominance=68.0,
        signal_type=RedditSignalType.FADE_HYPE,
        signal_strength=85.0,
        action="SHORT",
        reasoning=[
            "Extreme bullish sentiment (+0.65)",
            "Crowd is 72% bullish - too crowded",
            "Contrarian signal: FADE THE HYPE"
        ],
        warnings=["High WSB dominance (68%) - meme risk"],
        sample_posts=["[+0.8] r/wallstreetbets: 🚀🚀🚀 TO THE MOON!"]
    )
    
    # Create embed (simulating RedditChecker logic)
    embed1 = {
        "title": "🔻 REDDIT SIGNAL: GME",
        "color": 0xff0000,  # Red for SHORT
        "description": "**FADE_HYPE** | Strength: 85%",
        "fields": [
            {"name": "🎯 Action", "value": "**SHORT**", "inline": True},
            {"name": "📈 Sentiment", "value": "+0.65", "inline": True},
            {"name": "📊 Mentions", "value": "1,234", "inline": True},
            {"name": "🔺 Bullish", "value": "72%", "inline": True},
            {"name": "🔻 Bearish", "value": "15%", "inline": True},
            {"name": "🎰 WSB %", "value": "68%", "inline": True},
            {
                "name": "💡 Reasoning",
                "value": "• Extreme bullish sentiment (+0.65)\n• Crowd is 72% bullish - too crowded\n• Contrarian signal: FADE THE HYPE",
                "inline": False
            },
            {
                "name": "⚠️ Warnings",
                "value": "High WSB dominance (68%) - meme risk",
                "inline": False
            },
            {
                "name": "💬 Top Posts",
                "value": "[+0.8] r/wallstreetbets: 🚀🚀🚀 TO THE MOON!",
                "inline": False
            }
        ],
        "footer": {"text": "Reddit Exploiter | Contrarian Signal"},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    show_discord_embed("FADE_HYPE (SHORT)", embed1)
    
    # BULLISH_DIVERGENCE signal with price correlation
    bullish_div_signal = RedditTickerAnalysis(
        symbol="TSLA",
        timestamp=datetime.now(),
        total_mentions=856,
        mentions_today=320,
        mentions_24h_ago=280,
        mention_change_pct=14.3,
        avg_sentiment=0.35,
        bullish_pct=58.0,
        bearish_pct=25.0,
        sentiment_trend="IMPROVING",
        top_subreddits={'wallstreetbets': 420, 'stocks': 200},
        wsb_dominance=49.0,
        signal_type=RedditSignalType.BULLISH_DIVERGENCE,
        signal_strength=72.0,
        action="LONG",
        reasoning=[
            "📈 BULLISH DIVERGENCE detected",
            "Price: $245.50 (-4.2% 7d)",
            "Sentiment: +0.35 (improving)",
            "Smart money accumulating - potential reversal"
        ],
        warnings=[],
        sample_posts=[]
    )
    
    embed2 = {
        "title": "🔺 REDDIT SIGNAL: TSLA",
        "color": 0x00ff00,  # Green for LONG
        "description": "**BULLISH_DIVERGENCE** | Strength: 72%",
        "fields": [
            {"name": "🎯 Action", "value": "**LONG**", "inline": True},
            {"name": "📈 Sentiment", "value": "+0.35", "inline": True},
            {"name": "📊 Mentions", "value": "856", "inline": True},
            {
                "name": "📈 Sentiment Trend (7d)",
                "value": "`▁▂▃▅▆▇█`",
                "inline": False
            },
            {
                "name": "💰 Price Action",
                "value": "$245.50 (-4.2% 7d)\n⚠️ **DIVERGENCE**: BULLISH_DIV",
                "inline": False
            },
            {
                "name": "🎯 Trade Setup",
                "value": "Entry: $245.50\nStop: $240.59 (2.0% risk)\nTarget: $255.32 (4.0% reward)\nR/R: 2.0:1",
                "inline": False
            },
            {
                "name": "💡 Reasoning",
                "value": "• 📈 BULLISH DIVERGENCE detected\n• Price: $245.50 (-4.2% 7d)\n• Sentiment: +0.35 (improving)\n• Smart money accumulating - potential reversal",
                "inline": False
            }
        ],
        "footer": {"text": "Reddit Exploiter | Contrarian Signal"},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    show_discord_embed("BULLISH_DIVERGENCE (LONG)", embed2)
    
    # VELOCITY_SURGE signal
    embed3 = {
        "title": "⚡ REDDIT SIGNAL: XYZ",
        "color": 0xff6600,  # Orange for AVOID
        "description": "**VELOCITY_SURGE** | Strength: 75%",
        "fields": [
            {"name": "🎯 Action", "value": "**AVOID**", "inline": True},
            {"name": "📈 Sentiment", "value": "+0.42", "inline": True},
            {"name": "📊 Mentions", "value": "234", "inline": True},
            {
                "name": "⚡ Velocity Surge",
                "value": "🚨 VELOCITY SURGE: 3.8x normal mention rate\nLast hour: 45 mentions/hr\n24h avg: 12 mentions/hr\n⚠️ Early pump warning - monitor closely",
                "inline": False
            },
            {
                "name": "⚠️ Warnings",
                "value": "⚠️ High mention velocity - potential manipulation",
                "inline": False
            }
        ],
        "footer": {"text": "Reddit Exploiter | Contrarian Signal"},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    show_discord_embed("VELOCITY_SURGE (AVOID)", embed3)
    
    # Emerging ticker discovery
    embed4 = {
        "title": "🌱 EMERGING TICKER: PLTR",
        "color": 0x00ff00,  # Green for high momentum
        "description": "**Rapid mention growth (2.3x)**",
        "fields": [
            {"name": "📊 Mentions", "value": "45", "inline": True},
            {"name": "🚀 Velocity", "value": "2.3x", "inline": True},
            {"name": "📈 Momentum", "value": "78/100", "inline": True},
            {"name": "💭 Sentiment", "value": "+0.22", "inline": True},
            {"name": "📱 Top Subreddit", "value": "r/ValueInvesting", "inline": True},
        ],
        "footer": {"text": "Reddit Exploiter | Emerging Ticker Discovery"},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    show_discord_embed("EMERGING TICKER DISCOVERY", embed4)
    
    print(f"\n{'='*80}")
    print("✅ DISCORD ALERT DEMO COMPLETE!")
    print(f"{'='*80}\n")
    print("These alerts are sent to Discord via RedditChecker.check()")
    print("Each alert includes:")
    print("  • Rich embed with color coding")
    print("  • All relevant metrics")
    print("  • Reasoning and warnings")
    print("  • Trade setup (when actionable)")
    print("  • Sample posts (when available)")
    print()


if __name__ == '__main__':
    demo_discord_alerts()

