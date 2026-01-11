"""Source application commands."""

from typing import Any

from pydantic import BaseModel

from src.modules.sources.domain.entities import SourceType


class CreateSourceCommand(BaseModel):
    """Create a new source."""

    type: SourceType
    name: str
    config: dict[str, Any]
    fetch_interval_sec: int | None = None


class UpdateSourceCommand(BaseModel):
    """Update an existing source."""

    source_id: str
    name: str | None = None
    config: dict[str, Any] | None = None
    fetch_interval_sec: int | None = None


class EnableSourceCommand(BaseModel):
    """Enable a source."""

    source_id: str


class DisableSourceCommand(BaseModel):
    """Disable a source."""

    source_id: str


class DeleteSourceCommand(BaseModel):
    """Delete a source."""

    source_id: str
