"""Source domain entities."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from src.core.domain.aggregate_root import AggregateRoot


class SourceType(str, Enum):
    """Source type enum."""

    NEWSNOW = "NEWSNOW"
    RSS = "RSS"
    SITE = "SITE"


class Source(AggregateRoot):
    """Source aggregate root - 信息源实体。"""

    type: SourceType = Field(..., description="源类型")
    name: str = Field(..., description="源名称")
    enabled: bool = Field(default=True, description="是否启用")
    fetch_interval_sec: int = Field(default=1800, description="抓取间隔（秒）")
    next_fetch_at: datetime | None = Field(default=None, description="下次抓取时间")
    last_fetch_at: datetime | None = Field(default=None, description="最后抓取时间")
    error_streak: int = Field(default=0, description="连续错误次数")
    empty_streak: int = Field(default=0, description="连续空结果次数")
    config: dict[str, Any] = Field(default_factory=dict, description="源配置")

    # config schema based on type:
    # NEWSNOW: {"base_url": str, "source_id": str}
    # RSS: {"feed_url": str}
    # SITE: {"list_url": str, "selectors": {"item": str, "title": str, "link": str, "snippet": str}}

    def enable(self) -> None:
        """Enable the source."""
        if self.enabled:
            return
        self.enabled = True
        self._update_timestamp()

        from src.modules.sources.domain.events import SourceEnabledEvent

        self.add_domain_event(SourceEnabledEvent(source_id=self.id, name=self.name))

    def disable(self) -> None:
        """Disable the source."""
        if not self.enabled:
            return
        self.enabled = False
        self._update_timestamp()

        from src.modules.sources.domain.events import SourceDisabledEvent

        self.add_domain_event(SourceDisabledEvent(source_id=self.id, name=self.name))

    def mark_fetch_success(self, items_count: int) -> None:
        """Mark a successful fetch."""
        self.last_fetch_at = datetime.now()
        self.error_streak = 0
        if items_count == 0:
            self.empty_streak += 1
        else:
            self.empty_streak = 0
        self._schedule_next_fetch()
        self._update_timestamp()

    def mark_fetch_error(self) -> None:
        """Mark a failed fetch."""
        self.last_fetch_at = datetime.now()
        self.error_streak += 1
        self._schedule_next_fetch_with_backoff()
        self._update_timestamp()

    def _schedule_next_fetch(self) -> None:
        """Schedule the next fetch based on interval."""
        from datetime import timedelta

        self.next_fetch_at = datetime.now() + timedelta(seconds=self.fetch_interval_sec)

    def _schedule_next_fetch_with_backoff(self) -> None:
        """Schedule the next fetch with exponential backoff."""
        from datetime import timedelta

        # 指数退避: 2^error_streak * interval, 最大 4 小时
        backoff_multiplier = min(2**self.error_streak, 8)
        delay_seconds = min(self.fetch_interval_sec * backoff_multiplier, 14400)
        self.next_fetch_at = datetime.now() + timedelta(seconds=delay_seconds)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update source configuration."""
        self.config = config
        self._update_timestamp()

        from src.modules.sources.domain.events import SourceConfigUpdatedEvent

        self.add_domain_event(
            SourceConfigUpdatedEvent(source_id=self.id, name=self.name)
        )

    def update_name(self, name: str) -> None:
        """Update source name."""
        if name == self.name:
            return
        self.name = name
        self._update_timestamp()

    def update_fetch_interval(self, interval_sec: int) -> None:
        """Update fetch interval."""
        if interval_sec == self.fetch_interval_sec:
            return
        self.fetch_interval_sec = interval_sec
        self._update_timestamp()
