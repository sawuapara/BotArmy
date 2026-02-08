"""Persistence functions for conversations and turns (debug inspector)."""

import json
import logging
from datetime import datetime, timezone

from .connection import get_db_pool

logger = logging.getLogger("jarvis.conversations")


async def create_conversation(
    universe_id: str,
    agent_id: str,
    agent_name: str | None = None,
    agent_role: str | None = None,
    model: str | None = None,
    worker_id: str | None = None,
) -> str | None:
    """Insert a new conversation row. Returns the conversation ID."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO orchestration.conversations
                    (universe_id, agent_id, agent_name, agent_role, model, worker_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                universe_id, agent_id, agent_name, agent_role, model, worker_id,
            )
            return str(row["id"]) if row else None
    except Exception as e:
        logger.error("Failed to create conversation: %s", e)
        return None


async def insert_turn(
    universe_id: str,
    agent_id: str,
    data: dict,
) -> str | None:
    """Insert a turn row and update conversation aggregates. Returns turn ID."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Look up the conversation for this universe+agent
            conv_id = await conn.fetchval(
                """
                SELECT id FROM orchestration.conversations
                WHERE universe_id = $1 AND agent_id = $2
                ORDER BY created_at DESC LIMIT 1
                """,
                universe_id, agent_id,
            )
            if not conv_id:
                logger.warning(
                    "No conversation found for universe=%s agent=%s", universe_id, agent_id
                )
                return None

            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            turn_number = data.get("turn_number", 1)
            iteration = data.get("iteration", 0)

            row = await conn.fetchrow(
                """
                INSERT INTO orchestration.turns
                    (conversation_id, turn_number, iteration_number,
                     system_prompt, messages_sent, tools_available,
                     model, max_tokens, response_content, stop_reason,
                     input_tokens, output_tokens, tool_calls,
                     started_at, duration_ms)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb,
                        $7, $8, $9::jsonb, $10,
                        $11, $12, $13::jsonb,
                        $14, $15)
                RETURNING id
                """,
                conv_id,
                turn_number,
                iteration,
                data.get("system_prompt"),
                json.dumps(data.get("messages_sent")),
                json.dumps(data.get("tools_available")),
                data.get("model"),
                data.get("max_tokens", 4096),
                json.dumps(data.get("response_content")),
                data.get("stop_reason"),
                input_tokens,
                output_tokens,
                json.dumps(data.get("tool_calls", [])),
                datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.now(timezone.utc),
                data.get("duration_ms", 0),
            )

            # Update conversation aggregates
            await conn.execute(
                """
                UPDATE orchestration.conversations
                SET total_iterations = total_iterations + 1,
                    total_turns = GREATEST(total_turns, $2),
                    total_input_tokens = total_input_tokens + $3,
                    total_output_tokens = total_output_tokens + $4
                WHERE id = $1
                """,
                conv_id, turn_number, input_tokens, output_tokens,
            )

            return str(row["id"]) if row else None
    except Exception as e:
        logger.error("Failed to insert turn: %s", e)
        return None


async def complete_conversation(
    universe_id: str,
    agent_id: str,
    status: str = "completed",
    error_message: str | None = None,
) -> bool:
    """Mark a conversation as completed or errored."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            updated = await conn.fetchval(
                """
                UPDATE orchestration.conversations
                SET status = $3, error_message = $4, completed_at = NOW()
                WHERE universe_id = $1 AND agent_id = $2
                  AND status = 'running'
                RETURNING id
                """,
                universe_id, agent_id, status, error_message,
            )
            return updated is not None
    except Exception as e:
        logger.error("Failed to complete conversation: %s", e)
        return False


async def get_conversations_by_universe(universe_id: str) -> list[dict]:
    """List all conversations for a universe."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM orchestration.conversations
            WHERE universe_id = $1
            ORDER BY created_at DESC
            """,
            universe_id,
        )
        return [_conv_row_to_dict(row) for row in rows]


async def get_turns_by_conversation(conversation_id: str) -> list[dict]:
    """List all turns for a conversation, ordered by turn+iteration."""
    import uuid as _uuid
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM orchestration.turns
            WHERE conversation_id = $1
            ORDER BY turn_number, iteration_number
            """,
            _uuid.UUID(conversation_id),
        )
        return [_turn_row_to_dict(row) for row in rows]


async def get_turn_detail(conversation_id: str, turn_id: str) -> dict | None:
    """Get a single turn by ID."""
    import uuid as _uuid
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM orchestration.turns
            WHERE conversation_id = $1 AND id = $2
            """,
            _uuid.UUID(conversation_id), _uuid.UUID(turn_id),
        )
        return _turn_row_to_dict(row) if row else None


def _conv_row_to_dict(row) -> dict:
    return {
        "id": str(row["id"]),
        "universe_id": row["universe_id"],
        "agent_id": row["agent_id"],
        "agent_name": row["agent_name"],
        "agent_role": row["agent_role"],
        "model": row["model"],
        "worker_id": row["worker_id"],
        "task_prompt": row["task_prompt"],
        "status": row["status"],
        "error_message": row["error_message"],
        "total_turns": row["total_turns"],
        "total_iterations": row["total_iterations"],
        "total_input_tokens": row["total_input_tokens"],
        "total_output_tokens": row["total_output_tokens"],
        "created_at": row["created_at"].isoformat(),
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "updated_at": row["updated_at"].isoformat(),
    }


def _turn_row_to_dict(row) -> dict:
    return {
        "id": str(row["id"]),
        "conversation_id": str(row["conversation_id"]),
        "turn_number": row["turn_number"],
        "iteration_number": row["iteration_number"],
        "system_prompt": row["system_prompt"],
        "messages_sent": row["messages_sent"],
        "tools_available": row["tools_available"],
        "model": row["model"],
        "max_tokens": row["max_tokens"],
        "response_content": row["response_content"],
        "stop_reason": row["stop_reason"],
        "input_tokens": row["input_tokens"],
        "output_tokens": row["output_tokens"],
        "tool_calls": row["tool_calls"],
        "started_at": row["started_at"].isoformat(),
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "duration_ms": row["duration_ms"],
        "created_at": row["created_at"].isoformat(),
    }
