"""
Revenue check node.

Fetches hours billed this month from Harvest API and compares to target.
"""
from datetime import datetime
import httpx
import os

from ..state import OrchestratorState, RevenueStatus


async def get_harvest_hours_this_month() -> tuple[float, list[dict]]:
    """
    Fetch hours billed this month from Harvest API.

    Returns:
        Tuple of (total_hours, list of time entries)
    """
    account_id = os.getenv("HARVEST_ACCOUNT_ID")
    api_token = os.getenv("HARVEST_API_TOKEN")

    if not account_id or not api_token:
        raise ValueError("HARVEST_ACCOUNT_ID and HARVEST_API_TOKEN must be set")

    # Get first day of current month
    today = datetime.now()
    first_of_month = today.replace(day=1).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Harvest-Account-Id": account_id,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.harvestapp.com/v2/time_entries",
            headers=headers,
            params={
                "from": first_of_month,
                "to": today_str,
            }
        )
        response.raise_for_status()
        data = response.json()

    entries = data.get("time_entries", [])
    total_hours = sum(entry.get("hours", 0) for entry in entries)

    return total_hours, entries


def check_revenue(state: OrchestratorState) -> OrchestratorState:
    """
    Check monthly revenue status against target.

    This is a synchronous wrapper - in production, we'd make this async.
    For now, we'll use a placeholder that can be swapped out.
    """
    import asyncio

    # Load target from config (placeholder - will load from YAML)
    target_hours = float(os.getenv("MONTHLY_TARGET_HOURS", "120"))

    try:
        # Run async function
        billed_hours, _ = asyncio.run(get_harvest_hours_this_month())
    except Exception as e:
        # If Harvest fails, assume we need to work on consulting
        billed_hours = 0
        state["thought_log"].append(f"Warning: Could not fetch Harvest data: {e}")

    remaining = target_hours - billed_hours
    is_below = remaining > 0

    month = datetime.now().strftime("%Y-%m")

    revenue_status: RevenueStatus = {
        "target_hours": target_hours,
        "billed_hours": billed_hours,
        "remaining_hours": max(0, remaining),
        "is_below_target": is_below,
        "month": month,
    }

    thought = f"Revenue check: {billed_hours:.1f}/{target_hours:.1f} hours billed this month."
    if is_below:
        thought += f" Need {remaining:.1f} more hours. Prioritizing consulting work."
    else:
        thought += " Target met! Can work on product/personal projects."

    return {
        **state,
        "revenue_status": revenue_status,
        "thought_log": state["thought_log"] + [thought],
    }
