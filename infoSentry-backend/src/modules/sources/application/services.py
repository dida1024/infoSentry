"""Source application services."""

from src.modules.sources.application.models import (
    PublicSourceData,
    PublicSourceListData,
    SourceData,
    SourceListData,
)
from src.modules.sources.domain.entities import Source, SourceSubscription, SourceType
from src.modules.sources.domain.exceptions import SourceNotFoundError
from src.modules.sources.domain.repository import (
    SourceRepository,
    SourceSubscriptionRepository,
)


class SourceQueryService:
    """Source query service for list/detail views."""

    def __init__(
        self,
        source_repository: SourceRepository,
        subscription_repository: SourceSubscriptionRepository,
    ) -> None:
        self.source_repo = source_repository
        self.subscription_repo = subscription_repository

    @staticmethod
    def build_source_data(
        source: Source, subscription: SourceSubscription | None
    ) -> SourceData:
        """Convert source entity to source data."""
        return SourceData(
            id=source.id,
            type=source.type,
            name=source.name,
            is_private=source.is_private,
            enabled=subscription.enabled if subscription else source.enabled,
            fetch_interval_sec=source.fetch_interval_sec,
            next_fetch_at=source.next_fetch_at,
            last_fetch_at=source.last_fetch_at,
            error_streak=source.error_streak,
            config=source.config,
            created_at=source.created_at,
            updated_at=source.updated_at,
        )

    async def list_sources(
        self,
        user_id: str,
        source_type: str | None,
        page: int,
        page_size: int,
    ) -> SourceListData:
        """List sources by user subscription."""
        domain_type = SourceType(source_type) if source_type else None
        pairs, total = await self.subscription_repo.list_sources_by_user(
            user_id=user_id,
            source_type=domain_type,
            page=page,
            page_size=page_size,
        )

        items = [
            self.build_source_data(source, subscription)
            for source, subscription in pairs
        ]
        return SourceListData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    def build_public_source_data(
        source: Source, subscription: SourceSubscription | None
    ) -> PublicSourceData:
        """Convert source entity to public source data."""
        return PublicSourceData(
            id=source.id,
            type=source.type,
            name=source.name,
            is_private=source.is_private,
            enabled=subscription.enabled if subscription else False,
            fetch_interval_sec=source.fetch_interval_sec,
            next_fetch_at=source.next_fetch_at,
            last_fetch_at=source.last_fetch_at,
            error_streak=source.error_streak,
            config=source.config,
            created_at=source.created_at,
            updated_at=source.updated_at,
            is_subscribed=subscription is not None,
        )

    async def list_public_sources(
        self,
        user_id: str,
        source_type: str | None,
        page: int,
        page_size: int,
    ) -> PublicSourceListData:
        """List public sources with subscription status."""
        domain_type = SourceType(source_type) if source_type else None
        sources, total = await self.source_repo.list_public(
            source_type=domain_type,
            page=page,
            page_size=page_size,
        )
        source_ids = [source.id for source in sources]
        subscriptions = await self.subscription_repo.list_by_user_and_source_ids(
            user_id=user_id,
            source_ids=source_ids,
        )
        subscription_map = {s.source_id: s for s in subscriptions}
        items = [
            self.build_public_source_data(source, subscription_map.get(source.id))
            for source in sources
        ]
        return PublicSourceListData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_source(self, source_id: str, user_id: str) -> SourceData:
        """Get source detail by id."""
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise SourceNotFoundError(source_id=source_id)
        subscription = await self.subscription_repo.get_by_user_and_source(
            user_id=user_id, source_id=source_id
        )
        if not subscription:
            raise SourceNotFoundError(source_id=source_id)
        return self.build_source_data(source, subscription)
