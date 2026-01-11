"""Agent mappers."""

from src.modules.agent.domain.entities import (
    AgentActionLedger,
    AgentRun,
    AgentToolCall,
    BudgetDaily,
)
from src.modules.agent.infrastructure.models import (
    AgentActionLedgerModel,
    AgentRunModel,
    AgentToolCallModel,
    BudgetDailyModel,
)


class AgentRunMapper:
    """AgentRun mapper."""

    def to_domain(self, model: AgentRunModel) -> AgentRun:
        """Convert model to domain entity."""
        return AgentRun(
            id=model.id,
            trigger=model.trigger,
            goal_id=model.goal_id,
            status=model.status,
            plan_json=model.plan_json,
            input_snapshot_json=model.input_snapshot_json,
            output_snapshot_json=model.output_snapshot_json,
            final_actions_json=model.final_actions_json,
            budget_snapshot_json=model.budget_snapshot_json,
            llm_used=model.llm_used,
            model_name=model.model_name,
            latency_ms=model.latency_ms,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: AgentRun) -> AgentRunModel:
        """Convert domain entity to model."""
        return AgentRunModel(
            id=entity.id,
            trigger=entity.trigger,
            goal_id=entity.goal_id,
            status=entity.status,
            plan_json=entity.plan_json,
            input_snapshot_json=entity.input_snapshot_json,
            output_snapshot_json=entity.output_snapshot_json,
            final_actions_json=entity.final_actions_json,
            budget_snapshot_json=entity.budget_snapshot_json,
            llm_used=entity.llm_used,
            model_name=entity.model_name,
            latency_ms=entity.latency_ms,
            error_message=entity.error_message,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )

    def to_domain_list(self, models: list[AgentRunModel]) -> list[AgentRun]:
        """Convert models to domain entities."""
        return [self.to_domain(m) for m in models]


class AgentToolCallMapper:
    """AgentToolCall mapper."""

    def to_domain(self, model: AgentToolCallModel) -> AgentToolCall:
        """Convert model to domain entity."""
        return AgentToolCall(
            id=model.id,
            run_id=model.run_id,
            tool_name=model.tool_name,
            input_json=model.input_json,
            output_json=model.output_json,
            status=model.status,
            latency_ms=model.latency_ms,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: AgentToolCall) -> AgentToolCallModel:
        """Convert domain entity to model."""
        return AgentToolCallModel(
            id=entity.id,
            run_id=entity.run_id,
            tool_name=entity.tool_name,
            input_json=entity.input_json,
            output_json=entity.output_json,
            status=entity.status,
            latency_ms=entity.latency_ms,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )

    def to_domain_list(self, models: list[AgentToolCallModel]) -> list[AgentToolCall]:
        """Convert models to domain entities."""
        return [self.to_domain(m) for m in models]


class AgentActionLedgerMapper:
    """AgentActionLedger mapper."""

    def to_domain(self, model: AgentActionLedgerModel) -> AgentActionLedger:
        """Convert model to domain entity."""
        return AgentActionLedger(
            id=model.id,
            run_id=model.run_id,
            action_type=model.action_type,
            payload_json=model.payload_json,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: AgentActionLedger) -> AgentActionLedgerModel:
        """Convert domain entity to model."""
        return AgentActionLedgerModel(
            id=entity.id,
            run_id=entity.run_id,
            action_type=entity.action_type,
            payload_json=entity.payload_json,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )

    def to_domain_list(
        self, models: list[AgentActionLedgerModel]
    ) -> list[AgentActionLedger]:
        """Convert models to domain entities."""
        return [self.to_domain(m) for m in models]


class BudgetDailyMapper:
    """BudgetDaily mapper."""

    def to_domain(self, model: BudgetDailyModel) -> BudgetDaily:
        """Convert model to domain entity."""
        return BudgetDaily(
            id=model.id,
            date=model.date,
            embedding_tokens_est=model.embedding_tokens_est,
            judge_tokens_est=model.judge_tokens_est,
            usd_est=model.usd_est,
            embedding_disabled=model.embedding_disabled,
            judge_disabled=model.judge_disabled,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: BudgetDaily) -> BudgetDailyModel:
        """Convert domain entity to model."""
        return BudgetDailyModel(
            id=entity.id,
            date=entity.date,
            embedding_tokens_est=entity.embedding_tokens_est,
            judge_tokens_est=entity.judge_tokens_est,
            usd_est=entity.usd_est,
            embedding_disabled=entity.embedding_disabled,
            judge_disabled=entity.judge_disabled,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )

    def to_domain_list(self, models: list[BudgetDailyModel]) -> list[BudgetDaily]:
        """Convert models to domain entities."""
        return [self.to_domain(m) for m in models]
