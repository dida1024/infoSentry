"""Source domain events."""

from pydantic import Field

from src.core.domain.events import DomainEvent


class SourceCreatedEvent(DomainEvent):
    """Event raised when a source is created."""

    source_id: str = Field(..., description="源ID")
    name: str = Field(..., description="源名称")
    type: str = Field(..., description="源类型")


class SourceEnabledEvent(DomainEvent):
    """Event raised when a source is enabled."""

    source_id: str = Field(..., description="源ID")
    name: str = Field(..., description="源名称")


class SourceDisabledEvent(DomainEvent):
    """Event raised when a source is disabled."""

    source_id: str = Field(..., description="源ID")
    name: str = Field(..., description="源名称")


class SourceConfigUpdatedEvent(DomainEvent):
    """Event raised when source config is updated."""

    source_id: str = Field(..., description="源ID")
    name: str = Field(..., description="源名称")


class SourceFetchSuccessEvent(DomainEvent):
    """Event raised when a source fetch succeeds."""

    source_id: str = Field(..., description="源ID")
    items_count: int = Field(..., description="抓取的条目数")


class SourceFetchErrorEvent(DomainEvent):
    """Event raised when a source fetch fails."""

    source_id: str = Field(..., description="源ID")
    error: str = Field(..., description="错误信息")
    error_streak: int = Field(..., description="连续错误次数")
