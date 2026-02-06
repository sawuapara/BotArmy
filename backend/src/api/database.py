"""API endpoints for database introspection and viewing."""

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..db import get_db_pool
from ..logging import get_logger, get_log_dir, get_recent_logs

logger = get_logger("api.database")

router = APIRouter(prefix="/database", tags=["database"])


class TableInfo(BaseModel):
    """Information about a database table."""
    name: str
    schema_name: str
    row_count: int
    full_name: str  # schema.table format


class ColumnInfo(BaseModel):
    """Information about a table column."""
    name: str
    type: str
    nullable: bool
    default: Optional[str]
    is_primary: bool


class TableSchema(BaseModel):
    """Schema information for a table."""
    name: str
    schema_name: str
    columns: list[ColumnInfo]
    row_count: int


class TableDataResponse(BaseModel):
    """Response with table data."""
    table: str
    schema_name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total_count: int
    limit: int
    offset: int


class SchemaInfo(BaseModel):
    """Information about a database schema."""
    name: str
    tables: list[TableInfo]


@router.get("/tables", response_model=list[TableInfo])
async def list_tables():
    """List all tables in the database with row counts (all schemas)."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                schemaname,
                relname as table_name,
                n_live_tup as row_count
            FROM pg_stat_user_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, relname
        """)

        return [
            TableInfo(
                name=row["table_name"],
                schema_name=row["schemaname"],
                row_count=row["row_count"],
                full_name=f"{row['schemaname']}.{row['table_name']}"
            )
            for row in rows
        ]


@router.get("/schemas", response_model=list[SchemaInfo])
async def list_schemas():
    """List all schemas with their tables grouped."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                schemaname,
                relname as table_name,
                n_live_tup as row_count
            FROM pg_stat_user_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, relname
        """)

        # Group by schema
        schemas_dict: dict[str, list[TableInfo]] = {}
        for row in rows:
            schema = row["schemaname"]
            if schema not in schemas_dict:
                schemas_dict[schema] = []
            schemas_dict[schema].append(
                TableInfo(
                    name=row["table_name"],
                    schema_name=schema,
                    row_count=row["row_count"],
                    full_name=f"{schema}.{row['table_name']}"
                )
            )

        # Sort schemas with 'public' first
        sorted_schemas = sorted(schemas_dict.keys(), key=lambda x: (x != 'public', x))

        return [
            SchemaInfo(name=schema, tables=schemas_dict[schema])
            for schema in sorted_schemas
        ]


def parse_table_name(full_name: str) -> tuple[str, str]:
    """Parse schema.table or just table name. Returns (schema, table)."""
    if "." in full_name:
        parts = full_name.split(".", 1)
        return parts[0], parts[1]
    return "public", full_name


def validate_identifier(name: str) -> bool:
    """Validate that a name is a safe SQL identifier."""
    # Allow alphanumeric and underscore, must start with letter or underscore
    import re
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


