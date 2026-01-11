"""Push API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.push.domain.entities import (
    FeedbackType,
    PushChannel,
    PushDecision,
    PushStatus,
)


class EvidenceItem(BaseModel):
    """Evidence item in reason."""

    type: str = Field(..., description="证据类型")
    value: str = Field(..., description="证据值")
    quote: str | None = Field(None, description="引用文本")
    ref: dict[str, str] | None = Field(None, description="引用来源")


class ReasonResponse(BaseModel):
    """Reason response with evidence."""

    summary: str = Field(..., description="原因摘要")
    score: float = Field(..., description="匹配分数")
    evidence: list[EvidenceItem] = Field(default_factory=list, description="证据列表")


class ItemSummaryResponse(BaseModel):
    """Item summary in notification."""

    title: str = Field(..., description="标题")
    url: str = Field(..., description="原文URL")
    source_name: str | None = Field(None, description="来源名称")
    published_at: datetime | None = Field(None, description="发布时间")
    snippet: str | None = Field(None, description="摘要")


class ActionResponse(BaseModel):
    """Action item."""

    type: str = Field(..., description="操作类型")
    url: str | None = Field(None, description="操作URL")


class NotificationResponse(BaseModel):
    """Notification response."""

    id: str = Field(..., description="通知ID")
    goal_id: str = Field(..., description="Goal ID")
    item_id: str = Field(..., description="Item ID")
    decision: PushDecision = Field(..., description="推送决策")
    status: PushStatus = Field(..., description="推送状态")
    channel: PushChannel = Field(..., description="推送渠道")
    item: ItemSummaryResponse = Field(..., description="条目信息")
    reason: ReasonResponse | None = Field(None, description="原因")
    actions: list[ActionResponse] = Field(default_factory=list, description="可用操作")
    decided_at: datetime = Field(..., description="决策时间")
    sent_at: datetime | None = Field(None, description="发送时间")


class NotificationListResponse(BaseModel):
    """Notification list response."""

    notifications: list[NotificationResponse]
    next_cursor: str | None = None
    has_more: bool = False


class FeedbackRequest(BaseModel):
    """Feedback request."""

    goal_id: str = Field(..., description="Goal ID")
    feedback: FeedbackType = Field(..., description="反馈类型")
    block_source: bool = Field(default=False, description="是否屏蔽来源")

    class Config:
        json_schema_extra = {
            "example": {"goal_id": "uuid", "feedback": "LIKE", "block_source": False}
        }


class FeedbackResponse(BaseModel):
    """Feedback response."""

    ok: bool = True
    feedback_id: str = Field(..., description="反馈ID")
