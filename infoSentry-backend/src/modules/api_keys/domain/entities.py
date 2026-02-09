"""API Key domain entities."""

from datetime import datetime

from pydantic import Field

from src.core.domain.auth_scope import AuthScope
from src.core.domain.base_entity import BaseEntity

# Backward-compatible alias for API schemas/tests.
ApiKeyScope = AuthScope


# All scopes, granted to JWT-authenticated users.
ALL_SCOPES: frozenset[str] = frozenset(scope.value for scope in AuthScope)


class ApiKey(BaseEntity):
    """API Key entity for external agent authentication."""

    user_id: str = Field(..., description="所属用户 ID")
    name: str = Field(..., description="Key 名称（如 'My GPT Agent'）")
    key_prefix: str = Field(..., description="Key 前缀（isk_xxxx），用于识别和日志")
    key_hash: str = Field(..., description="SHA-256 哈希值")
    scopes: list[str] = Field(default_factory=list, description="授权 scope 列表")
    expires_at: datetime | None = Field(default=None, description="过期时间")
    last_used_at: datetime | None = Field(default=None, description="最后使用时间")
    is_active: bool = Field(default=True, description="是否激活")

    def revoke(self) -> None:
        """Revoke this API key."""
        self.is_active = False
        self._update_timestamp()

    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        from datetime import UTC

        return datetime.now(UTC) > self.expires_at

    def is_usable(self) -> bool:
        """Check if the key can be used for authentication."""
        return self.is_active and not self.is_expired() and not self.is_deleted

    def has_scope(self, scope: str) -> bool:
        """Check if this key has the given scope."""
        return scope in self.scopes

    def record_usage(self, used_at: datetime) -> None:
        """Record that this key was used."""
        self.last_used_at = used_at
