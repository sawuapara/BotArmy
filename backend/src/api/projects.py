"""API endpoints for project management."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db_pool
from ..logging import get_logger

logger = get_logger("api.projects")

router = APIRouter(prefix="/projects", tags=["projects"])


# --- Request/Response Models ---

class CreateProjectRequest(BaseModel):
    """Request body for creating a project."""
    name: str = Field(..., min_length=1, max_length=200)
    namespace_id: str
    description: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    """Request body for updating a project."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    namespace_id: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(active|archived|on_hold)$")
    tags: Optional[list[str]] = None
    repository_url: Optional[str] = None
    jira_project_key: Optional[str] = None
    salesforce_account_id: Optional[str] = None
    sort_order: Optional[int] = None


class LabelInfo(BaseModel):
    """Label info for responses."""
    id: str
    name: str
    color: Optional[str]


class NamespaceInfo(BaseModel):
    """Namespace info for responses."""
    id: str
    name: str


class ProjectResponse(BaseModel):
    """Response model for a project."""
    id: str
    name: str
    namespace_id: str
    namespace: Optional[NamespaceInfo] = None
    description: Optional[str]
    status: str
    tags: list[str]
    labels: list[LabelInfo] = []
    repository_url: Optional[str]
    jira_project_key: Optional[str]
    salesforce_account_id: Optional[str]
    sort_order: int = 0
    created_at: str
    updated_at: str
    archived_at: Optional[str]
    task_count: int = 0


class AddLabelRequest(BaseModel):
    """Request body for adding a label to a project."""
    label_id: str


# --- Endpoints ---

