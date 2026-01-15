"""Agent application services."""

import base64
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from src.core.config import settings
from src.core.domain.exceptions import EntityNotFoundError, ValidationError
from src.core.domain.ports.kv import KVClient
from src.modules.agent.application.models import (
    ActionLedgerData,
    AgentRunDetailData,
    AgentRunListData,
    AgentRunSummaryData,
    BudgetData,
    ToolCallData,
)
from src.modules.agent.domain.entities import AgentRunStatus
from src.modules.agent.domain.repository import (
    AgentActionLedgerRepository,
    AgentRunRepository,
    AgentToolCallRepository,
    BudgetDailyRepository,
)
from src.modules.items.application.budget_service import BudgetService


def _decode_cursor(cursor: str | None) -> tuple[int, int]:
    if not cursor:
        return settings.CURSOR_DEFAULT_PAGE, settings.CURSOR_DEFAULT_PAGE_SIZE
    try:
        decoded = base64.b64decode(cursor).decode()
        page, page_size = decoded.split(":")
        return int(page), int(page_size)
    except Exception as e:
        logger.debug(f"Failed to decode cursor '{cursor}', using defaults: {e}")
        return settings.CURSOR_DEFAULT_PAGE, settings.CURSOR_DEFAULT_PAGE_SIZE


def _encode_cursor(page: int, page_size: int) -> str:
    return base64.b64encode(f"{page}:{page_size}".encode()).decode()


class AgentRunQueryService:
    def __init__(
        self,
        run_repo: AgentRunRepository,
        tool_call_repo: AgentToolCallRepository,
        ledger_repo: AgentActionLedgerRepository,
    ) -> None:
        self.run_repo = run_repo
        self.tool_call_repo = tool_call_repo
        self.ledger_repo = ledger_repo

    async def list_runs(
        self,
        goal_id: str | None,
        cursor: str | None,
        run_status: str | None,
    ) -> AgentRunListData:
        page, page_size = _decode_cursor(cursor)

        status_filter = None
        if run_status:
            try:
                status_filter = AgentRunStatus(run_status)
            except ValueError:
                status_filter = None

        if goal_id:
            runs, total = await self.run_repo.list_by_goal(
                goal_id=goal_id,
                status=status_filter,
                page=page,
                page_size=page_size,
            )
        else:
            runs, total = await self.run_repo.list_recent(
                page=page,
                page_size=page_size,
            )

        items = [
            AgentRunSummaryData(
                id=run.id,
                trigger=run.trigger,
                goal_id=run.goal_id,
                status=run.status,
                llm_used=run.llm_used,
                model_name=run.model_name,
                latency_ms=run.latency_ms,
                created_at=run.created_at,
            )
            for run in runs
        ]

        has_more = (page * page_size) < total
        next_cursor = _encode_cursor(page + 1, page_size) if has_more else None

        return AgentRunListData(items=items, next_cursor=next_cursor, has_more=has_more)

    async def get_run_detail(self, run_id: str) -> AgentRunDetailData:
        run = await self.run_repo.get_by_id(run_id)
        if not run:
            raise EntityNotFoundError("AgentRun", run_id)

        tool_calls = await self.tool_call_repo.list_by_run(run_id)
        tool_call_responses = [
            ToolCallData(
                id=tc.id,
                tool_name=tc.tool_name,
                input=tc.input_json,
                output=tc.output_json,
                status=tc.status,
                latency_ms=tc.latency_ms,
            )
            for tc in tool_calls
        ]

        ledger_entries = await self.ledger_repo.list_by_run(run_id)
        ledger_responses = [
            ActionLedgerData(
                id=entry.id,
                action_type=entry.action_type,
                payload=entry.payload_json,
                created_at=entry.created_at,
            )
            for entry in ledger_entries
        ]

        return AgentRunDetailData(
            id=run.id,
            trigger=run.trigger,
            goal_id=run.goal_id,
            status=run.status,
            input_snapshot=run.input_snapshot_json,
            output_snapshot=run.output_snapshot_json,
            final_actions=run.final_actions_json,
            budget_snapshot=run.budget_snapshot_json,
            llm_used=run.llm_used,
            model_name=run.model_name,
            latency_ms=run.latency_ms,
            error_message=run.error_message,
            created_at=run.created_at,
            tool_calls=tool_call_responses,
            action_ledger=ledger_responses,
        )

    async def get_replay_info(self, run_id: str) -> dict[str, Any]:
        run = await self.run_repo.get_by_id(run_id)
        if not run:
            raise EntityNotFoundError("AgentRun", run_id)
        return {
            "original_run_id": run_id,
            "input_snapshot": run.input_snapshot_json,
            "original_output": run.output_snapshot_json,
            "message": "Replay endpoint available. Use input_snapshot to manually replay.",
        }


