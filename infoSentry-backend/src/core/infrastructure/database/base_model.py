"""Base SQLModel for all database models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    """Return current UTC datetime with timezone info."""
    return datetime.now(UTC)


class BaseModel(SQLModel):
    """Base model with common fields.

    所有时间戳字段使用 UTC 时区，与 domain/base_entity.py 保持一致。
    """

    model_config = {"arbitrary_types_allowed": True}

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)

    created_at: datetime = Field(
        default_factory=_utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )

    updated_at: datetime = Field(
        default_factory=_utc_now,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )

    is_deleted: bool = Field(default=False, nullable=False)
