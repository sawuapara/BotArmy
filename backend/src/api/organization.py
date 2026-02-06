"""API endpoints for organization management (namespaces and labels)."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db_pool
from ..logging import get_logger

logger = get_logger("api.organization")

router = APIRouter(prefix="/organization", tags=["organization"])


# --- Request/Response Models ---

class CreateNamespaceRequest(BaseModel):
    """Request body for creating a namespace."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class UpdateNamespaceRequest(BaseModel):
    """Request body for updating a namespace."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None


class NamespaceResponse(BaseModel):
    """Response model for a namespace."""
    id: str
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str
    project_count: int = 0


class CreateLabelRequest(BaseModel):
    """Request body for creating a label."""
    namespace_id: str
    name: str = Field(..., min_length=1, max_length=100)
    parent_label_id: Optional[str] = None
    color: Optional[str] = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")


class UpdateLabelRequest(BaseModel):
    """Request body for updating a label."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    parent_label_id: Optional[str] = None
    color: Optional[str] = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")


class LabelResponse(BaseModel):
    """Response model for a label."""
    id: str
    namespace_id: str
    name: str
    parent_label_id: Optional[str]
    color: Optional[str]
    created_at: str
    updated_at: str


# --- Namespace Endpoints ---

@router.get("/namespaces", response_model=list[NamespaceResponse])
async def list_namespaces():
    """List all namespaces."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT n.*, COALESCE(p.project_count, 0) as project_count
            FROM organization.namespaces n
            LEFT JOIN (
                SELECT namespace_id, COUNT(*) as project_count
                FROM projects.projects
                GROUP BY namespace_id
            ) p ON n.id = p.namespace_id
            ORDER BY n.name
        """)
        return [_namespace_row_to_response(row) for row in rows]


