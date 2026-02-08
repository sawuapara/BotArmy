"""Entry point for the Jarvis worker process.

Usage:
    python -m src.worker [options]

Options:
    --api-url URL               Backend server URL (default: http://localhost:8000)
    --worker-name NAME          Worker display name (default: hostname)
    --capacity N                Max concurrent agent loops (default: 1024)
    --capabilities CAP [CAP...] Worker capabilities (default: git claude-code)
    --port PORT                 Local HTTP server port (default: 8100)
    --heartbeat-interval SECS   Heartbeat interval in seconds (default: 30)
    --llm-base-url URL          LLM API base URL (default: ANTHROPIC_BASE_URL or https://api.anthropic.com)
    --llm-model MODEL           LLM model name (default: JARVIS_LLM_MODEL or claude-sonnet-4-5-20250929)
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
from .llm_client import LLMClient
from .manager import UniverseManager
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
    parser.add_argument("--capacity", type=int, default=1024, help="Max concurrent agent loops")
    parser.add_argument(
        "--capabilities", nargs="*", default=None, help="Worker capabilities"
    )
    parser.add_argument("--port", type=int, default=8100, help="Local HTTP server port")
    parser.add_argument(
        "--heartbeat-interval", type=int, default=30, help="Heartbeat interval (seconds)"
    )
    parser.add_argument("--llm-base-url", default="", help="LLM API base URL")
    parser.add_argument("--llm-model", default="", help="LLM model name")

    args = parser.parse_args()

    config = WorkerConfig(
        api_url=args.api_url,
        worker_name=args.worker_name,
        capacity=args.capacity,
        port=args.port,
        heartbeat_interval=args.heartbeat_interval,
        llm_base_url=args.llm_base_url,
        llm_model=args.llm_model,
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
    logger.info(f"  LLM:        {config.llm_model} @ {config.llm_base_url}")

    # Register with backend (retries indefinitely) — must happen before LLMClient
    # so that the auth token is available for credential fetching
    await client.register()

    # Credential provider closure: fetches ANTHROPIC_API_KEY from central
    async def fetch_anthropic_key() -> str:
        return await client.fetch_credential("ANTHROPIC_API_KEY")

    # Create LLM client and manager (after registration so auth token is available)
    llm = LLMClient(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
        default_model=config.llm_model,
        credential_provider=fetch_anthropic_key,
    )
    manager = UniverseManager(
        llm=llm,
        worker_id=config.worker_id,
        max_turns=config.max_agent_turns,
        max_iterations=config.max_tool_iterations,
        api_base=config.api_url,
    )

    # Start heartbeat loop
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(client, config, shutdown_event, manager)
    )

    # Start local HTTP server
    worker_app = create_worker_app(config, manager)
    uvi_config = uvicorn.Config(
        worker_app,
        host="0.0.0.0",
        port=config.port,
        log_level="warning",
    )
    server = uvicorn.Server(uvi_config)

    server_task = asyncio.create_task(server.serve())

    # Start event stream to backend (sends universe/agent events over WebSocket)
    event_stream_task = client.start_event_stream(manager.event_queue)

    logger.info("Worker is online and ready")

    # Wait for shutdown signal
    await shutdown_event.wait()
    logger.info("Shutdown signal received")

    # Graceful shutdown: stop all universes first
    await manager.stop_all()
    await llm.close()

    await client.stop_event_stream()
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