class AgentAdminService:
    def __init__(
        self,
        budget_repo: BudgetDailyRepository,
        kv_client: KVClient,
    ) -> None:
        self.budget_repo = budget_repo
        self.kv_client = kv_client

    async def get_budget_status(self) -> BudgetData:
        budget = await self.budget_repo.get_or_create_today()
        return BudgetData(
            date=budget.date,
            embedding_tokens_est=budget.embedding_tokens_est,
            judge_tokens_est=budget.judge_tokens_est,
            usd_est=budget.usd_est,
            embedding_disabled=budget.embedding_disabled,
            judge_disabled=budget.judge_disabled,
            daily_limit=settings.DAILY_USD_BUDGET,
        )

    async def get_config(self) -> dict[str, Any]:
        return {
            "LLM_ENABLED": settings.LLM_ENABLED,
            "EMBEDDING_ENABLED": settings.EMBEDDING_ENABLED,
            "IMMEDIATE_ENABLED": settings.IMMEDIATE_ENABLED,
            "EMAIL_ENABLED": settings.EMAIL_ENABLED,
            "DAILY_USD_BUDGET": settings.DAILY_USD_BUDGET,
            "IMMEDIATE_THRESHOLD": settings.IMMEDIATE_THRESHOLD,
            "BATCH_THRESHOLD": settings.BATCH_THRESHOLD,
            "BOUNDARY_LOW": settings.BOUNDARY_LOW,
            "BOUNDARY_HIGH": settings.BOUNDARY_HIGH,
        }

    async def update_config(self, config: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "LLM_ENABLED",
            "EMBEDDING_ENABLED",
            "IMMEDIATE_ENABLED",
            "EMAIL_ENABLED",
        }
        updated: dict[str, Any] = {}
        for key, value in config.items():
            if key in allowed_keys:
                await self.kv_client.set(f"config:{key}", str(value).lower())
                updated[key] = value
        return {"updated": updated}

    async def health_check(self) -> dict[str, Any]:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "components": {
                "database": "unknown",
                "redis": "unknown",
            },
        }

        try:
            await self.budget_repo.get_or_create_today()
            health_status["components"]["database"] = "healthy"
        except Exception as e:
            health_status["components"]["database"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"

        try:
            is_ok = await self.kv_client.ping()
            health_status["components"]["redis"] = "healthy" if is_ok else "unhealthy"
        except Exception as e:
            health_status["components"]["redis"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"

        return health_status

    async def get_monitoring_status(self) -> dict[str, Any]:
        from src.modules.agent.application.monitoring_service import MonitoringService

        monitoring = MonitoringService(self.kv_client)
        status = await monitoring.check_all()
        return status.to_dict()

    async def get_worker_status(self) -> dict[str, Any]:
        from src.modules.agent.application.monitoring_service import MonitoringService

        monitoring = MonitoringService(self.kv_client)
        workers_result = await monitoring.get_worker_heartbeats()
        return {"workers": workers_result.to_dict()}

    async def reset_budget(self) -> dict[str, Any]:
        budget_service = BudgetService(self.kv_client)
        await budget_service.reset_daily_budget()
        return {"reset": True}

    async def enable_feature(self, feature: str) -> dict[str, Any]:
        allowed_features = {"llm", "embedding", "immediate", "email"}
        if feature.lower() not in allowed_features:
            raise ValidationError(f"Unknown feature: {feature}")
        config_key = f"config:{feature.upper()}_ENABLED"
        await self.kv_client.set(config_key, "true")
        return {"feature": feature, "enabled": True}

    async def disable_feature(self, feature: str) -> dict[str, Any]:
        allowed_features = {"llm", "embedding", "immediate", "email"}
        if feature.lower() not in allowed_features:
            raise ValidationError(f"Unknown feature: {feature}")
        config_key = f"config:{feature.upper()}_ENABLED"
        await self.kv_client.set(config_key, "false")
        return {"feature": feature, "enabled": False}
