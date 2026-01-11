"""User domain entities."""

from datetime import datetime
from enum import Enum

from pydantic import EmailStr, Field

from src.core.domain.aggregate_root import AggregateRoot
from src.core.domain.base_entity import BaseEntity


class UserStatus(str, Enum):
    """User status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class User(AggregateRoot):
    """User aggregate root."""

    email: EmailStr = Field(..., description="用户邮箱")
    is_active: bool = Field(default=True, description="是否激活")
    status: UserStatus = Field(default=UserStatus.ACTIVE, description="用户状态")
    last_login_at: datetime | None = Field(default=None, description="最后登录时间")

    # Profile fields (optional for v0)
    display_name: str | None = Field(default=None, description="显示名称")
    timezone: str = Field(default="Asia/Shanghai", description="时区")

    def update_last_login(self) -> None:
        """Update last login timestamp."""
        self.last_login_at = datetime.now()
        self._update_timestamp()

        from src.modules.users.domain.events import UserLoggedInEvent

        self.add_domain_event(UserLoggedInEvent(user_id=self.id, email=self.email))

    def deactivate(self) -> None:
        """Deactivate user account."""
        if not self.is_active:
            return
        self.is_active = False
        self.status = UserStatus.INACTIVE
        self._update_timestamp()

        from src.modules.users.domain.events import UserDeactivatedEvent

        self.add_domain_event(UserDeactivatedEvent(user_id=self.id, email=self.email))

    def activate(self) -> None:
        """Activate user account."""
        if self.is_active:
            return
        self.is_active = True
        self.status = UserStatus.ACTIVE
        self._update_timestamp()

        from src.modules.users.domain.events import UserActivatedEvent

        self.add_domain_event(UserActivatedEvent(user_id=self.id, email=self.email))

    def update_profile(
        self,
        display_name: str | None = None,
        timezone: str | None = None,
    ) -> list[str]:
        """Update user profile."""
        updated_fields: list[str] = []

        if display_name is not None and display_name != self.display_name:
            self.display_name = display_name
            updated_fields.append("display_name")

        if timezone is not None and timezone != self.timezone:
            self.timezone = timezone
            updated_fields.append("timezone")

        if updated_fields:
            self._update_timestamp()
            from src.modules.users.domain.events import UserProfileUpdatedEvent

            self.add_domain_event(
                UserProfileUpdatedEvent(
                    user_id=self.id,
                    updated_fields=updated_fields,
                )
            )

        return updated_fields


class MagicLink(AggregateRoot):
    """Magic link for passwordless authentication."""

    email: EmailStr = Field(..., description="目标邮箱")
    token: str = Field(..., description="Magic link token")
    expires_at: datetime = Field(..., description="过期时间")
    is_used: bool = Field(default=False, description="是否已使用")
    used_at: datetime | None = Field(default=None, description="使用时间")

    def is_valid(self) -> bool:
        """Check if the magic link is still valid."""
        return not self.is_used and datetime.now() < self.expires_at

    def mark_as_used(self) -> None:
        """Mark the magic link as used."""
        self.is_used = True
        self.used_at = datetime.now()
        self._update_timestamp()


class UserBudgetDaily(BaseEntity):
    """User daily AI budget usage - 用户每日 AI 预算使用。"""

    user_id: str = Field(..., description="用户ID")
    date: str = Field(..., description="日期（YYYY-MM-DD）")
    embedding_tokens_est: int = Field(default=0, description="embedding token估算")
    judge_tokens_est: int = Field(default=0, description="judge token估算")
    usd_est: float = Field(default=0.0, description="美元估算")

    def add_embedding_tokens(self, tokens: int) -> None:
        """Add embedding tokens."""
        self.embedding_tokens_est += tokens
        self._update_timestamp()

    def add_judge_tokens(self, tokens: int) -> None:
        """Add judge tokens."""
        self.judge_tokens_est += tokens
        self._update_timestamp()

    def add_cost(self, usd: float) -> None:
        """Add estimated cost."""
        self.usd_est += usd
        self._update_timestamp()
