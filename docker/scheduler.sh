#!/bin/sh
# Scheduler script for Face Check-in application
# Runs auto_close_sessions and auto_open_sessions periodically
# Designed to run as a long-running process in Docker

set -e

SCHEDULE_INTERVAL=${SCHEDULE_INTERVAL:-60}

echo "=========================================="
echo "Face Check-in - Session Scheduler"
echo "=========================================="
echo "Schedule interval: ${SCHEDULE_INTERVAL} seconds"
echo "=========================================="

# Function to run session management commands
run_sessions_commands() {
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] Running session management commands..."
    
    echo "  Running auto_close_sessions..."
    python manage.py auto_close_sessions || echo "  Warning: auto_close_sessions had errors"
    
    echo "  Running auto_open_sessions..."
    python manage.py auto_open_sessions || echo "  Warning: auto_open_sessions had errors"
    
    echo "[${timestamp}] Session management commands completed"
}

# Initial run
run_sessions_commands

# Periodic execution
while true; do
    echo "Sleeping for ${SCHEDULE_INTERVAL} seconds..."
    sleep ${SCHEDULE_INTERVAL}
    run_sessions_commands
done
