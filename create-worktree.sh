#!/bin/bash
#
# create-worktree.sh - Create a new git worktree with auto-assigned ports
#
# Usage: ./create-worktree.sh <feature-name> [branch-name]
#
# This script:
# 1. Creates a git worktree in ../Jarvis-worktrees/<feature-name>
# 2. Assigns the next available port pair (30XX/80XX)
# 3. Creates .worktree-config with the port assignments
# 4. Runs npm install in the frontend
#
# Port Convention:
#   main:      3000/8000
#   ticket-1:  3001/8001
#   ticket-2:  3002/8002
#   ...etc

set -e

# Configuration
MAIN_REPO="/Users/samirawuapara/Jarvis"
WORKTREES_DIR="/Users/samirawuapara/Jarvis-worktrees"
BASE_FRONTEND_PORT=3000
BASE_BACKEND_PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check arguments
if [ -z "$1" ]; then
    echo -e "${RED}Error: Feature name required${NC}"
    echo ""
    echo "Usage: $0 <feature-name> [branch-name]"
    echo ""
    echo "Examples:"
    echo "  $0 auth-refactor"
    echo "  $0 auth-refactor feature/auth-refactor"
    exit 1
fi

FEATURE_NAME="$1"
BRANCH_NAME="${2:-feature/$FEATURE_NAME}"
WORKTREE_PATH="$WORKTREES_DIR/$FEATURE_NAME"

echo ""
echo -e "${GREEN}Creating Jarvis Worktree${NC}"
echo "=========================================="
echo "  Feature:   $FEATURE_NAME"
echo "  Branch:    $BRANCH_NAME"
echo "  Path:      $WORKTREE_PATH"
echo "=========================================="

# Check if worktree already exists
if [ -d "$WORKTREE_PATH" ]; then
    echo -e "${RED}Error: Worktree already exists at $WORKTREE_PATH${NC}"
    exit 1
fi

# Create worktrees directory if needed
mkdir -p "$WORKTREES_DIR"

# Find the next available port
echo ""
echo "Finding next available port pair..."

find_next_port() {
    local port=$1

    # Check all existing .worktree-config files for used ports
    local used_ports=""
    if [ -d "$WORKTREES_DIR" ]; then
        for config in "$WORKTREES_DIR"/*/.worktree-config 2>/dev/null; do
            if [ -f "$config" ]; then
                used_ports="$used_ports $(grep FRONTEND_PORT "$config" | cut -d'=' -f2)"
            fi
        done
    fi

    # Start from base+1 (main uses base)
    local next_port=$((port + 1))

    while true; do
        if ! echo "$used_ports" | grep -q "$next_port"; then
            # Also check if port is in use by a running process
            if ! lsof -i :$next_port > /dev/null 2>&1; then
                echo $next_port
                return
            fi
        fi
        next_port=$((next_port + 1))

        # Safety limit
        if [ $next_port -gt $((port + 100)) ]; then
            echo -e "${RED}Error: No available ports in range${NC}" >&2
            exit 1
        fi
    done
}

FRONTEND_PORT=$(find_next_port $BASE_FRONTEND_PORT)
BACKEND_PORT=$((FRONTEND_PORT - BASE_FRONTEND_PORT + BASE_BACKEND_PORT))

echo "  Frontend port: $FRONTEND_PORT"
echo "  Backend port:  $BACKEND_PORT"

# Create the branch if it doesn't exist
echo ""
echo "Setting up git branch..."
cd "$MAIN_REPO"

if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    echo "  Branch '$BRANCH_NAME' already exists"
else
    echo "  Creating branch '$BRANCH_NAME'"
    git branch "$BRANCH_NAME"
fi

# Create the worktree
echo ""
echo "Creating git worktree..."
git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"

# Create the config file
echo ""
echo "Creating .worktree-config..."
cat > "$WORKTREE_PATH/.worktree-config" << EOF
# Worktree port configuration
# Created: $(date)
# Feature: $FEATURE_NAME
FRONTEND_PORT=$FRONTEND_PORT
BACKEND_PORT=$BACKEND_PORT
EOF

echo "  Config file created"

# Install frontend dependencies
echo ""
echo "Installing frontend dependencies..."
cd "$WORKTREE_PATH/frontend"
npm install

# Print summary
echo ""
echo -e "${GREEN}=========================================="
echo "  Worktree created successfully!"
echo "==========================================${NC}"
echo ""
echo "  Location: $WORKTREE_PATH"
echo "  Branch:   $BRANCH_NAME"
echo ""
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Backend:  http://localhost:$BACKEND_PORT"
echo ""
echo "To start development servers:"
echo "  cd $WORKTREE_PATH"
echo "  ./start-worktree.sh"
echo ""
echo "To remove this worktree when done:"
echo "  git worktree remove $WORKTREE_PATH"
echo ""
