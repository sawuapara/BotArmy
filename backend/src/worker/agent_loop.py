"""Two-loop agentic architecture: inner tool-use loop + outer turn loop."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .llm_client import LLMClient
from .tools import (
    TOOL_DEFINITIONS,
    TASK_CREATOR_TOOLS,
    execute_tool,
    execute_task_creator_tool,
)

logger = logging.getLogger("jarvis.worker.agent")


@dataclass
class AgentHandle:
    """Tracks a single agent running inside a universe."""

    agent_id: str
    name: str
    role: str
    model: str | None
    status: str = "idle"  # idle, running, paused, completed, error
    current_turn: int = 0
    task_prompt: str = ""
    task: asyncio.Task | None = None

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "model": self.model,
            "status": self.status,
            "current_turn": self.current_turn,
        }


@dataclass
class UniverseHandle:
    """Tracks a universe and its agents on this worker."""

    universe_id: str
    dimension_id: str | None
    name: str
    worktree_path: str | None
    state: dict = field(default_factory=dict)
    state_version: int = 0
    status: str = "initializing"  # initializing, active, suspended, terminated, error
    agents: dict[str, AgentHandle] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "universe_id": self.universe_id,
            "name": self.name,
            "dimension_id": self.dimension_id,
            "status": self.status,
            "state_version": self.state_version,
            "created_at": self.created_at,
            "agents": [a.to_dict() for a in self.agents.values()],
        }


async def run_tool_use_loop(
    llm: LLMClient,
    *,
    model: str | None,
    system: str,
    messages: list[dict],
    worktree_path: str | None,
    max_iterations: int,
    emit: callable,
    agent_id: str,
    agent_name: str,
    universe_id: str,
    agent_role: str = "general",
    api_base: str = "",
    turn_number: int = 1,
) -> list[dict]:
    """Inner loop: send messages to LLM, execute tools, repeat until end_turn.

    Returns the final messages list.
    """
    # Select tools based on agent role
    if agent_role == "task-creator":
        tools = TASK_CREATOR_TOOLS
    elif worktree_path:
        tools = TOOL_DEFINITIONS
    else:
        tools = None

    for iteration in range(max_iterations):
        # Snapshot state before the LLM call for iteration_detail
        messages_snapshot = [dict(m) for m in messages]
        iteration_start = datetime.now(timezone.utc)

        response = await llm.chat(
            messages,
            model=model,
            system=system,
            tools=tools,
        )

        # Append assistant response
        assistant_msg = {"role": "assistant", "content": response["content"]}
        messages.append(assistant_msg)

        # Emit LLM response event
        text_content = ""
        for block in response["content"]:
            if block.get("type") == "text":
                text_content += block.get("text", "")

        await emit({
            "type": "llm_response",
            "universe_id": universe_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "data": {
                "text": text_content[:500],
                "usage": response.get("usage", {}),
                "stop_reason": response["stop_reason"],
                "iteration": iteration,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Check stop reason
        if response["stop_reason"] == "end_turn":
            # Emit iteration_detail before breaking (no tool calls)
            await emit({
                "type": "iteration_detail",
                "universe_id": universe_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "data": {
                    "turn_number": turn_number,
                    "iteration": iteration,
                    "system_prompt": system,
                    "messages_sent": messages_snapshot,
                    "tools_available": tools,
                    "model": model,
                    "max_tokens": 4096,
                    "response_content": response["content"],
                    "stop_reason": response["stop_reason"],
                    "usage": response.get("usage", {}),
                    "tool_calls": [],
                    "started_at": iteration_start.isoformat(),
                    "duration_ms": int((datetime.now(timezone.utc) - iteration_start).total_seconds() * 1000),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            break

        if response["stop_reason"] != "tool_use":
            # max_tokens or unexpected stop — emit detail then break
            await emit({
                "type": "iteration_detail",
                "universe_id": universe_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "data": {
                    "turn_number": turn_number,
                    "iteration": iteration,
                    "system_prompt": system,
                    "messages_sent": messages_snapshot,
                    "tools_available": tools,
                    "model": model,
                    "max_tokens": 4096,
                    "response_content": response["content"],
                    "stop_reason": response["stop_reason"],
                    "usage": response.get("usage", {}),
                    "tool_calls": [],
                    "started_at": iteration_start.isoformat(),
                    "duration_ms": int((datetime.now(timezone.utc) - iteration_start).total_seconds() * 1000),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            break

        # Execute tool calls
        tool_results = []
        collected_tool_calls = []
        for block in response["content"]:
            if block.get("type") == "tool_use":
                tool_name = block["name"]
                tool_input = block["input"]
                tool_id = block["id"]

                await emit({
                    "type": "tool_call",
                    "universe_id": universe_id,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "data": {
                        "tool": tool_name,
                        "input": tool_input,
                        "iteration": iteration,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                if agent_role == "task-creator":
                    result = await execute_task_creator_tool(
                        tool_name, tool_input, api_base
                    )
                elif worktree_path:
                    result = await execute_tool(tool_name, tool_input, worktree_path)
                else:
                    result = "Error: No tools configured for this universe."

                await emit({
                    "type": "tool_result",
                    "universe_id": universe_id,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "data": {
                        "tool": tool_name,
                        "result": result[:500],
                        "iteration": iteration,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result,
                })

                collected_tool_calls.append({
                    "name": tool_name,
                    "input": tool_input,
                    "result": result[:1000],
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Emit iteration_detail after tool execution
        await emit({
            "type": "iteration_detail",
            "universe_id": universe_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "data": {
                "turn_number": turn_number,
                "iteration": iteration,
                "system_prompt": system,
                "messages_sent": messages_snapshot,
                "tools_available": tools,
                "model": model,
                "max_tokens": 4096,
                "response_content": response["content"],
                "stop_reason": response["stop_reason"],
                "usage": response.get("usage", {}),
                "tool_calls": collected_tool_calls,
                "started_at": iteration_start.isoformat(),
                "duration_ms": int((datetime.now(timezone.utc) - iteration_start).total_seconds() * 1000),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return messages


async def run_agent(
    agent: AgentHandle,
    universe: UniverseHandle,
    llm: LLMClient,
    *,
    max_turns: int,
    max_iterations: int,
    emit: callable,
):
    """Outer loop: manages turns for an agent.

    Each turn starts a fresh conversation with state context.
    """
    agent.status = "running"

    # Resolve tool definitions for this agent (used in agent_started event)
    if agent.role == "task-creator":
        agent_tools = TASK_CREATOR_TOOLS
    elif universe.worktree_path:
        agent_tools = TOOL_DEFINITIONS
    else:
        agent_tools = None

    await emit({
        "type": "agent_started",
        "universe_id": universe.universe_id,
        "agent_id": agent.agent_id,
        "agent_name": agent.name,
        "data": {"role": agent.role, "model": agent.model, "tools": agent_tools},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # For task-creator: accumulate messages across turns (conversational)
    # For other roles: messages are reset each turn (stateless tool execution)
    persistent_messages = [{"role": "user", "content": agent.task_prompt}]

    try:
        for turn in range(1, max_turns + 1):
            agent.current_turn = turn

            await emit({
                "type": "turn_start",
                "universe_id": universe.universe_id,
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "data": {"turn": turn, "max_turns": max_turns},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Build system prompt from universe state
            state_summary = ""
            if universe.state:
                context = universe.state.get("context_summary", "")
                decisions = universe.state.get("decisions", [])
                if context:
                    state_summary += f"\n\nCurrent context: {context}"
                if decisions:
                    recent = decisions[-5:]
                    state_summary += "\n\nRecent decisions:\n" + "\n".join(
                        f"- {d.get('decision', '')}" for d in recent
                    )

            if agent.role == "task-creator":
                system = (
                    "You are a task creation assistant for Jarvis, an AI-powered project management system.\n\n"
                    "Help the user define a clear task. Gather: title, description, priority (0-100), "
                    "project, tags, and estimate if mentioned.\n"
                    "When you have enough information, use the create_task tool to create the task.\n"
                    "Be conversational but efficient.\n"
                    f"Turn {turn} of {max_turns}.{state_summary}"
                )
            else:
                system = (
                    f"You are {agent.name}, a {agent.role} agent working in the "
                    f"'{universe.name}' universe.\n"
                    f"Turn {turn} of {max_turns}.\n"
                    f"You have tools to read/write files, list directories, and run commands.\n"
                    f"Complete your task, then stop when done.{state_summary}"
                )

            # Task-creator: reuse messages (conversation accumulates)
            # Other roles: fresh messages each turn (stateless tool execution)
            if agent.role == "task-creator":
                messages = persistent_messages
            else:
                messages = [{"role": "user", "content": agent.task_prompt}]

            messages = await run_tool_use_loop(
                llm,
                model=agent.model,
                system=system,
                messages=messages,
                worktree_path=universe.worktree_path,
                max_iterations=max_iterations,
                emit=emit,
                agent_id=agent.agent_id,
                agent_name=agent.name,
                universe_id=universe.universe_id,
                agent_role=agent.role,
                api_base=universe.state.get("api_base", ""),
                turn_number=turn,
            )

            # Keep accumulated messages for task-creator
            if agent.role == "task-creator":
                persistent_messages = messages

            # Update universe state version
            universe.state_version += 1

            await emit({
                "type": "turn_end",
                "universe_id": universe.universe_id,
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "data": {
                    "turn": turn,
                    "state_version": universe.state_version,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Check if the agent signaled completion (last message was end_turn with no tools)
            # If the LLM ended its turn without requesting tools, assume it's done
            last_assistant = None
            for msg in reversed(messages):
                if msg["role"] == "assistant":
                    last_assistant = msg
                    break

            if last_assistant:
                has_tool_use = any(
                    b.get("type") == "tool_use"
                    for b in last_assistant.get("content", [])
                    if isinstance(b, dict)
                )
                if not has_tool_use:
                    # Agent finished without requesting more tools
                    break

        agent.status = "completed"
        await emit({
            "type": "agent_done",
            "universe_id": universe.universe_id,
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "data": {"final_turn": agent.current_turn},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    except asyncio.CancelledError:
        agent.status = "paused"
        logger.info("Agent %s cancelled", agent.name)
        raise

    except Exception as e:
        agent.status = "error"
        logger.exception("Agent %s failed: %s", agent.name, e)
        await emit({
            "type": "agent_error",
            "universe_id": universe.universe_id,
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "data": {"error": str(e)},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