@router.post("", response_model=ProjectResponse)
async def create_project(request: CreateProjectRequest):
    """Create a new project."""
    logger.info(f"Creating project: {request.name}")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        namespace_id = UUID(request.namespace_id)

        # Verify namespace exists
        ns_row = await conn.fetchrow(
            "SELECT id, name FROM organization.namespaces WHERE id = $1",
            namespace_id
        )
        if not ns_row:
            raise HTTPException(status_code=404, detail="Namespace not found")

        # Check if name already exists within namespace
        existing = await conn.fetchval(
            "SELECT id FROM projects.projects WHERE namespace_id = $1 AND name = $2",
            namespace_id, request.name
        )
        if existing:
            raise HTTPException(status_code=409, detail="Project with this name already exists in this namespace")

        row = await conn.fetchrow("""
            INSERT INTO projects.projects (namespace_id, name, description)
            VALUES ($1, $2, $3)
            RETURNING *
        """, namespace_id, request.name, request.description)

        return _row_to_response(row, 0, [], ns_row)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    status: Optional[str] = None,
    namespace_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all projects with optional filters."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Build query with filters
        conditions = []
        values = []
        param_idx = 1

        if status:
            conditions.append(f"p.status = ${param_idx}")
            values.append(status)
            param_idx += 1

        if namespace_id:
            conditions.append(f"p.namespace_id = ${param_idx}")
            values.append(UUID(namespace_id))
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        values.extend([limit, offset])
        query = f"""
            SELECT p.*, n.id as ns_id, n.name as ns_name,
                   COALESCE(t.task_count, 0) as task_count
            FROM projects.projects p
            JOIN organization.namespaces n ON p.namespace_id = n.id
            LEFT JOIN (
                SELECT project_id, COUNT(*) as task_count
                FROM tasks
                WHERE project_id IS NOT NULL
                GROUP BY project_id
            ) t ON p.id = t.project_id
            {where_clause}
            ORDER BY p.sort_order ASC, p.updated_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """

        rows = await conn.fetch(query, *values)

        # Get labels for each project
        project_ids = [row['id'] for row in rows]
        if project_ids:
            labels_rows = await conn.fetch("""
                SELECT pl.project_id, l.id, l.name, l.color
                FROM projects.project_labels pl
                JOIN organization.labels l ON pl.label_id = l.id
                WHERE pl.project_id = ANY($1)
            """, project_ids)

            # Group labels by project
            labels_by_project = {}
            for lr in labels_rows:
                pid = lr['project_id']
                if pid not in labels_by_project:
                    labels_by_project[pid] = []
                labels_by_project[pid].append({
                    "id": str(lr['id']),
                    "name": lr['name'],
                    "color": lr['color'],
                })
        else:
            labels_by_project = {}

        return [
            _row_to_response(
                row,
                row['task_count'],
                labels_by_project.get(row['id'], []),
                {"id": row['ns_id'], "name": row['ns_name']}
            )
            for row in rows
        ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: UUID):
    """Get a project by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT p.*, n.id as ns_id, n.name as ns_name,
                   COALESCE(t.task_count, 0) as task_count
            FROM projects.projects p
            JOIN organization.namespaces n ON p.namespace_id = n.id
            LEFT JOIN (
                SELECT project_id, COUNT(*) as task_count
                FROM tasks
                WHERE project_id IS NOT NULL
                GROUP BY project_id
            ) t ON p.id = t.project_id
            WHERE p.id = $1
        """, project_id)

        if not row:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get labels
        labels_rows = await conn.fetch("""
            SELECT l.id, l.name, l.color
            FROM projects.project_labels pl
            JOIN organization.labels l ON pl.label_id = l.id
            WHERE pl.project_id = $1
        """, project_id)

        labels = [{"id": str(lr['id']), "name": lr['name'], "color": lr['color']} for lr in labels_rows]

        return _row_to_response(
            row,
            row['task_count'],
            labels,
            {"id": row['ns_id'], "name": row['ns_name']}
        )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: UUID, request: UpdateProjectRequest):
    """Update a project."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Get current project
        current = await conn.fetchrow(
            "SELECT * FROM projects.projects WHERE id = $1",
            project_id
        )
        if not current:
            raise HTTPException(status_code=404, detail="Project not found")

        updates = []
        values = []
        param_idx = 1

        if request.namespace_id is not None:
            new_ns_id = UUID(request.namespace_id)
            # Verify new namespace exists
            ns_exists = await conn.fetchval(
                "SELECT id FROM organization.namespaces WHERE id = $1",
                new_ns_id
            )
            if not ns_exists:
                raise HTTPException(status_code=404, detail="Namespace not found")
            updates.append(f"namespace_id = ${param_idx}")
            values.append(new_ns_id)
            param_idx += 1

        if request.name is not None:
            # Check uniqueness within namespace
            check_ns_id = UUID(request.namespace_id) if request.namespace_id else current['namespace_id']
            existing = await conn.fetchval(
                "SELECT id FROM projects.projects WHERE namespace_id = $1 AND name = $2 AND id != $3",
                check_ns_id, request.name, project_id
            )
            if existing:
                raise HTTPException(status_code=409, detail="Project with this name already exists in this namespace")
            updates.append(f"name = ${param_idx}")
            values.append(request.name)
            param_idx += 1

        if request.description is not None:
            updates.append(f"description = ${param_idx}")
            values.append(request.description)
            param_idx += 1

        if request.status is not None:
            updates.append(f"status = ${param_idx}")
            values.append(request.status)
            param_idx += 1
            if request.status == "archived":
                updates.append(f"archived_at = NOW()")

        if request.tags is not None:
            updates.append(f"tags = ${param_idx}")
            values.append(request.tags)
            param_idx += 1

        if request.repository_url is not None:
            updates.append(f"repository_url = ${param_idx}")
            values.append(request.repository_url)
            param_idx += 1

        if request.jira_project_key is not None:
            updates.append(f"jira_project_key = ${param_idx}")
            values.append(request.jira_project_key)
            param_idx += 1

        if request.salesforce_account_id is not None:
            updates.append(f"salesforce_account_id = ${param_idx}")
            values.append(request.salesforce_account_id)
            param_idx += 1

        if request.sort_order is not None:
            updates.append(f"sort_order = ${param_idx}")
            values.append(request.sort_order)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(project_id)
        query = f"""
            UPDATE projects.projects
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(query, *values)

        # Get namespace info
        ns_row = await conn.fetchrow(
            "SELECT id, name FROM organization.namespaces WHERE id = $1",
            row['namespace_id']
        )

        # Get task count
        task_count = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE project_id = $1",
            project_id
        )

        # Get labels
        labels_rows = await conn.fetch("""
            SELECT l.id, l.name, l.color
            FROM projects.project_labels pl
            JOIN organization.labels l ON pl.label_id = l.id
            WHERE pl.project_id = $1
        """, project_id)
        labels = [{"id": str(lr['id']), "name": lr['name'], "color": lr['color']} for lr in labels_rows]

        return _row_to_response(row, task_count or 0, labels, ns_row)


