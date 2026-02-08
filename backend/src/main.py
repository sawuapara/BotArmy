"""
FastAPI Backend for LangGraph Orchestrator

Provides REST API and WebSocket endpoints for the React frontend.
"""
import asyncio
import uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .orchestrator.graph import create_orchestrator
from .orchestrator.state import OrchestratorState, TicketInfo
from .api.revenue import router as revenue_router
from .api.vault import router as vault_router
from .api.organization import router as organization_router
from .api.projects import router as projects_router
from .api.tasks import router as tasks_router
from .api.database import router as database_router
from .api.status import router as status_router
from .api.chat import router as chat_router
from .api.workers import router as workers_router
from .api.conversations import router as conversations_router
from .db.conversations import create_conversation, insert_turn, complete_conversation


# Store active sessions and their states
sessions: dict[str, dict] = {}
websocket_connections: dict[str, list[WebSocket]] = {}

# Universe streaming: worker connections and dashboard clients
worker_ws_connections: dict[str, WebSocket] = {}  # worker_id -> WS
dashboard_ws_clients: list[WebSocket] = []
universe_cache: dict[str, dict] = {}  # universe_id -> latest snapshot from worker events


async def _check_stale_workers():
    """Background task: detect and remove dead workers."""
    import httpx
    from .db import get_db_pool
    from .logging import get_logger
    logger = get_logger("workers")

    while True:
        await asyncio.sleep(30)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                # Find workers with no heartbeat in 90+ seconds
                stale_rows = await conn.fetch("""
                    SELECT id, hostname, worker_name, worker_address
                    FROM orchestration.workers
                    WHERE last_heartbeat_at < NOW() - INTERVAL '90 seconds'
                      AND status != 'offline'
                """)

                for row in stale_rows:
                    worker_id = row["id"]
                    address = row["worker_address"]
                    name = row["worker_name"] or row["hostname"]

                    # Try to ping the worker's health endpoint
                    if address:
                        try:
                            async with httpx.AsyncClient() as client:
                                resp = await client.get(f"{address}/health", timeout=5.0)
                                if resp.status_code == 200:
                                    logger.warning(f"Stale worker {name} ({worker_id}) responded to ping - updating heartbeat")
                                    await conn.execute(
                                        "UPDATE orchestration.workers SET last_heartbeat_at = NOW() WHERE id = $1",
                                        worker_id,
                                    )
                                    continue
                        except Exception:
                            pass  # Ping failed - worker is dead

                    # Worker is unreachable - set it offline
                    await conn.execute(
                        "UPDATE orchestration.workers SET status = 'offline' WHERE id = $1",
                        worker_id,
                    )
                    logger.info(f"Set dead worker offline: {name} ({worker_id})")

        except Exception as e:
            # Don't crash the background task on transient errors
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("Starting LangGraph Orchestrator...")
    stale_worker_task = asyncio.create_task(_check_stale_workers())
    yield
    stale_worker_task.cancel()
    print("Shutting down...")


app = FastAPI(
    title="LangGraph Orchestrator",
    description="Session orchestrator for MecanoLabs/MecanoConsulting work prioritization",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for React frontend (allow all 3000-range ports for local dev)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):30[0-9]{2}",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(revenue_router)
