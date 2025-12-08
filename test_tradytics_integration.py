#!/usr/bin/env python3
"""
🧪 TRADYTICS INTEGRATION TEST SUITE
Tests all components of the autonomous Tradytics analysis system
"""

import requests
import json
import time
from datetime import datetime

def test_health_endpoint():
    """Test 1: Health endpoint"""
    print("🧪 TEST 1: Health Endpoint")
    try:
        response = requests.get("https://lotto-machine.onrender.com/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_webhook_info():
    """Test 2: Webhook endpoint info"""
    print("\n🧪 TEST 2: Webhook Info Endpoint")
    try:
        response = requests.get("https://lotto-machine.onrender.com/tradytics-forward", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Webhook info retrieved: {data.get('endpoint', 'unknown')}")
            return True
        else:
            print(f"❌ Webhook info failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Webhook info error: {e}")
        return False

def test_forwarding_system():
    """Test 3: Forwarding system (simulated)"""
    print("\n🧪 TEST 3: Forwarding System Test")
    try:
        # Test payload that simulates a Tradytics alert
        test_payload = {
            "content": "TEST: NVDA $950 CALL SWEEP - $2.3M PREMIUM - Institutional buying detected",
            "username": "Bullseye",
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            "https://lotto-machine.onrender.com/tradytics-forward",
            json=test_payload,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Forwarding test passed: {data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Forwarding test failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Forwarding test error: {e}")
        return False

def test_direct_webhook():
    """Test 4: Direct webhook endpoint"""
    print("\n🧪 TEST 4: Direct Webhook Endpoint")
    try:
        test_payload = {
            "content": "TEST: SPY $500 BLOCK TRADE - $75M at $498.50",
            "author": {"username": "Darkpool"},
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            "https://lotto-machine.onrender.com/tradytics-webhook",
            json=test_payload,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Direct webhook test passed: {data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Direct webhook test failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Direct webhook test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 TRADYTICS INTEGRATION TEST SUITE")
    print("=" * 50)
    
    tests = [
        test_health_endpoint,
        test_webhook_info,
        test_forwarding_system,
        test_direct_webhook
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
        time.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Tradytics integration is ready!")
        return True
    else:
        print("⚠️ Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
