"""Source repository implementations."""

from datetime import datetime

from loguru import logger
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from src.core.domain.events import EventBus
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.sources.domain.entities import Source, SourceType
from src.modules.sources.domain.repository import SourceRepository
from src.modules.sources.infrastructure.mappers import SourceMapper
from src.modules.sources.infrastructure.models import SourceModel


class PostgreSQLSourceRepository(EventAwareRepository[Source], SourceRepository):
    """PostgreSQL source repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: SourceMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, source_id: str) -> Source | None:
        statement = select(SourceModel).where(
            SourceModel.id == source_id,
            col(SourceModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_name(self, name: str) -> Source | None:
        statement = select(SourceModel).where(
            SourceModel.name == name,
            col(SourceModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def exists_by_name(self, name: str, exclude_id: str | None = None) -> bool:
        statement = select(SourceModel).where(
            SourceModel.name == name,
            col(SourceModel.is_deleted).is_(False),
        )
        if exclude_id:
            statement = statement.where(SourceModel.id != exclude_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def list_by_type(
        self,
        source_type: SourceType | None = None,
        enabled_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Source], int]:
        statement = select(
            SourceModel, func.count(SourceModel.id).over().label("total_count")
        ).where(col(SourceModel.is_deleted).is_(False))

        if source_type:
            statement = statement.where(SourceModel.type == source_type)

        if enabled_only:
            statement = statement.where(col(SourceModel.enabled).is_(True))

        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(SourceModel.name)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.SourceModel for row in rows]
        return self.mapper.to_domain_list(models), total_count

    async def get_sources_due_for_fetch(
        self,
        before_time: datetime | None = None,
        limit: int = 10,
    ) -> list[Source]:
        if before_time is None:
            before_time = datetime.now()

        statement = (
            select(SourceModel)
            .where(
                col(SourceModel.is_deleted).is_(False),
                col(SourceModel.enabled).is_(True),
            )
            .where(
                (col(SourceModel.next_fetch_at).is_(None))
                | (SourceModel.next_fetch_at <= before_time)
            )
            .order_by(SourceModel.next_fetch_at.asc().nullsfirst())
            .limit(limit)
        )

        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def create(self, source: Source) -> Source:
        model = self.mapper.to_model(source)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(source)
        return self.mapper.to_domain(model)

    async def update(self, source: Source) -> Source:
        statement = select(SourceModel).where(SourceModel.id == source.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"Source with id {source.id} not found")

        existing.type = source.type
        existing.name = source.name
        existing.enabled = source.enabled
        existing.fetch_interval_sec = source.fetch_interval_sec
        existing.next_fetch_at = source.next_fetch_at
        existing.last_fetch_at = source.last_fetch_at
        existing.error_streak = source.error_streak
        existing.empty_streak = source.empty_streak
        existing.config = source.config
        existing.updated_at = source.updated_at
        existing.is_deleted = source.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(source)
        return self.mapper.to_domain(existing)

    async def delete(self, source: Source | str) -> bool:
        source_id = source.id if isinstance(source, Source) else source
        statement = select(SourceModel).where(
            SourceModel.id == source_id,
            col(SourceModel.is_deleted).is_(False),
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
    ) -> tuple[list[Source], int]:
        return await self.list_by_type(
            source_type=None,
            enabled_only=False,
            page=page,
            page_size=page_size,
        )
