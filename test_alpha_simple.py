#!/usr/bin/env python3
"""
🧪 SIMPLE ALPHA AGENT TEST
Test tools directly without complex imports
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

print("🧪 TESTING ALPHA INTELLIGENCE AGENT TOOLS\n")
print("="*70)

# Test 1: DP Intelligence Tool
print("\n📊 TEST 1: DP Intelligence Tool")
print("-"*70)
try:
    # Manually import to avoid package issues
    import importlib.util
    
    # Load base
    base_path_file = base_path / "discord_bot" / "agents" / "tools" / "base.py"
    spec = importlib.util.spec_from_file_location("base_tool", base_path_file)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    
    # Patch sys.modules for relative imports
    sys.modules['discord_bot'] = type(sys)('discord_bot')
    sys.modules['discord_bot.agents'] = type(sys)('discord_bot.agents')
    sys.modules['discord_bot.agents.tools'] = type(sys)('discord_bot.agents.tools')
    sys.modules['discord_bot.agents.tools.base'] = base
    
    # Load DP tool
    dp_path = base_path / "discord_bot" / "agents" / "tools" / "dp_intelligence.py"
    dp_spec = importlib.util.spec_from_file_location("dp_tool", dp_path)
    dp_tool = importlib.util.module_from_spec(dp_spec)
    dp_spec.loader.exec_module(dp_tool)
    
    # Test it
    tool = dp_tool.DPIntelligenceTool()
    print(f"✅ Tool initialized: {tool.name}")
    print(f"   Description: {tool.description}")
    print(f"   Keywords: {tool.keywords[:3]}...")
    
    # Test routing
    test_queries = [
        "What SPY levels should I watch?",
        "Where is QQQ support?",
        "Show me dark pool levels",
    ]
    
    print(f"\n🔀 Testing routing:")
    for query in test_queries:
        matches = tool.matches_query(query)
        symbol = tool.extract_symbol(query)
        print(f"   Query: '{query}'")
        print(f"   → Matches: {matches}, Symbol: {symbol}")
    
    # Test execution (if API key available)
    if os.getenv('CHARTEXCHANGE_API_KEY'):
        print(f"\n🔧 Testing execution:")
        result = tool.execute({"symbol": "SPY", "action": "levels"})
        if result.success:
            print(f"   ✅ Execution successful")
            print(f"   📊 Levels found: {len(result.data.get('levels', []))}")
            if result.data.get('levels'):
                print(f"   📈 Sample level: ${result.data['levels'][0].get('price', 0):.2f}")
        else:
            print(f"   ⚠️  Execution returned error: {result.error}")
    else:
        print(f"\n⚠️  CHARTEXCHANGE_API_KEY not set - skipping execution test")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Trade Calculator Tool
print("\n\n💰 TEST 2: Trade Calculator Tool")
print("-"*70)
try:
    trade_path = base_path / "discord_bot" / "agents" / "tools" / "trade_calc.py"
    trade_spec = importlib.util.spec_from_file_location("trade_tool", trade_path)
    trade_tool = importlib.util.module_from_spec(trade_spec)
    trade_spec.loader.exec_module(trade_tool)
    
    tool = trade_tool.TradeCalculatorTool()
    print(f"✅ Tool initialized: {tool.name}")
    
    # Test routing
    test_queries = [
        "Give me a long setup for SPY",
        "Calculate entry stop target",
        "What's the risk/reward?",
    ]
    
    print(f"\n🔀 Testing routing:")
    for query in test_queries:
        matches = tool.matches_query(query)
        print(f"   Query: '{query}' → Matches: {matches}")
    
    # Test execution
    print(f"\n🔧 Testing execution:")
    result = tool.execute({"symbol": "SPY", "direction": "LONG"})
    if result.success:
        print(f"   ✅ Execution successful")
        data = result.data
        print(f"   📊 Entry: ${data.get('entry', 0):.2f}")
        print(f"   🛑 Stop: ${data.get('stop_loss', 0):.2f}")
        print(f"   🎯 Target: ${data.get('take_profit', 0):.2f}")
        print(f"   ⚖️  R/R: {data.get('risk_reward_ratio', 0):.1f}:1")
        
        # Show formatted response
        formatted = tool.format_response(result)
        print(f"\n   📝 Formatted Response:")
        print(f"   {formatted[:300]}...")
    else:
        print(f"   ❌ Error: {result.error}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Signal Synthesis Tool
print("\n\n📈 TEST 3: Signal Synthesis Tool")
print("-"*70)
try:
    signal_path = base_path / "discord_bot" / "agents" / "tools" / "signal_synthesis.py"
    signal_spec = importlib.util.spec_from_file_location("signal_tool", signal_path)
    signal_tool = importlib.util.module_from_spec(signal_spec)
    signal_spec.loader.exec_module(signal_tool)
    
    tool = signal_tool.SignalSynthesisTool()
    print(f"✅ Tool initialized: {tool.name}")
    
    # Test execution
    result = tool.execute({"action": "synthesis"})
    if result.success:
        print(f"   ✅ Execution successful")
        data = result.data
        print(f"   📊 Direction: {data.get('direction', 'N/A')}")
        print(f"   🎯 Recommendation: {data.get('recommendation', 'N/A')}")
        print(f"   📈 Confluence: {data.get('confluence_score', 0):.0f}%")
        
        formatted = tool.format_response(result)
        print(f"\n   📝 Formatted Response:")
        print(f"   {formatted}")
    else:
        print(f"   ⚠️  Error: {result.error}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Routing Summary
print("\n\n🔀 ROUTING SUMMARY")
print("="*70)

queries = [
    ("What SPY levels should I watch?", ["dp_intelligence"]),
    ("What's the story on QQQ?", ["narrative_brain"]),
    ("Should I buy or sell SPY?", ["signal_synthesis"]),
    ("What's the rate cut probability?", ["fed_watch"]),
    ("Any economic data today?", ["economic"]),
    ("Give me a long setup for SPY", ["trade_calculator"]),
]

print("\nQuery → Expected Tool(s):")
for query, expected in queries:
    print(f"\n📝 '{query}'")
    print(f"   Expected: {', '.join(expected)}")
    
    # Simple keyword matching
    query_lower = query.lower()
    matched = []
    
    if any(kw in query_lower for kw in ["level", "support", "resistance", "watch", "dark pool"]):
        matched.append("dp_intelligence")
    if any(kw in query_lower for kw in ["story", "why", "context", "explain"]):
        matched.append("narrative_brain")
    if any(kw in query_lower for kw in ["buy", "sell", "should", "direction", "synthesis"]):
        matched.append("signal_synthesis")
    if any(kw in query_lower for kw in ["fed", "rate", "powell", "cut"]):
        matched.append("fed_watch")
    if any(kw in query_lower for kw in ["economic", "cpi", "gdp", "calendar", "event"]):
        matched.append("economic")
    if any(kw in query_lower for kw in ["setup", "entry", "stop", "target", "trade"]):
        matched.append("trade_calculator")
    
    if matched:
        print(f"   ✅ Matched: {', '.join(matched)}")
        if set(matched) == set(expected):
            print(f"   ✅ Perfect match!")
        else:
            print(f"   ⚠️  Partial match (expected {expected})")
    else:
        print(f"   ❌ No match")

print("\n\n✅ TEST COMPLETE!")
print("="*70)



