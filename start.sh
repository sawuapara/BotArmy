#!/bin/bash

# LangGraph Orchestrator - Single Launch Script
# Starts both backend and frontend, opens browser

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Use Python 3.10+ (required for LangGraph)
PYTHON="/usr/local/bin/python3.10"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting LangGraph Orchestrator...${NC}"

# Check if backend venv exists, create if not
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo -e "${BLUE}Creating Python virtual environment with Python 3.10...${NC}"
    $PYTHON -m venv "$BACKEND_DIR/.venv"
fi

# Install backend dependencies if needed
if [ ! -f "$BACKEND_DIR/.venv/installed" ]; then
    echo -e "${BLUE}Installing backend dependencies...${NC}"
    "$BACKEND_DIR/.venv/bin/pip" install --upgrade pip -q
    "$BACKEND_DIR/.venv/bin/pip" install -e "$BACKEND_DIR" -q
    touch "$BACKEND_DIR/.venv/installed"
fi

# Check if frontend node_modules exists
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${BLUE}Installing frontend dependencies...${NC}"
    cd "$FRONTEND_DIR" && npm install
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${BLUE}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Load .env file
if [ -f "$BACKEND_DIR/.env" ]; then
    export $(cat "$BACKEND_DIR/.env" | grep -v '^#' | xargs)
fi

# Start backend using venv's uvicorn directly
echo -e "${GREEN}Starting backend on port 8000...${NC}"
"$BACKEND_DIR/.venv/bin/uvicorn" src.main:app --port 8000 --app-dir "$BACKEND_DIR" &
BACKEND_PID=$!

# Start frontend
echo -e "${GREEN}Starting frontend on port 3000...${NC}"
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

# Wait for servers to be ready
sleep 3

# Open browser
echo -e "${GREEN}Opening browser...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:3000
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xdg-open http://localhost:3000
fi

echo -e "${GREEN}✅ Orchestrator running!${NC}"
echo -e "   Frontend: http://localhost:3000"
echo -e "   Backend:  http://localhost:8000"
echo -e "   Press Ctrl+C to stop"

# Wait for both processes
wait
