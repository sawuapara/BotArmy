"""Database connection management for Jarvis."""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg

# Use standard logging with deferred initialization
# This avoids circular import with the logging module
_db_logger = None
_migration_logger = None


def _get_db_logger():
    """Get the database logger, initializing if needed."""
    global _db_logger
    if _db_logger is None:
        try:
            from ..logging import get_logger
            _db_logger = get_logger("database")
        except Exception:
            _db_logger = logging.getLogger("jarvis.database")
    return _db_logger


def _get_migration_logger():
    """Get the migration logger, initializing if needed."""
    global _migration_logger
    if _migration_logger is None:
        try:
            from ..logging import get_logger
            _migration_logger = get_logger("migrations")
        except Exception:
            _migration_logger = logging.getLogger("jarvis.migrations")
    return _migration_logger


# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_credentials_from_secrets_manager() -> dict:
    """Fetch database credentials from AWS Secrets Manager."""
    import boto3

    secret_name = os.getenv("DB_SECRET_NAME", "jarvis/aurora-credentials")
    region = os.getenv("AWS_REGION", "us-west-2")

    _get_db_logger().debug(f"Fetching credentials from Secrets Manager: {secret_name}")
    client = boto3.client("secretsmanager", region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    _get_db_logger().debug("Credentials retrieved successfully")
    return json.loads(response["SecretString"])


async def init_db() -> asyncpg.Pool:
    """Initialize the database connection pool."""
    global _pool

    if _pool is not None:
        _get_db_logger().debug("Connection pool already initialized")
        return _pool

    # Check for direct DATABASE_URL first (local dev)
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        _get_db_logger().info("Connecting to database via DATABASE_URL")
        # Mask password in log
        masked_url = database_url.split('@')[-1] if '@' in database_url else database_url
        _get_db_logger().debug(f"Database host: {masked_url}")
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
        )
    else:
        _get_db_logger().info("Connecting to database via AWS Secrets Manager")
        # Use AWS Secrets Manager
        creds = await get_credentials_from_secrets_manager()
        _get_db_logger().debug(f"Connecting to {creds['host']}:{creds.get('port', 5432)}")
        _pool = await asyncpg.create_pool(
            host=creds["host"],
            port=creds.get("port", 5432),
            user=creds["username"],
            password=creds["password"],
            database=creds.get("database", "jarvis"),
            min_size=2,
            max_size=10,
        )

    _get_db_logger().info("Database connection pool created (min=2, max=10)")

    # Run migrations on startup
    await run_migrations(_pool)

    return _pool


async def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool, initializing if needed."""
    global _pool
    if _pool is None:
        _pool = await init_db()
    return _pool


async def close_db():
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        _get_db_logger().info("Closing database connection pool")
        await _pool.close()
        _pool = None
        _get_db_logger().debug("Connection pool closed")


@asynccontextmanager
async def get_connection():
    """Get a database connection from the pool."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn


async def run_migrations(pool: asyncpg.Pool):
    """Run database migrations."""
    _get_migration_logger().info("Checking for pending migrations...")

    async with pool.acquire() as conn:
        # Create migrations tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Get applied migrations
        applied = set(
            row["name"]
            for row in await conn.fetch("SELECT name FROM _migrations")
        )

        # Define migrations in order
        migrations = [
            ("001_create_tasks", MIGRATION_001_CREATE_TASKS),
            ("002_create_work_sessions", MIGRATION_002_CREATE_WORK_SESSIONS),
            ("003_create_projects", MIGRATION_003_CREATE_PROJECTS),
            ("004_create_knowledgebase_schema", MIGRATION_004_CREATE_KNOWLEDGEBASE_SCHEMA),
            ("005_create_organization_schema", MIGRATION_005_CREATE_ORGANIZATION_SCHEMA),
            ("006_create_projects_schema", MIGRATION_006_CREATE_PROJECTS_SCHEMA),
            ("007_rename_knowledgebase_to_knowledge", MIGRATION_007_RENAME_KNOWLEDGEBASE_TO_KNOWLEDGE),
            ("008_create_vault_schema", MIGRATION_008_CREATE_VAULT_SCHEMA),
            ("009_vault_encryption", MIGRATION_009_VAULT_ENCRYPTION),
            ("010_create_identity_schema", MIGRATION_010_CREATE_IDENTITY_SCHEMA),
            ("011_create_orchestration_schema", MIGRATION_011_CREATE_ORCHESTRATION_SCHEMA),
        ]

        # Count pending migrations
        pending = [m for m in migrations if m[0] not in applied]
        if pending:
            _get_migration_logger().info(f"Found {len(pending)} pending migration(s)")
        else:
            _get_migration_logger().info("All migrations up to date")

        # Apply new migrations
        for name, sql in migrations:
            if name not in applied:
                _get_migration_logger().info(f"Applying migration: {name}")
                try:
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO _migrations (name) VALUES ($1)",
                        name
                    )
                    _get_migration_logger().info(f"Migration {name} applied successfully")
                except Exception as e:
                    _get_migration_logger().error(f"Migration {name} failed: {e}")
                    raise


