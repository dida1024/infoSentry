"""Push domain entities."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field

from src.core.domain.aggregate_root import AggregateRoot
from src.core.domain.base_entity import BaseEntity


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class PushDecision(str, Enum):
    """Push decision types."""

    IMMEDIATE = "IMMEDIATE"
    BATCH = "BATCH"
    DIGEST = "DIGEST"
    IGNORE = "IGNORE"


class PushStatus(str, Enum):
    """Push status types."""

    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    READ = "READ"


class PushChannel(str, Enum):
    """Push channel types."""

    EMAIL = "EMAIL"
    IN_APP = "IN_APP"


class PushDecisionRecord(AggregateRoot):
    """Push decision record - 推送决策记录。"""

    goal_id: str = Field(..., description="Goal ID")
    item_id: str = Field(..., description="Item ID")
    decision: PushDecision = Field(..., description="推送决策")
    status: PushStatus = Field(default=PushStatus.PENDING, description="推送状态")
    channel: PushChannel = Field(default=PushChannel.EMAIL, description="推送渠道")
    reason_json: dict[str, Any] = Field(
        default_factory=dict, description="决策原因（含证据）"
    )
    decided_at: datetime = Field(default_factory=_utc_now, description="决策时间")
    sent_at: datetime | None = Field(default=None, description="发送时间")
    dedupe_key: str | None = Field(default=None, description="去重键")

    def mark_sent(self) -> None:
        """Mark as sent."""
        self.status = PushStatus.SENT
        self.sent_at = datetime.now(UTC)
        self._update_timestamp()

    def mark_failed(self) -> None:
        """Mark as failed."""
        self.status = PushStatus.FAILED
        self._update_timestamp()

    def mark_skipped(self) -> None:
        """Mark as skipped."""
        self.status = PushStatus.SKIPPED
        self._update_timestamp()

    def mark_read(self) -> None:
        """Mark as read."""
        self.status = PushStatus.READ
        self._update_timestamp()


class ClickEvent(BaseEntity):
    """Click event - 点击事件记录。"""

    item_id: str = Field(..., description="Item ID")
    goal_id: str | None = Field(default=None, description="Goal ID")
    channel: PushChannel = Field(default=PushChannel.EMAIL, description="来源渠道")
    clicked_at: datetime = Field(default_factory=_utc_now, description="点击时间")
    user_agent: str | None = Field(default=None, description="用户代理")
    ip_address: str | None = Field(default=None, description="IP地址")


class FeedbackType(str, Enum):
    """Feedback type enum."""

    LIKE = "LIKE"
    DISLIKE = "DISLIKE"


class ItemFeedback(BaseEntity):
    """Item feedback - 条目反馈。"""

    item_id: str = Field(..., description="Item ID")
    goal_id: str = Field(..., description="Goal ID")
    user_id: str = Field(..., description="User ID")
    feedback: FeedbackType = Field(..., description="反馈类型")
    block_source: bool = Field(default=False, description="是否屏蔽来源")


class BlockedSource(BaseEntity):
    """Blocked source - 屏蔽的来源。"""

    user_id: str = Field(..., description="User ID")
    goal_id: str | None = Field(
        default=None, description="Goal ID（可选，为空则全局屏蔽）"
    )
    source_id: str = Field(..., description="Source ID")
    blocked_at: datetime = Field(default_factory=_utc_now, description="屏蔽时间")
