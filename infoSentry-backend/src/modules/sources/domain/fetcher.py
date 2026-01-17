"""Fetcher domain interfaces and models."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from ipaddress import ip_address
from typing import Any, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from src.modules.sources.domain.entities import SourceType


class FetchStatus(str, Enum):
    """抓取状态枚举。"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    EMPTY = "empty"


class FetchedItem(BaseModel):
    """抓取到的条目数据模型。"""

    model_config = ConfigDict(frozen=True)

    url: str = Field(..., description="原文URL")
    title: str = Field(..., description="标题")
    snippet: str | None = Field(default=None, description="摘要片段")
    published_at: datetime | None = Field(default=None, description="发布时间")
    raw_data: dict[str, Any] | None = Field(default=None, description="原始数据")


@dataclass
class FetchResult:
    """抓取结果封装。"""

    status: FetchStatus
    items: list[FetchedItem] = field(default_factory=list)
    error_message: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status in (
            FetchStatus.SUCCESS,
            FetchStatus.PARTIAL,
            FetchStatus.EMPTY,
        )

    @property
    def items_count(self) -> int:
        return len(self.items)

    @classmethod
    def success(
        cls,
        items: list[FetchedItem],
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "FetchResult":
        status = FetchStatus.EMPTY if not items else FetchStatus.SUCCESS
        return cls(
            status=status,
            items=items,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

    @classmethod
    def partial(
        cls,
        items: list[FetchedItem],
        error_message: str,
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "FetchResult":
        return cls(
            status=FetchStatus.PARTIAL,
            items=items,
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

    @classmethod
    def failed(
        cls,
        error_message: str,
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "FetchResult":
        return cls(
            status=FetchStatus.FAILED,
            items=[],
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )


class BaseFetcher(ABC):
    """抓取器基类。"""

    def __init__(self, config: dict[str, Any], max_items: int = 20):
        self.config = config
        self.max_items = max_items

    @abstractmethod
    async def fetch(self) -> FetchResult: ...

    @abstractmethod
    def validate_config(self) -> tuple[bool, str | None]: ...

    def _truncate_snippet(self, text: str | None, max_length: int = 500) -> str | None:
        if not text:
            return None
        text = text.strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _clean_title(self, title: str | None) -> str:
        if not title:
            return ""
        cleaned = re.sub(r"<[^>]+>", "", title)
        return " ".join(cleaned.split())

    def _is_allowed_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        if host in {"localhost"}:
            return False
        if host.endswith((".local", ".internal")):
            return False
        try:
            ip_value = ip_address(host)
        except ValueError:
            return True
        if (
            ip_value.is_private
            or ip_value.is_loopback
            or ip_value.is_link_local
            or ip_value.is_reserved
            or ip_value.is_multicast
        ):
            return False
        return True


class FetcherFactory(Protocol):
    def create(
        self,
        source_type: SourceType,
        config: dict[str, Any],
        max_items: int | None = None,
    ) -> BaseFetcher: ...

    def get_default_interval(self, source_type: SourceType) -> int: ...
