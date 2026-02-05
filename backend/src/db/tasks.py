"""Task repository for database operations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

import asyncpg

from .models import Task, TaskStatus, TaskSource, WorkSession
from .connection import get_connection


class TaskRepository:
    """Repository for task CRUD operations."""

    @staticmethod
    def _row_to_task(row: asyncpg.Record) -> Task:
        """Convert a database row to a Task object."""
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            source=TaskSource(row["source"]),
            source_id=row["source_id"],
            source_url=row["source_url"],
            assigned_to=row["assigned_to"],
            tags=row["tags"] or [],
            project=row["project"],
            estimated_hours=row["estimated_hours"],
            actual_hours=row["actual_hours"],
            parent_task_id=row["parent_task_id"],
            blocked_by=row["blocked_by"] or [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            due_date=row["due_date"],
        )

    @staticmethod
    def _row_to_work_session(row: asyncpg.Record) -> WorkSession:
        """Convert a database row to a WorkSession object."""
        return WorkSession(
            id=row["id"],
            task_id=row["task_id"],
            worker_id=row["worker_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            status=row["status"],
            notes=row["notes"],
            hours_logged=row.get("hours_logged"),
        )


    # --- Task CRUD ---

    async def create(
        self,
        title: str,
        description: Optional[str] = None,
        status: TaskStatus = TaskStatus.PENDING,
        priority: int = 50,
        source: TaskSource = TaskSource.MANUAL,
        source_id: Optional[str] = None,
        source_url: Optional[str] = None,
        tags: Optional[list[str]] = None,
        project: Optional[str] = None,
        estimated_hours: Optional[float] = None,
        parent_task_id: Optional[UUID] = None,
        due_date: Optional[datetime] = None,
    ) -> Task:
        """Create a new task."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (
                    title, description, status, priority, source,
                    source_id, source_url, tags, project, estimated_hours,
                    parent_task_id, due_date
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING *
                """,
                title,
                description,
                status.value,
                priority,
                source.value,
                source_id,
                source_url,
                tags or [],
                project,
                estimated_hours,
                parent_task_id,
                due_date,
            )
            return self._row_to_task(row)

    async def get(self, task_id: UUID) -> Optional[Task]:
        """Get a task by ID."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tasks WHERE id = $1",
                task_id,
            )
            return self._row_to_task(row) if row else None

    async def list(
        self,
        status: Optional[TaskStatus] = None,
        source: Optional[TaskSource] = None,
        assigned_to: Optional[str] = None,
        project: Optional[str] = None,
        parent_task_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with optional filters."""
        conditions = []
        params = []
        param_idx = 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1

        if source:
            conditions.append(f"source = ${param_idx}")
            params.append(source.value)
            param_idx += 1

        if assigned_to is not None:
            if assigned_to == "":
                conditions.append("assigned_to IS NULL")
            else:
                conditions.append(f"assigned_to = ${param_idx}")
                params.append(assigned_to)
                param_idx += 1

        if project:
            conditions.append(f"project = ${param_idx}")
            params.append(project)
            param_idx += 1

        if parent_task_id is not None:
            conditions.append(f"parent_task_id = ${param_idx}")
            params.append(parent_task_id)
            param_idx += 1

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        params.extend([limit, offset])

        async with get_connection() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM tasks
                WHERE {where_clause}
                ORDER BY priority DESC, created_at ASC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
                """,
                *params,
            )
            return [self._row_to_task(row) for row in rows]

    async def get_pending_tasks(self, limit: int = 10) -> list[Task]:
        """Get pending tasks that are ready to be worked on, ordered by priority."""
        return await self.list(
            status=TaskStatus.PENDING,
            assigned_to="",  # Not assigned
            limit=limit,
        )

    async def get_subtasks(self, parent_id: UUID) -> list[Task]:
        """Get all subtasks for a parent task."""
        return await self.list(parent_task_id=parent_id)

    async def update(
        self,
        task_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[int] = None,
        assigned_to: Optional[str] = None,
        tags: Optional[list[str]] = None,
        project: Optional[str] = None,
        estimated_hours: Optional[float] = None,
        actual_hours: Optional[float] = None,
        due_date: Optional[datetime] = None,
    ) -> Optional[Task]:
        """Update a task."""
        updates = []
        params = []
        param_idx = 1

        if title is not None:
            updates.append(f"title = ${param_idx}")
            params.append(title)
            param_idx += 1

        if description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(description)
            param_idx += 1

        if status is not None:
            updates.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1
            # Auto-set timestamps based on status
            if status == TaskStatus.IN_PROGRESS:
                updates.append(f"started_at = COALESCE(started_at, ${param_idx})")
                params.append(datetime.utcnow())
                param_idx += 1
            elif status == TaskStatus.COMPLETED:
                updates.append(f"completed_at = ${param_idx}")
                params.append(datetime.utcnow())
                param_idx += 1

        if priority is not None:
            updates.append(f"priority = ${param_idx}")
            params.append(priority)
            param_idx += 1

        if assigned_to is not None:
            updates.append(f"assigned_to = ${param_idx}")
            params.append(assigned_to if assigned_to else None)
            param_idx += 1

        if tags is not None:
            updates.append(f"tags = ${param_idx}")
            params.append(tags)
            param_idx += 1

        if project is not None:
            updates.append(f"project = ${param_idx}")
            params.append(project)
            param_idx += 1

        if estimated_hours is not None:
            updates.append(f"estimated_hours = ${param_idx}")
            params.append(estimated_hours)
            param_idx += 1

        if actual_hours is not None:
            updates.append(f"actual_hours = ${param_idx}")
            params.append(actual_hours)
            param_idx += 1

        if due_date is not None:
            updates.append(f"due_date = ${param_idx}")
            params.append(due_date)
            param_idx += 1

        if not updates:
            return await self.get(task_id)

        params.append(task_id)
        set_clause = ", ".join(updates)

        async with get_connection() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE tasks
                SET {set_clause}
                WHERE id = ${param_idx}
                RETURNING *
                """,
                *params,
            )
            return self._row_to_task(row) if row else None

    async def delete(self, task_id: UUID) -> bool:
        """Delete a task."""
        async with get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM tasks WHERE id = $1",
                task_id,
            )
            return result == "DELETE 1"

    # --- Work Session Operations ---

    async def start_work_session(
        self,
        task_id: UUID,
        worker_id: str,
    ) -> WorkSession:
        """Start a new work session on a task."""
        async with get_connection() as conn:
            # Update task status and assignment
            await conn.execute(
                """
                UPDATE tasks
                SET status = $1, assigned_to = $2, started_at = COALESCE(started_at, NOW())
                WHERE id = $3
                """,
                TaskStatus.IN_PROGRESS.value,
                worker_id,
                task_id,
            )

            # Create work session
            row = await conn.fetchrow(
                """
                INSERT INTO work_sessions (task_id, worker_id)
                VALUES ($1, $2)
                RETURNING *
                """,
                task_id,
                worker_id,
            )
            return self._row_to_work_session(row)

    async def end_work_session(
        self,
        session_id: UUID,
        status: str,
        notes: Optional[str] = None,
        hours_logged: Optional[float] = None,
    ) -> Optional[WorkSession]:
        """End a work session."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                UPDATE work_sessions
                SET ended_at = NOW(), status = $1, notes = $2, hours_logged = $3
                WHERE id = $4
                RETURNING *
                """,
                status,
                notes,
                hours_logged,
                session_id,
            )

            if row:
                # Update task based on session status
                task_status = (
                    TaskStatus.COMPLETED if status == "completed"
                    else TaskStatus.BLOCKED if status == "blocked"
                    else TaskStatus.PENDING
                )
                await conn.execute(
                    """
                    UPDATE tasks
                    SET status = $1, assigned_to = NULL
                    WHERE id = $2
                    """,
                    task_status.value,
                    row["task_id"],
                )

            return self._row_to_work_session(row) if row else None

    async def get_active_session(
        self,
        worker_id: str,
    ) -> Optional[WorkSession]:
        """Get the active work session for a worker."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM work_sessions
                WHERE worker_id = $1 AND ended_at IS NULL
                ORDER BY started_at DESC
                LIMIT 1
                """,
                worker_id,
            )
            return self._row_to_work_session(row) if row else None

    async def get_task_sessions(
        self,
        task_id: UUID,
    ) -> list[WorkSession]:
        """Get all work sessions for a task."""
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM work_sessions
                WHERE task_id = $1
                ORDER BY started_at DESC
                """,
                task_id,
            )
            return [self._row_to_work_session(row) for row in rows]

    async def get_queue(self, limit: int = 50) -> list[Task]:
        """Get pending unassigned tasks ordered by priority (the task queue/buffer)."""
        async with get_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM tasks
                WHERE status = 'pending' AND assigned_to IS NULL
                ORDER BY priority DESC, created_at ASC
                LIMIT $1
                """,
                limit,
            )
            return [self._row_to_task(row) for row in rows]

    async def pick_next(self, worker_id: str) -> Optional[Task]:
        """Pick the next available task from the queue and assign it to a worker."""
        async with get_connection() as conn:
            # Atomically pick and assign the highest priority pending task
            row = await conn.fetchrow(
                """
                UPDATE tasks
                SET status = 'in_progress', assigned_to = $1, started_at = COALESCE(started_at, NOW())
                WHERE id = (
                    SELECT id FROM tasks
                    WHERE status = 'pending' AND assigned_to IS NULL
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
                """,
                worker_id,
            )
            return self._row_to_task(row) if row else None
