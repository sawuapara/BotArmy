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


# Store active sessions and their states
sessions: dict[str, dict] = {}
websocket_connections: dict[str, list[WebSocket]] = {}


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

                    # Worker is unreachable - delete it
                    await conn.execute(
                        "DELETE FROM orchestration.workers WHERE id = $1",
                        worker_id,
                    )
                    logger.info(f"Removed dead worker: {name} ({worker_id})")

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


# ---------- REST Endpoints ----------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


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


# ---------- WebSocket ----------

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket connection for real-time updates.

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


async def broadcast_to_session(session_id: str, message: dict):
    """Broadcast a message to all WebSocket clients for a session."""
    if session_id in websocket_connections:
        for ws in websocket_connections[session_id]:
            try:
                await ws.send_json(message)
            except:
                pass  # Client disconnected


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
