#!/usr/bin/env python3
"""
🔍 TEST TAVILY RAW OUTPUT
========================
See what Tavily ACTUALLY returns - not our filtered garbage.
"""

import os
from dotenv import load_dotenv
load_dotenv()

from live_monitoring.agents.narrative.tavily_client import TavilyClient

def main():
    tavily_key = os.getenv('TAVILY_API_KEY')
    if not tavily_key:
        print("❌ No TAVILY_API_KEY")
        return
    
    client = TavilyClient(tavily_key)
    
    print("=" * 80)
    print("🔍 RAW TAVILY OUTPUT - NO FILTERING")
    print("=" * 80)
    
    # Test 1: Fed narrative - SPECIFIC question
    print("\n📌 QUERY 1: WHY is the Fed cutting rates in December 2025?")
    print("-" * 60)
    result = client.search(
        "Why is the Federal Reserve cutting rates December 2025 what economic data is driving this decision specific reasons",
        search_depth="advanced",
        max_results=5
    )
    print(f"\n🤖 AI ANSWER:\n{result.answer}\n")
    print(f"📚 TOP SOURCES:")
    for r in result.results[:3]:
        print(f"\n   📰 {r.title}")
        print(f"   🔗 {r.url}")
        print(f"   📝 {r.content[:300]}...")
    
    # Test 2: What happened TODAY
    print("\n\n" + "=" * 80)
    print("\n📌 QUERY 2: What moved SPY today December 5 2025?")
    print("-" * 60)
    result = client.search(
        "SPY S&P 500 December 5 2025 what happened today key events market movers news",
        search_depth="advanced",
        max_results=5
    )
    print(f"\n🤖 AI ANSWER:\n{result.answer}\n")
    print(f"📚 TOP SOURCES:")
    for r in result.results[:3]:
        print(f"\n   📰 {r.title}")
        print(f"   🔗 {r.url}")
        print(f"   📝 {r.content[:300]}...")
    
    # Test 3: Trump tariffs SPECIFICS
    print("\n\n" + "=" * 80)
    print("\n📌 QUERY 3: Trump tariffs December 2025 - what EXACTLY was announced?")
    print("-" * 60)
    result = client.search(
        "Trump tariff announcement December 2025 specific details which products countries affected percentages",
        search_depth="advanced",
        max_results=5
    )
    print(f"\n🤖 AI ANSWER:\n{result.answer}\n")
    print(f"📚 TOP SOURCES:")
    for r in result.results[:3]:
        print(f"\n   📰 {r.title}")
        print(f"   🔗 {r.url}")
        print(f"   📝 {r.content[:300]}...")
    
    # Test 4: Institutional positioning
    print("\n\n" + "=" * 80)
    print("\n📌 QUERY 4: Hedge funds SPY positioning December 2025?")
    print("-" * 60)
    result = client.search(
        "hedge fund SPY positioning December 2025 13F filings institutional investors buying selling",
        search_depth="advanced",
        max_results=5
    )
    print(f"\n🤖 AI ANSWER:\n{result.answer}\n")
    print(f"📚 TOP SOURCES:")
    for r in result.results[:3]:
        print(f"\n   📰 {r.title}")
        print(f"   🔗 {r.url}")
        print(f"   📝 {r.content[:300]}...")

if __name__ == "__main__":
    main()

