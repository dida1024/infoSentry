"""Source application services."""

from src.modules.sources.application.models import SourceData, SourceListData
from src.modules.sources.domain.entities import Source, SourceType
from src.modules.sources.domain.exceptions import SourceNotFoundError
from src.modules.sources.domain.repository import SourceRepository


class SourceQueryService:
    """Source query service for list/detail views."""

    def __init__(self, source_repository: SourceRepository) -> None:
        self.source_repo = source_repository

    @staticmethod
    def build_source_data(source: Source) -> SourceData:
        """Convert source entity to source data."""
        return SourceData(
            id=source.id,
            type=source.type,
            name=source.name,
            enabled=source.enabled,
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
        source_type: str | None,
        page: int,
        page_size: int,
    ) -> SourceListData:
        """List sources by type."""
        domain_type = SourceType(source_type) if source_type else None
        sources, total = await self.source_repo.list_by_type(
            source_type=domain_type,
            enabled_only=False,
            page=page,
            page_size=page_size,
        )

        items = [self.build_source_data(source) for source in sources]
        return SourceListData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_source(self, source_id: str) -> SourceData:
        """Get source detail by id."""
        source = await self.source_repo.get_by_id(source_id)
        if not source:
            raise SourceNotFoundError(source_id=source_id)
        return self.build_source_data(source)
