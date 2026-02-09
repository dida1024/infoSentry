"""API Key database models."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field

from src.core.infrastructure.database.base_model import BaseModel


class ApiKeyModel(BaseModel, table=True):
    """API Key database model."""

    __tablename__ = "api_keys"

    user_id: str = Field(nullable=False, index=True)
    name: str = Field(nullable=False, max_length=100)
    key_prefix: str = Field(nullable=False, max_length=12)
    key_hash: str = Field(nullable=False, unique=True, index=True, max_length=64)
    scopes: list[str] = Field(default_factory=list, sa_type=JSON, nullable=False)
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    is_active: bool = Field(default=True, nullable=False)
