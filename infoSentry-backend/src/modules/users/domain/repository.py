"""User repository interface."""

from abc import abstractmethod

from src.core.domain.repository import BaseRepository
from src.modules.users.domain.entities import (
    DeviceSession,
    MagicLink,
    User,
    UserBudgetDaily,
)


class UserRepository(BaseRepository[User]):
    """User repository interface."""

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        pass

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        """Check if user with email exists."""
        pass


class MagicLinkRepository(BaseRepository[MagicLink]):
    """Magic link repository interface."""

    @abstractmethod
    async def get_by_token(self, token: str) -> MagicLink | None:
        """Get magic link by token."""
        pass

    @abstractmethod
    async def get_valid_by_email(self, email: str) -> MagicLink | None:
        """Get valid (unused, not expired) magic link for email."""
        pass

    @abstractmethod
    async def invalidate_all_for_email(self, email: str) -> int:
        """Invalidate all magic links for an email. Returns count of invalidated links."""
        pass


class DeviceSessionRepository(BaseRepository[DeviceSession]):
    """Device session repository interface."""

    @abstractmethod
    async def get_by_refresh_token_hash(
        self, refresh_token_hash: str
    ) -> DeviceSession | None:
        """Get device session by refresh token hash."""
        pass


class UserBudgetDailyRepository(BaseRepository[UserBudgetDaily]):
    """User daily budget repository interface."""

    @abstractmethod
    async def get_by_user_and_date(
        self, user_id: str, date: str
    ) -> UserBudgetDaily | None:
        """Get user budget by date."""
        pass

    @abstractmethod
    async def get_or_create(self, user_id: str, date: str) -> UserBudgetDaily:
        """Get or create budget record for user on date."""
        pass

    @abstractmethod
    async def list_by_user_date_range(
        self, user_id: str, start_date: str, end_date: str
    ) -> list[UserBudgetDaily]:
        """List user budgets within date range (inclusive)."""
        pass
