"""Goal domain events."""

from pydantic import Field

from src.core.domain.events import DomainEvent


class GoalCreatedEvent(DomainEvent):
    """Event raised when a goal is created."""

    goal_id: str = Field(..., description="Goal ID")
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="Goal名称")


class GoalUpdatedEvent(DomainEvent):
    """Event raised when a goal is updated."""

    goal_id: str = Field(..., description="Goal ID")
    name: str = Field(..., description="Goal名称")
    updated_fields: list[str] = Field(..., description="更新的字段")


class GoalPausedEvent(DomainEvent):
    """Event raised when a goal is paused."""

    goal_id: str = Field(..., description="Goal ID")
    name: str = Field(..., description="Goal名称")


class GoalResumedEvent(DomainEvent):
    """Event raised when a goal is resumed."""

    goal_id: str = Field(..., description="Goal ID")
    name: str = Field(..., description="Goal名称")


class GoalArchivedEvent(DomainEvent):
    """Event raised when a goal is archived."""

    goal_id: str = Field(..., description="Goal ID")
    name: str = Field(..., description="Goal名称")


class GoalTermsUpdatedEvent(DomainEvent):
    """Event raised when goal terms are updated."""

    goal_id: str = Field(..., description="Goal ID")
    priority_terms_count: int = Field(..., description="优先词条数量")
    negative_terms_count: int = Field(..., description="负面词条数量")
