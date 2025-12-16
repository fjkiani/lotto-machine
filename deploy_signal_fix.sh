#!/bin/bash

echo "==============================================================================="
echo "🚀 DEPLOYING SMART SIGNAL DIRECTION FIX"
echo "==============================================================================="

# Kill any existing processes
echo "📋 Checking for existing processes..."
EXISTING=$(ps aux | grep -E "python.*run_all_monitors" | grep -v grep | awk '{print $2}')
if [ ! -z "$EXISTING" ]; then
    echo "   ⚠️  Found existing process(es): $EXISTING"
    echo "   🛑 Stopping existing processes..."
    kill $EXISTING 2>/dev/null
    sleep 2
    # Force kill if still running
    kill -9 $EXISTING 2>/dev/null 2>/dev/null
    echo "   ✅ Processes stopped"
else
    echo "   ✅ No existing processes found"
fi

# Verify code is present
echo ""
echo "📋 Verifying code changes..."
if grep -q "STRONG_UPTREND\|STRONG_DOWNTREND" run_all_monitors.py; then
    echo "   ✅ Smart regime detection code found"
else
    echo "   ❌ ERROR: Smart regime detection code NOT found!"
    exit 1
fi

if grep -q "_detect_market_regime" run_all_monitors.py; then
    echo "   ✅ Regime detection method found"
else
    echo "   ❌ ERROR: Regime detection method NOT found!"
    exit 1
fi

# Start the monitoring system
echo ""
echo "🚀 Starting monitoring system with smart signal filters..."
echo "   → Regime-aware filtering: ENABLED"
echo "   → Synthesis alignment: ENABLED"
echo "   → Level-direction cooldown: ENABLED"
echo ""

# Start in background and log to file
nohup python3 run_all_monitors.py > logs/monitoring_$(date +%Y%m%d_%H%M%S).log 2>&1 &
PID=$!

echo "   ✅ Monitoring system started (PID: $PID)"
echo "   📄 Log file: logs/monitoring_$(date +%Y%m%d_%H%M%S).log"
echo ""
echo "==============================================================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "==============================================================================="
echo ""
echo "📊 Monitor the system:"
echo "   tail -f logs/monitoring_*.log"
echo ""
echo "🔍 Check for filter messages:"
echo "   grep 'REGIME FILTER\|SYNTHESIS CONFLICT\|FLIP PREVENTION' logs/monitoring_*.log"
echo ""
echo "📈 Check regime detection:"
echo "   grep 'REGIME:' logs/monitoring_*.log"
echo ""

