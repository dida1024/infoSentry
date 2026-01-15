"""Source API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Source type enum for API layer."""

    NEWSNOW = "NEWSNOW"
    RSS = "RSS"
    SITE = "SITE"


class SourceConfigSchema(BaseModel):
    """Source config based on type."""

    # Generic config - actual structure depends on type
    base_url: str | None = None
    source_id: str | None = None
    feed_url: str | None = None
    list_url: str | None = None
    selectors: dict[str, str] | None = None


class CreateSourceRequest(BaseModel):
    """Create source request."""

    type: SourceType = Field(..., description="源类型")
    name: str = Field(..., min_length=1, max_length=100, description="源名称")
    config: dict[str, Any] = Field(..., description="源配置")
    fetch_interval_sec: int | None = Field(None, ge=60, description="抓取间隔（秒）")

    class Config:
        json_schema_extra = {
            "example": {
                "type": "RSS",
                "name": "Hacker News",
                "config": {"feed_url": "https://news.ycombinator.com/rss"},
            }
        }


class UpdateSourceRequest(BaseModel):
    """Update source request."""

    name: str | None = Field(None, min_length=1, max_length=100, description="源名称")
    config: dict[str, Any] | None = Field(None, description="源配置")
    fetch_interval_sec: int | None = Field(None, ge=60, description="抓取间隔（秒）")


class SourceResponse(BaseModel):
    """Source response."""

    id: str = Field(..., description="源ID")
    type: SourceType = Field(..., description="源类型")
    name: str = Field(..., description="源名称")
    enabled: bool = Field(..., description="是否启用")
    fetch_interval_sec: int = Field(..., description="抓取间隔（秒）")
    next_fetch_at: datetime | None = Field(None, description="下次抓取时间")
    last_fetch_at: datetime | None = Field(None, description="最后抓取时间")
    error_streak: int = Field(..., description="连续错误次数")
    config: dict[str, Any] = Field(..., description="源配置")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        from_attributes = True


class SourceListResponse(BaseModel):
    """Source list response."""

    sources: list[SourceResponse]
