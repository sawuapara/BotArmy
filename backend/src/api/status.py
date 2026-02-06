"""Status API for checking connections to external services."""

import os
import time
from fastapi import APIRouter

from ..vault import vault_session, decrypt
from ..db import get_db_pool

router = APIRouter(prefix="/status", tags=["status"])


async def get_api_key(name: str) -> str:
    """
    Get an API key from the vault, falling back to environment variable.
    """
    # Try vault first
    if vault_session.is_unlocked:
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT encrypted_data, iv FROM vault.items WHERE name = $1 LIMIT 1",
                    name
                )
                if row:
                    return decrypt(vault_session.key, row["encrypted_data"], row["iv"])
        except Exception:
            pass  # Fall through to env var

    # Fallback to environment variable
    return os.getenv(name, "")


async def check_aws_connection() -> dict:
    """Check AWS connection by testing database pool."""
    start = time.time()
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        latency = int((time.time() - start) * 1000)
        return {"status": "connected", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_anthropic_connection() -> dict:
    """Check Anthropic API connection."""
    api_key = await get_api_key("ANTHROPIC_API_KEY")
    if not api_key:
        return {"status": "disconnected", "error": "API key not configured"}

    start = time.time()
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # Just check if we can reach the API (don't make actual API call to save costs)
            res = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10.0,
            )
            latency = int((time.time() - start) * 1000)
            if res.status_code == 200:
                return {"status": "connected", "latency_ms": latency}
            elif res.status_code == 401:
                return {"status": "error", "error": "Invalid API key"}
            else:
                return {"status": "error", "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_gemini_connection() -> dict:
    """Check Google Gemini API connection."""
    api_key = await get_api_key("GOOGLE_API_KEY") or await get_api_key("GEMINI_API_KEY")
    if not api_key:
        return {"status": "disconnected", "error": "API key not configured"}

    start = time.time()
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # List models endpoint to verify connection
            res = await client.get(
                f"https://generativelanguage.googleapis.com/v1/models?key={api_key}",
                timeout=10.0,
            )
            latency = int((time.time() - start) * 1000)
            if res.status_code == 200:
                return {"status": "connected", "latency_ms": latency}
            elif res.status_code == 400 or res.status_code == 403:
                return {"status": "error", "error": "Invalid API key"}
            else:
                return {"status": "error", "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_openai_connection() -> dict:
    """Check OpenAI API connection."""
    api_key = await get_api_key("OPENAI_API_KEY")
    if not api_key:
        return {"status": "disconnected", "error": "API key not configured"}

    start = time.time()
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # List models endpoint to verify connection
            res = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            latency = int((time.time() - start) * 1000)
            if res.status_code == 200:
                return {"status": "connected", "latency_ms": latency}
            elif res.status_code == 401:
                return {"status": "error", "error": "Invalid API key"}
            else:
                return {"status": "error", "error": f"HTTP {res.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/connections")
async def get_connection_status():
    """
    Check connection status for all external services.

    Returns status for:
    - AWS (database connection)
    - Anthropic API
    - Google Gemini API
    - OpenAI API
    """
    # Run all checks concurrently
    import asyncio
    aws, anthropic, gemini, openai = await asyncio.gather(
        check_aws_connection(),
        check_anthropic_connection(),
        check_gemini_connection(),
        check_openai_connection(),
    )

    return {
        "aws": aws,
        "anthropic": anthropic,
        "gemini": gemini,
        "openai": openai,
    }
