"""
Session Orchestrator Graph

This is the main LangGraph that decides what to work on.

Flow:
    [check_revenue]
        → [determine_work_type]
        → [fetch_tickets]
        → [rank_tickets]
        → [select_ticket]
        → [launch_worker]
        → [monitor_worker]
        → (loop back or complete)
"""
from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import OrchestratorState
from .nodes.revenue import check_revenue
from .nodes.routing import determine_work_type
from .nodes.tickets import fetch_tickets, rank_tickets, select_ticket
from .nodes.worker import launch_worker, monitor_worker


def should_work_consulting(state: OrchestratorState) -> Literal["fetch_consulting", "fetch_product"]:
    """Route based on revenue status."""
    if state["work_type"] == "consulting":
        return "fetch_consulting"
    return "fetch_product"


def has_tickets(state: OrchestratorState) -> Literal["rank", "no_tickets"]:
    """Check if we have tickets to work on."""
    if state["ticket_queue"] and len(state["ticket_queue"]) > 0:
        return "rank"
    return "no_tickets"


def worker_status(state: OrchestratorState) -> Literal["continue", "complete", "blocked", "error"]:
    """Check worker status after monitoring."""
    if state.get("error"):
        return "error"
    if state.get("worker_state", {}).get("status") == "blocked":
        return "blocked"
    if state.get("worker_state", {}).get("status") == "complete":
        return "complete"
    return "continue"


def build_orchestrator_graph() -> StateGraph:
    """
    Build and return the Session Orchestrator graph.
    """
    # Create the graph with our state schema
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("check_revenue", check_revenue)
    graph.add_node("determine_work_type", determine_work_type)
    graph.add_node("fetch_consulting_tickets", lambda s: fetch_tickets(s, source="jira"))
    graph.add_node("fetch_product_tickets", lambda s: fetch_tickets(s, source="salesforce"))
    graph.add_node("rank_tickets", rank_tickets)
    graph.add_node("select_ticket", select_ticket)
    graph.add_node("launch_worker", launch_worker)
    graph.add_node("monitor_worker", monitor_worker)
    graph.add_node("handle_no_tickets", lambda s: {**s, "thought_log": s["thought_log"] + ["No tickets found in queue. Session complete."]})
    graph.add_node("handle_blocked", lambda s: {**s, "thought_log": s["thought_log"] + [f"Ticket {s['current_ticket']['key']} is blocked. Moving to next ticket."]})
    graph.add_node("handle_error", lambda s: {**s, "thought_log": s["thought_log"] + [f"Error occurred: {s.get('error')}"]})

    # Set entry point
    graph.set_entry_point("check_revenue")

    # Add edges
    graph.add_edge("check_revenue", "determine_work_type")

    # Conditional: consulting vs product
    graph.add_conditional_edges(
        "determine_work_type",
        should_work_consulting,
        {
            "fetch_consulting": "fetch_consulting_tickets",
            "fetch_product": "fetch_product_tickets",
        }
    )

    # Both fetch paths lead to checking if we have tickets
    graph.add_conditional_edges(
        "fetch_consulting_tickets",
        has_tickets,
        {"rank": "rank_tickets", "no_tickets": "handle_no_tickets"}
    )
    graph.add_conditional_edges(
        "fetch_product_tickets",
        has_tickets,
        {"rank": "rank_tickets", "no_tickets": "handle_no_tickets"}
    )

    # Ranking and selection
    graph.add_edge("rank_tickets", "select_ticket")
    graph.add_edge("select_ticket", "launch_worker")
    graph.add_edge("launch_worker", "monitor_worker")

    # After monitoring, decide what to do
    graph.add_conditional_edges(
        "monitor_worker",
        worker_status,
        {
            "continue": "monitor_worker",      # Keep monitoring
            "complete": "check_revenue",       # Ticket done, pick next
            "blocked": "handle_blocked",       # Blocked, handle and move on
            "error": "handle_error",           # Error occurred
        }
    )

    # Blocked tickets: go back to ranking (will pick next in queue)
    graph.add_edge("handle_blocked", "rank_tickets")

    # End states
    graph.add_edge("handle_no_tickets", END)
    graph.add_edge("handle_error", END)

    return graph


async def create_orchestrator():
    """
    Create the orchestrator graph with memory checkpoint persistence.

    Note: For production, consider using SQLite or PostgreSQL checkpointer
    from langgraph-checkpoint-sqlite or langgraph-checkpoint-postgres packages.
    """
    graph = build_orchestrator_graph()

    # Set up memory checkpointer (in-memory, session-scoped)
    checkpointer = MemorySaver()

    # Compile the graph
    compiled = graph.compile(checkpointer=checkpointer)

    return compiled
