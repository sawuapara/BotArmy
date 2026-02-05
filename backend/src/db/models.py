"""Database models for Jarvis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class ProjectStatus(str, Enum):
    """Status of a project."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    ON_HOLD = "on_hold"


@dataclass
class Namespace:
    """Represents an organization namespace."""
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Label:
    """Represents a label within a namespace."""
    id: UUID
    namespace_id: UUID
    name: str
    parent_label_id: Optional[UUID] = None
    color: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "namespace_id": str(self.namespace_id),
            "name": self.name,
            "parent_label_id": str(self.parent_label_id) if self.parent_label_id else None,
            "color": self.color,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class EntryType(str, Enum):
    """Type of knowledge entry."""
    AGENT = "agent"
    SKILL = "skill"
    KNOWLEDGE = "knowledge"


class TaskStatus(str, Enum):
    """Status of a task in the system."""
    PENDING = "pending"          # Not yet started
    IN_PROGRESS = "in_progress"  # Currently being worked on
    BLOCKED = "blocked"          # Blocked by dependency or external factor
    COMPLETED = "completed"      # Done
    CANCELLED = "cancelled"      # Won't be done


class TaskSource(str, Enum):
    """Source of the task."""
    MANUAL = "manual"            # Created manually in Jarvis
    JIRA = "jira"                # Synced from JIRA
    SALESFORCE = "salesforce"    # Synced from Salesforce
    GITHUB = "github"            # Synced from GitHub
    CLAUDE_CODE = "claude_code"  # Created by Claude Code


@dataclass
class Task:
    """Represents a work task in Jarvis."""
    id: UUID
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 50  # 0-100, higher = more urgent

    # Source tracking
    source: TaskSource = TaskSource.MANUAL
    source_id: Optional[str] = None
    source_url: Optional[str] = None

    # Assignment
    assigned_to: Optional[str] = None

    # Categorization
    tags: list[str] = field(default_factory=list)
    project: Optional[str] = None

    # Estimation & tracking
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None

    # Relationships
    parent_task_id: Optional[UUID] = None
    blocked_by: list[UUID] = field(default_factory=list)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    due_date: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "source": self.source.value,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "assigned_to": self.assigned_to,
            "tags": self.tags,
            "project": self.project,
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
            "parent_task_id": str(self.parent_task_id) if self.parent_task_id else None,
            "blocked_by": [str(b) for b in self.blocked_by],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }


@dataclass
class WorkSession:
    """Tracks a work session on a task."""
    id: UUID
    task_id: UUID
    worker_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    status: Optional[str] = None  # completed, blocked, interrupted, paused
    notes: Optional[str] = None
    hours_logged: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "worker_id": self.worker_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "notes": self.notes,
            "hours_logged": self.hours_logged,
        }


@dataclass
class Project:
    """Represents a project in Jarvis."""
    id: UUID
    name: str
    namespace_id: UUID
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.ACTIVE

    # Categorization
    tags: list[str] = field(default_factory=list)

    # External links
    repository_url: Optional[str] = None
    jira_project_key: Optional[str] = None
    salesforce_account_id: Optional[str] = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    archived_at: Optional[datetime] = None

    # Labels (populated separately)
    labels: list[Label] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "namespace_id": str(self.namespace_id),
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "tags": self.tags,
            "repository_url": self.repository_url,
            "jira_project_key": self.jira_project_key,
            "salesforce_account_id": self.salesforce_account_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "labels": [l.to_dict() for l in self.labels],
        }


@dataclass
class KnowledgeEntry:
    """Represents a knowledge entry in the knowledge schema."""
    id: UUID
    title: str
    content: str
    path: str
    category: str  # Top-level: agents, skills, knowledge

    summary: Optional[str] = None
    entry_type: EntryType = EntryType.KNOWLEDGE
    tags: list[str] = field(default_factory=list)

    # Organization
    namespace_id: Optional[UUID] = None  # Direct namespace association

    # Relationships
    project_id: Optional[UUID] = None
    related_entries: list[UUID] = field(default_factory=list)

    # Source tracking
    source_file: Optional[str] = None
    source_repo: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    file_hash: Optional[str] = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "path": self.path,
            "category": self.category,
            "entry_type": self.entry_type.value,
            "tags": self.tags,
            "namespace_id": str(self.namespace_id) if self.namespace_id else None,
            "project_id": str(self.project_id) if self.project_id else None,
            "related_entries": [str(e) for e in self.related_entries],
            "source_file": self.source_file,
            "source_repo": self.source_repo,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "file_hash": self.file_hash,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class User:
    """Represents a user in the identity schema."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    password_hash: Optional[str] = None  # Argon2id hash (set when vault configured)
    salt: Optional[str] = None  # Base64 salt for PBKDF2 key derivation
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None

    @property
    def vault_configured(self) -> bool:
        """Check if user has configured their vault master password."""
        return self.password_hash is not None and self.salt is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "vault_configured": self.vault_configured,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


class VaultItemType(str, Enum):
    """Type of vault item."""
    SECRET = "secret"
    CREDENTIAL = "credential"
    API_KEY = "api_key"
    CERTIFICATE = "certificate"
    NOTE = "note"


# Deprecated: VaultMasterKey moved to identity.users
@dataclass
class VaultMasterKey:
    """Represents the master key for vault encryption."""
    id: UUID
    password_hash: str
    salt: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class VaultFolder:
    """Represents a folder in the vault schema."""
    id: UUID
    namespace_id: UUID
    name: str
    parent_folder_id: Optional[UUID] = None
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "namespace_id": str(self.namespace_id),
            "parent_folder_id": str(self.parent_folder_id) if self.parent_folder_id else None,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class VaultItem:
    """Represents an item in the vault schema."""
    id: UUID
    namespace_id: UUID
    name: str
    item_type: VaultItemType = VaultItemType.SECRET
    folder_id: Optional[UUID] = None
    encrypted_data: Optional[str] = None  # AES-GCM encrypted JSON blob (base64)
    iv: Optional[str] = None  # Initialization vector (base64)
    description: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "namespace_id": str(self.namespace_id),
            "folder_id": str(self.folder_id) if self.folder_id else None,
            "name": self.name,
            "item_type": self.item_type.value,
            "encrypted_data": self.encrypted_data,
            "iv": self.iv,
            "description": self.description,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
        }

