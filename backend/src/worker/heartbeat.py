"""Background heartbeat loop for the worker."""

import asyncio
import logging

from .client import BackendClient
from .config import WorkerConfig

logger = logging.getLogger("jarvis.worker.heartbeat")


async def heartbeat_loop(
    client: BackendClient,
    config: WorkerConfig,
    shutdown_event: asyncio.Event,
):
    """Send periodic heartbeats to the backend server.

    On 404 response (worker deleted from backend), triggers re-registration.
    Exits immediately when shutdown_event is set.
    """
    consecutive_failures = 0

    while not shutdown_event.is_set():
        success = await client.heartbeat(current_jobs=0, status="online")

        if success:
            if consecutive_failures > 0:
                logger.info("Heartbeat recovered after %d failures", consecutive_failures)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                logger.warning("Heartbeat: %d consecutive failures", consecutive_failures)

            # 404 means backend deleted us - re-register
            logger.info("Attempting re-registration with backend...")
            try:
                await client.register()
                consecutive_failures = 0
                logger.info("Re-registration successful")
            except Exception as e:
                logger.error(f"Re-registration failed: {e}")

        # Wait for the interval, but exit immediately on shutdown
        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=config.heartbeat_interval,
            )
            # If we get here, shutdown was signaled
            break
        except asyncio.TimeoutError:
            # Normal: interval elapsed, loop again
            pass