app.include_router(vault_router)
app.include_router(organization_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(database_router)
app.include_router(status_router)
app.include_router(chat_router)
app.include_router(workers_router, prefix="/api")
app.include_router(conversations_router)


# ---------- Pydantic Models ----------

class SessionCreate(BaseModel):
    """Request to create a new session."""
    pass


class SessionResponse(BaseModel):
    """Response with session info."""
    session_id: str
    status: str
    current_node: Optional[str] = None
    current_ticket: Optional[dict] = None
    thought_log: list[str] = []


class TicketQueueResponse(BaseModel):
    """Response with ticket queue."""
    tickets: list[dict]
    total: int


class ReorderRequest(BaseModel):
    """Request to reorder queue."""
    ticket_keys: list[str]  # New order of ticket keys


class LaunchUniverseRequest(BaseModel):
    """Request to dispatch a universe launch to a worker."""
    prompt: str
    name: str = ""
    agent_name: str = "assistant"
    agent_role: str = "task-creator"
    model: str | None = None
    context: dict | None = None  # project/namespace from frontend


# ---------- REST Endpoints ----------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/universes/launch")
async def dispatch_universe(request: LaunchUniverseRequest):
    """Dispatch a universe launch to an available worker."""
    import httpx
    from .db import get_db_pool

    # 1. Find an online worker with capacity
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        worker = await conn.fetchrow(
            "SELECT id, worker_address, worker_name, hostname FROM orchestration.workers "
            "WHERE status = 'online' AND current_agents < max_concurrent_agents "
            "ORDER BY current_agents ASC LIMIT 1"
        )
    if not worker:
        raise HTTPException(503, "No workers available")

    # 2. Build task prompt with context injection
    system_context = ""
    if request.context:
        if request.context.get("projectName"):
            system_context += f"\nProject: {request.context['projectName']}"
        if request.context.get("namespaceName"):
            system_context += f"\nNamespace: {request.context['namespaceName']}"

    task_prompt = request.prompt
    if system_context:
        task_prompt = f"{request.prompt}\n\nContext:{system_context}"

    # 3. POST to worker /launch
    name = request.name or f"task-{uuid.uuid4().hex[:8]}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(f"{worker['worker_address']}/launch", json={
            "name": name,
            "agents": [{
                "name": request.agent_name,
                "role": request.agent_role,
                "model": request.model,
                "task": task_prompt,
            }],
        })
    if res.status_code != 200:
        raise HTTPException(502, f"Worker returned {res.status_code}: {res.text}")

    data = res.json()
    return {
        "universe_id": data["universe_id"],
        "worker_id": str(worker["id"]),
        "worker_address": worker["worker_address"],
        "worker_name": worker["worker_name"] or worker["hostname"],
        "name": name,
    }


@app.post("/sessions", response_model=SessionResponse)
async def create_session():
    """
    Create a new orchestrator session.
    """
    session_id = str(uuid.uuid4())

    # Initialize state
    initial_state: OrchestratorState = {
        "session_id": session_id,
        "started_at": datetime.now().isoformat(),
        "revenue_status": None,
        "work_type": None,
        "ticket_queue": [],
        "current_ticket": None,
        "current_node": "start",
        "thought_log": [f"Session {session_id[:8]} started"],
        "active_worker": None,
        "worker_state": None,
        "is_paused": False,
        "paused_tickets": [],
        "error": None,
    }

    sessions[session_id] = {
        "state": initial_state,
        "status": "created",
        "created_at": datetime.now().isoformat(),
    }

    return SessionResponse(
        session_id=session_id,
        status="created",
        current_node="start",
        thought_log=initial_state["thought_log"],
    )


@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session status and state."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    state = session["state"]

    return SessionResponse(
        session_id=session_id,
        status=session["status"],
        current_node=state.get("current_node"),
        current_ticket=state.get("current_ticket"),
        thought_log=state.get("thought_log", []),
    )


@app.post("/sessions/{session_id}/start")
async def start_session(session_id: str):
    """
    Start running the orchestrator for a session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    if session["status"] == "running":
        raise HTTPException(status_code=400, detail="Session already running")

    session["status"] = "running"

    # Create orchestrator graph
    orchestrator = await create_orchestrator()

    # Run in background task
    asyncio.create_task(run_orchestrator(session_id, orchestrator))

    return {"message": "Session started", "session_id": session_id}


@app.post("/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause a running session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    session["state"]["is_paused"] = True
    session["status"] = "paused"

    # Notify websocket clients
    await broadcast_to_session(session_id, {
        "type": "session_paused",
        "session_id": session_id,
    })

    return {"message": "Session paused", "session_id": session_id}


@app.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a paused session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    session["state"]["is_paused"] = False
    session["status"] = "running"

    # TODO: Resume from checkpoint

    return {"message": "Session resumed", "session_id": session_id}


@app.get("/sessions/{session_id}/queue", response_model=TicketQueueResponse)
async def get_ticket_queue(session_id: str):
    """Get the current ticket queue for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    queue = sessions[session_id]["state"].get("ticket_queue", [])

    return TicketQueueResponse(tickets=queue, total=len(queue))


