#!/bin/bash
# Stop the Alpha Intelligence Monitor

PROJECT_DIR="/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main"
PID_FILE="$PROJECT_DIR/monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ No PID file found - monitor not running?"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "🛑 Stopping monitor (PID: $PID)..."
    kill "$PID"
    sleep 2
    
    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "   Force killing..."
        kill -9 "$PID"
    fi
    
    rm "$PID_FILE"
    echo "✅ Monitor stopped"
else
    echo "⚠️  Process $PID not running, removing stale PID file"
    rm "$PID_FILE"
fi

