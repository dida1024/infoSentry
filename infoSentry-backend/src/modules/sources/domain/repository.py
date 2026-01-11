"""Source repository interface."""

from abc import abstractmethod
from datetime import datetime

from src.core.domain.repository import BaseRepository
from src.modules.sources.domain.entities import Source, SourceType


class SourceRepository(BaseRepository[Source]):
    """Source repository interface."""

    @abstractmethod
    async def get_by_name(self, name: str) -> Source | None:
        """Get source by name."""
        pass

    @abstractmethod
    async def list_by_type(
        self,
        source_type: SourceType | None = None,
        enabled_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Source], int]:
        """List sources by type."""
        pass

    @abstractmethod
    async def get_sources_due_for_fetch(
        self,
        before_time: datetime | None = None,
        limit: int = 10,
    ) -> list[Source]:
        """Get sources that are due for fetching."""
        pass

    @abstractmethod
    async def exists_by_name(self, name: str, exclude_id: str | None = None) -> bool:
        """Check if source with name exists."""
        pass
