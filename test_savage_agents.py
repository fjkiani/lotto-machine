#!/usr/bin/env python3
"""
Test script for Savage LLM Agents

Tests the agent infrastructure without requiring full monitor setup.
"""

import os
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_agent_imports():
    """Test that all agent classes can be imported"""
    logger.info("Testing agent imports...")
    
    try:
        from backend.app.services.savage_agents import (
            SavageAgent, MarketAgent, SignalAgent, DarkPoolAgent, NarrativeBrainAgent
        )
        logger.info("✅ All agent classes imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Import error: {e}", exc_info=True)
        return False


def test_monitor_bridge_import():
    """Test MonitorBridge import"""
    logger.info("Testing MonitorBridge import...")
    
    try:
        from backend.app.integrations.unified_monitor_bridge import MonitorBridge
        logger.info("✅ MonitorBridge imported successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Import error: {e}", exc_info=True)
        return False


def test_market_agent():
    """Test MarketAgent with mock data"""
    logger.info("Testing MarketAgent...")
    
    try:
        from backend.app.services.savage_agents import MarketAgent
        
        agent = MarketAgent(redis_client=None)
        
        # Mock market data
        mock_data = {
            "symbol": "SPY",
            "price": 665.20,
            "change": 3.00,
            "change_percent": 0.45,
            "volume": 45000000,
            "high": 666.50,
            "low": 662.10,
            "open": 662.20,
            "regime": "UPTREND",
            "vix": 14.2
        }
        
        # Test prompt building
        prompt = agent._build_prompt(mock_data, context=None)
        logger.info(f"✅ MarketAgent prompt built ({len(prompt)} chars)")
        logger.debug(f"Prompt preview: {prompt[:200]}...")
        
        return True
    except Exception as e:
        logger.error(f"❌ MarketAgent test error: {e}", exc_info=True)
        return False


def test_signal_agent():
    """Test SignalAgent with mock data"""
    logger.info("Testing SignalAgent...")
    
    try:
        from backend.app.services.savage_agents import SignalAgent
        
        agent = SignalAgent(redis_client=None)
        
        # Mock signal data
        mock_data = {
            "signals": [
                {
                    "symbol": "SPY",
                    "action": "BUY",
                    "confidence": 0.85,
                    "signal_type": "BREAKOUT",
                    "entry_price": 665.20,
                    "target_price": 668.00,
                    "stop_price": 664.00,
                    "is_master_signal": True,
                    "rationale": "Breakout above DP resistance with volume confirmation"
                }
            ],
            "synthesis": None
        }
        
        # Test prompt building
        prompt = agent._build_prompt(mock_data, context=None)
        logger.info(f"✅ SignalAgent prompt built ({len(prompt)} chars)")
        logger.debug(f"Prompt preview: {prompt[:200]}...")
        
        return True
    except Exception as e:
        logger.error(f"❌ SignalAgent test error: {e}", exc_info=True)
        return False


def test_savage_llm_available():
    """Test if savage LLM function is available"""
    logger.info("Testing savage LLM availability...")
    
    try:
        from src.data.llm_api import query_llm_savage
        
        if query_llm_savage:
            logger.info("✅ query_llm_savage is available")
            return True
        else:
            logger.warning("⚠️ query_llm_savage is None")
            return False
    except ImportError as e:
        logger.warning(f"⚠️ query_llm_savage not available: {e}")
        return False


def main():
    """Run all tests"""
    logger.info("=" * 70)
    logger.info("🔥 SAVAGE LLM AGENTS - TEST SUITE")
    logger.info("=" * 70)
    
    tests = [
        ("Agent Imports", test_agent_imports),
        ("MonitorBridge Import", test_monitor_bridge_import),
        ("MarketAgent", test_market_agent),
        ("SignalAgent", test_signal_agent),
        ("Savage LLM Available", test_savage_llm_available),
    ]
    
    results = []
    for name, test_func in tests:
        logger.info(f"\n📋 Testing: {name}")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"❌ Test {name} crashed: {e}", exc_info=True)
            results.append((name, False))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.warning(f"⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

