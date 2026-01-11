"""Goal repository implementations."""

from loguru import logger
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.domain.events import EventBus
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.goals.domain.entities import (
    Goal,
    GoalPriorityTerm,
    GoalPushConfig,
    GoalStatus,
    TermType,
)
from src.modules.goals.domain.repository import (
    GoalPriorityTermRepository,
    GoalPushConfigRepository,
    GoalRepository,
)
from src.modules.goals.infrastructure.mappers import (
    GoalMapper,
    GoalPriorityTermMapper,
    GoalPushConfigMapper,
)
from src.modules.goals.infrastructure.models import (
    GoalModel,
    GoalPriorityTermModel,
    GoalPushConfigModel,
)


class PostgreSQLGoalRepository(EventAwareRepository[Goal], GoalRepository):
    """PostgreSQL goal repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: GoalMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, goal_id: str) -> Goal | None:
        statement = select(GoalModel).where(
            GoalModel.id == goal_id,
            GoalModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_user(
        self,
        user_id: str,
        status: GoalStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Goal], int]:
        statement = select(
            GoalModel, func.count(GoalModel.id).over().label("total_count")
        ).where(
            GoalModel.user_id == user_id,
            GoalModel.is_deleted.is_(False),
        )

        if status:
            statement = statement.where(GoalModel.status == status)

        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(GoalModel.created_at.desc())
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.GoalModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def get_active_goals(self) -> list[Goal]:
        statement = select(GoalModel).where(
            GoalModel.status == GoalStatus.ACTIVE,
            GoalModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def create(self, goal: Goal) -> Goal:
        model = self.mapper.to_model(goal)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(goal)
        return self.mapper.to_domain(model)

    async def update(self, goal: Goal) -> Goal:
        statement = select(GoalModel).where(GoalModel.id == goal.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"Goal with id {goal.id} not found")

        existing.name = goal.name
        existing.description = goal.description
        existing.status = goal.status
        existing.priority_mode = goal.priority_mode
        existing.time_window_days = goal.time_window_days
        existing.updated_at = goal.updated_at
        existing.is_deleted = goal.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(goal)
        return self.mapper.to_domain(existing)

    async def delete(self, goal: Goal | str) -> bool:
        goal_id = goal.id if isinstance(goal, Goal) else goal
        statement = select(GoalModel).where(
            GoalModel.id == goal_id,
            GoalModel.is_deleted.is_(False),
        )
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
    ) -> tuple[list[Goal], int]:
        statement = select(
            GoalModel, func.count(GoalModel.id).over().label("total_count")
        )

        if not include_deleted:
            statement = statement.where(GoalModel.is_deleted.is_(False))

        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(GoalModel.created_at.desc())
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.GoalModel for row in rows]
        return self.mapper.to_domain_list(models), total_count


class PostgreSQLGoalPushConfigRepository(
    EventAwareRepository[GoalPushConfig], GoalPushConfigRepository
):
    """PostgreSQL goal push config repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: GoalPushConfigMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper

    async def get_by_id(self, config_id: str) -> GoalPushConfig | None:
        statement = select(GoalPushConfigModel).where(
            GoalPushConfigModel.id == config_id,
            GoalPushConfigModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_goal_id(self, goal_id: str) -> GoalPushConfig | None:
        statement = select(GoalPushConfigModel).where(
            GoalPushConfigModel.goal_id == goal_id,
            GoalPushConfigModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def create(self, config: GoalPushConfig) -> GoalPushConfig:
        model = self.mapper.to_model(config)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self.mapper.to_domain(model)

    async def update(self, config: GoalPushConfig) -> GoalPushConfig:
        statement = select(GoalPushConfigModel).where(
            GoalPushConfigModel.id == config.id
        )
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"GoalPushConfig with id {config.id} not found")

        existing.batch_windows = config.batch_windows
        existing.digest_send_time = config.digest_send_time
        existing.immediate_enabled = config.immediate_enabled
        existing.batch_enabled = config.batch_enabled
        existing.digest_enabled = config.digest_enabled
        existing.updated_at = config.updated_at

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        return self.mapper.to_domain(existing)

    async def delete(self, config: GoalPushConfig | str) -> bool:
        config_id = config.id if isinstance(config, GoalPushConfig) else config
        statement = select(GoalPushConfigModel).where(
            GoalPushConfigModel.id == config_id
        )
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
    ) -> tuple[list[GoalPushConfig], int]:
        return [], 0


class PostgreSQLGoalPriorityTermRepository(
    EventAwareRepository[GoalPriorityTerm], GoalPriorityTermRepository
):
    """PostgreSQL goal priority term repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: GoalPriorityTermMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper

    async def get_by_id(self, term_id: str) -> GoalPriorityTerm | None:
        statement = select(GoalPriorityTermModel).where(
            GoalPriorityTermModel.id == term_id,
            GoalPriorityTermModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_goal(
        self,
        goal_id: str,
        term_type: TermType | None = None,
    ) -> list[GoalPriorityTerm]:
        statement = select(GoalPriorityTermModel).where(
            GoalPriorityTermModel.goal_id == goal_id,
            GoalPriorityTermModel.is_deleted.is_(False),
        )

        if term_type:
            statement = statement.where(GoalPriorityTermModel.term_type == term_type)

        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def delete_all_for_goal(self, goal_id: str) -> int:
        statement = select(GoalPriorityTermModel).where(
            GoalPriorityTermModel.goal_id == goal_id,
            GoalPriorityTermModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()

        count = 0
        for model in models:
            model.is_deleted = True
            self.session.add(model)
            count += 1

        await self.session.flush()
        return count

    async def bulk_create(
        self, terms: list[GoalPriorityTerm]
    ) -> list[GoalPriorityTerm]:
        models = [self.mapper.to_model(t) for t in terms]
        for model in models:
            self.session.add(model)
        await self.session.flush()
        for model in models:
            await self.session.refresh(model)
        return self.mapper.to_domain_list(models)

    async def create(self, term: GoalPriorityTerm) -> GoalPriorityTerm:
        model = self.mapper.to_model(term)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self.mapper.to_domain(model)

    async def update(self, term: GoalPriorityTerm) -> GoalPriorityTerm:
        statement = select(GoalPriorityTermModel).where(
            GoalPriorityTermModel.id == term.id
        )
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"GoalPriorityTerm with id {term.id} not found")

        existing.term = term.term
        existing.term_type = term.term_type
        existing.updated_at = term.updated_at

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        return self.mapper.to_domain(existing)

    async def delete(self, term: GoalPriorityTerm | str) -> bool:
        term_id = term.id if isinstance(term, GoalPriorityTerm) else term
        statement = select(GoalPriorityTermModel).where(
            GoalPriorityTermModel.id == term_id
        )
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
    ) -> tuple[list[GoalPriorityTerm], int]:
        return [], 0
