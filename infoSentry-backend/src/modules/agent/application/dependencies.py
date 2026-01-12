"""Agent module application dependencies."""

from typing import Any, NoReturn

from fastapi import Depends

from src.modules.agent.application.services import (
    AgentAdminService,
    AgentRunQueryService,
)
from src.modules.agent.domain.repository import (
    AgentActionLedgerRepository,
    AgentRunRepository,
    AgentToolCallRepository,
    BudgetDailyRepository,
)


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_agent_run_repository() -> AgentRunRepository:
    _missing_dependency("AgentRunRepository")


async def get_agent_tool_call_repository() -> AgentToolCallRepository:
    _missing_dependency("AgentToolCallRepository")


async def get_agent_action_ledger_repository() -> AgentActionLedgerRepository:
    _missing_dependency("AgentActionLedgerRepository")


async def get_budget_daily_repository() -> BudgetDailyRepository:
    _missing_dependency("BudgetDailyRepository")


async def get_kv_client() -> Any:
    _missing_dependency("RedisClient")


async def get_agent_run_query_service(
    run_repo: AgentRunRepository = Depends(get_agent_run_repository),
    tool_call_repo: AgentToolCallRepository = Depends(get_agent_tool_call_repository),
    ledger_repo: AgentActionLedgerRepository = Depends(
        get_agent_action_ledger_repository
    ),
) -> AgentRunQueryService:
    return AgentRunQueryService(run_repo, tool_call_repo, ledger_repo)


async def get_agent_admin_service(
    budget_repo: BudgetDailyRepository = Depends(get_budget_daily_repository),
    kv_client: Any = Depends(get_kv_client),
) -> AgentAdminService:
    return AgentAdminService(budget_repo, kv_client)