@router.get("/tables/{table_name:path}/schema", response_model=TableSchema)
async def get_table_schema(table_name: str):
    """Get schema information for a specific table. Accepts schema.table or just table."""
    schema_name, tbl_name = parse_table_name(table_name)

    # Validate names to prevent SQL injection
    if not validate_identifier(schema_name) or not validate_identifier(tbl_name):
        raise HTTPException(status_code=400, detail="Invalid table or schema name")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if table exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
        """, schema_name, tbl_name)

        if not exists:
            raise HTTPException(status_code=404, detail=f"Table '{schema_name}.{tbl_name}' not found")

        # Get column info
        columns = await conn.fetch("""
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_primary
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = $1
                    AND tc.table_name = $2
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_schema = $1 AND c.table_name = $2
            ORDER BY c.ordinal_position
        """, schema_name, tbl_name)

        # Get row count
        row_count = await conn.fetchval(
            f'SELECT COUNT(*) FROM "{schema_name}"."{tbl_name}"'
        )

        return TableSchema(
            name=tbl_name,
            schema_name=schema_name,
            columns=[
                ColumnInfo(
                    name=col["column_name"],
                    type=col["data_type"],
                    nullable=col["is_nullable"] == "YES",
                    default=col["column_default"],
                    is_primary=col["is_primary"],
                )
                for col in columns
            ],
            row_count=row_count,
        )


@router.get("/tables/{table_name:path}/data", response_model=TableDataResponse)
async def get_table_data(
    table_name: str,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    order_by: Optional[str] = None,
    order_dir: str = Query(default="DESC", pattern="^(ASC|DESC)$"),
):
    """Get data from a specific table with pagination. Accepts schema.table or just table."""
    schema_name, tbl_name = parse_table_name(table_name)

    # Validate names to prevent SQL injection
    if not validate_identifier(schema_name) or not validate_identifier(tbl_name):
        raise HTTPException(status_code=400, detail="Invalid table or schema name")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if table exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = $1 AND table_name = $2
            )
        """, schema_name, tbl_name)

        if not exists:
            raise HTTPException(status_code=404, detail=f"Table '{schema_name}.{tbl_name}' not found")

        # Get column names
        columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """, schema_name, tbl_name)
        column_names = [col["column_name"] for col in columns]

        # Validate order_by column
        if order_by and order_by not in column_names:
            raise HTTPException(status_code=400, detail=f"Invalid order_by column: {order_by}")

        # Build query
        order_clause = ""
        if order_by:
            order_clause = f'ORDER BY "{order_by}" {order_dir}'
        elif "created_at" in column_names:
            order_clause = f"ORDER BY created_at {order_dir}"
        elif "id" in column_names:
            order_clause = f"ORDER BY id {order_dir}"

        # Get total count
        total_count = await conn.fetchval(f'SELECT COUNT(*) FROM "{schema_name}"."{tbl_name}"')

        # Get data
        rows = await conn.fetch(
            f'SELECT * FROM "{schema_name}"."{tbl_name}" {order_clause} LIMIT $1 OFFSET $2',
            limit,
            offset,
        )

        # Convert rows to dicts, handling special types
        def serialize_value(val):
            if val is None:
                return None
            if isinstance(val, (list, tuple)):
                return list(val)
            if hasattr(val, 'isoformat'):
                return val.isoformat()
            return str(val) if not isinstance(val, (str, int, float, bool)) else val

        data = [
            {col: serialize_value(row[col]) for col in column_names}
            for row in rows
        ]

        return TableDataResponse(
            table=tbl_name,
            schema_name=schema_name,
            columns=column_names,
            rows=data,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )


# ---------- Logs Endpoints ----------

class LogFileInfo(BaseModel):
    """Information about a log file."""
    name: str
    size_bytes: int
    modified_at: str


class LogsResponse(BaseModel):
    """Response with log content."""
    lines: list[str]
    total_lines: int
    log_file: str


@router.get("/logs", response_model=list[LogFileInfo])
async def list_log_files():
    """List all available log files."""
    log_dir = get_log_dir()
    if not log_dir or not log_dir.exists():
        return []

    files = []
    for f in sorted(log_dir.glob("jarvis_*.log"), reverse=True):
        stat = f.stat()
        files.append(LogFileInfo(
            name=f.name,
            size_bytes=stat.st_size,
            modified_at=str(stat.st_mtime),
        ))

    return files


@router.get("/logs/recent", response_model=LogsResponse)
async def get_recent_log_entries(
    lines: int = Query(default=100, le=1000, ge=1),
):
    """Get the most recent log entries from the current log file."""
    log_dir = get_log_dir()
    if not log_dir:
        raise HTTPException(status_code=404, detail="Logging not initialized")

    latest = log_dir / "latest.log"
    if not latest.exists():
        raise HTTPException(status_code=404, detail="No log file found")

    log_lines = get_recent_logs(lines)
    return LogsResponse(
        lines=log_lines,
        total_lines=len(log_lines),
        log_file="latest.log",
    )


@router.get("/logs/{filename}", response_model=LogsResponse)
async def get_log_file(
    filename: str,
    lines: int = Query(default=100, le=1000, ge=1),
    offset: int = Query(default=0, ge=0),
):
    """Get contents of a specific log file."""
    log_dir = get_log_dir()
    if not log_dir:
        raise HTTPException(status_code=404, detail="Logging not initialized")

    # Security: only allow reading jarvis log files
    if not filename.startswith("jarvis_") or not filename.endswith(".log"):
        raise HTTPException(status_code=400, detail="Invalid log file name")

    log_file = log_dir / filename
    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"Log file '{filename}' not found")

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            total = len(all_lines)
            selected = all_lines[offset:offset + lines]
            return LogsResponse(
                lines=selected,
                total_lines=total,
                log_file=filename,
            )
    except Exception as e:
        logger.error(f"Failed to read log file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read log file")
