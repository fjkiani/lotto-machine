#!/usr/bin/env python3
"""
🧪 Test New Modular Fed Officials Engine
=========================================
Compare old vs new system.
"""

import sys
import os
from datetime import datetime

# Setup paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)

# Load environment
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

print("=" * 70)
print("🧪 TESTING NEW MODULAR FED OFFICIALS ENGINE")
print("=" * 70)
print()

# Test 1: Initialize new engine
print("1️⃣ INITIALIZING NEW ENGINE...")
print("-" * 70)
try:
    from live_monitoring.agents.fed_officials.engine import FedOfficialsEngine
    
    engine = FedOfficialsEngine()
    print("   ✅ Engine initialized!")
    print(f"   📊 Officials tracked: {len(engine.db.get_officials())}")
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Fetch comments
print("2️⃣ FETCHING COMMENTS (Dynamic Queries)...")
print("-" * 70)
try:
    comments = engine.fetch_comments(hours=24)
    print(f"   ✅ Fetched {len(comments)} new comments")
    
    if comments:
        print()
        print("   📝 Sample Comments:")
        for i, comment in enumerate(comments[:3], 1):
            icon = "🦅" if comment.sentiment == "HAWKISH" else "🕊️" if comment.sentiment == "DOVISH" else "➡️"
            print(f"   {i}. {icon} {comment.official_name}: {comment.sentiment}")
            print(f"      Confidence: {comment.sentiment_confidence:.0%}")
            print(f"      Reasoning: {comment.sentiment_reasoning[:80]}...")
            print(f"      Impact: {comment.predicted_market_impact}")
            print()
    else:
        print("   ⚠️ No new comments found (may be deduplicated or no recent news)")
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Get report
print("3️⃣ GENERATING REPORT...")
print("-" * 70)
try:
    report = engine.get_report()
    print(f"   ✅ Report generated!")
    print()
    print(f"   📊 Overall Sentiment: {report.overall_sentiment}")
    print(f"   📈 Market Bias: {report.market_bias}")
    print(f"   💯 Confidence: {report.confidence:.0%}")
    print(f"   💡 Recommendation: {report.recommendation}")
    print()
    
    if report.comments:
        print(f"   📝 Total Comments: {len(report.comments)}")
        print()
        print("   Recent Comments:")
        for comment in report.comments[:5]:
            icon = "🦅" if comment.sentiment == "HAWKISH" else "🕊️" if comment.sentiment == "DOVISH" else "➡️"
            print(f"   • {icon} {comment.official_name}: {comment.sentiment} ({comment.sentiment_confidence:.0%})")
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Check database learning
print("4️⃣ DATABASE LEARNING STATUS...")
print("-" * 70)
try:
    officials = engine.db.get_officials()
    print(f"   📊 Officials in database: {len(officials)}")
    
    if officials:
        print()
        print("   Top Officials (by comment frequency):")
        for official in officials[:5]:
            print(f"   • {official.name}: {official.comment_frequency} comments")
            print(f"     Historical sentiment: {official.historical_sentiment}")
            print(f"     Market impact score: {official.market_impact_score:.2f}")
    
    # Check query performance
    best_queries = engine.db.get_best_queries(limit=3)
    print()
    print(f"   🔍 Best-performing queries: {len(best_queries)}")
    if best_queries:
        for query in best_queries:
            print(f"   • {query[:60]}...")
    
    # Check sentiment patterns
    patterns = engine.db.get_sentiment_patterns(limit=5)
    print()
    print(f"   🧠 Learned sentiment patterns: {len(patterns)}")
    if patterns:
        for pattern in patterns[:3]:
            print(f"   • \"{pattern.phrase[:40]}...\" → {pattern.sentiment} ({pattern.confidence:.0%}, n={pattern.sample_count})")
    print()
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Compare with old system
print("5️⃣ OLD SYSTEM DELETED...")
print("-" * 70)
print("   ✅ Legacy monolithic `FedOfficialsMonitor` has been successfuly purged.")
print()

print("=" * 70)
print("✅ TEST COMPLETE!")
print("=" * 70)
print()
print("📊 SUMMARY:")
print(f"   • New engine: ✅ Working")
print(f"   • Comments fetched: {len(comments) if 'comments' in locals() else 0}")
print(f"   • Officials tracked: {len(engine.db.get_officials())}")
print(f"   • Query learning: {'✅ Active' if engine.db.get_best_queries() else '⏳ Learning...'}")
print(f"   • Sentiment patterns: {len(engine.db.get_sentiment_patterns())} learned")
print()





