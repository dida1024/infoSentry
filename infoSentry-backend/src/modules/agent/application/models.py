"""Agent application models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolCallData(BaseModel):
    id: str
    tool_name: str
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    status: str
    latency_ms: int | None = None


class ActionLedgerData(BaseModel):
    id: str
    action_type: str
    payload: dict[str, Any] | None = None
    created_at: datetime | None = None


class AgentRunSummaryData(BaseModel):
    id: str
    trigger: str
    goal_id: str | None = None
    status: str
    llm_used: bool
    model_name: str | None = None
    latency_ms: int | None = None
    created_at: datetime | None = None


class AgentRunDetailData(BaseModel):
    id: str
    trigger: str
    goal_id: str | None = None
    status: str
    input_snapshot: dict[str, Any] | None = None
    output_snapshot: dict[str, Any] | None = None
    final_actions: dict[str, Any] | None = None
    budget_snapshot: dict[str, Any] | None = None
    llm_used: bool
    model_name: str | None = None
    latency_ms: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    tool_calls: list[ToolCallData] = Field(default_factory=list)
    action_ledger: list[ActionLedgerData] = Field(default_factory=list)


class AgentRunListData(BaseModel):
    items: list[AgentRunSummaryData]
    next_cursor: str | None = None
    has_more: bool = False


class BudgetData(BaseModel):
    date: str
    embedding_tokens_est: int
    judge_tokens_est: int
    usd_est: float
    embedding_disabled: bool
    judge_disabled: bool
    daily_limit: float
