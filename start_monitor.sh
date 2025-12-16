#!/bin/bash
# Auto-start script for Alpha Intelligence Monitor
# Runs during RTH (9:30 AM - 4:00 PM ET, Mon-Fri)

set -e

PROJECT_DIR="/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main"
LOG_DIR="$PROJECT_DIR/logs/monitor"
PID_FILE="$PROJECT_DIR/monitor.pid"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Monitor already running (PID: $OLD_PID)"
        exit 0
    else
        echo "Removing stale PID file"
        rm "$PID_FILE"
    fi
fi

# Activate environment and start monitor
cd "$PROJECT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start monitor in background
LOG_FILE="$LOG_DIR/monitor_$(date +%Y%m%d).log"
echo "Starting monitor at $(date)" >> "$LOG_FILE"

nohup python3 run_all_monitors.py >> "$LOG_FILE" 2>&1 &
MONITOR_PID=$!

# Save PID
echo "$MONITOR_PID" > "$PID_FILE"

echo "✅ Monitor started (PID: $MONITOR_PID)"
echo "   Log: $LOG_FILE"
echo "   To stop: kill $MONITOR_PID"

