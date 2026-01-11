"""Push repository interfaces."""

from abc import abstractmethod
from datetime import datetime

from src.core.domain.repository import BaseRepository
from src.modules.push.domain.entities import (
    BlockedSource,
    ClickEvent,
    ItemFeedback,
    PushDecision,
    PushDecisionRecord,
    PushStatus,
)


class PushDecisionRepository(BaseRepository[PushDecisionRecord]):
    """Push decision repository interface."""

    @abstractmethod
    async def get_by_dedupe_key(self, dedupe_key: str) -> PushDecisionRecord | None:
        """Get by dedupe key."""
        pass

    @abstractmethod
    async def list_by_goal(
        self,
        goal_id: str,
        status: PushStatus | None = None,
        decision: PushDecision | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[PushDecisionRecord], int]:
        """List decisions by goal."""
        pass

    @abstractmethod
    async def list_pending_batch(
        self,
        goal_id: str,
        window_start: datetime,
        window_end: datetime,
        limit: int = 10,
    ) -> list[PushDecisionRecord]:
        """List pending batch decisions in a time window."""
        pass

    @abstractmethod
    async def list_pending_digest(
        self,
        goal_id: str,
        since: datetime,
        limit: int = 20,
    ) -> list[PushDecisionRecord]:
        """List items for digest that haven't been sent."""
        pass


class ClickEventRepository(BaseRepository[ClickEvent]):
    """Click event repository interface."""

    @abstractmethod
    async def list_by_item(self, item_id: str) -> list[ClickEvent]:
        """List clicks for an item."""
        pass

    @abstractmethod
    async def count_by_goal(
        self,
        goal_id: str,
        since: datetime | None = None,
    ) -> int:
        """Count clicks for a goal."""
        pass


class ItemFeedbackRepository(BaseRepository[ItemFeedback]):
    """Item feedback repository interface."""

    @abstractmethod
    async def get_by_item_goal_user(
        self,
        item_id: str,
        goal_id: str,
        user_id: str,
    ) -> ItemFeedback | None:
        """Get feedback for specific item/goal/user combination."""
        pass

    @abstractmethod
    async def list_by_goal(
        self,
        goal_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ItemFeedback], int]:
        """List feedback for a goal."""
        pass


class BlockedSourceRepository(BaseRepository[BlockedSource]):
    """Blocked source repository interface."""

    @abstractmethod
    async def is_blocked(
        self,
        user_id: str,
        source_id: str,
        goal_id: str | None = None,
    ) -> bool:
        """Check if source is blocked."""
        pass

    @abstractmethod
    async def list_by_user(
        self,
        user_id: str,
        goal_id: str | None = None,
    ) -> list[BlockedSource]:
        """List blocked sources for user."""
        pass
