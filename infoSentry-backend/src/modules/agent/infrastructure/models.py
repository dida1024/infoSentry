"""Agent database models."""

from typing import Any

from sqlalchemy import JSON, Enum, Text
from sqlmodel import Field

from src.core.infrastructure.database.base_model import BaseModel
from src.modules.agent.domain.entities import (
    ActionType,
    AgentRunStatus,
    AgentTrigger,
    ToolCallStatus,
)


class AgentRunModel(BaseModel, table=True):
    """Agent run database model."""

    __tablename__ = "agent_runs"

    trigger: AgentTrigger = Field(
        sa_type=Enum(
            AgentTrigger,
            name="agenttrigger",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    goal_id: str | None = Field(default=None, nullable=True, index=True)
    status: AgentRunStatus = Field(
        default=AgentRunStatus.RUNNING,
        sa_type=Enum(
            AgentRunStatus,
            name="agentrunstatus",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
        index=True,
    )
    plan_json: dict[str, Any] | None = Field(
        default=None,
        sa_type=JSON,
        nullable=True,
    )
    input_snapshot_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )
    output_snapshot_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )
    final_actions_json: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_type=JSON,
        nullable=False,
    )
    budget_snapshot_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )
    llm_used: bool = Field(default=False, nullable=False)
    model_name: str | None = Field(default=None, nullable=True)
    latency_ms: int | None = Field(default=None, nullable=True)
    error_message: str | None = Field(default=None, sa_type=Text, nullable=True)


class AgentToolCallModel(BaseModel, table=True):
    """Agent tool call database model."""

    __tablename__ = "agent_tool_calls"

    run_id: str = Field(nullable=False, index=True)
    tool_name: str = Field(nullable=False)
    input_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )
    output_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )
    status: ToolCallStatus = Field(
        default=ToolCallStatus.SUCCESS,
        sa_type=Enum(
            ToolCallStatus,
            name="toolcallstatus",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
    latency_ms: int | None = Field(default=None, nullable=True)


class AgentActionLedgerModel(BaseModel, table=True):
    """Agent action ledger database model."""

    __tablename__ = "agent_action_ledger"

    run_id: str = Field(nullable=False, index=True)
    action_type: ActionType = Field(
        sa_type=Enum(
            ActionType,
            name="actiontype",
            values_callable=lambda e: [i.value for i in e],
            create_constraint=False,
        ),
        nullable=False,
    )
    payload_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        nullable=False,
    )


class BudgetDailyModel(BaseModel, table=True):
    """Budget daily database model."""

    __tablename__ = "budget_daily"

    date: str = Field(nullable=False, unique=True, index=True)
    embedding_tokens_est: int = Field(default=0, nullable=False)
    judge_tokens_est: int = Field(default=0, nullable=False)
    usd_est: float = Field(default=0.0, nullable=False)
    embedding_disabled: bool = Field(default=False, nullable=False)
    judge_disabled: bool = Field(default=False, nullable=False)