# Migration SQL
MIGRATION_001_CREATE_TASKS = """
-- Tasks: Work items / requests to do something
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, in_progress, blocked, completed, cancelled
    priority INTEGER NOT NULL DEFAULT 50,     -- 0-100, higher = more urgent

    -- Source tracking (where did this task come from?)
    source TEXT NOT NULL DEFAULT 'manual',    -- manual, jira, salesforce, github, claude_code
    source_id TEXT,                           -- External ID (JIRA-123, etc.)
    source_url TEXT,                          -- Link to external system

    -- Assignment
    assigned_to TEXT,                         -- Who/what is working on this (worker_id, agent_id, etc.)

    -- Categorization
    tags TEXT[] DEFAULT '{}',
    project TEXT,                             -- Project this task belongs to

    -- Estimation & tracking
    estimated_hours FLOAT,
    actual_hours FLOAT,

    -- Relationships
    parent_task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,  -- For subtasks
    blocked_by UUID[] DEFAULT '{}',           -- Task IDs that block this one

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    due_date TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_source ON tasks(source, source_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks;
CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""

MIGRATION_002_CREATE_WORK_SESSIONS = """
-- Work sessions: Track time spent working on tasks
CREATE TABLE IF NOT EXISTS work_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    worker_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status TEXT,      -- completed, blocked, interrupted, paused
    notes TEXT,
    hours_logged FLOAT  -- Can be auto-calculated or manually set
);

CREATE INDEX IF NOT EXISTS idx_work_sessions_task ON work_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_work_sessions_worker ON work_sessions(worker_id);
CREATE INDEX IF NOT EXISTS idx_work_sessions_active ON work_sessions(worker_id)
    WHERE ended_at IS NULL;
"""

MIGRATION_003_CREATE_PROJECTS = """
-- Projects: Grouping for tasks and knowledge entries
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',  -- active, archived, on_hold

    -- Categorization
    tags TEXT[] DEFAULT '{}',

    -- External links
    repository_url TEXT,                    -- GitHub/GitLab repo
    jira_project_key TEXT,                  -- JIRA project key
    salesforce_account_id TEXT,             -- Salesforce account

    -- Metadata
    metadata JSONB DEFAULT '{}',            -- Flexible additional data

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_tags ON projects USING GIN(tags);

DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add foreign key from tasks to projects (alter existing table)
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES projects(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
"""

MIGRATION_004_CREATE_KNOWLEDGEBASE_SCHEMA = """
-- Create knowledgebase schema
CREATE SCHEMA IF NOT EXISTS knowledgebase;

-- Knowledge entries: Represents a knowledge article/document
CREATE TABLE IF NOT EXISTS knowledgebase.entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    title TEXT NOT NULL,
    content TEXT NOT NULL,                  -- Markdown content
    summary TEXT,                           -- Brief summary for index

    -- Path info (mirrors file system structure)
    path TEXT NOT NULL UNIQUE,              -- e.g., 'technical/tools/github.md'
    category TEXT NOT NULL,                 -- Top-level: agents, skills, knowledge

    -- Classification
    entry_type TEXT NOT NULL DEFAULT 'knowledge',  -- agent, skill, knowledge
    tags TEXT[] DEFAULT '{}',

    -- Relationships
    project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL,
    related_entries UUID[] DEFAULT '{}',    -- Links to other entries

    -- Source tracking
    source_file TEXT,                       -- Original file path on disk
    source_repo TEXT,                       -- Git repo URL
    last_synced_at TIMESTAMPTZ,             -- When last synced from file
    file_hash TEXT,                         -- Hash of source file for change detection

    -- Metadata
    metadata JSONB DEFAULT '{}',            -- Flexible additional data (author, version, etc.)

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entries_path ON knowledgebase.entries(path);
CREATE INDEX IF NOT EXISTS idx_entries_category ON knowledgebase.entries(category);
CREATE INDEX IF NOT EXISTS idx_entries_entry_type ON knowledgebase.entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_entries_tags ON knowledgebase.entries USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_entries_project ON knowledgebase.entries(project_id);
CREATE INDEX IF NOT EXISTS idx_entries_content_search ON knowledgebase.entries
    USING GIN(to_tsvector('english', title || ' ' || COALESCE(summary, '') || ' ' || content));

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION knowledgebase.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_entries_updated_at ON knowledgebase.entries;
CREATE TRIGGER update_entries_updated_at
    BEFORE UPDATE ON knowledgebase.entries
    FOR EACH ROW
    EXECUTE FUNCTION knowledgebase.update_updated_at_column();
"""

MIGRATION_005_CREATE_ORGANIZATION_SCHEMA = """
-- Create organization schema for multi-tenant organization with namespaces and labels
CREATE SCHEMA IF NOT EXISTS organization;

-- Namespaces: Top-level organization groupings (e.g., Personal, Mecano Consulting LLC, etc.)
CREATE TABLE IF NOT EXISTS organization.namespaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_namespaces_name ON organization.namespaces(name);

-- Labels: Flexible categorization within namespaces, with optional hierarchy
CREATE TABLE IF NOT EXISTS organization.labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace_id UUID NOT NULL REFERENCES organization.namespaces(id) ON DELETE CASCADE,
    parent_label_id UUID REFERENCES organization.labels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT,  -- Optional color for UI display (e.g., "#FF5733")
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(namespace_id, name, parent_label_id)
);

CREATE INDEX IF NOT EXISTS idx_labels_namespace ON organization.labels(namespace_id);
CREATE INDEX IF NOT EXISTS idx_labels_parent ON organization.labels(parent_label_id);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION organization.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_namespaces_updated_at ON organization.namespaces;
CREATE TRIGGER update_namespaces_updated_at
    BEFORE UPDATE ON organization.namespaces
    FOR EACH ROW
    EXECUTE FUNCTION organization.update_updated_at_column();

DROP TRIGGER IF EXISTS update_labels_updated_at ON organization.labels;
CREATE TRIGGER update_labels_updated_at
    BEFORE UPDATE ON organization.labels
    FOR EACH ROW
    EXECUTE FUNCTION organization.update_updated_at_column();

-- Insert default namespaces
INSERT INTO organization.namespaces (name, description) VALUES
    ('Personal', 'Personal projects and tasks'),
    ('Mecano Consulting LLC', 'Consulting projects and client work'),
    ('Mecano Labs', 'Research and experimental projects'),
    ('Public', 'Open source and public projects')
ON CONFLICT (name) DO NOTHING;
"""

MIGRATION_006_CREATE_PROJECTS_SCHEMA = """
-- Create projects schema and migrate the projects table
CREATE SCHEMA IF NOT EXISTS projects;

-- Move projects table to projects schema by creating new table and migrating data
CREATE TABLE IF NOT EXISTS projects.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace_id UUID NOT NULL REFERENCES organization.namespaces(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',  -- active, archived, on_hold

    -- Categorization
    tags TEXT[] DEFAULT '{}',

    -- External links
    repository_url TEXT,
    jira_project_key TEXT,
    salesforce_account_id TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at TIMESTAMPTZ,

    -- Name unique within namespace
    UNIQUE(namespace_id, name)
);

CREATE INDEX IF NOT EXISTS idx_projects_projects_namespace ON projects.projects(namespace_id);
CREATE INDEX IF NOT EXISTS idx_projects_projects_status ON projects.projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_projects_name ON projects.projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_projects_tags ON projects.projects USING GIN(tags);

-- Project labels junction table
CREATE TABLE IF NOT EXISTS projects.project_labels (
    project_id UUID NOT NULL REFERENCES projects.projects(id) ON DELETE CASCADE,
    label_id UUID NOT NULL REFERENCES organization.labels(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, label_id)
);

CREATE INDEX IF NOT EXISTS idx_project_labels_project ON projects.project_labels(project_id);
CREATE INDEX IF NOT EXISTS idx_project_labels_label ON projects.project_labels(label_id);

