"""
Worker launch and monitoring nodes.

These nodes handle launching ticket-specific sub-workflows
and monitoring their progress.
"""
from ..state import OrchestratorState


def launch_worker(state: OrchestratorState) -> OrchestratorState:
    """
    Launch the appropriate worker workflow for the selected ticket.

    Based on ticket_type, we'll invoke different sub-graphs:
    - bug → BugWorker
    - feature → FeatureWorker
    - question → QuestionWorker
    - task → TaskWorker
    """
    ticket = state.get("current_ticket")

    if not ticket:
        return {
            **state,
            "error": "No ticket selected to work on",
            "thought_log": state["thought_log"] + ["Error: No ticket to launch worker for"],
        }

    ticket_type = ticket.get("ticket_type", "task")
    ticket_key = ticket.get("key")

    # Map ticket type to worker
    worker_map = {
        "bug": "bug_worker",
        "feature": "feature_worker",
        "question": "question_worker",
        "task": "task_worker",
    }

    worker_name = worker_map.get(ticket_type, "task_worker")

    thought = f"Launching {worker_name} for ticket [{ticket_key}]"
    thought += f"\n  Ticket type: {ticket_type}"
    thought += f"\n  Summary: {ticket.get('summary', '')[:80]}"

    # Initialize worker state
    worker_state = {
        "status": "running",
        "ticket_key": ticket_key,
        "ticket_type": ticket_type,
        "current_node": "start",
        "started_at": None,  # Will be set by worker
        "nodes_completed": [],
        "chain_of_thought": [],
    }

    return {
        **state,
        "active_worker": worker_name,
        "worker_state": worker_state,
        "current_node": "launch_worker",
        "thought_log": state["thought_log"] + [thought],
    }


def monitor_worker(state: OrchestratorState) -> OrchestratorState:
    """
    Monitor the running worker and check its status.

    This node will:
    1. Check if the worker sub-graph has completed
    2. Check for blocks or errors
    3. Stream progress updates to the UI

    For now, this is a placeholder that simulates worker completion.
    In the full implementation, this will invoke the actual sub-graph.
    """
    worker_state = state.get("worker_state", {})
    worker_name = state.get("active_worker")

    if not worker_state:
        return {
            **state,
            "error": "No worker state to monitor",
        }

    # TODO: Actually invoke/check sub-graph
    # For now, mark as complete for testing
    updated_worker_state = {
        **worker_state,
        "status": "complete",  # or "running", "blocked", "error"
        "current_node": "end",
    }

    thought = f"Worker {worker_name} completed for [{worker_state.get('ticket_key')}]"

    return {
        **state,
        "worker_state": updated_worker_state,
        "thought_log": state["thought_log"] + [thought],
    }
