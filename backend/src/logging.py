"""
Centralized logging configuration for Jarvis.

Provides:
- Console logging with colored, prefixed output by application area
- File logging with timestamps for post-mortem analysis
- Easy-to-use logger factory for different components
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ANSI color codes for console output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"


# Area-specific colors and prefixes
AREA_CONFIG = {
    "main": {"color": Colors.BRIGHT_CYAN, "prefix": "JARVIS.main"},
    "database": {"color": Colors.BRIGHT_BLUE, "prefix": "JARVIS.database"},
    "api": {"color": Colors.BRIGHT_GREEN, "prefix": "JARVIS.api"},
    "api.tasks": {"color": Colors.GREEN, "prefix": "JARVIS.api.tasks"},
    "api.projects": {"color": Colors.GREEN, "prefix": "JARVIS.api.projects"},
    "api.organization": {"color": Colors.GREEN, "prefix": "JARVIS.api.organization"},
    "api.database": {"color": Colors.GREEN, "prefix": "JARVIS.api.database"},
    "orchestrator": {"color": Colors.BRIGHT_MAGENTA, "prefix": "JARVIS.orchestrator"},
    "workers": {"color": Colors.BRIGHT_YELLOW, "prefix": "JARVIS.workers"},
    "websocket": {"color": Colors.CYAN, "prefix": "JARVIS.websocket"},
    "migrations": {"color": Colors.BLUE, "prefix": "JARVIS.migrations"},
}

# Default for unknown areas
DEFAULT_AREA_CONFIG = {"color": Colors.WHITE, "prefix": "JARVIS"}


class ColoredConsoleFormatter(logging.Formatter):
    """Custom formatter that adds colors and area prefixes to console output."""

    LEVEL_COLORS = {
        logging.DEBUG: Colors.DIM,
        logging.INFO: Colors.RESET,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BRIGHT_RED + Colors.BOLD,
    }

    def __init__(self, area: str = "main"):
        super().__init__()
        config = AREA_CONFIG.get(area, DEFAULT_AREA_CONFIG)
        self.area_color = config["color"]
        self.area_prefix = config["prefix"]

    def format(self, record: logging.LogRecord) -> str:
        # Get level color
        level_color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)

        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        # Build the formatted message
        # Format: [JARVIS.area] HH:MM:SS LEVEL: message
        prefix = f"{self.area_color}[{self.area_prefix}]{Colors.RESET}"
        time_str = f"{Colors.DIM}{timestamp}{Colors.RESET}"
        level_str = f"{level_color}{record.levelname:<8}{Colors.RESET}"

        return f"{prefix} {time_str} {level_str} {record.getMessage()}"


class FileFormatter(logging.Formatter):
    """Formatter for file output with full timestamps and structured format."""

    def __init__(self, area: str = "main"):
        super().__init__()
        config = AREA_CONFIG.get(area, DEFAULT_AREA_CONFIG)
        self.area_prefix = config["prefix"]

    def format(self, record: logging.LogRecord) -> str:
        # ISO timestamp for file logs
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

        # Include extra context if available
        extra = ""
        if hasattr(record, "request_id"):
            extra += f" request_id={record.request_id}"
        if hasattr(record, "user_id"):
            extra += f" user_id={record.user_id}"

        # Format: TIMESTAMP [AREA] LEVEL: message (extra)
        return f"{timestamp} [{self.area_prefix}] {record.levelname}: {record.getMessage()}{extra}"


# Global log directory
_log_dir: Optional[Path] = None
_file_handler: Optional[logging.FileHandler] = None


def setup_logging(
    log_dir: Optional[str] = None,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> Path:
    """
    Initialize the logging system.

    Args:
        log_dir: Directory for log files. Defaults to ./logs
        console_level: Minimum level for console output
        file_level: Minimum level for file output

    Returns:
        Path to the log directory
    """
    global _log_dir, _file_handler

    # Determine log directory
    if log_dir:
        _log_dir = Path(log_dir)
    else:
        # Default to logs/ in the backend directory
        _log_dir = Path(__file__).parent.parent / "logs"

    # Create log directory
    _log_dir.mkdir(parents=True, exist_ok=True)

    # Create log file with timestamp
    log_filename = datetime.now().strftime("jarvis_%Y%m%d_%H%M%S.log")
    log_path = _log_dir / log_filename

    # Also create/update a symlink to latest log
    latest_link = _log_dir / "latest.log"
    try:
        if latest_link.is_symlink() or latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(log_filename)
    except OSError:
        pass  # Symlinks may not work on all systems

    # Create file handler
    _file_handler = logging.FileHandler(log_path, encoding="utf-8")
    _file_handler.setLevel(file_level)
    _file_handler.setFormatter(FileFormatter("main"))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything, handlers filter

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Add file handler to root
    root_logger.addHandler(_file_handler)

    # Log startup
    root_logger.info(f"Logging initialized. Log file: {log_path}")

    return _log_dir


def get_logger(area: str = "main") -> logging.Logger:
    """
    Get a logger for a specific application area.

    Args:
        area: The application area (e.g., "database", "api.tasks", "orchestrator")

    Returns:
        Configured logger instance

    Example:
        logger = get_logger("database")
        logger.info("Connected to database")
        # Output: [JARVIS.database] 14:32:15 INFO     Connected to database
    """
    # Create logger with area name
    logger = logging.getLogger(f"jarvis.{area}")

    # Only configure if not already done
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColoredConsoleFormatter(area))
        logger.addHandler(console_handler)

        # Add file handler if setup_logging was called
        if _file_handler:
            # Create area-specific file formatter
            area_file_handler = logging.FileHandler(
                _file_handler.baseFilename,
                encoding="utf-8"
            )
            area_file_handler.setLevel(logging.DEBUG)
            area_file_handler.setFormatter(FileFormatter(area))
            logger.addHandler(area_file_handler)

        # Don't propagate to root to avoid duplicate logs
        logger.propagate = False

    return logger


def get_log_dir() -> Optional[Path]:
    """Get the current log directory path."""
    return _log_dir


def get_recent_logs(lines: int = 100) -> list[str]:
    """
    Read the most recent log entries.

    Args:
        lines: Number of lines to return

    Returns:
        List of log lines (most recent last)
    """
    if not _log_dir:
        return []

    latest = _log_dir / "latest.log"
    if not latest.exists():
        return []

    try:
        with open(latest, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception:
        return []


# Convenience loggers for common areas
main_logger = None
db_logger = None
api_logger = None


def init_default_loggers():
    """Initialize the default loggers after setup_logging is called."""
    global main_logger, db_logger, api_logger
    main_logger = get_logger("main")
    db_logger = get_logger("database")
    api_logger = get_logger("api")
