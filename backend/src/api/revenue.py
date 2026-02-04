"""
Revenue API endpoints.

Provides comprehensive revenue data from Harvest for the dashboard.
"""
import os
import json
from datetime import datetime
from calendar import monthrange
from pathlib import Path
from typing import Optional

import httpx
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/revenue", tags=["revenue"])


# ---------- Pydantic Models ----------

class ClientRevenue(BaseModel):
    """Revenue breakdown for a single client."""
    client_name: str
    hours: float
    rate: float
    revenue: float


class RevenueMetrics(BaseModel):
    """Comprehensive revenue metrics for the dashboard."""
    # MTD (Month to Date) metrics
    mtd_hours: float
    mtd_revenue: float
    mtd_goal_hours: float
    mtd_goal_revenue: float
    mtd_gap_hours: float
    mtd_gap_revenue: float

    # Progress
    hours_progress_pct: float
    revenue_progress_pct: float

    # Forecast
    month_forecast_hours: float
    month_forecast_gross: float
    month_forecast_net: float
    month_forecast_annualized_gross: float
    month_forecast_annualized_net: float

    # Breakdown by client
    by_client: list[ClientRevenue]

    # Meta
    month: str
    days_elapsed: int
    days_in_month: int
    days_remaining: int
    last_updated: str


# ---------- Helper Functions ----------

def load_config() -> dict:
    """Load rates and targets configuration."""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "rates.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def get_harvest_credentials() -> tuple[str, str]:
    """Get Harvest API credentials from environment or config file."""
    account_id = os.getenv("HARVEST_ACCOUNT_ID")
    api_token = os.getenv("HARVEST_API_TOKEN")

    # Fall back to config file if env vars not set
    if not account_id or not api_token:
        config_path = Path(__file__).parent.parent.parent.parent.parent.parent / "scripts" / "harvest_config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                account_id = config.get("HARVEST_ACCOUNT_ID")
                api_token = config.get("HARVEST_API_TOKEN")

    if not account_id or not api_token:
        raise ValueError("Harvest credentials not configured")

    return account_id, api_token


def get_rate_for_entry(entry: dict, config: dict) -> float:
    """
    Determine the billing rate for a time entry.

    Uses client/project mapping and user-specific rates where applicable.
    """
    project_name = entry.get("project", {}).get("name", "").lower()
    user_name = entry.get("user", {}).get("name", "").lower()

    clients = config.get("clients", {})

    # Match project to client
    for client_key, client_config in clients.items():
        if client_key in project_name or client_config.get("display_name", "").lower() in project_name:
            rates = client_config.get("rates", {})

            # Check for user-specific rate
            for user_key, rate in rates.items():
                if user_key != "default" and user_key.lower() in user_name:
                    return float(rate)

            # Return default rate for client
            return float(rates.get("default", 0))

    # Default fallback rate
    return 0.0


async def fetch_harvest_entries(from_date: str, to_date: str) -> list[dict]:
    """Fetch time entries from Harvest API."""
    account_id, api_token = get_harvest_credentials()

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Harvest-Account-Id": account_id,
        "Content-Type": "application/json",
    }

    all_entries = []
    page = 1

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                "https://api.harvestapp.com/v2/time_entries",
                headers=headers,
                params={
                    "from": from_date,
                    "to": to_date,
                    "page": page,
                    "per_page": 100,
                }
            )
            response.raise_for_status()
            data = response.json()

            entries = data.get("time_entries", [])
            all_entries.extend(entries)

            # Check if there are more pages
            if len(entries) < 100:
                break
            page += 1

    return all_entries


