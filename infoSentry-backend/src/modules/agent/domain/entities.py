"""Agent domain entities."""

from enum import Enum
from typing import Any

from pydantic import Field

from src.core.domain.aggregate_root import AggregateRoot
from src.core.domain.base_entity import BaseEntity


class AgentTrigger(str, Enum):
    """Agent trigger types."""

    MATCH_COMPUTED = "MatchComputed"
    BATCH_WINDOW_TICK = "BatchWindowTick"
    DIGEST_TICK = "DigestTick"


class AgentRunStatus(str, Enum):
    """Agent run status."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    FALLBACK = "FALLBACK"


class ToolCallStatus(str, Enum):
    """Tool call status."""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class ActionType(str, Enum):
    """Action types in ledger."""

    EMIT_DECISION = "EMIT_DECISION"
    ENQUEUE_EMAIL = "ENQUEUE_EMAIL"
    SUGGEST_TUNING = "SUGGEST_TUNING"


class AgentRun(AggregateRoot):
    """Agent run record - Agent 运行记录。"""

    trigger: AgentTrigger = Field(..., description="触发类型")
    goal_id: str | None = Field(default=None, description="关联的Goal ID")
    status: AgentRunStatus = Field(
        default=AgentRunStatus.RUNNING, description="运行状态"
    )
    plan_json: dict[str, Any] | None = Field(default=None, description="执行计划")
    input_snapshot_json: dict[str, Any] = Field(
        default_factory=dict, description="输入快照（脱敏）"
    )
    output_snapshot_json: dict[str, Any] = Field(
        default_factory=dict, description="输出快照"
    )
    final_actions_json: list[dict[str, Any]] = Field(
        default_factory=list, description="最终动作列表"
    )
    budget_snapshot_json: dict[str, Any] = Field(
        default_factory=dict, description="预算快照"
    )
    llm_used: bool = Field(default=False, description="是否使用了LLM")
    model_name: str | None = Field(default=None, description="使用的模型名称")
    latency_ms: int | None = Field(default=None, description="执行耗时（毫秒）")
    error_message: str | None = Field(default=None, description="错误信息")

    def mark_success(
        self,
        output: dict[str, Any],
        actions: list[dict[str, Any]],
        latency_ms: int,
    ) -> None:
        """Mark run as successful."""
        self.status = AgentRunStatus.SUCCESS
        self.output_snapshot_json = output
        self.final_actions_json = actions
        self.latency_ms = latency_ms
        self._update_timestamp()

    def mark_error(self, error: str, latency_ms: int) -> None:
        """Mark run as errored."""
        self.status = AgentRunStatus.ERROR
        self.error_message = error
        self.latency_ms = latency_ms
        self._update_timestamp()

    def mark_timeout(self, latency_ms: int) -> None:
        """Mark run as timed out."""
        self.status = AgentRunStatus.TIMEOUT
        self.latency_ms = latency_ms
        self._update_timestamp()

    def mark_fallback(
        self,
        output: dict[str, Any],
        actions: list[dict[str, Any]],
        latency_ms: int,
    ) -> None:
        """Mark run as fallback."""
        self.status = AgentRunStatus.FALLBACK
        self.output_snapshot_json = output
        self.final_actions_json = actions
        self.latency_ms = latency_ms
        self._update_timestamp()

    def set_llm_used(self, model_name: str) -> None:
        """Set LLM usage info."""
        self.llm_used = True
        self.model_name = model_name


class AgentToolCall(BaseEntity):
    """Agent tool call record - Agent 工具调用记录。"""

    run_id: str = Field(..., description="关联的运行ID")
    tool_name: str = Field(..., description="工具名称")
    input_json: dict[str, Any] = Field(default_factory=dict, description="输入参数")
    output_json: dict[str, Any] = Field(default_factory=dict, description="输出结果")
    status: ToolCallStatus = Field(
        default=ToolCallStatus.SUCCESS, description="调用状态"
    )
    latency_ms: int | None = Field(default=None, description="调用耗时（毫秒）")


class AgentActionLedger(BaseEntity):
    """Agent action ledger - Agent 动作账本（不可变）。"""

    run_id: str = Field(..., description="关联的运行ID")
    action_type: ActionType = Field(..., description="动作类型")
    payload_json: dict[str, Any] = Field(default_factory=dict, description="动作载荷")


class BudgetDaily(BaseEntity):
    """Daily budget record - 每日预算记录。"""

    date: str = Field(..., description="日期（YYYY-MM-DD）")
    embedding_tokens_est: int = Field(default=0, description="embedding token估算")
    judge_tokens_est: int = Field(default=0, description="judge token估算")
    usd_est: float = Field(default=0.0, description="美元估算")
    embedding_disabled: bool = Field(default=False, description="embedding是否禁用")
    judge_disabled: bool = Field(default=False, description="judge是否禁用")

    def add_embedding_tokens(self, tokens: int) -> None:
        """Add embedding tokens."""
        self.embedding_tokens_est += tokens
        self._update_timestamp()

    def add_judge_tokens(self, tokens: int) -> None:
        """Add judge tokens."""
        self.judge_tokens_est += tokens
        self._update_timestamp()

    def update_cost(self, usd: float) -> None:
        """Update estimated cost."""
        self.usd_est += usd
        self._update_timestamp()

    def disable_embedding(self) -> None:
        """Disable embedding due to budget."""
        self.embedding_disabled = True
        self._update_timestamp()

    def disable_judge(self) -> None:
        """Disable judge due to budget."""
        self.judge_disabled = True
        self._update_timestamp()
