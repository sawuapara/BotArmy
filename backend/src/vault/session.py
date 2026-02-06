"""
Vault session management - holds encryption key in memory.

The key is derived on unlock and cleared on lock.
Future: Add inactivity timeout, session tokens, etc.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VaultSession:
    """Holds the vault encryption key in memory."""

    _key: Optional[bytes] = None
    _unlocked_at: Optional[datetime] = None
    _user_id: Optional[str] = None

    @property
    def is_unlocked(self) -> bool:
        """Check if vault is currently unlocked."""
        return self._key is not None

    @property
    def key(self) -> bytes:
        """Get the encryption key. Raises if locked."""
        if self._key is None:
            raise ValueError("Vault is locked")
        return self._key

    @property
    def unlocked_at(self) -> Optional[datetime]:
        """When the vault was unlocked."""
        return self._unlocked_at

    @property
    def user_id(self) -> Optional[str]:
        """The user who unlocked the vault."""
        return self._user_id

    def unlock(self, key: bytes, user_id: str) -> None:
        """Store the encryption key in memory."""
        self._key = key
        self._unlocked_at = datetime.now()
        self._user_id = user_id

    def lock(self) -> None:
        """Clear the encryption key from memory."""
        self._key = None
        self._unlocked_at = None
        self._user_id = None


# Global singleton - the vault session for this backend instance
vault_session = VaultSession()
