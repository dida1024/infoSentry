"""Item domain events."""

from pydantic import Field

from src.core.domain.events import DomainEvent


class ItemIngestedEvent(DomainEvent):
    """Event raised when an item is ingested."""

    item_id: str = Field(..., description="Item ID")
    source_id: str = Field(..., description="来源ID")
    url: str = Field(..., description="原文URL")


class ItemEmbeddedEvent(DomainEvent):
    """Event raised when an item is embedded."""

    item_id: str = Field(..., description="Item ID")
    model: str = Field(..., description="使用的模型")


class MatchComputedEvent(DomainEvent):
    """Event raised when a match is computed."""

    goal_id: str = Field(..., description="Goal ID")
    item_id: str = Field(..., description="Item ID")
    score: float = Field(..., description="匹配分数")
    features: dict = Field(..., description="特征值")