@app.put("/sessions/{session_id}/queue/reorder")
async def reorder_queue(session_id: str, request: ReorderRequest):
    """
    Reorder the ticket queue (drag-and-drop from UI).
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = sessions[session_id]["state"]
    current_queue = state.get("ticket_queue", [])

    # Build new queue based on provided order
    ticket_map = {t["key"]: t for t in current_queue}
    new_queue = []

    for key in request.ticket_keys:
        if key in ticket_map:
            new_queue.append(ticket_map[key])

    # Add any tickets not in the reorder request at the end
    for ticket in current_queue:
        if ticket["key"] not in request.ticket_keys:
            new_queue.append(ticket)

    state["ticket_queue"] = new_queue
    state["thought_log"].append(f"Queue manually reordered by user")

    # Notify websocket clients
    await broadcast_to_session(session_id, {
        "type": "queue_updated",
        "queue": new_queue,
    })

    return {"message": "Queue reordered", "new_order": [t["key"] for t in new_queue]}


@app.get("/sessions/{session_id}/thoughts")
async def get_thought_log(session_id: str):
    """Get the chain of thought log for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"thoughts": sessions[session_id]["state"].get("thought_log", [])}


# ---------- Universe Streaming ----------

async def broadcast_to_dashboard(message: dict):
    """Broadcast a universe event to all connected dashboard clients."""
    disconnected = []
    for ws in dashboard_ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        dashboard_ws_clients.remove(ws)


async def broadcast_to_session(session_id: str, message: dict):
    """Broadcast a message to all WebSocket clients for a session."""
    if session_id in websocket_connections:
        for ws in websocket_connections[session_id]:
            try:
                await ws.send_json(message)
            except:
                pass  # Client disconnected


# IMPORTANT: Specific WebSocket routes must be declared BEFORE the catch-all
# /ws/{session_id} route, otherwise FastAPI matches "universes" as a session_id.

@app.websocket("/ws/universes")
async def universe_dashboard_stream(websocket: WebSocket):
    """Stream universe events to dashboard frontend clients."""
    await websocket.accept()
    dashboard_ws_clients.append(websocket)

    try:
        # Send current snapshot on connect
        await websocket.send_json({
            "type": "snapshot",
            "universes": list(universe_cache.values()),
        })

        # Keep alive — client doesn't need to send messages
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        if websocket in dashboard_ws_clients:
            dashboard_ws_clients.remove(websocket)
    except Exception:
        if websocket in dashboard_ws_clients:
            dashboard_ws_clients.remove(websocket)


@app.websocket("/ws/worker/{worker_id}")
async def worker_event_stream(websocket: WebSocket, worker_id: str):
    """Receive events from a worker and relay to dashboard clients."""
    await websocket.accept()
    worker_ws_connections[worker_id] = websocket

    try:
        while True:
            data = await websocket.receive_json()

            # Update universe cache from events
            event_type = data.get("type", "")
            universe_id = data.get("universe_id")

            if event_type == "universe_created" and universe_id:
                universe_cache[universe_id] = {
                    "id": universe_id,
                    "name": data.get("data", {}).get("name", ""),
                    "dimension_id": data.get("data", {}).get("dimension_id"),
                    "status": "active",
                    "worker_id": worker_id,
                    "agents": [],
                    "state_version": 0,
                    "created_at": data.get("timestamp", ""),
                }
            elif event_type == "universe_stopped" and universe_id:
                if universe_id in universe_cache:
                    universe_cache[universe_id]["status"] = "terminated"
            elif event_type == "agent_started" and universe_id:
                if universe_id in universe_cache:
                    agent_data = {
                        "id": data.get("agent_id", ""),
                        "name": data.get("agent_name", ""),
                        "role": data.get("data", {}).get("role", ""),
                        "model": data.get("data", {}).get("model"),
                        "status": "running",
                        "current_turn": 0,
                    }
                    # Replace existing or add new
                    agents = universe_cache[universe_id]["agents"]
                    existing = [a for a in agents if a["id"] == agent_data["id"]]
                    if existing:
                        existing[0].update(agent_data)
                    else:
                        agents.append(agent_data)
            elif event_type in ("agent_done", "agent_error") and universe_id:
                if universe_id in universe_cache:
                    agent_id = data.get("agent_id", "")
                    for agent in universe_cache[universe_id]["agents"]:
                        if agent["id"] == agent_id:
                            agent["status"] = "completed" if event_type == "agent_done" else "error"
                            if event_type == "agent_error":
                                agent["error"] = data.get("data", {}).get("error", "")
            elif event_type == "turn_start" and universe_id:
                if universe_id in universe_cache:
                    agent_id = data.get("agent_id", "")
                    for agent in universe_cache[universe_id]["agents"]:
                        if agent["id"] == agent_id:
                            agent["current_turn"] = data.get("data", {}).get("turn", 0)
            elif event_type == "turn_end" and universe_id:
                if universe_id in universe_cache:
                    universe_cache[universe_id]["state_version"] = (
                        data.get("data", {}).get("state_version", 0)
                    )

            # Persist conversation/turn data (fire-and-forget)
            if event_type == "agent_started" and universe_id:
                agent_data = data.get("data", {})
                asyncio.create_task(create_conversation(
                    universe_id=universe_id,
                    agent_id=data.get("agent_id", ""),
                    agent_name=data.get("agent_name"),
                    agent_role=agent_data.get("role"),
                    model=agent_data.get("model"),
                    worker_id=worker_id,
                ))
            elif event_type == "iteration_detail" and universe_id:
                asyncio.create_task(insert_turn(
                    universe_id=universe_id,
                    agent_id=data.get("agent_id", ""),
                    data=data.get("data", {}),
                ))
            elif event_type == "agent_done" and universe_id:
                asyncio.create_task(complete_conversation(
                    universe_id=universe_id,
                    agent_id=data.get("agent_id", ""),
                    status="completed",
                ))
            elif event_type == "agent_error" and universe_id:
                asyncio.create_task(complete_conversation(
                    universe_id=universe_id,
                    agent_id=data.get("agent_id", ""),
                    status="error",
                    error_message=data.get("data", {}).get("error"),
                ))

            # Forward all events to dashboard clients
            await broadcast_to_dashboard(data)

    except WebSocketDisconnect:
        worker_ws_connections.pop(worker_id, None)
    except Exception:
        worker_ws_connections.pop(worker_id, None)


