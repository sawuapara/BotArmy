"""Entry point for the Jarvis worker process.

Usage:
    python -m src.worker [options]

Options:
    --api-url URL               Backend server URL (default: http://localhost:8000)
    --worker-name NAME          Worker display name (default: hostname)
    --capacity N                Max concurrent jobs (default: 2)
    --capabilities CAP [CAP...] Worker capabilities (default: git claude-code)
    --port PORT                 Local HTTP server port (default: 8100)
    --heartbeat-interval SECS   Heartbeat interval in seconds (default: 30)
"""

import argparse
import asyncio
import logging
import signal
import sys

import uvicorn

from .client import BackendClient
from .config import WorkerConfig
from .heartbeat import heartbeat_loop
from .server import create_worker_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis.worker")


def parse_args() -> WorkerConfig:
    parser = argparse.ArgumentParser(description="Jarvis Worker Process")
    parser.add_argument("--api-url", default="", help="Backend server URL")
    parser.add_argument("--worker-name", default="", help="Worker display name")
    parser.add_argument("--capacity", type=int, default=2, help="Max concurrent jobs")
    parser.add_argument(
        "--capabilities", nargs="*", default=None, help="Worker capabilities"
    )
    parser.add_argument("--port", type=int, default=8100, help="Local HTTP server port")
    parser.add_argument(
        "--heartbeat-interval", type=int, default=30, help="Heartbeat interval (seconds)"
    )

    args = parser.parse_args()

    config = WorkerConfig(
        api_url=args.api_url,
        worker_name=args.worker_name,
        capacity=args.capacity,
        port=args.port,
        heartbeat_interval=args.heartbeat_interval,
    )
    if args.capabilities is not None:
        config.capabilities = args.capabilities

    return config


async def run(config: WorkerConfig):
    shutdown_event = asyncio.Event()

    # Handle SIGTERM/SIGINT
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    client = BackendClient(config)

    logger.info("Jarvis Worker starting")
    logger.info(f"  Worker ID:  {config.worker_id}")
    logger.info(f"  Name:       {config.worker_name}")
    logger.info(f"  Backend:    {config.api_url}")
    logger.info(f"  Address:    {config.worker_address}")
    logger.info(f"  Capacity:   {config.capacity}")
    logger.info(f"  Port:       {config.port}")

    # Register with backend (retries indefinitely)
    await client.register()

    # Start heartbeat loop
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(client, config, shutdown_event)
    )

    # Start local HTTP server
    worker_app = create_worker_app(config)
    uvi_config = uvicorn.Config(
        worker_app,
        host="0.0.0.0",
        port=config.port,
        log_level="warning",
    )
    server = uvicorn.Server(uvi_config)

    server_task = asyncio.create_task(server.serve())

    logger.info("Worker is online and ready")

    # Wait for shutdown signal
    await shutdown_event.wait()
    logger.info("Shutdown signal received")

    # Graceful shutdown
    heartbeat_task.cancel()
    server.should_exit = True

    # Deregister from backend
    await client.deregister()
    await client.close()

    # Wait for server to finish
    await server_task

    logger.info("Worker stopped")


def main():
    config = parse_args()
    try:
        asyncio.run(run(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
