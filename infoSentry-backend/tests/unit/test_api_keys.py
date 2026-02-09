"""Tests for API Key module — domain entities, service, and unified auth."""

from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.modules.api_keys.application.service import (
    ApiKeyInvalidError,
    ApiKeyLimitExceededError,
    ApiKeyNotFoundError,
    ApiKeyService,
)
from src.modules.api_keys.domain.entities import ALL_SCOPES, ApiKey, ApiKeyScope
from src.modules.api_keys.domain.repository import ApiKeyRepository

# ============================================
# Domain Entity Tests
# ============================================


class TestApiKeyEntity:
    """Tests for ApiKey domain entity."""

    def test_create_api_key(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=["goals:read", "goals:write"],
        )
        assert key.user_id == "user-123"
        assert key.name == "Test Key"
        assert key.is_active is True
        assert key.is_deleted is False
        assert key.expires_at is None
        assert key.last_used_at is None

    def test_revoke(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=["goals:read"],
        )
        key.revoke()
        assert key.is_active is False

    def test_is_expired_no_expiry(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=[],
            expires_at=None,
        )
        assert key.is_expired() is False

    def test_is_expired_future(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=[],
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        assert key.is_expired() is False

    def test_is_expired_past(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=[],
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert key.is_expired() is True

    def test_is_usable(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=["goals:read"],
        )
        assert key.is_usable() is True

    def test_is_usable_revoked(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=["goals:read"],
            is_active=False,
        )
        assert key.is_usable() is False

    def test_is_usable_deleted(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=["goals:read"],
            is_deleted=True,
        )
        assert key.is_usable() is False

    def test_has_scope(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=["goals:read", "sources:read"],
        )
        assert key.has_scope("goals:read") is True
        assert key.has_scope("goals:write") is False

    def test_record_usage(self) -> None:
        key = ApiKey(
            user_id="user-123",
            name="Test Key",
            key_prefix="isk_AbCdEfGh",
            key_hash="abc123hash",
            scopes=[],
        )
        now = datetime.now(UTC)
        key.record_usage(now)
        assert key.last_used_at == now

    def test_scope_enum_values(self) -> None:
        assert ApiKeyScope.GOALS_READ.value == "goals:read"
        assert ApiKeyScope.ADMIN_WRITE.value == "admin:write"

    def test_all_scopes_frozenset(self) -> None:
        assert isinstance(ALL_SCOPES, frozenset)
        assert "goals:read" in ALL_SCOPES
        assert len(ALL_SCOPES) == len(ApiKeyScope)


# ============================================
# In-Memory Repository for Service Tests
# ============================================


class InMemoryApiKeyRepository(ApiKeyRepository):
    """In-memory repository for testing ApiKeyService."""

    def __init__(self) -> None:
        self.keys: dict[str, ApiKey] = {}
        self.update_last_used_calls: list[tuple[str, datetime]] = []

    async def get_by_id(self, key_id: str) -> ApiKey | None:
        key = self.keys.get(key_id)
        if key and not key.is_deleted:
            return key
        return None

    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        for key in self.keys.values():
            if key.key_hash == key_hash and not key.is_deleted:
                return key
        return None

    async def list_by_user(self, user_id: str) -> list[ApiKey]:
        return [
            key
            for key in self.keys.values()
            if key.user_id == user_id and not key.is_deleted
        ]

    async def count_active_by_user(self, user_id: str) -> int:
        return sum(
            1
            for key in self.keys.values()
            if key.user_id == user_id and not key.is_deleted and key.is_active
        )

    async def update_last_used(self, key_id: str, used_at: datetime) -> None:
        self.update_last_used_calls.append((key_id, used_at))
        if key_id in self.keys:
            self.keys[key_id].last_used_at = used_at

    async def create(self, entity: ApiKey) -> ApiKey:
        self.keys[entity.id] = entity
        return entity

    async def update(self, entity: ApiKey) -> ApiKey:
        self.keys[entity.id] = entity
        return entity

    async def delete(self, entity: ApiKey | str) -> bool:
        key_id = entity.id if isinstance(entity, ApiKey) else entity
        if key_id in self.keys:
            self.keys[key_id].is_deleted = True
            return True
        return False

    async def list_all(
        self, page: int = 1, page_size: int = 10, include_deleted: bool = False
    ) -> tuple[list[ApiKey], int]:
        keys = list(self.keys.values())
        return keys, len(keys)


# ============================================
# Service Tests
# ============================================


class TestApiKeyService:
    """Tests for ApiKeyService."""

    @pytest.fixture
    def repo(self) -> InMemoryApiKeyRepository:
        return InMemoryApiKeyRepository()

    @pytest.fixture
    def service(self, repo: InMemoryApiKeyRepository) -> ApiKeyService:
        return ApiKeyService(repository=repo)

    @pytest.mark.anyio
    async def test_create_key(self, service: ApiKeyService) -> None:
        """Test basic key creation."""
        key, raw = await service.create_key(
            user_id="user-1",
            name="My Agent",
            scopes=["goals:read"],
        )

        assert key.user_id == "user-1"
        assert key.name == "My Agent"
        assert key.scopes == ["goals:read"]
        assert key.is_active is True
        assert raw.startswith("isk_")
        assert len(raw) > 16  # isk_ + 32-byte urlsafe encoded
        assert key.key_prefix == raw[:12]

    @pytest.mark.anyio
    async def test_create_key_hash_stored(
        self, service: ApiKeyService, repo: InMemoryApiKeyRepository
    ) -> None:
        """Test that only the hash is stored, not the raw key."""
        key, raw = await service.create_key(
            user_id="user-1",
            name="Test",
            scopes=["goals:read"],
        )

        # The raw key should NOT be stored in the repo
        stored_key = repo.keys[key.id]
        assert stored_key.key_hash != raw
        # The hash should match SHA-256 of raw
        expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert stored_key.key_hash == expected_hash

    @pytest.mark.anyio
    async def test_create_key_with_expiry(self, service: ApiKeyService) -> None:
        """Test key creation with explicit expiry."""
        key, _ = await service.create_key(
            user_id="user-1",
            name="Expiring Key",
            scopes=["goals:read"],
            expires_in_days=30,
        )

        assert key.expires_at is not None
        # Should expire approximately 30 days from now
        delta = key.expires_at - datetime.now(UTC)
        assert 29 <= delta.days <= 30

    @pytest.mark.anyio
    async def test_create_key_limit_exceeded(
        self, service: ApiKeyService, repo: InMemoryApiKeyRepository
    ) -> None:
        """Test that key creation fails when limit is reached."""
        # Create max number of keys
        with patch(
            "src.modules.api_keys.application.service.settings"
        ) as mock_settings:
            mock_settings.API_KEY_MAX_PER_USER = 2
            mock_settings.API_KEY_DEFAULT_EXPIRE_DAYS = 0

            await service.create_key("user-1", "Key 1", ["goals:read"])
            await service.create_key("user-1", "Key 2", ["goals:read"])

            with pytest.raises(ApiKeyLimitExceededError):
                await service.create_key("user-1", "Key 3", ["goals:read"])

    @pytest.mark.anyio
    async def test_validate_key_success(self, service: ApiKeyService) -> None:
        """Test successful key validation."""
        _, raw = await service.create_key(
            user_id="user-1",
            name="Valid Key",
            scopes=["goals:read"],
        )

        validated = await service.validate_key(raw)
        assert validated.user_id == "user-1"
        assert validated.name == "Valid Key"

    @pytest.mark.anyio
    async def test_validate_key_invalid_format(self, service: ApiKeyService) -> None:
        """Test validation with wrong key format."""
        with pytest.raises(ApiKeyInvalidError, match="format"):
            await service.validate_key("not_a_valid_key")

    @pytest.mark.anyio
    async def test_validate_key_not_found(self, service: ApiKeyService) -> None:
        """Test validation with unknown key."""
        with pytest.raises(ApiKeyInvalidError, match="Invalid"):
            await service.validate_key("isk_nonexistent_key_here_123456")

    @pytest.mark.anyio
    async def test_validate_key_revoked(self, service: ApiKeyService) -> None:
        """Test validation with revoked key."""
        key, raw = await service.create_key(
            user_id="user-1",
            name="Revoked Key",
            scopes=["goals:read"],
        )
        await service.revoke_key("user-1", key.id)

        with pytest.raises(ApiKeyInvalidError, match="revoked"):
            await service.validate_key(raw)

    @pytest.mark.anyio
    async def test_validate_key_expired(
        self, service: ApiKeyService, repo: InMemoryApiKeyRepository
    ) -> None:
        """Test validation with expired key."""
        key, raw = await service.create_key(
            user_id="user-1",
            name="Expired Key",
            scopes=["goals:read"],
        )
        # Manually set expires_at to past
        repo.keys[key.id].expires_at = datetime.now(UTC) - timedelta(hours=1)

        with pytest.raises(ApiKeyInvalidError, match="expired"):
            await service.validate_key(raw)

    @pytest.mark.anyio
    async def test_validate_key_hmac_compare(self, service: ApiKeyService) -> None:
        """Test that validation uses timing-safe comparison."""
        _, raw = await service.create_key(
            user_id="user-1",
            name="HMAC Test",
            scopes=["goals:read"],
        )

        # The actual hmac.compare_digest call happens inside validate_key
        validated = await service.validate_key(raw)
        assert validated is not None

    @pytest.mark.anyio
    async def test_revoke_key(
        self, service: ApiKeyService, repo: InMemoryApiKeyRepository
    ) -> None:
        """Test key revocation."""
        key, _ = await service.create_key(
            user_id="user-1",
            name="To Revoke",
            scopes=["goals:read"],
        )

        revoked = await service.revoke_key("user-1", key.id)
        assert revoked.is_active is False
        assert repo.keys[key.id].is_active is False

    @pytest.mark.anyio
    async def test_revoke_key_wrong_user(self, service: ApiKeyService) -> None:
        """Test that keys can only be revoked by their owner."""
        key, _ = await service.create_key(
            user_id="user-1",
            name="Not Yours",
            scopes=["goals:read"],
        )

        with pytest.raises(ApiKeyNotFoundError):
            await service.revoke_key("user-2", key.id)

    @pytest.mark.anyio
    async def test_rotate_key(
        self, service: ApiKeyService, repo: InMemoryApiKeyRepository
    ) -> None:
        """Test key rotation (create new, revoke old)."""
        old_key, old_raw = await service.create_key(
            user_id="user-1",
            name="Rotate Me",
            scopes=["goals:read", "sources:read"],
        )

        new_key, new_raw = await service.rotate_key("user-1", old_key.id)

        # New key should be different
        assert new_key.id != old_key.id
        assert new_raw != old_raw
        assert new_raw.startswith("isk_")

        # New key inherits name and scopes
        assert new_key.name == "Rotate Me"
        assert new_key.scopes == ["goals:read", "sources:read"]

        # Old key should be revoked
        old_stored = repo.keys[old_key.id]
        assert old_stored.is_active is False

        # New key should be active
        assert new_key.is_active is True

    @pytest.mark.anyio
    async def test_rotate_key_succeeds_at_limit(self, service: ApiKeyService) -> None:
        """Rotate should work even when user already reached key limit."""
        with patch(
            "src.modules.api_keys.application.service.settings"
        ) as mock_settings:
            mock_settings.API_KEY_MAX_PER_USER = 1
            mock_settings.API_KEY_DEFAULT_EXPIRE_DAYS = 0

            old_key, _ = await service.create_key("user-1", "Only Key", ["goals:read"])
            new_key, raw_key = await service.rotate_key("user-1", old_key.id)

            assert new_key.id != old_key.id
            assert raw_key.startswith("isk_")

    @pytest.mark.anyio
    async def test_list_keys(self, service: ApiKeyService) -> None:
        """Test listing keys for a user."""
        await service.create_key("user-1", "Key 1", ["goals:read"])
        await service.create_key("user-1", "Key 2", ["sources:read"])
        await service.create_key("user-2", "Key 3", ["goals:read"])

        user1_keys = await service.list_keys("user-1")
        assert len(user1_keys) == 2

        user2_keys = await service.list_keys("user-2")
        assert len(user2_keys) == 1


# ============================================
# Unified Auth Tests
# ============================================


class TestUnifiedAuth:
    """Tests for unified auth (AuthContext + require_scope)."""

    def test_auth_context_has_scope(self) -> None:
        from src.core.application.security import AuthContext

        ctx = AuthContext(
            user_id="user-1",
            auth_method="api_key",
            scopes=frozenset(["goals:read", "sources:read"]),
            api_key_id="key-1",
        )
        assert ctx.has_scope("goals:read") is True
        assert ctx.has_scope("goals:write") is False

    def test_auth_context_jwt_all_scopes(self) -> None:
        from src.core.application.security import AuthContext

        ctx = AuthContext(
            user_id="user-1",
            auth_method="jwt",
            scopes=ALL_SCOPES,
        )
        # JWT users get all scopes
        for scope in ApiKeyScope:
            assert ctx.has_scope(scope.value) is True

    def test_auth_context_frozen(self) -> None:
        from src.core.application.security import AuthContext

        ctx = AuthContext(
            user_id="user-1",
            auth_method="jwt",
            scopes=ALL_SCOPES,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.user_id = "user-2"

    @pytest.mark.anyio
    async def test_jwt_only_user_id_rejects_api_key_header(self) -> None:
        from starlette.requests import Request

        from src.core.infrastructure.security.unified_auth import (
            get_current_user_id_from_jwt_only,
        )

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/v1/keys",
            "headers": [(b"x-api-key", b"isk_test_only")],
        }
        request = Request(scope)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user_id_from_jwt_only(request)

        assert exc_info.value.status_code == 401

    def test_main_wires_get_current_user_id_to_jwt_only(self) -> None:
        """Regression: generic current-user dependency must remain JWT-only."""
        from main import app
        from src.core.application import security as app_security
        from src.core.infrastructure.security.unified_auth import (
            get_current_user_id_from_jwt_only,
        )

        assert (
            app.dependency_overrides[app_security.get_current_user_id]
            is get_current_user_id_from_jwt_only
        )

    @pytest.mark.anyio
    async def test_get_current_auth_falls_back_to_jwt_when_api_key_invalid(
        self,
    ) -> None:
        """When both headers exist, invalid API key should not block valid JWT."""
        from starlette.requests import Request

        from src.core.application.security import AuthContext
        from src.core.infrastructure.security.unified_auth import get_current_auth

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/v1/goals",
                "headers": [
                    (b"x-api-key", b"isk_invalid"),
                    (b"authorization", b"Bearer valid_jwt"),
                ],
            }
        )

        with (
            patch(
                "src.core.infrastructure.security.unified_auth._authenticate_api_key",
                side_effect=HTTPException(status_code=401, detail="Invalid API key"),
            ),
            patch(
                "src.core.infrastructure.security.unified_auth._authenticate_jwt",
                return_value=AuthContext(
                    user_id="user-jwt",
                    auth_method="jwt",
                    scopes=ALL_SCOPES,
                ),
            ),
        ):
            auth = await get_current_auth(request, api_key_service=AsyncMock())

        assert auth.user_id == "user-jwt"
        assert auth.auth_method == "jwt"

    @pytest.mark.anyio
    async def test_get_current_auth_does_not_fallback_on_non_401_api_key_error(
        self,
    ) -> None:
        """Only 401 API key failures may fall back to JWT."""
        from starlette.requests import Request

        from src.core.infrastructure.security.unified_auth import get_current_auth

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/v1/goals",
                "headers": [
                    (b"x-api-key", b"isk_invalid"),
                    (b"authorization", b"Bearer valid_jwt"),
                ],
            }
        )

        with (
            patch(
                "src.core.infrastructure.security.unified_auth._authenticate_api_key",
                side_effect=HTTPException(status_code=503, detail="upstream error"),
            ),
            patch(
                "src.core.infrastructure.security.unified_auth._authenticate_jwt",
                return_value=AsyncMock(),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_auth(request, api_key_service=AsyncMock())

        assert exc_info.value.status_code == 503

    def test_openapi_has_no_global_security_requirement(self) -> None:
        """OpenAPI must not apply auth requirement to every route globally."""
        from main import app

        app.openapi_schema = None
        schema = app.openapi()
        assert "security" not in schema
