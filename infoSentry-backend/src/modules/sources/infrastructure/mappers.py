"""Source entity-model mappers."""

from src.core.infrastructure.database.mapper import BaseMapper
from src.modules.sources.domain.entities import Source, SourceSubscription
from src.modules.sources.infrastructure.models import (
    SourceModel,
    SourceSubscriptionModel,
)


class SourceMapper(BaseMapper[Source, SourceModel]):
    """Source entity-model mapper."""

    def to_domain(self, model: SourceModel) -> Source:
        return Source(
            id=model.id,
            type=model.type,
            name=model.name,
            owner_id=model.owner_id,
            is_private=model.is_private,
            enabled=model.enabled,
            fetch_interval_sec=model.fetch_interval_sec,
            next_fetch_at=model.next_fetch_at,
            last_fetch_at=model.last_fetch_at,
            error_streak=model.error_streak,
            empty_streak=model.empty_streak,
            config=model.config,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: Source) -> SourceModel:
        return SourceModel(
            id=entity.id,
            type=entity.type,
            name=entity.name,
            owner_id=entity.owner_id,
            is_private=entity.is_private,
            enabled=entity.enabled,
            fetch_interval_sec=entity.fetch_interval_sec,
            next_fetch_at=entity.next_fetch_at,
            last_fetch_at=entity.last_fetch_at,
            error_streak=entity.error_streak,
            empty_streak=entity.empty_streak,
            config=entity.config,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )


class SourceSubscriptionMapper(BaseMapper[SourceSubscription, SourceSubscriptionModel]):
    """Source subscription entity-model mapper."""

    def to_domain(self, model: SourceSubscriptionModel) -> SourceSubscription:
        return SourceSubscription(
            id=model.id,
            user_id=model.user_id,
            source_id=model.source_id,
            enabled=model.enabled,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: SourceSubscription) -> SourceSubscriptionModel:
        return SourceSubscriptionModel(
            id=entity.id,
            user_id=entity.user_id,
            source_id=entity.source_id,
            enabled=entity.enabled,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )
