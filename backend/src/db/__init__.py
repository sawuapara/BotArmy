"""Database module for Jarvis task management."""

from .connection import get_db_pool, init_db, close_db
from .tasks import TaskRepository
from .models import (
    Task,
    TaskStatus,
    TaskSource,
    WorkSession,
    Project,
    ProjectStatus,
    KnowledgeEntry,
    EntryType,
    Namespace,
    Label,
    VaultFolder,
    VaultItem,
    VaultItemType,
)

__all__ = [
    "get_db_pool",
    "init_db",
    "close_db",
    "TaskRepository",
    "Task",
    "TaskStatus",
    "TaskSource",
    "WorkSession",
    "Project",
    "ProjectStatus",
    "KnowledgeEntry",
    "EntryType",
    "Namespace",
    "Label",
    "VaultFolder",
    "VaultItem",
    "VaultItemType",
]