-- Trigger for updated_at on projects.projects
CREATE OR REPLACE FUNCTION projects.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_projects_projects_updated_at ON projects.projects;
CREATE TRIGGER update_projects_projects_updated_at
    BEFORE UPDATE ON projects.projects
    FOR EACH ROW
    EXECUTE FUNCTION projects.update_updated_at_column();

-- Migrate existing data from public.projects if the table exists and has data
DO $$
DECLARE
    default_namespace_id UUID;
BEGIN
    -- Get the first namespace (Personal) as default
    SELECT id INTO default_namespace_id FROM organization.namespaces WHERE name = 'Personal' LIMIT 1;

    -- Check if public.projects exists and has data to migrate
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'projects') THEN
        -- Migrate existing projects to new schema
        INSERT INTO projects.projects (id, namespace_id, name, description, status, tags, repository_url, jira_project_key, salesforce_account_id, metadata, created_at, updated_at, archived_at)
        SELECT id, default_namespace_id, name, description, status, tags, repository_url, jira_project_key, salesforce_account_id, metadata, created_at, updated_at, archived_at
        FROM public.projects
        ON CONFLICT (id) DO NOTHING;

        -- Update tasks to reference new projects table (project_id column already exists)
        -- The foreign key will be recreated below
    END IF;
END $$;

-- Update tasks foreign key to reference projects.projects
ALTER TABLE public.tasks DROP CONSTRAINT IF EXISTS tasks_project_id_fkey;
ALTER TABLE public.tasks
    ADD CONSTRAINT tasks_project_id_fkey
    FOREIGN KEY (project_id) REFERENCES projects.projects(id) ON DELETE SET NULL;

-- Update knowledgebase.entries foreign key to reference projects.projects
ALTER TABLE knowledgebase.entries DROP CONSTRAINT IF EXISTS entries_project_id_fkey;
ALTER TABLE knowledgebase.entries
    ADD CONSTRAINT entries_project_id_fkey
    FOREIGN KEY (project_id) REFERENCES projects.projects(id) ON DELETE SET NULL;

-- Drop old projects table from public schema (keep as backup for now, can drop later)
-- DROP TABLE IF EXISTS public.projects;
"""

MIGRATION_007_RENAME_KNOWLEDGEBASE_TO_KNOWLEDGE = """
-- Rename knowledgebase schema to knowledge and add namespace_id field
-- This provides direct namespace association for entries (even if also linked via project)

-- Rename the schema
ALTER SCHEMA knowledgebase RENAME TO knowledge;

-- Add namespace_id column to entries (optional - can be inferred from project)
ALTER TABLE knowledge.entries
    ADD COLUMN IF NOT EXISTS namespace_id UUID REFERENCES organization.namespaces(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_entries_namespace ON knowledge.entries(namespace_id);

-- Update the trigger function to use the new schema name
CREATE OR REPLACE FUNCTION knowledge.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Recreate the trigger with the new schema
DROP TRIGGER IF EXISTS update_entries_updated_at ON knowledge.entries;
CREATE TRIGGER update_entries_updated_at
    BEFORE UPDATE ON knowledge.entries
    FOR EACH ROW
    EXECUTE FUNCTION knowledge.update_updated_at_column();
"""

MIGRATION_008_CREATE_VAULT_SCHEMA = """
-- Create vault schema for secure item storage with folder organization
CREATE SCHEMA IF NOT EXISTS vault;

-- Folders: Hierarchical organization within namespaces
CREATE TABLE IF NOT EXISTS vault.folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace_id UUID NOT NULL REFERENCES organization.namespaces(id) ON DELETE CASCADE,
    parent_folder_id UUID REFERENCES vault.folders(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(namespace_id, parent_folder_id, name)
);

CREATE INDEX IF NOT EXISTS idx_vault_folders_namespace ON vault.folders(namespace_id);
CREATE INDEX IF NOT EXISTS idx_vault_folders_parent ON vault.folders(parent_folder_id);

-- Items: Stored items within the vault
CREATE TABLE IF NOT EXISTS vault.items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace_id UUID NOT NULL REFERENCES organization.namespaces(id) ON DELETE CASCADE,
    folder_id UUID REFERENCES vault.folders(id) ON DELETE SET NULL,

    -- Item identification
    name TEXT NOT NULL,
    item_type TEXT NOT NULL DEFAULT 'secret',  -- secret, credential, api_key, certificate, note, etc.

    -- Content (encrypted in practice)
    content TEXT,                              -- The actual secret/value

    -- Metadata
    description TEXT,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',               -- Flexible additional data (rotation policy, expiry, etc.)

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,                    -- Optional expiration
    last_accessed_at TIMESTAMPTZ,

    UNIQUE(namespace_id, folder_id, name)
);

