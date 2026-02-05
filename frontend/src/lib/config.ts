// Centralized configuration for worktree port isolation
// VITE_API_PORT is set by start-worktree.sh based on .worktree-config
export const API_BASE = `http://localhost:${import.meta.env.VITE_API_PORT || '8000'}`;
