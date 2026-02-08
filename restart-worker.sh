#!/bin/bash
#
# restart-worker.sh - Kill and restart the local Jarvis worker
#
# Usage: ./restart-worker.sh [--backend-too]
#
# By default restarts only the worker process. Pass --backend-too to also
# restart the backend (needed after DB migration changes).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/.worktree-config"
MAIN_REPO="/Users/samirawuapara/Jarvis"

BACKEND_PORT=${BACKEND_PORT:-8000}
WORKER_PORT=${WORKER_PORT:-8100}
RESTART_BACKEND=false

# Load config
if [ -f "$CONFIG_FILE" ]; then
    export $(grep -v '^#' "$CONFIG_FILE" | xargs)
fi

for arg in "$@"; do
    case $arg in
        --backend-too) RESTART_BACKEND=true ;;
    esac
done

# Find Python
if [ -d "$SCRIPT_DIR/backend/.venv" ]; then
    PYTHON="$SCRIPT_DIR/backend/.venv/bin/python"
elif [ -d "$MAIN_REPO/backend/.venv" ]; then
    PYTHON="$MAIN_REPO/backend/.venv/bin/python"
else
    PYTHON="python3"
fi

# Kill worker
echo "Stopping worker on port $WORKER_PORT..."
lsof -ti :$WORKER_PORT 2>/dev/null | xargs kill 2>/dev/null || true
sleep 1

# Kill backend if requested
if [ "$RESTART_BACKEND" = true ]; then
    echo "Stopping backend on port $BACKEND_PORT..."
    lsof -ti :$BACKEND_PORT 2>/dev/null | while read pid; do
        # Don't kill Chrome or other non-Python processes
        if ps -p "$pid" -o command= 2>/dev/null | grep -q python; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    sleep 2

    echo "Starting backend on port $BACKEND_PORT..."
    cd "$SCRIPT_DIR/backend"
    $PYTHON -m uvicorn src.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"

    # Wait for backend
    echo "Waiting for backend..."
    for i in $(seq 1 30); do
        if curl -s "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
            echo "Backend is ready"
            break
        fi
        sleep 1
    done
fi

# Start worker
echo "Starting worker on port $WORKER_PORT..."
cd "$SCRIPT_DIR/backend"
$PYTHON -m src.worker --api-url "http://localhost:$BACKEND_PORT" --port $WORKER_PORT &
WORKER_PID=$!

sleep 2

echo ""
echo "=========================================="
echo "  Worker restarted"
echo "  PID:     $WORKER_PID"
echo "  Port:    $WORKER_PORT"
echo "  Backend: http://localhost:$BACKEND_PORT"
echo "=========================================="
