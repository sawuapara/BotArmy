"""REST endpoints for conversation/turn inspection (debug inspector)."""

from fastapi import APIRouter, HTTPException

from ..db.conversations import (
    get_conversations_by_universe,
    get_turns_by_conversation,
    get_turn_detail,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/by-universe/{universe_id}")
async def list_conversations(universe_id: str):
    """List all conversations for a universe."""
    return await get_conversations_by_universe(universe_id)


@router.get("/{conversation_id}/turns")
async def list_turns(conversation_id: str):
    """List all turns for a conversation, ordered by turn+iteration."""
    turns = await get_turns_by_conversation(conversation_id)
    if not turns:
        # Could be empty or invalid ID — return empty list either way
        return []
    return turns


@router.get("/{conversation_id}/turns/{turn_id}")
async def get_single_turn(conversation_id: str, turn_id: str):
    """Get a single turn by ID."""
    turn = await get_turn_detail(conversation_id, turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")
    return turn
