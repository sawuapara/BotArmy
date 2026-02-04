"""
Work type routing node.

Determines whether to work on MecanoConsulting (billable) or Product work.
"""
from typing import Literal
from ..state import OrchestratorState


def determine_work_type(state: OrchestratorState) -> OrchestratorState:
    """
    Decide whether to work on consulting or product based on revenue status.

    Rules:
    1. If below monthly target → consulting work
    2. If at/above target → product work
    3. (Future) Minimum product hours per week override
    """
    revenue = state.get("revenue_status")

    if not revenue:
        # No revenue data, default to consulting (safer)
        work_type: Literal["consulting", "product"] = "consulting"
        thought = "No revenue data available. Defaulting to consulting work."
    elif revenue["is_below_target"]:
        work_type = "consulting"
        thought = f"Below target by {revenue['remaining_hours']:.1f} hours. Working on consulting."
    else:
        work_type = "product"
        thought = "Monthly target met! Switching to product/personal projects."

    return {
        **state,
        "work_type": work_type,
        "thought_log": state["thought_log"] + [thought],
    }
