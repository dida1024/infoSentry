"""Agent API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentTrigger(str, Enum):
    """Agent trigger types for API layer."""

    MATCH_COMPUTED = "MatchComputed"
    BATCH_WINDOW_TICK = "BatchWindowTick"
    DIGEST_TICK = "DigestTick"


class AgentRunStatus(str, Enum):
    """Agent run status for API layer."""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    FALLBACK = "FALLBACK"


class ToolCallStatus(str, Enum):
    """Tool call status for API layer."""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class ActionType(str, Enum):
    """Action types in ledger for API layer."""

    EMIT_DECISION = "EMIT_DECISION"
    ENQUEUE_EMAIL = "ENQUEUE_EMAIL"
    SUGGEST_TUNING = "SUGGEST_TUNING"


class AgentRunSummaryResponse(BaseModel):
    """Agent run summary response."""

    id: str = Field(..., description="运行ID")
    trigger: AgentTrigger = Field(..., description="触发类型")
    goal_id: str | None = Field(None, description="Goal ID")
    status: AgentRunStatus = Field(..., description="运行状态")
    llm_used: bool = Field(..., description="是否使用LLM")
    model_name: str | None = Field(None, description="模型名称")
    latency_ms: int | None = Field(None, description="耗时（毫秒）")
    created_at: datetime = Field(..., description="创建时间")


class ToolCallResponse(BaseModel):
    """Tool call response."""

    id: str = Field(..., description="调用ID")
    tool_name: str = Field(..., description="工具名称")
    input: dict[str, Any] = Field(..., description="输入参数")
    output: dict[str, Any] = Field(..., description="输出结果")
    status: ToolCallStatus = Field(..., description="调用状态")
    latency_ms: int | None = Field(None, description="耗时（毫秒）")


class ActionLedgerResponse(BaseModel):
    """Action ledger response."""

    id: str = Field(..., description="动作ID")
    action_type: ActionType = Field(..., description="动作类型")
    payload: dict[str, Any] = Field(..., description="动作载荷")
    created_at: datetime = Field(..., description="创建时间")


class AgentRunDetailResponse(BaseModel):
    """Agent run detail response."""

    id: str = Field(..., description="运行ID")
    trigger: AgentTrigger = Field(..., description="触发类型")
    goal_id: str | None = Field(None, description="Goal ID")
    status: AgentRunStatus = Field(..., description="运行状态")
    input_snapshot: dict[str, Any] = Field(..., description="输入快照")
    output_snapshot: dict[str, Any] = Field(..., description="输出快照")
    final_actions: list[dict[str, Any]] = Field(..., description="最终动作")
    budget_snapshot: dict[str, Any] = Field(..., description="预算快照")
    llm_used: bool = Field(..., description="是否使用LLM")
    model_name: str | None = Field(None, description="模型名称")
    latency_ms: int | None = Field(None, description="耗时（毫秒）")
    error_message: str | None = Field(None, description="错误信息")
    created_at: datetime = Field(..., description="创建时间")
    tool_calls: list[ToolCallResponse] = Field(
        default_factory=list, description="工具调用记录"
    )
    action_ledger: list[ActionLedgerResponse] = Field(
        default_factory=list, description="动作账本"
    )


class BudgetResponse(BaseModel):
    """Budget response."""

    date: str = Field(..., description="日期")
    embedding_tokens_est: int = Field(..., description="embedding token估算")
    judge_tokens_est: int = Field(..., description="judge token估算")
    usd_est: float = Field(..., description="美元估算")
    embedding_disabled: bool = Field(..., description="embedding是否禁用")
    judge_disabled: bool = Field(..., description="judge是否禁用")
    daily_limit: float = Field(..., description="每日预算上限")
