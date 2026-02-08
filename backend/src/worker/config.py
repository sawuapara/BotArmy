"""Worker configuration with CLI > env var > defaults precedence."""

import os
import socket
import uuid
from dataclasses import dataclass, field
from pathlib import Path


JARVIS_DIR = Path.home() / ".jarvis"
WORKER_ID_FILE = JARVIS_DIR / "worker_id"


def _load_or_create_worker_id() -> str:
    """Load persistent worker ID from ~/.jarvis/worker_id, or create one."""
    JARVIS_DIR.mkdir(parents=True, exist_ok=True)

    if WORKER_ID_FILE.exists():
        stored = WORKER_ID_FILE.read_text().strip()
        if stored:
            return stored

    worker_id = str(uuid.uuid4())
    WORKER_ID_FILE.write_text(worker_id)
    return worker_id


@dataclass
class WorkerConfig:
    """Configuration for a worker process."""
    api_url: str = ""
    worker_name: str = ""
    capacity: int = 1024
    capabilities: list[str] = field(default_factory=lambda: ["git", "claude-code"])
    port: int = 8100
    heartbeat_interval: int = 30
    worker_id: str = ""

    # LLM configuration
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    max_agent_turns: int = 10
    max_tool_iterations: int = 200

    def __post_init__(self):
        # Apply env var defaults before CLI overrides
        if not self.api_url:
            self.api_url = os.getenv("JARVIS_API_URL", "http://localhost:8000")
        if not self.worker_name:
            self.worker_name = os.getenv("JARVIS_WORKER_NAME", socket.gethostname())
        if self.capacity == 1024:
            env_cap = os.getenv("JARVIS_CAPACITY")
            if env_cap:
                self.capacity = int(env_cap)
        if self.port == 8100:
            env_port = os.getenv("JARVIS_WORKER_PORT")
            if env_port:
                self.port = int(env_port)
        if not self.worker_id:
            self.worker_id = _load_or_create_worker_id()

        # LLM defaults from env
        if not self.llm_base_url:
            self.llm_base_url = os.getenv(
                "ANTHROPIC_BASE_URL", "https://api.anthropic.com"
            )
        if not self.llm_api_key:
            self.llm_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not self.llm_model:
            self.llm_model = os.getenv(
                "JARVIS_LLM_MODEL", "claude-sonnet-4-5-20250929"
            )

    @property
    def worker_address(self) -> str:
        """The address the backend can use to reach this worker."""
        addr = os.getenv("JARVIS_WORKER_ADDRESS")
        if addr:
            return addr
        return f"http://localhost:{self.port}"
