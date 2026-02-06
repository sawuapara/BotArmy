"""
Persists last username to file for login convenience.
Username is not sensitive - just saves typing on restart.
"""

from pathlib import Path

# Store in backend directory
LAST_USERNAME_FILE = Path(__file__).parent.parent.parent / ".last_username"


def save_last_username(username: str) -> None:
    """Save the last logged-in username to file."""
    try:
        LAST_USERNAME_FILE.write_text(username)
    except Exception:
        pass


def get_last_username() -> str | None:
    """Get the last logged-in username from file."""
    try:
        if LAST_USERNAME_FILE.exists():
            return LAST_USERNAME_FILE.read_text().strip()
    except Exception:
        pass
    return None
