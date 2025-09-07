#!/bin/bash

# Pi-Power-Butler Startup Script
# This script starts the bot in the background and keeps it running

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

# Set up logging
LOG_FILE="logs/bot_$(date +%Y%m%d).log"
PID_FILE="bot.pid"

# Function to start the bot
start_bot() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Bot is already running (PID: $(cat "$PID_FILE"))"
        return 1
    fi
    
    echo "Starting Pi-Power-Butler bot..."
    echo "Log file: $LOG_FILE"
    echo "PID file: $PID_FILE"
    
    # Start the bot in background with nohup
    nohup uv run src/main.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    # Wait a moment to check if it started successfully
    sleep 2
    
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Bot started successfully (PID: $(cat "$PID_FILE"))"
        echo "To view logs: tail -f $LOG_FILE"
        echo "To stop bot: ./start_bot.sh stop"
    else
        echo "Failed to start bot. Check logs: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to stop the bot
stop_bot() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Bot is not running (no PID file found)"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "Bot is not running (PID $PID not found)"
        rm -f "$PID_FILE"
        return 1
    fi
    
    echo "Stopping bot (PID: $PID)..."
    kill "$PID"
    
    # Wait for graceful shutdown
    for i in {1..10}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "Bot stopped successfully"
            rm -f "$PID_FILE"
            return 0
        fi
        sleep 1
    done
    
    # Force kill if still running
    echo "Force stopping bot..."
    kill -9 "$PID" 2>/dev/null
    rm -f "$PID_FILE"
    echo "Bot force stopped"
}

# Function to check bot status
status_bot() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Bot is not running (no PID file found)"
        return 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if kill -0 "$PID" 2>/dev/null; then
        echo "Bot is running (PID: $PID)"
        echo "Log file: $LOG_FILE"
        return 0
    else
        echo "Bot is not running (PID $PID not found)"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Function to restart the bot
restart_bot() {
    echo "Restarting bot..."
    stop_bot
    sleep 2
    start_bot
}

# Function to show logs
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "Showing recent logs from $LOG_FILE:"
        echo "----------------------------------------"
        tail -n 50 "$LOG_FILE"
        echo "----------------------------------------"
        echo "To follow logs in real-time: tail -f $LOG_FILE"
    else
        echo "No log file found: $LOG_FILE"
    fi
}

# Main script logic
case "${1:-start}" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the bot in background"
        echo "  stop    - Stop the running bot"
        echo "  restart - Restart the bot"
        echo "  status  - Check if bot is running"
        echo "  logs    - Show recent logs"
        exit 1
        ;;
esac