CREATE INDEX IF NOT EXISTS idx_vault_items_namespace ON vault.items(namespace_id);
CREATE INDEX IF NOT EXISTS idx_vault_items_folder ON vault.items(folder_id);
CREATE INDEX IF NOT EXISTS idx_vault_items_type ON vault.items(item_type);
CREATE INDEX IF NOT EXISTS idx_vault_items_tags ON vault.items USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_vault_items_expires ON vault.items(expires_at) WHERE expires_at IS NOT NULL;

-- Trigger function for vault schema
CREATE OR REPLACE FUNCTION vault.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_vault_folders_updated_at ON vault.folders;
CREATE TRIGGER update_vault_folders_updated_at
    BEFORE UPDATE ON vault.folders
    FOR EACH ROW
    EXECUTE FUNCTION vault.update_updated_at_column();

DROP TRIGGER IF EXISTS update_vault_items_updated_at ON vault.items;
CREATE TRIGGER update_vault_items_updated_at
    BEFORE UPDATE ON vault.items
    FOR EACH ROW
    EXECUTE FUNCTION vault.update_updated_at_column();
"""

MIGRATION_009_VAULT_ENCRYPTION = """
-- Add client-side encryption support to vault
-- Master key table stores password hash and salt for key derivation

-- Master key table (single row for global vault password)
CREATE TABLE IF NOT EXISTS vault.master_key (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    password_hash TEXT NOT NULL,        -- Argon2id hash for verification
    salt TEXT NOT NULL,                 -- Base64 salt for PBKDF2 key derivation
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger for updated_at on master_key
DROP TRIGGER IF EXISTS update_vault_master_key_updated_at ON vault.master_key;
CREATE TRIGGER update_vault_master_key_updated_at
    BEFORE UPDATE ON vault.master_key
    FOR EACH ROW
    EXECUTE FUNCTION vault.update_updated_at_column();

-- Add encryption columns to vault.items
ALTER TABLE vault.items
    ADD COLUMN IF NOT EXISTS encrypted_data TEXT,
    ADD COLUMN IF NOT EXISTS iv TEXT;

-- Migrate existing content to encrypted_data (will be plaintext until re-encrypted)
UPDATE vault.items
SET encrypted_data = content
WHERE content IS NOT NULL AND encrypted_data IS NULL;

-- Drop the plain content column (data migrated to encrypted_data)
ALTER TABLE vault.items DROP COLUMN IF EXISTS content;
"""

MIGRATION_010_CREATE_IDENTITY_SCHEMA = """
-- Create identity schema for user management
CREATE SCHEMA IF NOT EXISTS identity;

-- Users table: Core user identity with vault master key
CREATE TABLE IF NOT EXISTS identity.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    email TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,

    -- Vault master key (nullable - set when user configures vault)
    password_hash TEXT,              -- Argon2id hash for verification
    salt TEXT,                       -- Base64 salt for PBKDF2 key derivation

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_identity_users_email ON identity.users(email);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION identity.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_identity_users_updated_at ON identity.users;
CREATE TRIGGER update_identity_users_updated_at
    BEFORE UPDATE ON identity.users
    FOR EACH ROW
    EXECUTE FUNCTION identity.update_updated_at_column();

-- Migrate existing vault.master_key data to identity.users if exists
-- (Creates a placeholder user for existing vault setups)
DO $$
DECLARE
    existing_master_key RECORD;
BEGIN
    SELECT password_hash, salt, created_at INTO existing_master_key
    FROM vault.master_key LIMIT 1;

    IF existing_master_key.password_hash IS NOT NULL THEN
        INSERT INTO identity.users (email, first_name, last_name, password_hash, salt, created_at)
        VALUES ('owner@jarvis.local', 'Jarvis', 'Owner',
                existing_master_key.password_hash, existing_master_key.salt,
                existing_master_key.created_at)
        ON CONFLICT (email) DO NOTHING;
    END IF;
END $$;

-- Drop the old vault.master_key table (data migrated to identity.users)
DROP TABLE IF EXISTS vault.master_key;
"""

MIGRATION_011_CREATE_ORCHESTRATION_SCHEMA = """
-- Create orchestration schema for workflow management (LangGraph-style)
CREATE SCHEMA IF NOT EXISTS orchestration;

-- Workflows: Define reusable workflow templates
CREATE TABLE IF NOT EXISTS orchestration.workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace_id UUID REFERENCES organization.namespaces(id) ON DELETE SET NULL,

    -- Identity
    name TEXT NOT NULL,
    description TEXT,
    version TEXT NOT NULL DEFAULT '1.0.0',

    -- Status
    status TEXT NOT NULL DEFAULT 'draft',  -- draft, active, archived, deprecated
    is_template BOOLEAN NOT NULL DEFAULT FALSE,  -- Can be cloned/forked

    -- Configuration
    config JSONB DEFAULT '{}',              -- Entry point, checkpointer settings, etc.

    -- Metadata
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,               -- When made active

    UNIQUE(namespace_id, name, version)
);

