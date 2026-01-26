"""Goal repository interfaces."""

from abc import abstractmethod

from src.core.domain.repository import BaseRepository
from src.modules.goals.domain.entities import (
    Goal,
    GoalPriorityTerm,
    GoalPushConfig,
    GoalStatus,
    TermType,
)


class GoalRepository(BaseRepository[Goal]):
    """Goal repository interface."""

    @abstractmethod
    async def list_by_user(
        self,
        user_id: str,
        status: GoalStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Goal], int]:
        """List goals for a user."""
        pass

    @abstractmethod
    async def get_active_goals(self) -> list[Goal]:
        """Get all active goals (for matching)."""
        pass


class GoalPushConfigRepository(BaseRepository[GoalPushConfig]):
    """Goal push config repository interface."""

    @abstractmethod
    async def get_by_goal_id(self, goal_id: str) -> GoalPushConfig | None:
        """Get push config for a goal."""
        pass

    @abstractmethod
    async def get_by_goal_ids(self, goal_ids: list[str]) -> dict[str, GoalPushConfig]:
        """Get push configs for multiple goals (batch query).

        Args:
            goal_ids: List of goal IDs to fetch

        Returns:
            Dict mapping goal_id -> GoalPushConfig for found configs
        """
        pass


class GoalPriorityTermRepository(BaseRepository[GoalPriorityTerm]):
    """Goal priority term repository interface."""

    @abstractmethod
    async def list_by_goal(
        self,
        goal_id: str,
        term_type: TermType | None = None,
    ) -> list[GoalPriorityTerm]:
        """List terms for a goal."""
        pass

    @abstractmethod
    async def list_by_goal_ids(
        self,
        goal_ids: list[str],
    ) -> dict[str, list[GoalPriorityTerm]]:
        """List terms for multiple goals (batch query).

        Args:
            goal_ids: List of goal IDs to fetch

        Returns:
            Dict mapping goal_id -> list of GoalPriorityTerm
        """
        pass

    @abstractmethod
    async def delete_all_for_goal(self, goal_id: str) -> int:
        """Delete all terms for a goal. Returns count deleted."""
        pass

    @abstractmethod
    async def bulk_create(
        self, terms: list[GoalPriorityTerm]
    ) -> list[GoalPriorityTerm]:
        """Bulk create terms."""
        pass
