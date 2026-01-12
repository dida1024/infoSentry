"""Push application models."""

from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceItemData(BaseModel):
    type: str
    value: str
    quote: str | None = None
    ref: str | None = None


class ReasonData(BaseModel):
    summary: str
    score: float
    evidence: list[EvidenceItemData] = Field(default_factory=list)


class ItemSummaryData(BaseModel):
    title: str
    url: str
    source_name: str | None = None
    published_at: datetime | None = None
    snippet: str | None = None


class ActionData(BaseModel):
    type: str
    url: str | None = None


class NotificationData(BaseModel):
    id: str
    goal_id: str
    item_id: str
    decision: str
    status: str
    channel: str
    item: ItemSummaryData
    reason: ReasonData | None = None
    actions: list[ActionData]
    decided_at: datetime | None = None
    sent_at: datetime | None = None


class NotificationListData(BaseModel):
    notifications: list[NotificationData]
    next_cursor: str | None = None
    has_more: bool = False


class BudgetData(BaseModel):
    date: str
    embedding_tokens_est: int
    judge_tokens_est: int
    usd_est: float
    embedding_disabled: bool
    judge_disabled: bool
    daily_limit: float


class ClickResult(BaseModel):
    target_url: str
    item_id: str
    goal_id: str | None = None
    channel: str
