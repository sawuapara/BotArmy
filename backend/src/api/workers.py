"""API endpoints for worker management."""

import hashlib
import secrets
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db_pool
from ..logging import get_logger
from .status import get_api_key

logger = get_logger("workers")

router = APIRouter(prefix="/workers", tags=["workers"])


# --- Request/Response Models ---

class RegisterWorkerRequest(BaseModel):
    """Request body for registering a worker."""
    worker_id: Optional[str] = None  # If provided, upsert by this ID
    hostname: str
    worker_name: Optional[str] = None
    worker_address: Optional[str] = None
    max_concurrent_agents: int = Field(default=1024, ge=1)
    capabilities: list[str] = []


class HeartbeatRequest(BaseModel):
    """Request body for worker heartbeat."""
    current_agents: int = 0
    status: str = "online"


class WorkerResponse(BaseModel):
    """Response model for a worker."""
    id: str
    hostname: str
    worker_name: Optional[str]
    worker_address: Optional[str]
    max_concurrent_agents: int
    current_agents: int
    capabilities: list[str]
    status: str
    last_heartbeat_at: str
    registered_at: str
    updated_at: str


# --- Endpoints ---

@router.post("/register")
async def register_worker(request: RegisterWorkerRequest):
    """Register or re-register a worker (upsert by worker_id)."""
    logger.info(f"Worker registration request from {request.hostname} (name={request.worker_name})")

    # Generate a fresh auth token on every registration
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if request.worker_id:
            # Upsert: update if exists, insert if not
            worker_uuid = UUID(request.worker_id)
            row = await conn.fetchrow("""
                INSERT INTO orchestration.workers (id, hostname, worker_name, worker_address, max_concurrent_agents, capabilities, status, last_heartbeat_at, auth_token_hash)
                VALUES ($1, $2, $3, $4, $5, $6, 'online', NOW(), $7)
                ON CONFLICT (id) DO UPDATE SET
                    hostname = EXCLUDED.hostname,
                    worker_name = EXCLUDED.worker_name,
                    worker_address = EXCLUDED.worker_address,
                    max_concurrent_agents = EXCLUDED.max_concurrent_agents,
                    capabilities = EXCLUDED.capabilities,
                    status = 'online',
                    last_heartbeat_at = NOW(),
                    current_agents = 0,
                    auth_token_hash = EXCLUDED.auth_token_hash
                RETURNING *
            """, worker_uuid, request.hostname, request.worker_name,
                request.worker_address, request.max_concurrent_agents, request.capabilities,
                token_hash)
        else:
            # Insert new worker
            row = await conn.fetchrow("""
                INSERT INTO orchestration.workers (hostname, worker_name, worker_address, max_concurrent_agents, capabilities, auth_token_hash)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
            """, request.hostname, request.worker_name,
                request.worker_address, request.max_concurrent_agents, request.capabilities,
                token_hash)

        logger.info(f"Worker registered: {row['id']} ({request.hostname})")
        response = _row_to_response(row)
        response["auth_token"] = raw_token
        return response


@router.post("/{worker_id}/heartbeat", response_model=WorkerResponse)
async def worker_heartbeat(worker_id: UUID, request: HeartbeatRequest):
    """Receive heartbeat from a worker, update last_heartbeat_at."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE orchestration.workers
            SET last_heartbeat_at = NOW(),
                current_agents = $2,
                status = $3
            WHERE id = $1
            RETURNING *
        """, worker_id, request.current_agents, request.status)

        if not row:
            raise HTTPException(status_code=404, detail="Worker not found")

        return _row_to_response(row)


@router.post("/{worker_id}/deregister")
async def deregister_worker(worker_id: UUID):
    """Graceful shutdown: set worker status to offline."""
    logger.info(f"Worker deregistering: {worker_id}")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        updated = await conn.fetchval(
            "UPDATE orchestration.workers SET status = 'offline' WHERE id = $1 RETURNING id",
            worker_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Worker not found")

        logger.info(f"Worker set offline: {worker_id}")
        return {"message": "Worker set offline", "worker_id": str(worker_id)}


_ALLOWED_CREDENTIAL_KEYS = {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"}


@router.get("/credentials/{key_name}")
async def get_worker_credential(key_name: str, authorization: str = Header()):
    """Return a credential value to an authenticated worker."""
    # Validate Bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization[7:]
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, status FROM orchestration.workers WHERE auth_token_hash = $1",
            token_hash,
        )

    if not row:
        raise HTTPException(status_code=401, detail="Invalid auth token")

    if row["status"] == "offline":
        raise HTTPException(status_code=403, detail="Worker is offline")

    if key_name not in _ALLOWED_CREDENTIAL_KEYS:
        raise HTTPException(status_code=400, detail=f"Key '{key_name}' is not in the allowlist")

    key_value = await get_api_key(key_name)
    if not key_value:
        raise HTTPException(status_code=404, detail=f"Key '{key_name}' not found in vault or environment")

    return {"key_name": key_name, "key_value": key_value}


@router.get("", response_model=list[WorkerResponse])
async def list_workers(status: Optional[str] = None):
    """List workers with optional status filter."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM orchestration.workers WHERE status = $1 ORDER BY registered_at DESC",
                status,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM orchestration.workers ORDER BY registered_at DESC"
            )

        return [_row_to_response(row) for row in rows]


@router.get("/{worker_id}", response_model=WorkerResponse)
async def get_worker(worker_id: UUID):
    """Get a single worker by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM orchestration.workers WHERE id = $1",
            worker_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Worker not found")

        return _row_to_response(row)


# --- Helpers ---

def _row_to_response(row) -> dict:
    """Convert a database row to a WorkerResponse dict."""
    return {
        "id": str(row["id"]),
        "hostname": row["hostname"],
        "worker_name": row["worker_name"],
        "worker_address": row["worker_address"],
        "max_concurrent_agents": row["max_concurrent_agents"],
        "current_agents": row["current_agents"],
        "capabilities": row["capabilities"] or [],
        "status": row["status"],
        "last_heartbeat_at": row["last_heartbeat_at"].isoformat(),
        "registered_at": row["registered_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
