"""Lightweight HTTP server exposed by the worker for on-demand queries."""

import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .config import WorkerConfig

_start_time = time.monotonic()


class AgentConfig(BaseModel):
    name: str = "agent"
    role: str = "general"
    model: Optional[str] = None
    task: str = ""


class LaunchRequest(BaseModel):
    name: str
    dimension_id: Optional[str] = None
    agents: list[AgentConfig] = []
    worktree_path: Optional[str] = None


class AddAgentRequest(BaseModel):
    name: str = "agent"
    role: str = "general"
    model: Optional[str] = None
    task: str = ""


def create_worker_app(config: WorkerConfig, manager=None) -> FastAPI:
    """Create the worker's local FastAPI app."""
    app = FastAPI(title="Jarvis Worker", version="0.1.0")

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/info")
    async def info():
        result = {
            "worker_id": config.worker_id,
            "worker_name": config.worker_name,
            "hostname": config.worker_name,
            "status": "online",
            "current_agents": 0,
            "max_concurrent_agents": config.capacity,
            "capabilities": config.capabilities,
            "uptime_seconds": round(time.monotonic() - _start_time, 1),
            "api_url": config.api_url,
        }
        if manager:
            status = manager.get_status()
            result["current_agents"] = status["running_agents"]
            result["active_universes"] = status["active_universes"]
            result["universes"] = status["universes"]
        return result

    @app.post("/launch")
    async def launch_universe(req: LaunchRequest):
        if not manager:
            raise HTTPException(status_code=503, detail="Manager not initialized")

        agents_config = [
            {
                "name": a.name,
                "role": a.role,
                "model": a.model,
                "task": a.task,
            }
            for a in req.agents
        ]

        universe_id = await manager.launch_universe(
            name=req.name,
            dimension_id=req.dimension_id,
            agents_config=agents_config,
            worktree_path=req.worktree_path,
        )

        return {"universe_id": universe_id, "status": "launched"}

    @app.get("/universes")
    async def list_universes():
        if not manager:
            return {"universes": []}
        return {"universes": manager.get_status()["universes"]}

    @app.get("/universes/{universe_id}")
    async def get_universe(universe_id: str):
        if not manager:
            raise HTTPException(status_code=503, detail="Manager not initialized")
        universe = manager.active_universes.get(universe_id)
        if not universe:
            raise HTTPException(status_code=404, detail="Universe not found")
        return universe.to_dict()

    @app.post("/universes/{universe_id}/agents")
    async def add_agent(universe_id: str, req: AddAgentRequest):
        if not manager:
            raise HTTPException(status_code=503, detail="Manager not initialized")

        agent_id = await manager.launch_agent(
            universe_id=universe_id,
            name=req.name,
            role=req.role,
            model=req.model,
            task_prompt=req.task,
        )

        return {"agent_id": agent_id, "status": "launched"}

    return app
