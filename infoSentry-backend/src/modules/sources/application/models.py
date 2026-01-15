"""Source application data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.modules.sources.domain.entities import SourceType


class SourceData(BaseModel):
    """Source data for queries."""

    id: str
    type: SourceType
    name: str
    enabled: bool
    fetch_interval_sec: int
    next_fetch_at: datetime | None = None
    last_fetch_at: datetime | None = None
    error_streak: int
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SourceListData(BaseModel):
    """Source list query result."""

    items: list[SourceData]
    total: int
    page: int
    page_size: int
