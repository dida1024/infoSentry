"""Source entity-model mappers."""

from src.core.infrastructure.database.mapper import BaseMapper
from src.modules.sources.domain.entities import Source
from src.modules.sources.infrastructure.models import SourceModel


class SourceMapper(BaseMapper[Source, SourceModel]):
    """Source entity-model mapper."""

    def to_domain(self, model: SourceModel) -> Source:
        return Source(
            id=model.id,
            type=model.type,
            name=model.name,
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
