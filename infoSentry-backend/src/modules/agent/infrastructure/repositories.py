"""Agent repository implementations."""

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from src.core.domain.events import EventBus
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.agent.domain.entities import (
    AgentActionLedger,
    AgentRun,
    AgentRunStatus,
    AgentToolCall,
    AgentTrigger,
    BudgetDaily,
)
from src.modules.agent.domain.repository import (
    AgentActionLedgerRepository,
    AgentRunRepository,
    AgentToolCallRepository,
    BudgetDailyRepository,
)
from src.modules.agent.infrastructure.mappers import (
    AgentActionLedgerMapper,
    AgentRunMapper,
    AgentToolCallMapper,
    BudgetDailyMapper,
)
from src.modules.agent.infrastructure.models import (
    AgentActionLedgerModel,
    AgentRunModel,
    AgentToolCallModel,
    BudgetDailyModel,
)


class PostgreSQLAgentRunRepository(EventAwareRepository[AgentRun], AgentRunRepository):
    """PostgreSQL AgentRun repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: AgentRunMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, run_id: str) -> AgentRun | None:
        statement = select(AgentRunModel).where(
            AgentRunModel.id == run_id,
            col(AgentRunModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_goal(
        self,
        goal_id: str,
        status: AgentRunStatus | None = None,
        trigger: AgentTrigger | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AgentRun], int]:
        statement = select(
            AgentRunModel, func.count(AgentRunModel.id).over().label("total_count")
        ).where(
            AgentRunModel.goal_id == goal_id,
            col(AgentRunModel.is_deleted).is_(False),
        )

        if status:
            statement = statement.where(AgentRunModel.status == status)
        if trigger:
            statement = statement.where(AgentRunModel.trigger == trigger)

        statement = (
            statement.order_by(AgentRunModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.AgentRunModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def list_recent(
        self,
        since: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AgentRun], int]:
        statement = select(
            AgentRunModel, func.count(AgentRunModel.id).over().label("total_count")
        ).where(col(AgentRunModel.is_deleted).is_(False))

        if since:
            statement = statement.where(AgentRunModel.created_at >= since)

        statement = (
            statement.order_by(AgentRunModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.AgentRunModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def create(self, run: AgentRun) -> AgentRun:
        model = self.mapper.to_model(run)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self.mapper.to_domain(model)

    async def update(self, run: AgentRun) -> AgentRun:
        statement = select(AgentRunModel).where(AgentRunModel.id == run.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"AgentRun with id {run.id} not found")

        existing.status = run.status
        existing.plan_json = run.plan_json
        existing.output_snapshot_json = run.output_snapshot_json
        existing.final_actions_json = run.final_actions_json
        existing.budget_snapshot_json = run.budget_snapshot_json
        existing.llm_used = run.llm_used
        existing.model_name = run.model_name
        existing.latency_ms = run.latency_ms
        existing.error_message = run.error_message
        existing.updated_at = run.updated_at

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        return self.mapper.to_domain(existing)

    async def delete(self, run: AgentRun | str) -> bool:
        run_id = run.id if isinstance(run, AgentRun) else run
        statement = select(AgentRunModel).where(AgentRunModel.id == run_id)
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.is_deleted = True
        self.session.add(model)
        await self.session.flush()
        return True

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[AgentRun], int]:
        return await self.list_recent(page=page, page_size=page_size)


class PostgreSQLAgentToolCallRepository(
    EventAwareRepository[AgentToolCall], AgentToolCallRepository
):
    """PostgreSQL AgentToolCall repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: AgentToolCallMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper

    async def get_by_id(self, call_id: str) -> AgentToolCall | None:
        statement = select(AgentToolCallModel).where(
            AgentToolCallModel.id == call_id,
            col(AgentToolCallModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_run(self, run_id: str) -> list[AgentToolCall]:
        statement = (
            select(AgentToolCallModel)
            .where(
                AgentToolCallModel.run_id == run_id,
                col(AgentToolCallModel.is_deleted).is_(False),
            )
            .order_by(AgentToolCallModel.created_at.asc())
        )

        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def create(self, call: AgentToolCall) -> AgentToolCall:
        model = self.mapper.to_model(call)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self.mapper.to_domain(model)

    async def update(self, call: AgentToolCall) -> AgentToolCall:
        raise NotImplementedError("Tool calls are immutable")

    async def delete(self, call: AgentToolCall | str) -> bool:
        call_id = call.id if isinstance(call, AgentToolCall) else call
        statement = select(AgentToolCallModel).where(AgentToolCallModel.id == call_id)
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.is_deleted = True
        self.session.add(model)
        await self.session.flush()
        return True

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[AgentToolCall], int]:
        return [], 0


class PostgreSQLAgentActionLedgerRepository(
    EventAwareRepository[AgentActionLedger], AgentActionLedgerRepository
):
    """PostgreSQL AgentActionLedger repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: AgentActionLedgerMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper

    async def get_by_id(self, ledger_id: str) -> AgentActionLedger | None:
        statement = select(AgentActionLedgerModel).where(
            AgentActionLedgerModel.id == ledger_id,
            col(AgentActionLedgerModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_run(self, run_id: str) -> list[AgentActionLedger]:
        statement = (
            select(AgentActionLedgerModel)
            .where(
                AgentActionLedgerModel.run_id == run_id,
                col(AgentActionLedgerModel.is_deleted).is_(False),
            )
            .order_by(AgentActionLedgerModel.created_at.asc())
        )

        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def create(self, ledger: AgentActionLedger) -> AgentActionLedger:
        model = self.mapper.to_model(ledger)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self.mapper.to_domain(model)

    async def update(self, ledger: AgentActionLedger) -> AgentActionLedger:
        raise NotImplementedError("Action ledger is immutable")

    async def delete(self, ledger: AgentActionLedger | str) -> bool:
        # Action ledger should not be deleted
        return False

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[AgentActionLedger], int]:
        return [], 0


class PostgreSQLBudgetDailyRepository(
    EventAwareRepository[BudgetDaily], BudgetDailyRepository
):
    """PostgreSQL BudgetDaily repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: BudgetDailyMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper

    async def get_by_id(self, budget_id: str) -> BudgetDaily | None:
        statement = select(BudgetDailyModel).where(
            BudgetDailyModel.id == budget_id,
            col(BudgetDailyModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_date(self, date: str) -> BudgetDaily | None:
        statement = select(BudgetDailyModel).where(
            BudgetDailyModel.date == date,
            col(BudgetDailyModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_or_create_today(self) -> BudgetDaily:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        existing = await self.get_by_date(today)
        if existing:
            return existing

        budget = BudgetDaily(date=today)
        return await self.create(budget)

    async def create(self, budget: BudgetDaily) -> BudgetDaily:
        model = self.mapper.to_model(budget)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self.mapper.to_domain(model)

    async def update(self, budget: BudgetDaily) -> BudgetDaily:
        statement = select(BudgetDailyModel).where(BudgetDailyModel.id == budget.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"BudgetDaily with id {budget.id} not found")

        existing.embedding_tokens_est = budget.embedding_tokens_est
        existing.judge_tokens_est = budget.judge_tokens_est
        existing.usd_est = budget.usd_est
        existing.embedding_disabled = budget.embedding_disabled
        existing.judge_disabled = budget.judge_disabled
        existing.updated_at = budget.updated_at

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        return self.mapper.to_domain(existing)

    async def delete(self, budget: BudgetDaily | str) -> bool:
        budget_id = budget.id if isinstance(budget, BudgetDaily) else budget
        statement = select(BudgetDailyModel).where(BudgetDailyModel.id == budget_id)
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.is_deleted = True
        self.session.add(model)
        await self.session.flush()
        return True

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[BudgetDaily], int]:
        statement = select(
            BudgetDailyModel,
            func.count(BudgetDailyModel.id).over().label("total_count"),
        )

        if not include_deleted:
            statement = statement.where(col(BudgetDailyModel.is_deleted).is_(False))

        statement = (
            statement.order_by(BudgetDailyModel.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.BudgetDailyModel for row in rows]
        return self.mapper.to_domain_list(models), total_count
