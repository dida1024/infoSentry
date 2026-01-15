"""User query service."""

from src.modules.users.application.models import UserData
from src.modules.users.domain.exceptions import UserNotFoundError
from src.modules.users.domain.repository import UserRepository


class UserQueryService:
    """Query service for user views."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repo = user_repository

    async def get_current_user(self, user_id: str) -> UserData:
        """Get current user data."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id=user_id)

        return UserData(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            status=user.status.value,
            display_name=user.display_name,
            timezone=user.timezone,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
