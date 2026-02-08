#!/bin/bash
#
# start-worktree.sh - Start frontend, backend, and worker with worktree-specific ports
#
# Usage: ./start-worktree.sh [options]
#
# Options:
#   --frontend-only   Only start the frontend
#   --backend-only    Only start the backend
#   --worker-only     Only start the worker
#   --no-worker       Start frontend + backend but skip the worker
#
# Reads port configuration from .worktree-config if present,
# otherwise uses defaults (3000 for frontend, 8000 for backend).
# Worker runs on a fixed port (8100) since there's typically one per machine.

set -e

# Get the directory where this script is located (worktree root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/.worktree-config"
MAIN_REPO="/Users/samirawuapara/Jarvis"

# Default ports (main worktree)
FRONTEND_PORT=${FRONTEND_PORT:-3000}
BACKEND_PORT=${BACKEND_PORT:-8000}
WORKER_PORT=${WORKER_PORT:-8100}

# Load config file if present
if [ -f "$CONFIG_FILE" ]; then
    echo "Loading configuration from $CONFIG_FILE"
    export $(grep -v '^#' "$CONFIG_FILE" | xargs)
fi

# Find Python with the right venv
# Worktrees share the main repo's venv
find_python() {
    if [ -d "$SCRIPT_DIR/backend/.venv" ]; then
        echo "$SCRIPT_DIR/backend/.venv/bin/python"
    elif [ -d "$MAIN_REPO/backend/.venv" ]; then
        echo "$MAIN_REPO/backend/.venv/bin/python"
    else
        echo "python3"
    fi
}

PYTHON=$(find_python)

echo "=========================================="
echo "  Jarvis Worktree Startup"
echo "=========================================="
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "  Worker:   http://localhost:$WORKER_PORT"
echo "  Python:   $PYTHON"
echo "=========================================="

# Parse arguments
START_FRONTEND=true
START_BACKEND=true
START_WORKER=true

for arg in "$@"; do
    case $arg in
        --frontend-only)
            START_BACKEND=false
            START_WORKER=false
            ;;
        --backend-only)
            START_FRONTEND=false
            START_WORKER=false
            ;;
        --worker-only)
            START_FRONTEND=false
            START_BACKEND=false
            ;;
        --no-worker)
            START_WORKER=false
            ;;
    esac
done

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$WORKER_PID" ] && kill $WORKER_PID 2>/dev/null || true
    [ -n "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null || true
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
if [ "$START_BACKEND" = true ]; then
    echo ""
    echo "Starting backend on port $BACKEND_PORT..."
    cd "$SCRIPT_DIR/backend"
    $PYTHON -m uvicorn src.main:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"

    # Wait for backend to be ready before starting worker
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
if [ "$START_WORKER" = true ]; then
    echo ""
    echo "Starting worker on port $WORKER_PORT..."
    cd "$SCRIPT_DIR/backend"
    $PYTHON -m src.worker --api-url "http://localhost:$BACKEND_PORT" --port $WORKER_PORT &
    WORKER_PID=$!
    echo "Worker PID: $WORKER_PID"
fi

# Start frontend
if [ "$START_FRONTEND" = true ]; then
    echo ""
    echo "Starting frontend on port $FRONTEND_PORT..."
    cd "$SCRIPT_DIR/frontend"

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "Installing frontend dependencies..."
        npm install
    fi

    VITE_API_PORT=$BACKEND_PORT npm run dev -- --port $FRONTEND_PORT &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID"
fi

echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for processes
wait
