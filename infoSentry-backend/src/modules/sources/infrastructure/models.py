"""Source database models."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Text, UniqueConstraint
from sqlmodel import Field

from src.core.infrastructure.database.base_model import BaseModel
from src.modules.sources.domain.entities import IngestStatus, SourceType


class SourceModel(BaseModel, table=True):
    """Source database model."""

    __tablename__ = "sources"

    type: SourceType = Field(
        sa_type=Enum(
            SourceType,
            name="sourcetype",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    owner_id: str | None = Field(default=None, nullable=True, index=True)
    name: str = Field(nullable=False, unique=True, index=True)
    is_private: bool = Field(default=False, nullable=False, index=True)
    enabled: bool = Field(default=True, nullable=False, index=True)
    fetch_interval_sec: int = Field(default=1800, nullable=False)
    next_fetch_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_fetch_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    error_streak: int = Field(default=0, nullable=False)
    empty_streak: int = Field(default=0, nullable=False)
    config: dict = Field(default_factory=dict, sa_type=JSON, nullable=False)


class SourceSubscriptionModel(BaseModel, table=True):
    """Source subscription database model."""

    __tablename__ = "source_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_id",
            name="uq_source_subscriptions_user_source",
        ),
    )

    user_id: str = Field(nullable=False, index=True)
    source_id: str = Field(nullable=False, index=True)
    enabled: bool = Field(default=True, nullable=False, index=True)


class IngestLogModel(BaseModel, table=True):
    """Ingest log database model.

    用于记录每次抓取的详细信息，便于监控和排查问题。
    """

    __tablename__ = "ingest_logs"

    source_id: str = Field(nullable=False, index=True)
    started_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    status: IngestStatus = Field(
        sa_type=Enum(
            IngestStatus,
            name="ingeststatus",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    items_fetched: int = Field(default=0, nullable=False)
    items_new: int = Field(default=0, nullable=False)
    items_duplicate: int = Field(default=0, nullable=False)
    error_message: str | None = Field(default=None, sa_type=Text, nullable=True)
    duration_ms: int | None = Field(default=None, nullable=True)
    metadata_json: dict | None = Field(default=None, sa_type=JSON, nullable=True)
