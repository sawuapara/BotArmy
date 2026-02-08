"""HTTP client for communicating with the Jarvis backend server."""

import asyncio
import json
import logging

import httpx

from .config import WorkerConfig

logger = logging.getLogger("jarvis.worker.client")


class BackendClient:
    """Async HTTP client for the Jarvis backend API."""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.base_url = config.api_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=10.0)
        self._ws = None
        self._ws_task: asyncio.Task | None = None
        self.auth_token: str | None = None

    async def close(self):
        await self._client.aclose()

    async def register(self) -> dict:
        """Register with the backend, retrying with exponential backoff."""
        delay = 1.0
        max_delay = 60.0

        while True:
            try:
                resp = await self._client.post(
                    f"{self.base_url}/api/workers/register",
                    json={
                        "worker_id": self.config.worker_id,
                        "hostname": self.config.worker_name,
                        "worker_name": self.config.worker_name,
                        "worker_address": self.config.worker_address,
                        "max_concurrent_agents": self.config.capacity,
                        "capabilities": self.config.capabilities,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                self.auth_token = data.get("auth_token")
                if self.auth_token:
                    logger.info(f"Registered with backend as {data['id']} (received auth token)")
                else:
                    logger.info(f"Registered with backend as {data['id']}")
                return data
            except Exception as e:
                logger.warning(f"Registration failed ({e}), retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

    async def heartbeat(self, current_agents: int = 0, status: str = "online") -> bool:
        """Send heartbeat to backend. Returns True on success, False on failure."""
        try:
            resp = await self._client.post(
                f"{self.base_url}/api/workers/{self.config.worker_id}/heartbeat",
                json={"current_agents": current_agents, "status": status},
            )
            if resp.status_code == 404:
                logger.warning("Heartbeat got 404 - worker not found on backend")
                return False
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            return False

    async def deregister(self):
        """Best-effort deregister on shutdown (5s timeout)."""
        try:
            await self._client.post(
                f"{self.base_url}/api/workers/{self.config.worker_id}/deregister",
                timeout=5.0,
            )
            logger.info("Deregistered from backend")
        except Exception as e:
            logger.debug(f"Deregister failed (best-effort): {e}")

    async def fetch_credential(self, key_name: str) -> str:
        """Fetch a credential from the backend's credential endpoint."""
        if not self.auth_token:
            raise RuntimeError("No auth token available - worker not registered")

        resp = await self._client.get(
            f"{self.base_url}/api/workers/credentials/{key_name}",
            headers={"Authorization": f"Bearer {self.auth_token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["key_value"]

    async def stream_events(self, event_queue: asyncio.Queue) -> None:
        """Consume events from queue and send over WebSocket to backend.

        Opens a persistent WebSocket to the backend and streams events.
        Auto-reconnects on disconnect.
        """
        import websockets

        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/ws/worker/{self.config.worker_id}"
        logger.info(f"Event stream task started, connecting to {ws_url}")

        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    logger.info("Event stream connected to backend")
                    self._ws = ws
                    while True:
                        event = await event_queue.get()
                        try:
                            await ws.send(json.dumps(event))
                            logger.debug(f"Event sent: {event.get('type', '?')}")
                        except Exception as send_err:
                            logger.warning(f"Event send failed: {send_err}")
                            # Put event back and reconnect
                            await event_queue.put(event)
                            break
            except asyncio.CancelledError:
                logger.info("Event stream task cancelled")
                break
            except Exception as e:
                logger.warning(f"Event stream error: {type(e).__name__}: {e}, reconnecting in 5s...")
                self._ws = None
                await asyncio.sleep(5)

    def start_event_stream(self, event_queue: asyncio.Queue) -> asyncio.Task:
        """Start the event streaming background task."""
        self._ws_task = asyncio.create_task(
            self.stream_events(event_queue),
            name="event-stream",
        )
        # Log unhandled exceptions from the task instead of silently swallowing
        def _on_done(task: asyncio.Task):
            if task.cancelled():
                return
            exc = task.exception()
            if exc:
                logger.error(f"Event stream task crashed: {type(exc).__name__}: {exc}")
        self._ws_task.add_done_callback(_on_done)
        return self._ws_task

    async def stop_event_stream(self):
        """Stop the event streaming task."""
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
