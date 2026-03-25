"""Discovery session database models."""

from datetime import datetime

from typing import Any

from sqlalchemy import JSON, Column, DateTime, Index, Text
from sqlmodel import Field

from src.core.infrastructure.database.base_model import BaseModel


class DiscoverySessionModel(BaseModel, table=True):
    """Discovery session database model."""

    __tablename__ = "discovery_sessions"
    __table_args__ = (
        Index("ix_discovery_sessions_user_created", "user_id", "created_at"),
    )

    user_id: str = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
    )
    status: str = Field(default="active", nullable=False, index=True, max_length=20)
    initial_query: str = Field(nullable=False, sa_type=Text)
    messages_json: dict[str, list[dict[str, Any]]] | None = Field(
        default=None, sa_type=JSON, nullable=True
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class DiscoveryCandidateModel(BaseModel, table=True):
    """Discovery candidate source database model."""

    __tablename__ = "discovery_candidates"
    __table_args__ = (
        Index("ix_discovery_candidates_session", "session_id"),
    )

    session_id: str = Field(
        foreign_key="discovery_sessions.id",
        nullable=False,
        index=True,
    )
    source_type: str = Field(nullable=False, max_length=20)
    name: str = Field(nullable=False, max_length=255)
    url: str = Field(nullable=False, sa_type=Text)
    config_json: dict[str, Any] | None = Field(default=None, sa_type=JSON, nullable=True)
    status: str = Field(default="discovered", nullable=False, max_length=20)
    validation_result_json: dict[str, Any] | None = Field(
        default=None, sa_type=JSON, nullable=True
    )
    discovered_via: str = Field(nullable=False, max_length=30)
    source_id: str | None = Field(
        default=None,
        foreign_key="sources.id",
        nullable=True,
        max_length=36,
    )
