"""Agent module dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.agent.infrastructure.mappers import (
    AgentActionLedgerMapper,
    AgentRunMapper,
    AgentToolCallMapper,
    BudgetDailyMapper,
)
from src.modules.agent.infrastructure.repositories import (
    PostgreSQLAgentActionLedgerRepository,
    PostgreSQLAgentRunRepository,
    PostgreSQLAgentToolCallRepository,
    PostgreSQLBudgetDailyRepository,
)


def get_agent_run_mapper() -> AgentRunMapper:
    return AgentRunMapper()


def get_agent_tool_call_mapper() -> AgentToolCallMapper:
    return AgentToolCallMapper()


def get_agent_action_ledger_mapper() -> AgentActionLedgerMapper:
    return AgentActionLedgerMapper()


def get_budget_daily_mapper() -> BudgetDailyMapper:
    return BudgetDailyMapper()


async def get_agent_run_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: AgentRunMapper = Depends(get_agent_run_mapper),
) -> PostgreSQLAgentRunRepository:
    return PostgreSQLAgentRunRepository(session, mapper, get_event_bus())


async def get_agent_tool_call_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: AgentToolCallMapper = Depends(get_agent_tool_call_mapper),
) -> PostgreSQLAgentToolCallRepository:
    return PostgreSQLAgentToolCallRepository(session, mapper, get_event_bus())


async def get_agent_action_ledger_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: AgentActionLedgerMapper = Depends(get_agent_action_ledger_mapper),
) -> PostgreSQLAgentActionLedgerRepository:
    return PostgreSQLAgentActionLedgerRepository(session, mapper, get_event_bus())


async def get_budget_daily_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: BudgetDailyMapper = Depends(get_budget_daily_mapper),
) -> PostgreSQLBudgetDailyRepository:
    return PostgreSQLBudgetDailyRepository(session, mapper, get_event_bus())
