"""
Ticket fetching, ranking, and selection nodes.
"""
import os
from datetime import datetime
from typing import Literal
import httpx
import yaml

from ..state import OrchestratorState, TicketInfo


def load_priorities_config() -> dict:
    """Load priorities configuration from YAML."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "..", "config", "priorities.yaml"
    )
    try:
        with open(config_path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {"clients": {}, "projects": {}, "scoring": {}}


async def fetch_jira_tickets(project_keys: list[str]) -> list[dict]:
    """
    Fetch open tickets from JIRA for given project keys.
    """
    jira_url = os.getenv("JIRA_URL")
    jira_email = os.getenv("JIRA_EMAIL")
    jira_token = os.getenv("JIRA_API_TOKEN")

    if not all([jira_url, jira_email, jira_token]):
        raise ValueError("JIRA credentials not configured")

    # Build JQL for all projects
    project_jql = " OR ".join([f"project = {key}" for key in project_keys])
    jql = f"({project_jql}) AND status NOT IN (Done, Closed, Resolved) ORDER BY updated DESC"

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{jira_url}/rest/api/3/search",
            auth=(jira_email, jira_token),
            params={
                "jql": jql,
                "maxResults": 100,
                "fields": "summary,status,priority,created,updated,labels,assignee,timeestimate,project,issuetype"
            }
        )
        response.raise_for_status()
        data = response.json()

    return data.get("issues", [])


def jira_to_ticket_info(issue: dict, config: dict) -> TicketInfo:
    """Convert JIRA issue to our TicketInfo format."""
    fields = issue.get("fields", {})
    project_key = fields.get("project", {}).get("key", "")
    project_name = fields.get("project", {}).get("name", "")

    # Map JIRA issue type to our types
    issue_type = fields.get("issuetype", {}).get("name", "").lower()
    if "bug" in issue_type:
        ticket_type = "bug"
    elif "feature" in issue_type or "story" in issue_type:
        ticket_type = "feature"
    elif "question" in issue_type or "support" in issue_type:
        ticket_type = "question"
    else:
        ticket_type = "task"

    # Get labels
    labels = [label for label in fields.get("labels", [])]

    # Estimate completion (placeholder - could check subtasks, linked PRs, etc.)
    completion_pct = 0.0

    return {
        "key": issue.get("key", ""),
        "source": "jira",
        "project": project_name,
        "summary": fields.get("summary", ""),
        "status": fields.get("status", {}).get("name", ""),
        "ticket_type": ticket_type,
        "priority_score": 0.0,  # Will be calculated in rank_tickets
        "created_date": fields.get("created", ""),
        "updated_date": fields.get("updated", ""),
        "labels": labels,
        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
        "estimated_hours": (fields.get("timeestimate") or 0) / 3600 if fields.get("timeestimate") else None,
        "completion_pct": completion_pct,
    }


def fetch_tickets(state: OrchestratorState, source: Literal["jira", "salesforce"]) -> OrchestratorState:
    """
    Fetch tickets from the appropriate source.
    """
    import asyncio

    config = load_priorities_config()
    tickets: list[TicketInfo] = []

    if source == "jira":
        # Get all configured client project keys
        project_keys = [
            client_config.get("jira_project_key")
            for client_config in config.get("clients", {}).values()
            if client_config.get("jira_project_key")
        ]

        if project_keys:
            try:
                jira_issues = asyncio.run(fetch_jira_tickets(project_keys))
                tickets = [jira_to_ticket_info(issue, config) for issue in jira_issues]
            except Exception as e:
                state["thought_log"].append(f"Error fetching JIRA tickets: {e}")

    elif source == "salesforce":
        # TODO: Implement Salesforce/AdminPro ticket fetching
        # For now, placeholder
        state["thought_log"].append("Salesforce ticket fetching not yet implemented")

    thought = f"Fetched {len(tickets)} tickets from {source}"
    if tickets:
        projects = set(t["project"] for t in tickets)
        thought += f" across projects: {', '.join(projects)}"

    return {
        **state,
        "ticket_queue": tickets,
        "thought_log": state["thought_log"] + [thought],
    }


def calculate_priority_score(ticket: TicketInfo, config: dict) -> float:
    """
    Calculate priority score for a ticket based on configured weights.

    Formula:
        score = client_weight
              + (revenue_potential * revenue_weight)
              + (completion_pct * completion_weight)
              + (age_days * age_weight)
              + urgency_boost (if urgent)
              + blocker_boost (if blocking others)
    """
    scoring = config.get("scoring", {})
    clients = config.get("clients", {})

    # Base score from client priority
    client_weight = 0
    for client_name, client_config in clients.items():
        if client_name.lower() in ticket["project"].lower():
            client_weight = client_config.get("weight", 50)
            break

    # Revenue potential (estimated hours)
    revenue_weight = scoring.get("revenue_weight", 10)
    revenue_score = (ticket.get("estimated_hours") or 1) * revenue_weight

    # Completion proximity (higher = closer to done = prioritize finishing)
    completion_weight = scoring.get("completion_weight", 50)
    completion_score = (ticket.get("completion_pct") or 0) / 100 * completion_weight

    # Age factor (days since created)
    age_weight = scoring.get("age_weight", 0.5)
    try:
        created = datetime.fromisoformat(ticket["created_date"].replace("Z", "+00:00"))
        age_days = (datetime.now(created.tzinfo) - created).days
    except:
        age_days = 0
    age_score = age_days * age_weight

    # Urgency boost
    urgency_boost = scoring.get("urgency_boost", 100)
    urgent_labels = ["urgent", "critical", "blocker", "high-priority"]
    has_urgency = any(label.lower() in urgent_labels for label in ticket.get("labels", []))
    urgency_score = urgency_boost if has_urgency else 0

    # Blocker boost (if ticket is blocking others)
    blocker_boost = scoring.get("blocker_boost", 75)
    is_blocker = "blocker" in [l.lower() for l in ticket.get("labels", [])]
    blocker_score = blocker_boost if is_blocker else 0

    total = client_weight + revenue_score + completion_score + age_score + urgency_score + blocker_score

    return round(total, 2)


def rank_tickets(state: OrchestratorState) -> OrchestratorState:
    """
    Rank tickets by priority score.
    """
    config = load_priorities_config()

    # Calculate scores
    scored_tickets = []
    for ticket in state["ticket_queue"]:
        score = calculate_priority_score(ticket, config)
        scored_tickets.append({**ticket, "priority_score": score})

    # Sort by score descending
    scored_tickets.sort(key=lambda t: t["priority_score"], reverse=True)

    # Log top 5 for visibility
    top_5 = scored_tickets[:5]
    thought = "Ranked tickets by priority:\n"
    for i, t in enumerate(top_5, 1):
        thought += f"  {i}. [{t['key']}] {t['summary'][:50]}... (score: {t['priority_score']})\n"

    return {
        **state,
        "ticket_queue": scored_tickets,
        "thought_log": state["thought_log"] + [thought],
    }


def select_ticket(state: OrchestratorState) -> OrchestratorState:
    """
    Select the top-ranked ticket to work on.
    """
    if not state["ticket_queue"]:
        return {
            **state,
            "current_ticket": None,
            "thought_log": state["thought_log"] + ["No tickets to select."],
        }

    selected = state["ticket_queue"][0]
    remaining = state["ticket_queue"][1:]

    thought = f"Selected ticket: [{selected['key']}] {selected['summary']}"
    thought += f"\n  Type: {selected['ticket_type']}, Project: {selected['project']}, Score: {selected['priority_score']}"

    return {
        **state,
        "current_ticket": selected,
        "ticket_queue": remaining,
        "thought_log": state["thought_log"] + [thought],
    }
