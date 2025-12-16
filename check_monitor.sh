#!/bin/bash
# Check if Alpha Intelligence Monitor is running

PROJECT_DIR="/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main"
PID_FILE="$PROJECT_DIR/monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ Monitor NOT running (no PID file)"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ Monitor RUNNING (PID: $PID)"
    
    # Show recent log entries
    LOG_FILE="$PROJECT_DIR/logs/monitor/monitor_$(date +%Y%m%d).log"
    if [ -f "$LOG_FILE" ]; then
        echo ""
        echo "📋 Last 10 log entries:"
        tail -10 "$LOG_FILE"
    fi
    
    exit 0
else
    echo "❌ Monitor NOT running (stale PID: $PID)"
    rm "$PID_FILE"
    exit 1
fi

