"""API endpoints for worker management."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db_pool
from ..logging import get_logger

logger = get_logger("workers")

router = APIRouter(prefix="/workers", tags=["workers"])


# --- Request/Response Models ---

class RegisterWorkerRequest(BaseModel):
    """Request body for registering a worker."""
    worker_id: Optional[str] = None  # If provided, upsert by this ID
    hostname: str
    worker_name: Optional[str] = None
    worker_address: Optional[str] = None
    max_concurrent_jobs: int = Field(default=2, ge=1)
    capabilities: list[str] = []


class HeartbeatRequest(BaseModel):
    """Request body for worker heartbeat."""
    current_jobs: int = 0
    status: str = "online"


class WorkerResponse(BaseModel):
    """Response model for a worker."""
    id: str
    hostname: str
    worker_name: Optional[str]
    worker_address: Optional[str]
    max_concurrent_jobs: int
    current_jobs: int
    capabilities: list[str]
    status: str
    last_heartbeat_at: str
    registered_at: str
    updated_at: str


# --- Endpoints ---

@router.post("/register", response_model=WorkerResponse)
async def register_worker(request: RegisterWorkerRequest):
    """Register or re-register a worker (upsert by worker_id)."""
    logger.info(f"Worker registration request from {request.hostname} (name={request.worker_name})")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if request.worker_id:
            # Upsert: update if exists, insert if not
            worker_uuid = UUID(request.worker_id)
            row = await conn.fetchrow("""
                INSERT INTO orchestration.workers (id, hostname, worker_name, worker_address, max_concurrent_jobs, capabilities, status, last_heartbeat_at)
                VALUES ($1, $2, $3, $4, $5, $6, 'online', NOW())
                ON CONFLICT (id) DO UPDATE SET
                    hostname = EXCLUDED.hostname,
                    worker_name = EXCLUDED.worker_name,
                    worker_address = EXCLUDED.worker_address,
                    max_concurrent_jobs = EXCLUDED.max_concurrent_jobs,
                    capabilities = EXCLUDED.capabilities,
                    status = 'online',
                    last_heartbeat_at = NOW(),
                    current_jobs = 0
                RETURNING *
            """, worker_uuid, request.hostname, request.worker_name,
                request.worker_address, request.max_concurrent_jobs, request.capabilities)
        else:
            # Insert new worker
            row = await conn.fetchrow("""
                INSERT INTO orchestration.workers (hostname, worker_name, worker_address, max_concurrent_jobs, capabilities)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """, request.hostname, request.worker_name,
                request.worker_address, request.max_concurrent_jobs, request.capabilities)

        logger.info(f"Worker registered: {row['id']} ({request.hostname})")
        return _row_to_response(row)


@router.post("/{worker_id}/heartbeat", response_model=WorkerResponse)
async def worker_heartbeat(worker_id: UUID, request: HeartbeatRequest):
    """Receive heartbeat from a worker, update last_heartbeat_at."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE orchestration.workers
            SET last_heartbeat_at = NOW(),
                current_jobs = $2,
                status = $3
            WHERE id = $1
            RETURNING *
        """, worker_id, request.current_jobs, request.status)

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
        "max_concurrent_jobs": row["max_concurrent_jobs"],
        "current_jobs": row["current_jobs"],
        "capabilities": row["capabilities"] or [],
        "status": row["status"],
        "last_heartbeat_at": row["last_heartbeat_at"].isoformat(),
        "registered_at": row["registered_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
