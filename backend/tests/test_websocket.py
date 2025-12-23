"""
🧪 WebSocket Test Client

Simple test script to verify WebSocket endpoints are working.
"""

import asyncio
import json
import websockets
from datetime import datetime


async def test_unified_stream():
    """Test unified WebSocket stream"""
    print("🔌 Connecting to /ws/unified...")
    
    try:
        async with websockets.connect("ws://localhost:8000/api/v1/ws/unified") as websocket:
            # Wait for welcome message
            welcome = await websocket.recv()
            print(f"✅ Connected! Welcome: {json.loads(welcome)}")
            
            # Send ping
            await websocket.send(json.dumps({"type": "ping"}))
            pong = await websocket.recv()
            print(f"✅ Pong received: {json.loads(pong)}")
            
            # Wait for a few messages (if any)
            print("⏳ Waiting for messages (10 seconds)...")
            try:
                for i in range(10):
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    print(f"📨 Message received: {data.get('type', 'unknown')} - {data.get('alert_type', 'N/A')}")
            except asyncio.TimeoutError:
                print("⏱️ No messages received (this is normal if no alerts are being sent)")
            
            print("✅ Test complete!")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_market_stream(symbol="SPY"):
    """Test market-specific WebSocket stream"""
    print(f"🔌 Connecting to /ws/market/{symbol}...")
    
    try:
        async with websockets.connect(f"ws://localhost:8000/api/v1/ws/market/{symbol}") as websocket:
            welcome = await websocket.recv()
            print(f"✅ Connected! Welcome: {json.loads(welcome)}")
            
            await websocket.send(json.dumps({"type": "ping"}))
            pong = await websocket.recv()
            print(f"✅ Pong received: {json.loads(pong)}")
            
            print("⏳ Waiting for messages (10 seconds)...")
            try:
                for i in range(10):
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    print(f"📨 Message received: {data.get('type', 'unknown')}")
            except asyncio.TimeoutError:
                print("⏱️ No messages received")
            
            print("✅ Test complete!")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_signals_stream():
    """Test signals WebSocket stream"""
    print("🔌 Connecting to /ws/signals...")
    
    try:
        async with websockets.connect("ws://localhost:8000/api/v1/ws/signals") as websocket:
            welcome = await websocket.recv()
            print(f"✅ Connected! Welcome: {json.loads(welcome)}")
            
            await websocket.send(json.dumps({"type": "ping"}))
            pong = await websocket.recv()
            print(f"✅ Pong received: {json.loads(pong)}")
            
            print("⏳ Waiting for signals (10 seconds)...")
            try:
                for i in range(10):
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    print(f"📨 Signal received: {data.get('type', 'unknown')}")
            except asyncio.TimeoutError:
                print("⏱️ No signals received")
            
            print("✅ Test complete!")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_narrative_stream():
    """Test narrative WebSocket stream"""
    print("🔌 Connecting to /ws/narrative...")
    
    try:
        async with websockets.connect("ws://localhost:8000/api/v1/ws/narrative") as websocket:
            welcome = await websocket.recv()
            print(f"✅ Connected! Welcome: {json.loads(welcome)}")
            
            await websocket.send(json.dumps({"type": "ping"}))
            pong = await websocket.recv()
            print(f"✅ Pong received: {json.loads(pong)}")
            
            print("⏳ Waiting for narrative updates (10 seconds)...")
            try:
                for i in range(10):
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    print(f"📨 Narrative received: {data.get('type', 'unknown')}")
            except asyncio.TimeoutError:
                print("⏱️ No narrative updates received")
            
            print("✅ Test complete!")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_stats():
    """Test WebSocket stats endpoint"""
    import aiohttp
    
    print("📊 Fetching WebSocket stats...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/api/v1/ws/stats") as response:
                stats = await response.json()
                print(f"✅ Stats: {json.dumps(stats, indent=2)}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all tests"""
    print("🧪 WebSocket Test Suite\n")
    print("=" * 50)
    
    # Test stats first
    await test_stats()
    print()
    
    # Test unified stream
    await test_unified_stream()
    print()
    
    # Test market stream
    await test_market_stream("SPY")
    print()
    
    # Test signals stream
    await test_signals_stream()
    print()
    
    # Test narrative stream
    await test_narrative_stream()
    print()
    
    print("=" * 50)
    print("✅ All tests complete!")


if __name__ == "__main__":
    print("⚠️  Make sure the backend is running on http://localhost:8000")
    print("⚠️  Run: python3 run_backend_api.py\n")
    
    asyncio.run(main())


