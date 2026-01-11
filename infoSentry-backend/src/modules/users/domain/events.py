"""User domain events."""

from pydantic import Field

from src.core.domain.events import DomainEvent


class UserCreatedEvent(DomainEvent):
    """Event raised when a user is created."""

    user_id: str = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")


class UserLoggedInEvent(DomainEvent):
    """Event raised when a user logs in."""

    user_id: str = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")


class UserDeactivatedEvent(DomainEvent):
    """Event raised when a user is deactivated."""

    user_id: str = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")


class UserActivatedEvent(DomainEvent):
    """Event raised when a user is activated."""

    user_id: str = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")


class UserProfileUpdatedEvent(DomainEvent):
    """Event raised when user profile is updated."""

    user_id: str = Field(..., description="用户ID")
    updated_fields: list[str] = Field(..., description="更新的字段列表")


class MagicLinkRequestedEvent(DomainEvent):
    """Event raised when a magic link is requested."""

    email: str = Field(..., description="请求的邮箱")
    magic_link_id: str = Field(..., description="Magic link ID")
