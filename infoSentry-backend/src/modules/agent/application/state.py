"""Agent State 数据结构。

根据 AGENT_RUNTIME_SPEC.md 第 3 节设计，包含：
- 触发上下文
- Goal/Item/Match 上下文
- 历史/预算上下文
- 草稿和最终动作
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class DecisionBucket(str, Enum):
    """决策分桶。"""

    IMMEDIATE = "IMMEDIATE"  # 即时推送 (score >= 0.93)
    BOUNDARY = "BOUNDARY"  # 边界区域，需要 LLM 判别 (0.88 <= score < 0.93)
    BATCH = "BATCH"  # 批量推送 (0.75 <= score < 0.88)
    IGNORE = "IGNORE"  # 忽略 (score < 0.75)


class BlockReason(str, Enum):
    """阻止原因。"""

    BLOCKED_SOURCE = "BLOCKED_SOURCE"
    NEGATIVE_TERM = "NEGATIVE_TERM"
    STRICT_NO_HIT = "STRICT_NO_HIT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


# ============================================
# 上下文数据结构
# ============================================


class GoalContext(BaseModel):
    """Goal 上下文。"""

    goal_id: str
    user_id: str
    name: str
    description: str
    priority_mode: str  # "STRICT" | "SOFT"
    must_terms: list[str] = Field(default_factory=list)
    negative_terms: list[str] = Field(default_factory=list)
    blocked_sources: list[str] = Field(default_factory=list)
    time_window_days: int = 7


class ItemContext(BaseModel):
    """Item 上下文。"""

    item_id: str
    source_id: str
    source_name: str | None = None
    title: str
    url: str
    snippet: str | None = None
    published_at: datetime | None = None


class MatchContext(BaseModel):
    """匹配上下文。"""

    score: float
    features: dict[str, Any] = Field(default_factory=dict)
    reasons: dict[str, Any] = Field(default_factory=dict)


class HistoryContext(BaseModel):
    """历史上下文。"""

    recent_decisions: list[dict[str, Any]] = Field(default_factory=list)
    recent_clicks: list[dict[str, Any]] = Field(default_factory=list)
    feedback_stats: dict[str, int] = Field(
        default_factory=lambda: {"like": 0, "dislike": 0}
    )


class BudgetContext(BaseModel):
    """预算上下文。"""

    embedding_disabled: bool = False
    judge_disabled: bool = False
    usd_est_today: float = 0.0
    daily_limit: float = 0.33


class DraftContext(BaseModel):
    """草稿上下文。"""

    preliminary_bucket: DecisionBucket | None = None
    blocked: bool = False
    block_reason: BlockReason | None = None
    block_details: str | None = None
    llm_proposal: dict[str, Any] | None = None
    llm_confidence: float | None = None
    push_worthiness: dict[str, Any] | None = None
    adjusted_score: float | None = None
    record_ignore: bool = False
    fallback_reason: str | None = None


class ActionProposal(BaseModel):
    """动作提案。"""

    action_type: str  # "EMIT_DECISION" | "ENQUEUE_EMAIL"
    decision: str | None = None  # "IMMEDIATE" | "BATCH" | "DIGEST" | "IGNORE"
    goal_id: str
    item_id: str
    reason: str = ""
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    dedupe_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================
# AgentState 主结构
# ============================================


class AgentState(BaseModel):
    """Agent 状态。

    每个 Node 接收 AgentState，处理后返回修改后的 AgentState。
    副作用只能通过 Tools 执行。
    """

    # 运行标识
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    trigger: Literal["MatchComputed", "BatchWindowTick", "DigestTick"] = "MatchComputed"
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # 上下文
    goal: GoalContext | None = None
    item: ItemContext | None = None
    match: MatchContext | None = None
    history: HistoryContext = Field(default_factory=HistoryContext)
    budget: BudgetContext = Field(default_factory=BudgetContext)

    # 草稿（Node 处理过程中填充）
    draft: DraftContext = Field(default_factory=DraftContext)

    # 最终动作
    actions: list[ActionProposal] = Field(default_factory=list)

    # 元数据
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_input_snapshot(self) -> dict[str, Any]:
        """生成输入快照（用于回放）。"""
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "started_at": self.started_at.isoformat(),
            "goal": self.goal.model_dump() if self.goal else None,
            "item": self.item.model_dump() if self.item else None,
            "match": self.match.model_dump() if self.match else None,
            "history": self.history.model_dump(),
            "budget": self.budget.model_dump(),
        }

    def to_output_snapshot(self) -> dict[str, Any]:
        """生成输出快照。"""
        return {
            "run_id": self.run_id,
            "draft": self.draft.model_dump(),
            "actions": [a.model_dump() for a in self.actions],
            "metadata": self.metadata,
        }


# ============================================
# 阈值配置
# ============================================


@dataclass
class ThresholdConfig:
    """阈值配置。"""

    immediate_threshold: float = 0.93  # >= 此值直通 IMMEDIATE
    boundary_lower: float = 0.88  # >= 此值且 < immediate 进入 BOUNDARY
    batch_threshold: float = 0.75  # >= 此值且 < boundary_lower 进入 BATCH
    # < batch_threshold 则 IGNORE

    def get_bucket(self, score: float) -> DecisionBucket:
        """根据分数获取分桶。"""
        if score >= self.immediate_threshold:
            return DecisionBucket.IMMEDIATE
        elif score >= self.boundary_lower:
            return DecisionBucket.BOUNDARY
        elif score >= self.batch_threshold:
            return DecisionBucket.BATCH
        else:
            return DecisionBucket.IGNORE


# 默认阈值配置
DEFAULT_THRESHOLDS = ThresholdConfig()
