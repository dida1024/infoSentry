"""API Key application service."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import status

from src.core.config import settings
from src.core.domain.exceptions import DomainException
from src.core.infrastructure.logging import BusinessEvents
from src.modules.api_keys.domain.entities import ApiKey
from src.modules.api_keys.domain.repository import ApiKeyRepository


class ApiKeyLimitExceededError(DomainException):
    """Raised when user has reached the maximum number of API keys."""

    http_status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "API_KEY_LIMIT_EXCEEDED"


class ApiKeyNotFoundError(DomainException):
    """Raised when an API key is not found."""

    http_status_code = status.HTTP_404_NOT_FOUND
    error_code = "API_KEY_NOT_FOUND"


class ApiKeyInvalidError(DomainException):
    """Raised when an API key validation fails."""

    http_status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "API_KEY_INVALID"


class ApiKeyService:
    """Application service for API Key management."""

    def __init__(self, repository: ApiKeyRepository) -> None:
        self._repo = repository

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        """Compute SHA-256 hash of a raw API key."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def create_key(
        self,
        user_id: str,
        name: str,
        scopes: list[str],
        expires_in_days: int | None = None,
        *,
        skip_limit_check: bool = False,
    ) -> tuple[ApiKey, str]:
        """Create a new API key.

        Returns:
            Tuple of (created ApiKey entity, raw key string).
            The raw key is only available at creation time.
        """
        # Check limit
        if not skip_limit_check:
            active_count = await self._repo.count_active_by_user(user_id)
            if active_count >= settings.API_KEY_MAX_PER_USER:
                raise ApiKeyLimitExceededError(
                    f"Maximum {settings.API_KEY_MAX_PER_USER} API keys per user"
                )

        # Generate key
        random_part = secrets.token_urlsafe(32)
        raw_key = f"isk_{random_part}"
        key_prefix = raw_key[:12]
        key_hash = self._hash_key(raw_key)

        # Calculate expiry
        expires_at: datetime | None = None
        if expires_in_days is not None:
            expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
        elif settings.API_KEY_DEFAULT_EXPIRE_DAYS > 0:
            expires_at = datetime.now(UTC) + timedelta(
                days=settings.API_KEY_DEFAULT_EXPIRE_DAYS
            )

        # Create entity
        api_key = ApiKey(
            user_id=user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
        )

        created = await self._repo.create(api_key)

        BusinessEvents.log_event(
            "api_key_created",
            user_id=user_id,
            event_data={
                "key_id": created.id,
                "key_prefix": key_prefix,
                "scopes": scopes,
                "expires_at": str(expires_at) if expires_at else None,
            },
        )

        return created, raw_key

    async def validate_key(self, raw_key: str) -> ApiKey:
        """Validate a raw API key and return the entity if valid.

        Raises:
            ApiKeyInvalidError: If the key is invalid, expired, or revoked.
        """
        if not raw_key.startswith("isk_"):
            raise ApiKeyInvalidError("Invalid API key format")

        key_hash = self._hash_key(raw_key)
        api_key = await self._repo.get_by_key_hash(key_hash)

        if api_key is None:
            BusinessEvents.log_event(
                "api_key_auth_failed",
                event_data={"reason": "key_not_found", "key_prefix": raw_key[:12]},
            )
            raise ApiKeyInvalidError("Invalid API key")

        # Timing-safe comparison (defense in depth, even though we looked up by hash)
        if not hmac.compare_digest(api_key.key_hash, key_hash):
            raise ApiKeyInvalidError("Invalid API key")

        if not api_key.is_usable():
            reason = "expired" if api_key.is_expired() else "revoked"
            BusinessEvents.log_event(
                "api_key_auth_failed",
                event_data={
                    "reason": reason,
                    "key_id": api_key.id,
                    "key_prefix": api_key.key_prefix,
                },
            )
            raise ApiKeyInvalidError(f"API key is {reason}")

        # Keep this in request flow to avoid background task/session lifetime races.
        now = datetime.now(UTC)
        await self._repo.update_last_used(api_key.id, now)

        return api_key

    async def revoke_key(self, user_id: str, key_id: str) -> ApiKey:
        """Revoke an API key.

        Raises:
            ApiKeyNotFoundError: If the key doesn't exist or doesn't belong to the user.
        """
        api_key = await self._repo.get_by_id(key_id)
        if api_key is None or api_key.user_id != user_id or api_key.is_deleted:
            raise ApiKeyNotFoundError(f"API key {key_id} not found")

        api_key.revoke()
        updated = await self._repo.update(api_key)

        BusinessEvents.log_event(
            "api_key_revoked",
            user_id=user_id,
            event_data={"key_id": key_id, "key_prefix": api_key.key_prefix},
        )

        return updated

    async def rotate_key(
        self,
        user_id: str,
        key_id: str,
    ) -> tuple[ApiKey, str]:
        """Rotate an API key: create new key, then revoke old one.

        Both operations use the same DB session (transaction), so they are atomic.

        Returns:
            Tuple of (new ApiKey entity, new raw key string).

        Raises:
            ApiKeyNotFoundError: If the old key doesn't exist or doesn't belong to the user.
        """
        old_key = await self._repo.get_by_id(key_id)
        if old_key is None or old_key.user_id != user_id or old_key.is_deleted:
            raise ApiKeyNotFoundError(f"API key {key_id} not found")

        # Create new key with same name and scopes
        new_key, raw_key = await self.create_key(
            user_id=user_id,
            name=old_key.name,
            scopes=old_key.scopes,
            expires_in_days=None,  # Use default expiry
            skip_limit_check=True,  # rotation replaces one existing key
        )

        # Revoke old key
        old_key.revoke()
        await self._repo.update(old_key)

        BusinessEvents.log_event(
            "api_key_rotated",
            user_id=user_id,
            event_data={
                "old_key_id": key_id,
                "new_key_id": new_key.id,
                "old_prefix": old_key.key_prefix,
                "new_prefix": new_key.key_prefix,
            },
        )

        return new_key, raw_key

    async def list_keys(self, user_id: str) -> list[ApiKey]:
        """List all API keys for a user."""
        return await self._repo.list_by_user(user_id)
