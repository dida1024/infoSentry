"""Item database models."""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Enum, Text
from sqlmodel import Field

from src.core.config import settings
from src.core.infrastructure.database.base_model import BaseModel
from src.modules.items.domain.entities import EmbeddingStatus


class ItemModel(BaseModel, table=True):
    """Item database model."""

    __tablename__ = "items"

    source_id: str = Field(nullable=False, index=True)
    url: str = Field(nullable=False, sa_type=Text)
    url_hash: str = Field(nullable=False, unique=True, index=True)
    title: str = Field(nullable=False, sa_type=Text)
    snippet: str | None = Field(default=None, sa_type=Text, nullable=True)
    summary: str | None = Field(default=None, sa_type=Text, nullable=True)
    published_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    ingested_at: datetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Embedding - using pgvector
    embedding: list[float] | None = Field(
        default=None,
        sa_type=Vector(settings.EMBEDDING_DIMENSION),
        nullable=True,
    )
    embedding_status: EmbeddingStatus = Field(
        default=EmbeddingStatus.PENDING,
        sa_type=Enum(
            EmbeddingStatus,
            name="embeddingstatus",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    embedding_model: str | None = Field(default=None, nullable=True)

    # Raw data
    raw_data: dict[str, Any] | None = Field(
        default=None,
        sa_type=JSON,
        nullable=True,
    )


class GoalItemMatchModel(BaseModel, table=True):
    """Goal-Item match database model."""

    __tablename__ = "goal_item_matches"

    goal_id: str = Field(nullable=False, index=True)
    item_id: str = Field(nullable=False, index=True)
    match_score: float = Field(nullable=False, index=True)
    features_json: dict = Field(default_factory=dict, sa_type=JSON, nullable=False)
    reasons_json: dict = Field(default_factory=dict, sa_type=JSON, nullable=False)
    computed_at: datetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )

    # Composite unique constraint would be defined in migration
