#!/usr/bin/env python3
"""
🧪 TEST ALPHA INTELLIGENCE AGENT
Test the agent locally with various queries
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))
sys.path.insert(0, str(base_path / "discord_bot" / "agents"))

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


async def test_query(agent, query: str, expected_tools: list = None):
    """Test a single query"""
    print("\n" + "=" * 70)
    print(f"📝 QUERY: {query}")
    print("=" * 70)
    
    try:
        response = await agent.process(query)
        
        if response.success:
            print(f"✅ SUCCESS")
            print(f"🔧 Tools Used: {', '.join(response.tools_used)}")
            if expected_tools:
                matched = all(tool in response.tools_used for tool in expected_tools)
                if matched:
                    print(f"✅ Expected tools matched!")
                else:
                    print(f"⚠️  Expected {expected_tools}, got {response.tools_used}")
            print(f"\n📊 RESPONSE:")
            print("-" * 70)
            print(response.response)
            print("-" * 70)
        else:
            print(f"❌ FAILED: {response.error}")
            print(f"Response: {response.response}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_all():
    """Test all query types"""
    print("\n" + "🧠" * 35)
    print("ALPHA INTELLIGENCE AGENT - LOCAL TEST")
    print("🧠" * 35)
    
    # Initialize agent (direct import to avoid discord dependency)
    try:
        # Import directly from module file
        import alpha_agent
        agent = alpha_agent.AlphaIntelligenceAgent()
        print(f"\n✅ Agent initialized with {len(agent.tools)} tools")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test queries
    test_cases = [
        # DP Intelligence queries
        {
            "query": "What SPY levels should I watch?",
            "expected_tools": ["dp_intelligence"]
        },
        {
            "query": "Where is QQQ support?",
            "expected_tools": ["dp_intelligence"]
        },
        {
            "query": "Show me dark pool levels for SPY",
            "expected_tools": ["dp_intelligence"]
        },
        {
            "query": "What are the battlegrounds for SPY?",
            "expected_tools": ["dp_intelligence"]
        },
        
        # Narrative Brain queries
        {
            "query": "What's the story on SPY today?",
            "expected_tools": ["narrative_brain"]
        },
        {
            "query": "Why is QQQ moving?",
            "expected_tools": ["narrative_brain"]
        },
        {
            "query": "Explain what happened with SPY",
            "expected_tools": ["narrative_brain"]
        },
        
        # Signal Synthesis queries
        {
            "query": "Should I buy or sell SPY?",
            "expected_tools": ["signal_synthesis"]
        },
        {
            "query": "What's the overall market direction?",
            "expected_tools": ["signal_synthesis"]
        },
        {
            "query": "Any high-confidence setups?",
            "expected_tools": ["signal_synthesis"]
        },
        
        # Fed Watch queries
        {
            "query": "What's the rate cut probability?",
            "expected_tools": ["fed_watch"]
        },
        {
            "query": "What did Powell say?",
            "expected_tools": ["fed_watch"]
        },
        {
            "query": "Is the Fed hawkish or dovish?",
            "expected_tools": ["fed_watch"]
        },
        
        # Economic Calendar queries
        {
            "query": "Any economic data today?",
            "expected_tools": ["economic"]
        },
        {
            "query": "When is the next Fed meeting?",
            "expected_tools": ["economic"]
        },
        {
            "query": "What's the impact of CPI?",
            "expected_tools": ["economic"]
        },
        
        # Trade Calculator queries
        {
            "query": "Give me a long setup for SPY",
            "expected_tools": ["trade_calculator"]
        },
        {
            "query": "What's the risk/reward on this trade?",
            "expected_tools": ["trade_calculator"]
        },
        {
            "query": "Calculate entry stop target for QQQ long",
            "expected_tools": ["trade_calculator"]
        },
        
        # Multi-tool queries (should route to multiple)
        {
            "query": "What SPY levels and what's the market context?",
            "expected_tools": ["dp_intelligence", "narrative_brain"]
        },
        {
            "query": "Give me a trade setup considering Fed sentiment",
            "expected_tools": ["trade_calculator", "fed_watch"]
        },
        
        # Edge cases
        {
            "query": "Hello, how are you?",
            "expected_tools": None  # Should handle gracefully
        },
        {
            "query": "What's the weather?",
            "expected_tools": None  # Should handle gracefully
        },
    ]
    
    # Run tests
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n🔬 TEST {i}/{len(test_cases)}")
        await test_query(agent, test_case["query"], test_case.get("expected_tools"))
        
        # Simple pass/fail check
        try:
            response = await agent.process(test_case["query"])
            if response.success:
                passed += 1
            else:
                failed += 1
        except:
            failed += 1
    
    # Summary
    print("\n\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
    print("=" * 70)
    
    # Test individual tools
    print("\n\n🔧 TESTING INDIVIDUAL TOOLS")
    print("=" * 70)
    
    for tool_name, tool in agent.tools.items():
        print(f"\n📊 Testing {tool_name}...")
        try:
            # Test with default params
            result = tool.execute({"symbol": "SPY"})
            if result.success:
                print(f"  ✅ {tool_name} works")
                # Show formatted response
                formatted = tool.format_response(result)
                print(f"  📝 Sample output (first 200 chars):")
                print(f"     {formatted[:200]}...")
            else:
                print(f"  ⚠️  {tool_name} returned error: {result.error}")
        except Exception as e:
            print(f"  ❌ {tool_name} failed: {e}")


async def test_help():
    """Test help message"""
    print("\n\n📚 TESTING HELP MESSAGE")
    print("=" * 70)
    
    try:
        import alpha_agent
        agent = alpha_agent.AlphaIntelligenceAgent()
        help_msg = agent.get_help_message()
        print(help_msg)
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Main test runner"""
    try:
        # Test help
        await test_help()
        
        # Test all queries
        await test_all()
        
        print("\n\n✅ ALL TESTS COMPLETE!")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

