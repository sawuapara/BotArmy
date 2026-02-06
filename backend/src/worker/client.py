"""HTTP client for communicating with the Jarvis backend server."""

import asyncio
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
                        "max_concurrent_jobs": self.config.capacity,
                        "capabilities": self.config.capabilities,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"Registered with backend as {data['id']}")
                return data
            except Exception as e:
                logger.warning(f"Registration failed ({e}), retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

    async def heartbeat(self, current_jobs: int = 0, status: str = "online") -> bool:
        """Send heartbeat to backend. Returns True on success, False on failure."""
        try:
            resp = await self._client.post(
                f"{self.base_url}/api/workers/{self.config.worker_id}/heartbeat",
                json={"current_jobs": current_jobs, "status": status},
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