@router.delete("/{project_id}")
async def delete_project(project_id: UUID):
    """Delete a project."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "DELETE FROM projects.projects WHERE id = $1 RETURNING id",
            project_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project deleted"}


# --- Label Management Endpoints ---

@router.get("/{project_id}/labels", response_model=list[LabelInfo])
async def get_project_labels(project_id: UUID):
    """Get all labels for a project."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Verify project exists
        project_exists = await conn.fetchval(
            "SELECT id FROM projects.projects WHERE id = $1",
            project_id
        )
        if not project_exists:
            raise HTTPException(status_code=404, detail="Project not found")

        rows = await conn.fetch("""
            SELECT l.id, l.name, l.color
            FROM projects.project_labels pl
            JOIN organization.labels l ON pl.label_id = l.id
            WHERE pl.project_id = $1
            ORDER BY l.name
        """, project_id)

        return [{"id": str(row['id']), "name": row['name'], "color": row['color']} for row in rows]


@router.post("/{project_id}/labels", response_model=list[LabelInfo])
async def add_label_to_project(project_id: UUID, request: AddLabelRequest):
    """Add a label to a project."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        label_id = UUID(request.label_id)

        # Get project with its namespace
        project = await conn.fetchrow(
            "SELECT id, namespace_id FROM projects.projects WHERE id = $1",
            project_id
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Verify label exists and is in the same namespace
        label = await conn.fetchrow(
            "SELECT id, namespace_id FROM organization.labels WHERE id = $1",
            label_id
        )
        if not label:
            raise HTTPException(status_code=404, detail="Label not found")
        if label['namespace_id'] != project['namespace_id']:
            raise HTTPException(status_code=400, detail="Label must be in the same namespace as the project")

        # Add label (ignore if already exists)
        await conn.execute("""
            INSERT INTO projects.project_labels (project_id, label_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
        """, project_id, label_id)

        # Return updated label list
        rows = await conn.fetch("""
            SELECT l.id, l.name, l.color
            FROM projects.project_labels pl
            JOIN organization.labels l ON pl.label_id = l.id
            WHERE pl.project_id = $1
            ORDER BY l.name
        """, project_id)

        return [{"id": str(row['id']), "name": row['name'], "color": row['color']} for row in rows]


@router.delete("/{project_id}/labels/{label_id}")
async def remove_label_from_project(project_id: UUID, label_id: UUID):
    """Remove a label from a project."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval("""
            DELETE FROM projects.project_labels
            WHERE project_id = $1 AND label_id = $2
            RETURNING project_id
        """, project_id, label_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Label not found on this project")

        return {"message": "Label removed from project"}


# --- Helper Functions ---

def _row_to_response(row, task_count: int, labels: list, namespace_info=None) -> dict:
    """Convert a database row to response dict."""
    ns = None
    if namespace_info:
        if isinstance(namespace_info, dict):
            ns = {"id": str(namespace_info["id"]), "name": namespace_info["name"]}
        else:
            ns = {"id": str(namespace_info["id"]), "name": namespace_info["name"]}

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "namespace_id": str(row["namespace_id"]),
        "namespace": ns,
        "description": row["description"],
        "status": row["status"],
        "tags": row["tags"] or [],
        "labels": labels,
        "repository_url": row["repository_url"],
        "jira_project_key": row["jira_project_key"],
        "salesforce_account_id": row["salesforce_account_id"],
        "sort_order": row.get("sort_order", 0),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "archived_at": row["archived_at"].isoformat() if row["archived_at"] else None,
        "task_count": task_count,
    }
