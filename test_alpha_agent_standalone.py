#!/usr/bin/env python3
"""
🧪 TEST ALPHA INTELLIGENCE AGENT (Standalone)
Test the agent locally with various queries - standalone version
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project paths
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))

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


async def test_tool(tool, params: dict, tool_name: str):
    """Test a single tool"""
    print(f"\n{'='*70}")
    print(f"🔧 TESTING: {tool_name}")
    print(f"{'='*70}")
    print(f"📝 Params: {params}")
    
    try:
        result = tool.execute(params)
        
        if result.success:
            print(f"✅ SUCCESS")
            print(f"\n📊 DATA:")
            print(f"   {result.data}")
            
            # Try to format response
            if hasattr(tool, 'format_response'):
                formatted = tool.format_response(result)
                print(f"\n📝 FORMATTED RESPONSE:")
                print(f"{'-'*70}")
                print(formatted)
                print(f"{'-'*70}")
        else:
            print(f"❌ FAILED: {result.error}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_agent_routing():
    """Test agent routing logic"""
    print("\n" + "🧠" * 35)
    print("TESTING AGENT ROUTING")
    print("🧠" * 35)
    
    # Import tools directly using importlib to avoid package __init__
    import importlib.util
    
    # Load base tool first and add to sys.modules
    base_path_tool = base_path / "discord_bot" / "agents" / "tools" / "base.py"
    base_spec = importlib.util.spec_from_file_location("base", base_path_tool)
    base_module = importlib.util.module_from_spec(base_spec)
    base_spec.loader.exec_module(base_module)
    sys.modules['base'] = base_module
    
    # Create a fake tools package to satisfy relative imports
    class FakeToolsPackage:
        base = base_module
    sys.modules['discord_bot.agents.tools'] = FakeToolsPackage()
    sys.modules['discord_bot.agents.tools.base'] = base_module
    
    def load_tool_module(name):
        """Load a tool module directly"""
        tool_path = base_path / "discord_bot" / "agents" / "tools" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"tools.{name}", tool_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"discord_bot.agents.tools.{name}"] = module
        spec.loader.exec_module(module)
        return module
    
    # Load tools
    dp_module = load_tool_module("dp_intelligence")
    narrative_module = load_tool_module("narrative_brain")
    signal_module = load_tool_module("signal_synthesis")
    fed_module = load_tool_module("fed_watch")
    economic_module = load_tool_module("economic")
    trade_module = load_tool_module("trade_calc")
    
    DPIntelligenceTool = dp_module.DPIntelligenceTool
    NarrativeBrainTool = narrative_module.NarrativeBrainTool
    SignalSynthesisTool = signal_module.SignalSynthesisTool
    FedWatchTool = fed_module.FedWatchTool
    EconomicTool = economic_module.EconomicTool
    TradeCalculatorTool = trade_module.TradeCalculatorTool
    
    tools = {
        "dp_intelligence": DPIntelligenceTool(),
        "narrative_brain": NarrativeBrainTool(),
        "signal_synthesis": SignalSynthesisTool(),
        "fed_watch": FedWatchTool(),
        "economic": EconomicTool(),
        "trade_calculator": TradeCalculatorTool(),
    }
    
    print(f"\n✅ Loaded {len(tools)} tools")
    
    # Test each tool
    test_cases = [
        ("dp_intelligence", {"symbol": "SPY", "action": "levels"}),
        ("dp_intelligence", {"symbol": "QQQ", "action": "battlegrounds"}),
        ("narrative_brain", {"symbol": "SPY", "action": "context"}),
        ("narrative_brain", {"symbol": "SPY", "action": "confluence"}),
        ("signal_synthesis", {"action": "synthesis"}),
        ("fed_watch", {"action": "probabilities"}),
        ("economic", {"action": "today"}),
        ("trade_calculator", {"symbol": "SPY", "direction": "LONG"}),
    ]
    
    for tool_name, params in test_cases:
        if tool_name in tools:
            await test_tool(tools[tool_name], params, tool_name)
        else:
            print(f"⚠️  Tool {tool_name} not found")
    
    # Test routing logic
    print("\n\n" + "="*70)
    print("🔀 TESTING ROUTING LOGIC")
    print("="*70)
    
    queries = [
        "What SPY levels should I watch?",
        "What's the story on QQQ?",
        "Should I buy or sell SPY?",
        "What's the rate cut probability?",
        "Any economic data today?",
        "Give me a long setup for SPY",
    ]
    
    for query in queries:
        print(f"\n📝 Query: {query}")
        matched_tools = []
        
        for tool_name, tool in tools.items():
            if tool.matches_query(query):
                matched_tools.append(tool_name)
                print(f"   ✅ Matches: {tool_name}")
        
        if not matched_tools:
            print(f"   ⚠️  No tools matched")
        
        # Extract symbol
        symbols = ['SPY', 'QQQ', 'AAPL', 'MSFT', 'TSLA', 'NVDA']
        query_upper = query.upper()
        found_symbol = None
        for symbol in symbols:
            if symbol in query_upper:
                found_symbol = symbol
                break
        
        if found_symbol:
            print(f"   📊 Extracted symbol: {found_symbol}")
        else:
            print(f"   📊 Default symbol: SPY")


async def main():
    """Main test runner"""
    try:
        await test_agent_routing()
        print("\n\n✅ ALL TESTS COMPLETE!")
        
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