def calculate_metrics(entries: list[dict], config: dict) -> RevenueMetrics:
    """Calculate comprehensive revenue metrics from time entries."""
    now = datetime.now()
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = monthrange(now.year, now.month)[1]
    days_elapsed = now.day
    days_remaining = days_in_month - days_elapsed

    # Calculate revenue by client
    client_hours: dict[str, float] = {}
    client_revenue: dict[str, float] = {}
    client_rates: dict[str, float] = {}

    total_hours = 0.0
    total_revenue = 0.0

    for entry in entries:
        hours = entry.get("hours", 0)
        rate = get_rate_for_entry(entry, config)
        revenue = hours * rate

        project_name = entry.get("project", {}).get("name", "Unknown")

        # Aggregate by project/client
        client_hours[project_name] = client_hours.get(project_name, 0) + hours
        client_revenue[project_name] = client_revenue.get(project_name, 0) + revenue
        if project_name not in client_rates or rate > 0:
            client_rates[project_name] = rate

        total_hours += hours
        total_revenue += revenue

    # Build client breakdown
    by_client = [
        ClientRevenue(
            client_name=name,
            hours=client_hours[name],
            rate=client_rates.get(name, 0),
            revenue=client_revenue[name]
        )
        for name in sorted(client_hours.keys(), key=lambda x: client_revenue.get(x, 0), reverse=True)
    ]

    # Get targets from config
    targets = config.get("targets", {})
    expenses = config.get("expenses", {})

    target_hours = targets.get("monthly_hours", 120)
    target_revenue = targets.get("monthly_revenue_gross", 20000)
    monthly_overhead = expenses.get("monthly_overhead", 1000)
    tax_rate = expenses.get("tax_rate", 0.35)

    # MTD metrics
    mtd_gap_hours = max(0, target_hours - total_hours)
    mtd_gap_revenue = max(0, target_revenue - total_revenue)

    # Progress percentages
    hours_progress_pct = (total_hours / target_hours * 100) if target_hours > 0 else 0
    revenue_progress_pct = (total_revenue / target_revenue * 100) if target_revenue > 0 else 0

    # Forecast based on current pace
    if days_elapsed > 0:
        daily_hours_pace = total_hours / days_elapsed
        daily_revenue_pace = total_revenue / days_elapsed
    else:
        daily_hours_pace = 0
        daily_revenue_pace = 0

    forecast_hours = daily_hours_pace * days_in_month
    forecast_gross = daily_revenue_pace * days_in_month

    # Net calculation: Gross - Overhead, then apply tax
    forecast_pre_tax = forecast_gross - monthly_overhead
    forecast_net = forecast_pre_tax * (1 - tax_rate) if forecast_pre_tax > 0 else 0

    # Annualized
    annualized_gross = forecast_gross * 12
    annualized_net = forecast_net * 12

    return RevenueMetrics(
        mtd_hours=round(total_hours, 2),
        mtd_revenue=round(total_revenue, 2),
        mtd_goal_hours=target_hours,
        mtd_goal_revenue=target_revenue,
        mtd_gap_hours=round(mtd_gap_hours, 2),
        mtd_gap_revenue=round(mtd_gap_revenue, 2),
        hours_progress_pct=round(hours_progress_pct, 1),
        revenue_progress_pct=round(revenue_progress_pct, 1),
        month_forecast_hours=round(forecast_hours, 1),
        month_forecast_gross=round(forecast_gross, 2),
        month_forecast_net=round(forecast_net, 2),
        month_forecast_annualized_gross=round(annualized_gross, 2),
        month_forecast_annualized_net=round(annualized_net, 2),
        by_client=by_client,
        month=now.strftime("%Y-%m"),
        days_elapsed=days_elapsed,
        days_in_month=days_in_month,
        days_remaining=days_remaining,
        last_updated=now.isoformat(),
    )


# ---------- API Endpoints ----------

@router.get("/metrics", response_model=RevenueMetrics)
async def get_revenue_metrics():
    """
    Get comprehensive revenue metrics for the current month.

    Fetches data from Harvest API and calculates:
    - MTD Revenue, Goal, Gap
    - Month Forecast (Gross and Net)
    - Annualized projections
    - Breakdown by client
    """
    try:
        config = load_config()

        # Get date range for current month
        now = datetime.now()
        first_of_month = now.replace(day=1).strftime("%Y-%m-%d")
        today = now.strftime("%Y-%m-%d")

        # Fetch entries
        entries = await fetch_harvest_entries(first_of_month, today)

        # Calculate metrics
        metrics = calculate_metrics(entries, config)

        return metrics

    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Harvest API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating metrics: {e}")


@router.get("/health")
async def revenue_health():
    """Check if Harvest API is accessible."""
    try:
        account_id, api_token = get_harvest_credentials()
        return {"status": "configured", "account_id_set": bool(account_id)}
    except ValueError:
        return {"status": "not_configured", "error": "Harvest credentials missing"}
