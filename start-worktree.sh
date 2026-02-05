#!/bin/bash
#
# start-worktree.sh - Start frontend and backend with worktree-specific ports
#
# Usage: ./start-worktree.sh [--frontend-only | --backend-only]
#
# Reads port configuration from .worktree-config if present,
# otherwise uses defaults (3000 for frontend, 8000 for backend).

set -e

# Get the directory where this script is located (worktree root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/.worktree-config"

# Default ports (main worktree)
FRONTEND_PORT=${FRONTEND_PORT:-3000}
BACKEND_PORT=${BACKEND_PORT:-8000}

# Load config file if present
if [ -f "$CONFIG_FILE" ]; then
    echo "Loading configuration from $CONFIG_FILE"
    export $(grep -v '^#' "$CONFIG_FILE" | xargs)
fi

echo "=========================================="
echo "  Jarvis Worktree Startup"
echo "=========================================="
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo "=========================================="

# Parse arguments
FRONTEND_ONLY=false
BACKEND_ONLY=false

for arg in "$@"; do
    case $arg in
        --frontend-only)
            FRONTEND_ONLY=true
            shift
            ;;
        --backend-only)
            BACKEND_ONLY=true
            shift
            ;;
    esac
done

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend
if [ "$FRONTEND_ONLY" = false ]; then
    echo ""
    echo "Starting backend on port $BACKEND_PORT..."
    cd "$SCRIPT_DIR/backend"

    # Check for virtual environment
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        source venv/bin/activate
    fi

    python -m uvicorn src.main:app --host 0.0.0.0 --port $BACKEND_PORT &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"
fi

# Start frontend
if [ "$BACKEND_ONLY" = false ]; then
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
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for processes
wait
