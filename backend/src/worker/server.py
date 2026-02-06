"""Lightweight HTTP server exposed by the worker for on-demand queries."""

import time

from fastapi import FastAPI

from .config import WorkerConfig

_start_time = time.monotonic()


def create_worker_app(config: WorkerConfig) -> FastAPI:
    """Create the worker's local FastAPI app."""
    app = FastAPI(title="Jarvis Worker", version="0.1.0")

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/info")
    async def info():
        return {
            "worker_id": config.worker_id,
            "worker_name": config.worker_name,
            "hostname": config.worker_name,
            "status": "online",
            "current_jobs": 0,
            "max_concurrent_jobs": config.capacity,
            "capabilities": config.capabilities,
            "uptime_seconds": round(time.monotonic() - _start_time, 1),
            "api_url": config.api_url,
        }

    return app
