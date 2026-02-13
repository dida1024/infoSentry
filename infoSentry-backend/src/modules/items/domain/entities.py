"""Item domain entities."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field

from src.core.domain.aggregate_root import AggregateRoot


def _utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


class EmbeddingStatus(str, Enum):
    """Embedding status enum."""

    PENDING = "pending"
    DONE = "done"
    SKIPPED_BUDGET = "skipped_budget"
    FAILED = "failed"


class RankMode(str, Enum):
    """Goal match ranking mode."""

    HYBRID = "hybrid"
    MATCH_SCORE = "match_score"
    RECENT = "recent"


class Item(AggregateRoot):
    """Item aggregate root - 信息条目。"""

    source_id: str = Field(..., description="来源ID")
    url: str = Field(..., description="原文URL")
    url_hash: str = Field(..., description="URL哈希（用于去重）")
    title: str = Field(..., description="标题")
    snippet: str | None = Field(default=None, description="摘要片段")
    summary: str | None = Field(default=None, description="AI生成的摘要")
    published_at: datetime | None = Field(default=None, description="发布时间")
    ingested_at: datetime = Field(default_factory=_utc_now, description="入库时间")

    # Embedding
    embedding: list[float] | None = Field(default=None, description="向量嵌入")
    embedding_status: EmbeddingStatus = Field(
        default=EmbeddingStatus.PENDING, description="嵌入状态"
    )
    embedding_model: str | None = Field(default=None, description="嵌入模型")

    # Metadata
    raw_data: dict[str, Any] | None = Field(default=None, description="原始数据")

    def mark_embedding_done(self, embedding: list[float], model: str) -> None:
        """Mark embedding as done."""
        self.embedding = embedding
        self.embedding_status = EmbeddingStatus.DONE
        self.embedding_model = model
        self._update_timestamp()

    def mark_embedding_failed(self) -> None:
        """Mark embedding as failed."""
        self.embedding_status = EmbeddingStatus.FAILED
        self._update_timestamp()

    def mark_embedding_skipped_budget(self) -> None:
        """Mark embedding as skipped due to budget."""
        self.embedding_status = EmbeddingStatus.SKIPPED_BUDGET
        self._update_timestamp()

    def set_summary(self, summary: str) -> None:
        """Set AI-generated summary."""
        self.summary = summary
        self._update_timestamp()


class GoalItemMatch(AggregateRoot):
    """Goal-Item match record - 目标与条目的匹配记录。"""

    goal_id: str = Field(..., description="Goal ID")
    item_id: str = Field(..., description="Item ID")
    match_score: float = Field(..., ge=0, le=1, description="匹配分数")
    features_json: dict[str, Any] = Field(default_factory=dict, description="特征值")
    reasons_json: dict[str, Any] = Field(default_factory=dict, description="匹配原因")
    computed_at: datetime = Field(default_factory=_utc_now, description="计算时间")

    def update_score(
        self,
        score: float,
        features: dict[str, Any],
        reasons: dict[str, Any],
    ) -> None:
        """Update match score and reasons."""
        self.match_score = score
        self.features_json = features
        self.reasons_json = reasons
        self.computed_at = datetime.now(UTC)
        self._update_timestamp()
