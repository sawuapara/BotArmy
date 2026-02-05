# Jarvis Project Instructions

## Git Worktree Workflow (REQUIRED)

**All code changes MUST be made in a dedicated worktree, not in the main working directory.**

### Port Convention

Each worktree gets isolated frontend/backend ports:

| Worktree | Frontend | Backend |
|----------|----------|---------|
| main     | 3000     | 8000    |
| ticket-1 | 3001     | 8001    |
| ticket-2 | 3002     | 8002    |
| ...      | 30XX     | 80XX    |

### Quick Start

**Create a new worktree:**
```bash
cd /Users/samirawuapara/Jarvis
./create-worktree.sh <feature-name>
# Example: ./create-worktree.sh auth-refactor
```

**Start development servers:**
```bash
cd /Users/samirawuapara/Jarvis-worktrees/<feature-name>
./start-worktree.sh
```

The script automatically:
- Reads ports from `.worktree-config`
- Starts backend on the assigned port
- Starts frontend with `VITE_API_PORT` set correctly
- Handles graceful shutdown with Ctrl+C

### Worktree Location
- Main repo: `/Users/samirawuapara/Jarvis` (main branch - do not modify directly)
- Worktrees: `/Users/samirawuapara/Jarvis-worktrees/<feature-name>`

### Manual Worktree Creation (if needed)

1. Check for existing worktrees: `git worktree list`
2. Create a new branch and worktree:
   ```bash
   cd /Users/samirawuapara/Jarvis
   git branch feature/<name>
   git worktree add ../Jarvis-worktrees/<feature-name> feature/<name>
   ```
3. Create `.worktree-config` with your port assignments:
   ```
   FRONTEND_PORT=30XX
   BACKEND_PORT=80XX
   ```
4. Run `npm install` in the frontend directory
5. All file edits should target `/Users/samirawuapara/Jarvis-worktrees/<feature-name>/...`

### Running Dev Servers Manually

```bash
cd /Users/samirawuapara/Jarvis-worktrees/<feature-name>

# Frontend (in one terminal)
cd frontend && VITE_API_PORT=80XX npm run dev -- --port 30XX

# Backend (in another terminal)
cd backend && source .venv/bin/activate && uvicorn src.main:app --port 80XX
```

### After Feature Complete

1. Commit changes in the worktree
2. Create PR or merge to main
3. Clean up: `git worktree remove ../Jarvis-worktrees/<feature-name>`

## Project Structure

- `/frontend` - React + Vite + TypeScript frontend
- `/backend` - Python FastAPI backend
- `/infrastructure` - Deployment/infra configs

## Current Active Worktrees

| Worktree | Branch | Ports | Purpose |
|----------|--------|-------|---------|
| `/Users/samirawuapara/Jarvis-worktrees/feature-app-auth` | `feature/app-auth` | 3001/8001 | App-wide authentication |

## Configuration Files

- `.worktree-config` - Per-worktree port configuration (gitignored)
- `start-worktree.sh` - Startup script for both servers
- `create-worktree.sh` - Creates new worktree with auto-assigned ports