@router.post("/namespaces", response_model=NamespaceResponse)
async def create_namespace(request: CreateNamespaceRequest):
    """Create a new namespace."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if name already exists
        existing = await conn.fetchval(
            "SELECT id FROM organization.namespaces WHERE name = $1",
            request.name
        )
        if existing:
            raise HTTPException(status_code=409, detail="Namespace with this name already exists")

        row = await conn.fetchrow("""
            INSERT INTO organization.namespaces (name, description)
            VALUES ($1, $2)
            RETURNING *, 0 as project_count
        """, request.name, request.description)

        return _namespace_row_to_response(row)


@router.get("/namespaces/{namespace_id}", response_model=NamespaceResponse)
async def get_namespace(namespace_id: UUID):
    """Get a namespace by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT n.*, COALESCE(p.project_count, 0) as project_count
            FROM organization.namespaces n
            LEFT JOIN (
                SELECT namespace_id, COUNT(*) as project_count
                FROM projects.projects
                GROUP BY namespace_id
            ) p ON n.id = p.namespace_id
            WHERE n.id = $1
        """, namespace_id)

        if not row:
            raise HTTPException(status_code=404, detail="Namespace not found")

        return _namespace_row_to_response(row)


@router.patch("/namespaces/{namespace_id}", response_model=NamespaceResponse)
async def update_namespace(namespace_id: UUID, request: UpdateNamespaceRequest):
    """Update a namespace."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        updates = []
        values = []
        param_idx = 1

        if request.name is not None:
            # Check uniqueness
            existing = await conn.fetchval(
                "SELECT id FROM organization.namespaces WHERE name = $1 AND id != $2",
                request.name, namespace_id
            )
            if existing:
                raise HTTPException(status_code=409, detail="Namespace with this name already exists")
            updates.append(f"name = ${param_idx}")
            values.append(request.name)
            param_idx += 1

        if request.description is not None:
            updates.append(f"description = ${param_idx}")
            values.append(request.description)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(namespace_id)
        query = f"""
            UPDATE organization.namespaces
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(status_code=404, detail="Namespace not found")

        # Get project count
        project_count = await conn.fetchval(
            "SELECT COUNT(*) FROM projects.projects WHERE namespace_id = $1",
            namespace_id
        )

        return _namespace_row_to_response(row, project_count or 0)


@router.delete("/namespaces/{namespace_id}")
async def delete_namespace(namespace_id: UUID):
    """Delete a namespace."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if there are any projects in this namespace
        project_count = await conn.fetchval(
            "SELECT COUNT(*) FROM projects.projects WHERE namespace_id = $1",
            namespace_id
        )
        if project_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete namespace with {project_count} projects. Move or delete projects first."
            )

        deleted = await conn.fetchval(
            "DELETE FROM organization.namespaces WHERE id = $1 RETURNING id",
            namespace_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Namespace not found")
        return {"message": "Namespace deleted"}


# --- Label Endpoints ---

@router.get("/namespaces/{namespace_id}/labels", response_model=list[LabelResponse])
async def list_labels_in_namespace(namespace_id: UUID):
    """List all labels in a namespace."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # First verify namespace exists
        ns_exists = await conn.fetchval(
            "SELECT id FROM organization.namespaces WHERE id = $1",
            namespace_id
        )
        if not ns_exists:
            raise HTTPException(status_code=404, detail="Namespace not found")

        rows = await conn.fetch("""
            SELECT * FROM organization.labels
            WHERE namespace_id = $1
            ORDER BY parent_label_id NULLS FIRST, name
        """, namespace_id)
        return [_label_row_to_response(row) for row in rows]


@router.post("/labels", response_model=LabelResponse)
async def create_label(request: CreateLabelRequest):
    """Create a new label."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        namespace_id = UUID(request.namespace_id)
        parent_label_id = UUID(request.parent_label_id) if request.parent_label_id else None

        # Verify namespace exists
        ns_exists = await conn.fetchval(
            "SELECT id FROM organization.namespaces WHERE id = $1",
            namespace_id
        )
        if not ns_exists:
            raise HTTPException(status_code=404, detail="Namespace not found")

        # Verify parent label exists and is in same namespace
        if parent_label_id:
            parent = await conn.fetchrow(
                "SELECT id, namespace_id FROM organization.labels WHERE id = $1",
                parent_label_id
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Parent label not found")
            if parent['namespace_id'] != namespace_id:
                raise HTTPException(status_code=400, detail="Parent label must be in the same namespace")

        # Check for duplicate
        existing = await conn.fetchval("""
            SELECT id FROM organization.labels
            WHERE namespace_id = $1 AND name = $2 AND parent_label_id IS NOT DISTINCT FROM $3
        """, namespace_id, request.name, parent_label_id)
        if existing:
            raise HTTPException(status_code=409, detail="Label with this name already exists in this context")

        row = await conn.fetchrow("""
            INSERT INTO organization.labels (namespace_id, name, parent_label_id, color)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """, namespace_id, request.name, parent_label_id, request.color)

        return _label_row_to_response(row)


@router.get("/labels/{label_id}", response_model=LabelResponse)
async def get_label(label_id: UUID):
    """Get a label by ID."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM organization.labels WHERE id = $1",
            label_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Label not found")
        return _label_row_to_response(row)


@router.patch("/labels/{label_id}", response_model=LabelResponse)
async def update_label(label_id: UUID, request: UpdateLabelRequest):
    """Update a label."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Get current label
        current = await conn.fetchrow(
            "SELECT * FROM organization.labels WHERE id = $1",
            label_id
        )
        if not current:
            raise HTTPException(status_code=404, detail="Label not found")

        updates = []
        values = []
        param_idx = 1

        if request.name is not None:
            updates.append(f"name = ${param_idx}")
            values.append(request.name)
            param_idx += 1

        if request.parent_label_id is not None:
            parent_uuid = UUID(request.parent_label_id) if request.parent_label_id else None
            if parent_uuid:
                # Verify parent exists and is in same namespace
                parent = await conn.fetchrow(
                    "SELECT id, namespace_id FROM organization.labels WHERE id = $1",
                    parent_uuid
                )
                if not parent:
                    raise HTTPException(status_code=404, detail="Parent label not found")
                if parent['namespace_id'] != current['namespace_id']:
                    raise HTTPException(status_code=400, detail="Parent label must be in the same namespace")
                # Prevent circular references
                if parent_uuid == label_id:
                    raise HTTPException(status_code=400, detail="Label cannot be its own parent")
            updates.append(f"parent_label_id = ${param_idx}")
            values.append(parent_uuid)
            param_idx += 1

        if request.color is not None:
            updates.append(f"color = ${param_idx}")
            values.append(request.color)
            param_idx += 1

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        values.append(label_id)
        query = f"""
            UPDATE organization.labels
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING *
        """

        row = await conn.fetchrow(query, *values)
        return _label_row_to_response(row)


@router.delete("/labels/{label_id}")
async def delete_label(label_id: UUID):
    """Delete a label."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "DELETE FROM organization.labels WHERE id = $1 RETURNING id",
            label_id
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Label not found")
        return {"message": "Label deleted"}


# --- Helper Functions ---

def _namespace_row_to_response(row, project_count: int = None) -> dict:
    """Convert a database row to namespace response dict."""
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "project_count": project_count if project_count is not None else row.get("project_count", 0),
    }


def _label_row_to_response(row) -> dict:
    """Convert a database row to label response dict."""
    return {
        "id": str(row["id"]),
        "namespace_id": str(row["namespace_id"]),
        "name": row["name"],
        "parent_label_id": str(row["parent_label_id"]) if row["parent_label_id"] else None,
        "color": row["color"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
