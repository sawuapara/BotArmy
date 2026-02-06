"""API endpoints for task management."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import TaskRepository, TaskStatus
from ..db.models import TaskSource
from ..logging import get_logger

logger = get_logger("api.tasks")

router = APIRouter(prefix="/tasks", tags=["tasks"])
task_repo = TaskRepository()


# --- Request/Response Models ---

class CreateTaskRequest(BaseModel):
    """Request body for creating a task."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = "pending"
    priority: int = Field(default=50, ge=0, le=100)
    source: str = "manual"
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    tags: list[str] = []
    project: Optional[str] = None
    estimated_hours: Optional[float] = None
    parent_task_id: Optional[str] = None
    due_date: Optional[str] = None  # ISO format


class UpdateTaskRequest(BaseModel):
    """Request body for updating a task."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=0, le=100)
    assigned_to: Optional[str] = None
    tags: Optional[list[str]] = None
    project: Optional[str] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    due_date: Optional[str] = None


class TaskResponse(BaseModel):
    """Response model for a task."""
    id: str
    title: str
    description: Optional[str]
    status: str
    priority: int
    source: str
    source_id: Optional[str]
    source_url: Optional[str]
    assigned_to: Optional[str]
    tags: list[str]
    project: Optional[str]
    estimated_hours: Optional[float]
    actual_hours: Optional[float]
    parent_task_id: Optional[str]
    blocked_by: list[str]
    created_at: str
    updated_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    due_date: Optional[str]


class StartWorkSessionRequest(BaseModel):
    """Request to start a work session."""
    worker_id: str


class EndWorkSessionRequest(BaseModel):
    """Request to end a work session."""
    status: str = Field(..., pattern="^(completed|blocked|interrupted|paused)$")
    notes: Optional[str] = None
    hours_logged: Optional[float] = None


class WorkSessionResponse(BaseModel):
    """Response model for a work session."""
    id: str
    task_id: str
    worker_id: str
    started_at: str
    ended_at: Optional[str]
    status: Optional[str]
    notes: Optional[str]
    hours_logged: Optional[float]


class PickNextRequest(BaseModel):
    """Request to pick the next task from queue."""
    worker_id: str


# --- Task Endpoints ---

@router.post("", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest):
    """Create a new task."""
    try:
        status = TaskStatus(request.status) if request.status else TaskStatus.PENDING
        source = TaskSource(request.source) if request.source else TaskSource.MANUAL
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    parent_id = UUID(request.parent_task_id) if request.parent_task_id else None
    due = datetime.fromisoformat(request.due_date) if request.due_date else None

    task = await task_repo.create(
        title=request.title,
        description=request.description,
        status=status,
        priority=request.priority,
        source=source,
        source_id=request.source_id,
        source_url=request.source_url,
        tags=request.tags,
        project=request.project,
        estimated_hours=request.estimated_hours,
        parent_task_id=parent_id,
        due_date=due,
    )

    return task.to_dict()


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    source: Optional[str] = None,
    assigned_to: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List tasks with optional filters."""
    try:
        status_enum = TaskStatus(status) if status else None
        source_enum = TaskSource(source) if source else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tasks = await task_repo.list(
        status=status_enum,
        source=source_enum,
        assigned_to=assigned_to,
        project=project,
        limit=limit,
        offset=offset,
    )
    return [t.to_dict() for t in tasks]


@router.get("/queue", response_model=list[TaskResponse])
async def get_task_queue(limit: int = 50):
    """Get the task queue - pending unassigned tasks ordered by priority."""
    tasks = await task_repo.get_queue(limit=limit)
    return [t.to_dict() for t in tasks]


@router.post("/queue/pick", response_model=TaskResponse)
async def pick_next_task(request: PickNextRequest):
    """Pick the next available task from the queue and assign it to a worker."""
    task = await task_repo.pick_next(request.worker_id)
    if not task:
        raise HTTPException(status_code=404, detail="No tasks available in queue")
    return task.to_dict()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID):
    """Get a task by ID."""
    task = await task_repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.get("/{task_id}/subtasks", response_model=list[TaskResponse])
async def get_subtasks(task_id: UUID):
    """Get all subtasks for a task."""
    subtasks = await task_repo.get_subtasks(task_id)
    return [t.to_dict() for t in subtasks]


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, request: UpdateTaskRequest):
    """Update a task."""
    try:
        status_enum = TaskStatus(request.status) if request.status else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    due = datetime.fromisoformat(request.due_date) if request.due_date else None

    task = await task_repo.update(
        task_id=task_id,
        title=request.title,
        description=request.description,
        status=status_enum,
        priority=request.priority,
        assigned_to=request.assigned_to,
        tags=request.tags,
        project=request.project,
        estimated_hours=request.estimated_hours,
        actual_hours=request.actual_hours,
        due_date=due,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.delete("/{task_id}")
async def delete_task(task_id: UUID):
    """Delete a task."""
    deleted = await task_repo.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}


# --- Work Session Endpoints ---

@router.post("/{task_id}/sessions", response_model=WorkSessionResponse)
async def start_work_session(task_id: UUID, request: StartWorkSessionRequest):
    """Start a work session on a task."""
    task = await task_repo.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.assigned_to:
        raise HTTPException(
            status_code=409,
            detail=f"Task already assigned to: {task.assigned_to}"
        )

    session = await task_repo.start_work_session(task_id, request.worker_id)
    return session.to_dict()


@router.patch("/sessions/{session_id}", response_model=WorkSessionResponse)
async def end_work_session(session_id: UUID, request: EndWorkSessionRequest):
    """End a work session."""
    session = await task_repo.end_work_session(
        session_id=session_id,
        status=request.status,
        notes=request.notes,
        hours_logged=request.hours_logged,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Work session not found")
    return session.to_dict()


@router.get("/{task_id}/sessions", response_model=list[WorkSessionResponse])
async def get_task_sessions(task_id: UUID):
    """Get all work sessions for a task."""
    sessions = await task_repo.get_task_sessions(task_id)
    return [s.to_dict() for s in sessions]
