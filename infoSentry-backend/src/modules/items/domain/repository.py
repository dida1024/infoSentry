"""Item repository interfaces."""

from abc import abstractmethod
from datetime import datetime

from src.core.domain.repository import BaseRepository
from src.modules.items.domain.entities import GoalItemMatch, Item


class ItemRepository(BaseRepository[Item]):
    """Item repository interface."""

    @abstractmethod
    async def get_by_url_hash(self, url_hash: str) -> Item | None:
        """Get item by URL hash."""
        pass

    @abstractmethod
    async def exists_by_url_hash(self, url_hash: str) -> bool:
        """Check if item with URL hash exists."""
        pass

    @abstractmethod
    async def list_by_source(
        self,
        source_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Item], int]:
        """List items by source."""
        pass

    @abstractmethod
    async def list_pending_embedding(self, limit: int = 100) -> list[Item]:
        """List items pending embedding."""
        pass

    @abstractmethod
    async def list_recent(
        self,
        since: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Item], int]:
        """List recent items."""
        pass

    @abstractmethod
    async def search_similar(
        self,
        embedding: list[float],
        limit: int = 20,
        min_score: float = 0.5,
    ) -> list[tuple[Item, float]]:
        """Search similar items by embedding."""
        pass


class GoalItemMatchRepository(BaseRepository[GoalItemMatch]):
    """Goal-Item match repository interface."""

    @abstractmethod
    async def get_by_goal_and_item(
        self, goal_id: str, item_id: str
    ) -> GoalItemMatch | None:
        """Get match by goal and item."""
        pass

    @abstractmethod
    async def list_by_goal(
        self,
        goal_id: str,
        min_score: float | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GoalItemMatch], int]:
        """List matches for a goal."""
        pass

    @abstractmethod
    async def list_by_item(self, item_id: str) -> list[GoalItemMatch]:
        """List matches for an item."""
        pass

    @abstractmethod
    async def upsert(self, match: GoalItemMatch) -> GoalItemMatch:
        """Insert or update a match."""
        pass
