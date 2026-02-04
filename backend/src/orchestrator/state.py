"""
State schema for the Session Orchestrator graph.

This defines the shared state that flows through all nodes.
"""
from typing import TypedDict, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime


class TicketInfo(TypedDict):
    """Information about a single ticket."""
    key: str                    # e.g., "MOL-483"
    source: str                 # "jira" or "salesforce"
    project: str                # e.g., "Moloco"
    summary: str
    status: str
    ticket_type: str            # "bug", "feature", "question", etc.
    priority_score: float       # Calculated score
    created_date: str
    updated_date: str
    labels: list[str]
    assignee: Optional[str]
    estimated_hours: Optional[float]
    completion_pct: Optional[float]


class RevenueStatus(TypedDict):
    """Monthly revenue/hours tracking."""
    target_hours: float
    billed_hours: float
    remaining_hours: float
    is_below_target: bool
    month: str                  # e.g., "2025-02"


class OrchestratorState(TypedDict):
    """
    Main state for the Session Orchestrator graph.

    This state is passed through all nodes and persisted at checkpoints.
    """
    # Session info
    session_id: str
    started_at: str

    # Revenue check results
    revenue_status: Optional[RevenueStatus]

    # Work type decision
    work_type: Optional[Literal["consulting", "product"]]

    # Ticket queue (sorted by priority)
    ticket_queue: list[TicketInfo]

    # Currently selected ticket
    current_ticket: Optional[TicketInfo]

    # Current node in the workflow
    current_node: str

    # Chain of thought / decision log
    thought_log: list[str]

    # Active sub-workflow (if ticket is being worked)
    active_worker: Optional[str]
    worker_state: Optional[dict]

    # Interrupts and paused work
    is_paused: bool
    paused_tickets: list[dict]  # Tickets that were interrupted

    # Errors
    error: Optional[str]


# Project queue for non-consulting work
class ProjectInfo(TypedDict):
    """Information about a priority project."""
    name: str
    weight: int
    source: str                 # "salesforce", "github", "local"
    active_tickets: int
    last_worked: Optional[str]
