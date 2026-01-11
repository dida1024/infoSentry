"""抓取器基类定义。

提供统一的抓取接口，所有具体抓取器（NewsNow/RSS/SITE）都继承此基类。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FetchStatus(str, Enum):
    """抓取状态枚举。"""

    SUCCESS = "success"
    PARTIAL = "partial"  # 部分成功
    FAILED = "failed"
    EMPTY = "empty"  # 成功但无数据


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
        """是否成功（包含部分成功）。"""
        return self.status in (
            FetchStatus.SUCCESS,
            FetchStatus.PARTIAL,
            FetchStatus.EMPTY,
        )

    @property
    def items_count(self) -> int:
        """抓取到的条目数。"""
        return len(self.items)

    @classmethod
    def success(
        cls,
        items: list[FetchedItem],
        duration_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> "FetchResult":
        """创建成功结果。"""
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
        """创建部分成功结果。"""
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
        """创建失败结果。"""
        return cls(
            status=FetchStatus.FAILED,
            items=[],
            error_message=error_message,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )


class BaseFetcher(ABC):
    """抓取器基类。

    所有具体抓取器都应继承此基类并实现 fetch 方法。
    """

    def __init__(self, config: dict[str, Any], max_items: int = 20):
        """初始化抓取器。

        Args:
            config: 源配置（不同类型的源有不同的配置结构）
            max_items: 单次抓取最大条目数
        """
        self.config = config
        self.max_items = max_items

    @abstractmethod
    async def fetch(self) -> FetchResult:
        """执行抓取操作。

        Returns:
            FetchResult: 抓取结果
        """
        pass

    @abstractmethod
    def validate_config(self) -> tuple[bool, str | None]:
        """验证配置是否有效。

        Returns:
            (是否有效, 错误信息)
        """
        pass

    def _truncate_snippet(self, text: str | None, max_length: int = 500) -> str | None:
        """截断摘要文本。"""
        if not text:
            return None
        text = text.strip()
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def _clean_title(self, title: str | None) -> str:
        """清理标题文本。"""
        if not title:
            return ""
        # 移除多余空白
        return " ".join(title.split())
