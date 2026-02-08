"""UniverseManager — coordination layer for universes and agents."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from .agent_loop import AgentHandle, UniverseHandle, run_agent
from .llm_client import LLMClient

logger = logging.getLogger("jarvis.worker.manager")


class UniverseManager:
    """Manages active universes and their agents on this worker."""

    def __init__(
        self,
        llm: LLMClient,
        worker_id: str,
        max_turns: int = 10,
        max_iterations: int = 200,
        api_base: str = "",
    ):
        self.llm = llm
        self.worker_id = worker_id
        self.max_turns = max_turns
        self.max_iterations = max_iterations
        self.api_base = api_base
        self.active_universes: dict[str, UniverseHandle] = {}
        self.active_agents: dict[str, AgentHandle] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()

    async def _emit(self, event: dict):
        """Push an event to the shared queue."""
        event.setdefault("worker_id", self.worker_id)
        await self.event_queue.put(event)

    async def launch_universe(
        self,
        name: str,
        dimension_id: str | None = None,
        agents_config: list[dict] | None = None,
        worktree_path: str | None = None,
    ) -> str:
        """Create a universe and optionally launch agents inside it."""
        universe_id = str(uuid.uuid4())

        universe = UniverseHandle(
            universe_id=universe_id,
            dimension_id=dimension_id,
            name=name,
            worktree_path=worktree_path,
            state={
                "plan": {"goal": name, "milestones": [], "current_focus": ""},
                "decisions": [],
                "knowledge": [],
                "file_manifest": {"created": [], "modified": [], "deleted": []},
                "context_summary": "",
                "blockers": [],
                "agent_notes": {},
                "api_base": self.api_base,
            },
        )
        universe.status = "active"
        self.active_universes[universe_id] = universe

        await self._emit({
            "type": "universe_created",
            "universe_id": universe_id,
            "data": {
                "name": name,
                "dimension_id": dimension_id,
                "worktree_path": worktree_path,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info("Universe created: %s (%s)", name, universe_id[:8])

        # Launch initial agents if provided
        if agents_config:
            for ac in agents_config:
                await self.launch_agent(
                    universe_id=universe_id,
                    name=ac.get("name", "agent"),
                    role=ac.get("role", "general"),
                    model=ac.get("model"),
                    task_prompt=ac.get("task", ""),
                )

        return universe_id

    async def launch_agent(
        self,
        universe_id: str,
        name: str,
        role: str,
        model: str | None = None,
        task_prompt: str = "",
    ) -> str:
        """Create and start an agent in a universe."""
        universe = self.active_universes.get(universe_id)
        if not universe:
            raise ValueError(f"Universe {universe_id} not found")

        agent_id = str(uuid.uuid4())
        resolved_model = model or self.llm.default_model
        agent = AgentHandle(
            agent_id=agent_id,
            name=name,
            role=role,
            model=resolved_model,
            task_prompt=task_prompt,
        )

        # Start the agent loop as an asyncio task
        task = asyncio.create_task(
            run_agent(
                agent,
                universe,
                self.llm,
                max_turns=self.max_turns,
                max_iterations=self.max_iterations,
                emit=self._emit,
            ),
            name=f"agent-{name}-{agent_id[:8]}",
        )
        agent.task = task
        universe.agents[agent_id] = agent
        self.active_agents[agent_id] = agent

        # Monitor for completion to update universe status
        task.add_done_callback(
            lambda t, uid=universe_id: asyncio.get_event_loop().call_soon(
                self._check_universe_completion, uid
            )
        )

        logger.info(
            "Agent launched: %s (%s) in universe %s",
            name, agent_id[:8], universe.name,
        )
        return agent_id

    def _check_universe_completion(self, universe_id: str):
        """Check if all agents in a universe are done."""
        universe = self.active_universes.get(universe_id)
        if not universe:
            return

        all_done = all(
            a.status in ("completed", "error")
            for a in universe.agents.values()
        )
        if all_done and universe.agents:
            universe.status = "terminated"
            for aid in universe.agents:
                self.active_agents.pop(aid, None)
            del self.active_universes[universe_id]
            logger.info("Universe %s completed (all agents done)", universe.name)

    async def stop_agent(self, universe_id: str, agent_id: str):
        """Cancel a running agent."""
        universe = self.active_universes.get(universe_id)
        if not universe:
            return
        agent = universe.agents.get(agent_id)
        if not agent or not agent.task:
            return
        agent.task.cancel()
        agent.status = "paused"
        logger.info("Agent %s stopped", agent.name)

    async def stop_universe(self, universe_id: str):
        """Stop all agents and mark universe terminated."""
        universe = self.active_universes.get(universe_id)
        if not universe:
            return

        for agent in universe.agents.values():
            if agent.task and not agent.task.done():
                agent.task.cancel()
                agent.status = "paused"

        universe.status = "terminated"

        await self._emit({
            "type": "universe_stopped",
            "universe_id": universe_id,
            "data": {"name": universe.name},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info("Universe %s stopped", universe.name)

    async def stop_all(self):
        """Stop all active universes (called on shutdown)."""
        for uid in list(self.active_universes):
            await self.stop_universe(uid)
        self.active_agents.clear()

    @property
    def running_agent_count(self) -> int:
        """Count agents currently running across all active universes."""
        return sum(
            1
            for u in self.active_universes.values()
            for a in u.agents.values()
            if a.status == "running"
        )

    def get_status(self) -> dict:
        """Snapshot for /info endpoint."""
        return {
            "active_universes": len(self.active_universes),
            "running_agents": self.running_agent_count,
            "total_agents_tracked": len(self.active_agents),
            "universes": [
                u.to_dict() for u in self.active_universes.values()
            ],
        }