# ---------- Session WebSocket (catch-all, must be AFTER specific routes) ----------

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket connection for real-time session updates.

    Clients connect here to receive:
    - Node transitions
    - Thought log updates
    - Queue changes
    - Worker status updates
    """
    await websocket.accept()

    # Track connection
    if session_id not in websocket_connections:
        websocket_connections[session_id] = []
    websocket_connections[session_id].append(websocket)

    try:
        # Send current state on connect
        if session_id in sessions:
            await websocket.send_json({
                "type": "initial_state",
                "state": sessions[session_id]["state"],
            })

        # Keep connection alive and handle messages
        while True:
            data = await websocket.receive_json()

            # Handle client messages (e.g., manual interrupt)
            if data.get("type") == "interrupt":
                if session_id in sessions:
                    sessions[session_id]["state"]["is_paused"] = True
                    await broadcast_to_session(session_id, {
                        "type": "interrupted",
                        "reason": data.get("reason", "Manual interrupt"),
                    })

    except WebSocketDisconnect:
        websocket_connections[session_id].remove(websocket)


@app.get("/api/universes")
async def list_universes():
    """REST fallback: return all known universes from cache."""
    return list(universe_cache.values())


# ---------- Background Task ----------

async def run_orchestrator(session_id: str, orchestrator):
    """
    Run the orchestrator graph in the background.

    Streams updates to connected WebSocket clients.
    """
    if session_id not in sessions:
        return

    state = sessions[session_id]["state"]

    try:
        # Run the graph with streaming
        async for event in orchestrator.astream(state):
            # Check for pause
            if sessions[session_id]["state"].get("is_paused"):
                await broadcast_to_session(session_id, {
                    "type": "paused",
                    "state": sessions[session_id]["state"],
                })
                break

            # Update stored state
            if isinstance(event, dict):
                for key, value in event.items():
                    if key in state:
                        state[key] = value

            # Broadcast update
            await broadcast_to_session(session_id, {
                "type": "state_update",
                "node": state.get("current_node"),
                "thought_log": state.get("thought_log", []),
                "current_ticket": state.get("current_ticket"),
            })

        sessions[session_id]["status"] = "completed"
        await broadcast_to_session(session_id, {
            "type": "completed",
            "state": state,
        })

    except Exception as e:
        sessions[session_id]["status"] = "error"
        sessions[session_id]["state"]["error"] = str(e)
        await broadcast_to_session(session_id, {
            "type": "error",
            "error": str(e),
        })


# ---------- Entry Point ----------

def run():
    """Run the server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()
