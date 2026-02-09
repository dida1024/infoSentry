"""API Key repository interfaces."""

from abc import abstractmethod
from datetime import datetime

from src.core.domain.repository import BaseRepository
from src.modules.api_keys.domain.entities import ApiKey


class ApiKeyRepository(BaseRepository[ApiKey]):
    """API Key repository interface."""

    @abstractmethod
    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        """Get an API key by its SHA-256 hash."""
        pass

    @abstractmethod
    async def list_by_user(self, user_id: str) -> list[ApiKey]:
        """List all API keys for a user (excluding deleted)."""
        pass

    @abstractmethod
    async def count_active_by_user(self, user_id: str) -> int:
        """Count active (non-deleted, non-revoked) keys for a user."""
        pass

    @abstractmethod
    async def update_last_used(self, key_id: str, used_at: datetime) -> None:
        """Update the last_used_at timestamp for a key.

        This is intended to be called asynchronously (fire-and-forget).
        """
        pass
