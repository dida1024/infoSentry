"""Source repository implementations."""

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import exists, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from src.core.domain.events import EventBus
from src.core.domain.exceptions import EntityNotFoundError
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.sources.domain.entities import Source, SourceSubscription, SourceType
from src.modules.sources.domain.repository import (
    SourceRepository,
    SourceSubscriptionRepository,
)
from src.modules.sources.infrastructure.mappers import (
    SourceMapper,
    SourceSubscriptionMapper,
)
from src.modules.sources.infrastructure.models import (
    SourceModel,
    SourceSubscriptionModel,
)


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

    async def get_by_ids(self, source_ids: list[str]) -> dict[str, Source]:
        """Get sources by IDs (batch query)."""
        if not source_ids:
            return {}

        statement = select(SourceModel).where(
            SourceModel.id.in_(source_ids),
            col(SourceModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return {model.id: self.mapper.to_domain(model) for model in models}

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
        require_subscription: bool = False,
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

        if require_subscription:
            statement = statement.where(
                exists(
                    select(SourceSubscriptionModel.id).where(
                        SourceSubscriptionModel.source_id == SourceModel.id,
                        col(SourceSubscriptionModel.is_deleted).is_(False),
                        col(SourceSubscriptionModel.enabled).is_(True),
                    )
                )
            )

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

    async def list_public(
        self,
        source_type: SourceType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Source], int]:
        statement = select(
            SourceModel, func.count(SourceModel.id).over().label("total_count")
        ).where(
            col(SourceModel.is_deleted).is_(False),
            col(SourceModel.is_private).is_(False),
        )

        if source_type:
            statement = statement.where(SourceModel.type == source_type)

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
            before_time = datetime.now(UTC)

        statement = (
            select(SourceModel)
            .where(
                col(SourceModel.is_deleted).is_(False),
                col(SourceModel.enabled).is_(True),
                exists(
                    select(SourceSubscriptionModel.id).where(
                        SourceSubscriptionModel.source_id == SourceModel.id,
                        col(SourceSubscriptionModel.is_deleted).is_(False),
                        col(SourceSubscriptionModel.enabled).is_(True),
                    )
                ),
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
            raise EntityNotFoundError("Source", source.id)

        existing.type = source.type
        existing.name = source.name
        existing.owner_id = source.owner_id
        existing.is_private = source.is_private
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


class PostgreSQLSourceSubscriptionRepository(
    EventAwareRepository[SourceSubscription], SourceSubscriptionRepository
):
    """PostgreSQL source subscription repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: SourceSubscriptionMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, subscription_id: str) -> SourceSubscription | None:
        statement = select(SourceSubscriptionModel).where(
            SourceSubscriptionModel.id == subscription_id,
            col(SourceSubscriptionModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_user_and_source(
        self,
        user_id: str,
        source_id: str,
        include_deleted: bool = False,
    ) -> SourceSubscription | None:
        statement = select(SourceSubscriptionModel).where(
            SourceSubscriptionModel.user_id == user_id,
            SourceSubscriptionModel.source_id == source_id,
        )
        if not include_deleted:
            statement = statement.where(
                col(SourceSubscriptionModel.is_deleted).is_(False)
            )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_sources_by_user(
        self,
        user_id: str,
        source_type: SourceType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[tuple[Source, SourceSubscription]], int]:
        statement = (
            select(
                SourceModel,
                SourceSubscriptionModel,
                func.count(SourceSubscriptionModel.id).over().label("total_count"),
            )
            .join(
                SourceSubscriptionModel,
                SourceSubscriptionModel.source_id == SourceModel.id,
            )
            .where(
                SourceSubscriptionModel.user_id == user_id,
                col(SourceSubscriptionModel.is_deleted).is_(False),
                col(SourceModel.is_deleted).is_(False),
            )
        )

        if source_type:
            statement = statement.where(SourceModel.type == source_type)

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
        items: list[tuple[Source, SourceSubscription]] = []
        source_mapper = SourceMapper()
        for row in rows:
            subscription = self.mapper.to_domain(row.SourceSubscriptionModel)
            source = source_mapper.to_domain(row.SourceModel)
            items.append((source, subscription))

        return items, total_count

    async def list_by_user_and_source_ids(
        self, user_id: str, source_ids: list[str]
    ) -> list[SourceSubscription]:
        if not source_ids:
            return []
        statement = select(SourceSubscriptionModel).where(
            SourceSubscriptionModel.user_id == user_id,
            SourceSubscriptionModel.source_id.in_(source_ids),
            col(SourceSubscriptionModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def create(self, subscription: SourceSubscription) -> SourceSubscription:
        model = self.mapper.to_model(subscription)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(subscription)
        return self.mapper.to_domain(model)

    async def update(self, subscription: SourceSubscription) -> SourceSubscription:
        statement = select(SourceSubscriptionModel).where(
            SourceSubscriptionModel.id == subscription.id
        )
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise EntityNotFoundError("SourceSubscription", subscription.id)

        existing.user_id = subscription.user_id
        existing.source_id = subscription.source_id
        existing.enabled = subscription.enabled
        existing.updated_at = subscription.updated_at
        existing.is_deleted = subscription.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(subscription)
        return self.mapper.to_domain(existing)

    async def delete(self, subscription: SourceSubscription | str) -> bool:
        subscription_id = (
            subscription.id
            if isinstance(subscription, SourceSubscription)
            else subscription
        )
        statement = select(SourceSubscriptionModel).where(
            SourceSubscriptionModel.id == subscription_id,
            col(SourceSubscriptionModel.is_deleted).is_(False),
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
    ) -> tuple[list[SourceSubscription], int]:
        statement = select(
            SourceSubscriptionModel,
            func.count(SourceSubscriptionModel.id).over().label("total_count"),
        )

        if not include_deleted:
            statement = statement.where(
                col(SourceSubscriptionModel.is_deleted).is_(False)
            )

        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(SourceSubscriptionModel.created_at.desc())
        )

        result = await self.session.execute(statement)
        rows = result.all()
        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.SourceSubscriptionModel for row in rows]
        return self.mapper.to_domain_list(models), total_count
