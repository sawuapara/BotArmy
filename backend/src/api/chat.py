"""Chat API for LLM interactions."""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..vault import vault_session, decrypt
from ..db import get_db_pool

router = APIRouter(prefix="/chat", tags=["chat"])


async def get_api_key(name: str) -> str:
    """
    Get an API key from the vault.
    Falls back to environment variable if vault is locked or key not found.
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


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None  # Source context (task, project, etc.)
    history: list[ChatMessage] = []  # Previous messages in conversation


class ApiCallDebug(BaseModel):
    """Debug info for the API call."""
    endpoint: str
    model: str
    system: str
    messages: list[dict]
    tools: Optional[list[dict]] = None
    thinking: Optional[dict] = None
    max_tokens: int


class UsageInfo(BaseModel):
    """Token usage information."""
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    message: str
    model: str
    usage: UsageInfo
    request_debug: ApiCallDebug
    response_raw: dict  # Full raw response from API


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message to the LLM and get a response.

    Currently uses Anthropic Claude. Will be extended to support
    model selection and agentic loops.
    """
    api_key = await get_api_key("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured. Add it to vault or set ANTHROPIC_API_KEY env var."
        )

    import httpx

    # Build messages array
    messages = []
    for msg in request.history:
        messages.append({
            "role": msg.role,
            "content": msg.content,
        })
    messages.append({
        "role": "user",
        "content": request.message,
    })

    # Build system prompt with context
    system_parts = ["You are a helpful assistant."]
    if request.context:
        context_type = request.context.get("type", "general")
        if context_type == "task":
            system_parts.append("\nThe user is creating a new task.")
            if request.context.get("projectName"):
                system_parts.append(f"Project: {request.context['projectName']}")
            if request.context.get("namespaceName"):
                system_parts.append(f"Namespace: {request.context['namespaceName']}")
        elif context_type == "project":
            system_parts.append("\nThe user is creating a new project.")
            if request.context.get("namespaceName"):
                system_parts.append(f"Namespace: {request.context['namespaceName']}")

    system_prompt = "\n".join(system_parts)

    # Build request payload
    model = "claude-sonnet-4-20250514"
    max_tokens = 1024
    request_payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages,
    }

    # Debug info for the request
    request_debug = ApiCallDebug(
        endpoint="https://api.anthropic.com/v1/messages",
        model=model,
        system=system_prompt,
        messages=messages,
        tools=None,  # Will be populated when we add tools
        thinking=None,  # Will be populated when we add extended thinking
        max_tokens=max_tokens,
    )

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=request_payload,
                timeout=60.0,
            )

            if res.status_code != 200:
                error_detail = res.text
                raise HTTPException(
                    status_code=res.status_code,
                    detail=f"Anthropic API error: {error_detail}"
                )

            data = res.json()

            # Extract text from response
            content = data.get("content", [])
            response_text = ""
            for block in content:
                if block.get("type") == "text":
                    response_text += block.get("text", "")

            # Extract usage
            usage_data = data.get("usage", {})
            usage = UsageInfo(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
            )

            return ChatResponse(
                message=response_text,
                model=data.get("model", model),
                usage=usage,
                request_debug=request_debug,
                response_raw=data,
            )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Request to Anthropic API timed out"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calling Anthropic API: {str(e)}"
        )
