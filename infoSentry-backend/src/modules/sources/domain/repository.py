"""Source repository interface."""

from abc import abstractmethod
from datetime import datetime

from src.core.domain.repository import BaseRepository
from src.modules.sources.domain.entities import Source, SourceSubscription, SourceType


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
        require_subscription: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Source], int]:
        """List sources by type."""
        pass

    @abstractmethod
    async def list_public(
        self,
        source_type: SourceType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Source], int]:
        """List public sources."""
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


class SourceSubscriptionRepository(BaseRepository[SourceSubscription]):
    """Source subscription repository interface."""

    @abstractmethod
    async def get_by_user_and_source(
        self,
        user_id: str,
        source_id: str,
        include_deleted: bool = False,
    ) -> SourceSubscription | None:
        """Get subscription by user and source."""
        pass

    @abstractmethod
    async def list_sources_by_user(
        self,
        user_id: str,
        source_type: SourceType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[tuple[Source, SourceSubscription]], int]:
        """List sources for a user with subscriptions."""
        pass

    @abstractmethod
    async def list_by_user_and_source_ids(
        self, user_id: str, source_ids: list[str]
    ) -> list[SourceSubscription]:
        """List subscriptions by user and source ids."""
        pass
