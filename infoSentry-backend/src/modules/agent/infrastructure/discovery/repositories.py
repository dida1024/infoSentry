"""Discovery session repository implementations."""

from loguru import logger
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from src.core.domain.events import EventBus
from src.core.domain.exceptions import DuplicateEntityError, EntityNotFoundError
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.agent.domain.discovery_entities import (
    CandidateSource,
    DiscoverySession,
    SessionStatus,
)
from src.modules.agent.domain.repository import (
    DiscoveryCandidateRepository,
    DiscoverySessionRepository,
)
from src.modules.agent.infrastructure.discovery.mappers import (
    DiscoveryCandidateMapper,
    DiscoverySessionMapper,
)
from src.modules.agent.infrastructure.discovery.models import (
    DiscoveryCandidateModel,
    DiscoverySessionModel,
)

# Terminal statuses that no longer count as "active"
_TERMINAL_STATUSES = {
    SessionStatus.COMPLETED.value,
    SessionStatus.FAILED.value,
    SessionStatus.EXPIRED.value,
}
_ACTIVE_SESSION_INDEX = "uq_discovery_sessions_active_per_user"


class PostgreSQLDiscoverySessionRepository(
    EventAwareRepository[DiscoverySession], DiscoverySessionRepository
):
    """PostgreSQL discovery session repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: DiscoverySessionMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, entity_id: str) -> DiscoverySession | None:
        statement = select(DiscoverySessionModel).where(
            DiscoverySessionModel.id == entity_id,
            col(DiscoverySessionModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def create(self, entity: DiscoverySession) -> DiscoverySession:
        model = self.mapper.to_model(entity)
        self.session.add(model)
        try:
            await self.session.flush()
            await self.session.refresh(model)
        except IntegrityError as e:
            await self.session.rollback()
            if _ACTIVE_SESSION_INDEX in str(e):
                raise DuplicateEntityError(
                    "DiscoverySession",
                    "user_id",
                    entity.user_id,
                ) from e
            raise
        await self._publish_events_from_entity(entity)
        return self.mapper.to_domain(model)

    async def update(self, entity: DiscoverySession) -> DiscoverySession:
        statement = select(DiscoverySessionModel).where(
            DiscoverySessionModel.id == entity.id
        )
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise EntityNotFoundError("DiscoverySession", entity.id)

        updated_model = self.mapper.to_model(entity)
        existing.status = updated_model.status
        existing.messages_json = updated_model.messages_json
        existing.expires_at = updated_model.expires_at
        existing.updated_at = updated_model.updated_at
        existing.is_deleted = updated_model.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(entity)
        return self.mapper.to_domain(existing)

    async def delete(self, entity: DiscoverySession | str) -> bool:
        entity_id = entity.id if isinstance(entity, DiscoverySession) else entity
        statement = select(DiscoverySessionModel).where(
            DiscoverySessionModel.id == entity_id,
            col(DiscoverySessionModel.is_deleted).is_(False),
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
    ) -> tuple[list[DiscoverySession], int]:
        statement = select(
            DiscoverySessionModel,
            func.count(col(DiscoverySessionModel.id)).over().label("total_count"),
        )
        if not include_deleted:
            statement = statement.where(
                col(DiscoverySessionModel.is_deleted).is_(False)
            )
        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(col(DiscoverySessionModel.created_at).desc())
        )
        result = await self.session.execute(statement)
        rows = result.all()
        if not rows:
            return [], 0
        total_count = rows[0].total_count
        models = [row.DiscoverySessionModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DiscoverySession], int]:
        statement = select(
            DiscoverySessionModel,
            func.count(col(DiscoverySessionModel.id)).over().label("total_count"),
        ).where(
            DiscoverySessionModel.user_id == user_id,
            col(DiscoverySessionModel.is_deleted).is_(False),
        )
        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(col(DiscoverySessionModel.created_at).desc())
        )
        result = await self.session.execute(statement)
        rows = result.all()
        if not rows:
            return [], 0
        total_count = rows[0].total_count
        models = [row.DiscoverySessionModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def count_active_by_user(self, user_id: str) -> int:
        statement = select(func.count()).select_from(DiscoverySessionModel).where(
            DiscoverySessionModel.user_id == user_id,
            col(DiscoverySessionModel.is_deleted).is_(False),
            col(DiscoverySessionModel.status).notin_(_TERMINAL_STATUSES),
        )
        result = await self.session.execute(statement)
        return result.scalar_one()


class PostgreSQLDiscoveryCandidateRepository(
    EventAwareRepository[CandidateSource], DiscoveryCandidateRepository
):
    """PostgreSQL discovery candidate repository."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: DiscoveryCandidateMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, entity_id: str) -> CandidateSource | None:
        statement = select(DiscoveryCandidateModel).where(
            DiscoveryCandidateModel.id == entity_id,
            col(DiscoveryCandidateModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def create(self, entity: CandidateSource) -> CandidateSource:
        model = self.mapper.to_model(entity)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(entity)
        return self.mapper.to_domain(model)

    async def update(self, entity: CandidateSource) -> CandidateSource:
        statement = select(DiscoveryCandidateModel).where(
            DiscoveryCandidateModel.id == entity.id
        )
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise EntityNotFoundError("CandidateSource", entity.id)

        updated_model = self.mapper.to_model(entity)
        existing.status = updated_model.status
        existing.validation_result_json = updated_model.validation_result_json
        existing.source_id = updated_model.source_id
        existing.config_json = updated_model.config_json
        existing.updated_at = updated_model.updated_at
        existing.is_deleted = updated_model.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(entity)
        return self.mapper.to_domain(existing)

    async def delete(self, entity: CandidateSource | str) -> bool:
        entity_id = entity.id if isinstance(entity, CandidateSource) else entity
        statement = select(DiscoveryCandidateModel).where(
            DiscoveryCandidateModel.id == entity_id,
            col(DiscoveryCandidateModel.is_deleted).is_(False),
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
    ) -> tuple[list[CandidateSource], int]:
        statement = select(
            DiscoveryCandidateModel,
            func.count(col(DiscoveryCandidateModel.id)).over().label("total_count"),
        )
        if not include_deleted:
            statement = statement.where(
                col(DiscoveryCandidateModel.is_deleted).is_(False)
            )
        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(col(DiscoveryCandidateModel.created_at).desc())
        )
        result = await self.session.execute(statement)
        rows = result.all()
        if not rows:
            return [], 0
        total_count = rows[0].total_count
        models = [row.DiscoveryCandidateModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def list_by_session(self, session_id: str) -> list[CandidateSource]:
        statement = (
            select(DiscoveryCandidateModel)
            .where(
                DiscoveryCandidateModel.session_id == session_id,
                col(DiscoveryCandidateModel.is_deleted).is_(False),
            )
            .order_by(col(DiscoveryCandidateModel.created_at).asc())
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))
