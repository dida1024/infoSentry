"""Source application commands."""

from typing import Any

from pydantic import BaseModel

from src.modules.sources.domain.entities import SourceType


class CreateSourceCommand(BaseModel):
    """Create a new source."""

    user_id: str
    type: SourceType
    name: str
    config: dict[str, Any]
    fetch_interval_sec: int | None = None
    is_private: bool = False


class UpdateSourceCommand(BaseModel):
    """Update an existing source."""

    source_id: str
    user_id: str
    name: str | None = None
    config: dict[str, Any] | None = None
    fetch_interval_sec: int | None = None


class EnableSourceCommand(BaseModel):
    """Enable a source."""

    source_id: str
    user_id: str


class DisableSourceCommand(BaseModel):
    """Disable a source."""

    source_id: str
    user_id: str


class DeleteSourceCommand(BaseModel):
    """Delete a source."""

    source_id: str
    user_id: str


class SubscribeSourceCommand(BaseModel):
    """Subscribe to a source."""

    source_id: str
    user_id: str
