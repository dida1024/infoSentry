"""Push database models."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Text
from sqlmodel import Field

from src.core.infrastructure.database.base_model import BaseModel
from src.modules.push.domain.entities import (
    FeedbackType,
    PushChannel,
    PushDecision,
    PushStatus,
)


class PushDecisionModel(BaseModel, table=True):
    """Push decision database model."""

    __tablename__ = "push_decisions"

    goal_id: str = Field(nullable=False, index=True)
    item_id: str = Field(nullable=False, index=True)
    decision: PushDecision = Field(
        sa_type=Enum(
            PushDecision,
            name="pushdecision",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    status: PushStatus = Field(
        default=PushStatus.PENDING,
        sa_type=Enum(
            PushStatus,
            name="pushstatus",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    channel: PushChannel = Field(
        default=PushChannel.EMAIL,
        sa_type=Enum(
            PushChannel,
            name="pushchannel",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
    reason_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )
    decided_at: datetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    sent_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    dedupe_key: str | None = Field(default=None, unique=True, nullable=True)


class ClickEventModel(BaseModel, table=True):
    """Click event database model."""

    __tablename__ = "click_events"

    item_id: str = Field(nullable=False, index=True)
    goal_id: str | None = Field(default=None, nullable=True, index=True)
    channel: PushChannel = Field(
        default=PushChannel.EMAIL,
        sa_type=Enum(
            PushChannel,
            name="pushchannel",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
    clicked_at: datetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    user_agent: str | None = Field(default=None, sa_type=Text, nullable=True)
    ip_address: str | None = Field(default=None, nullable=True)


class ItemFeedbackModel(BaseModel, table=True):
    """Item feedback database model."""

    __tablename__ = "item_feedback"

    item_id: str = Field(nullable=False, index=True)
    goal_id: str = Field(nullable=False, index=True)
    user_id: str = Field(nullable=False, index=True)
    feedback: FeedbackType = Field(
        sa_type=Enum(
            FeedbackType,
            name="feedbacktype",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
    block_source: bool = Field(default=False, nullable=False)


class BlockedSourceModel(BaseModel, table=True):
    """Blocked source database model."""

    __tablename__ = "blocked_sources"

    user_id: str = Field(nullable=False, index=True)
    goal_id: str | None = Field(default=None, nullable=True, index=True)
    source_id: str = Field(nullable=False, index=True)
    blocked_at: datetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