CREATE INDEX IF NOT EXISTS idx_orchestration_workflows_namespace ON orchestration.workflows(namespace_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_workflows_status ON orchestration.workflows(status);
CREATE INDEX IF NOT EXISTS idx_orchestration_workflows_name ON orchestration.workflows(name);
CREATE INDEX IF NOT EXISTS idx_orchestration_workflows_tags ON orchestration.workflows USING GIN(tags);

-- Nodes: Individual steps/states in a workflow
CREATE TABLE IF NOT EXISTS orchestration.nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES orchestration.workflows(id) ON DELETE CASCADE,

    -- Identity
    name TEXT NOT NULL,                     -- Node identifier (e.g., 'check_revenue', 'pick_ticket')
    display_name TEXT,                      -- Human-readable name
    description TEXT,

    -- Node type and behavior
    node_type TEXT NOT NULL DEFAULT 'action',  -- action, condition, subgraph, tool, human_input, start, end

    -- Execution
    handler TEXT,                           -- Python function/class path (e.g., 'src.nodes.revenue.check_revenue')
    config JSONB DEFAULT '{}',              -- Node-specific configuration

    -- Position for visual editor
    position_x FLOAT DEFAULT 0,
    position_y FLOAT DEFAULT 0,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(workflow_id, name)
);

CREATE INDEX IF NOT EXISTS idx_orchestration_nodes_workflow ON orchestration.nodes(workflow_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_nodes_type ON orchestration.nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_orchestration_nodes_name ON orchestration.nodes(name);

-- Edges: Connections between nodes (transitions)
CREATE TABLE IF NOT EXISTS orchestration.edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES orchestration.workflows(id) ON DELETE CASCADE,

    -- Connection
    source_node_id UUID NOT NULL REFERENCES orchestration.nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES orchestration.nodes(id) ON DELETE CASCADE,

    -- Edge properties
    name TEXT,                              -- Optional edge label
    condition TEXT,                         -- Condition expression (for conditional routing)
    priority INTEGER DEFAULT 0,             -- For ordering when multiple edges from same source

    -- Edge type
    edge_type TEXT NOT NULL DEFAULT 'default',  -- default, conditional, fallback

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orchestration_edges_workflow ON orchestration.edges(workflow_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_edges_source ON orchestration.edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_edges_target ON orchestration.edges(target_node_id);

-- Unique index to prevent duplicate edges (using COALESCE for nullable condition)
CREATE UNIQUE INDEX IF NOT EXISTS idx_orchestration_edges_unique
    ON orchestration.edges(workflow_id, source_node_id, target_node_id, COALESCE(condition, ''));

-- Trigger function for orchestration schema
CREATE OR REPLACE FUNCTION orchestration.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_orchestration_workflows_updated_at ON orchestration.workflows;
CREATE TRIGGER update_orchestration_workflows_updated_at
    BEFORE UPDATE ON orchestration.workflows
    FOR EACH ROW
    EXECUTE FUNCTION orchestration.update_updated_at_column();

DROP TRIGGER IF EXISTS update_orchestration_nodes_updated_at ON orchestration.nodes;
CREATE TRIGGER update_orchestration_nodes_updated_at
    BEFORE UPDATE ON orchestration.nodes
    FOR EACH ROW
    EXECUTE FUNCTION orchestration.update_updated_at_column();

DROP TRIGGER IF EXISTS update_orchestration_edges_updated_at ON orchestration.edges;
CREATE TRIGGER update_orchestration_edges_updated_at
    BEFORE UPDATE ON orchestration.edges
    FOR EACH ROW
    EXECUTE FUNCTION orchestration.update_updated_at_column();
"""
