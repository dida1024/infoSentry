"""User command handlers."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from loguru import logger

from src.core.config import settings
from src.core.domain.ports.token import TokenService
from src.core.infrastructure.logging import BusinessEvents
from src.modules.users.application.commands import (
    ConsumeMagicLinkCommand,
    RequestMagicLinkCommand,
    UpdateProfileCommand,
)
from src.modules.users.domain.entities import MagicLink, User
from src.modules.users.domain.events import MagicLinkRequestedEvent, UserCreatedEvent
from src.modules.users.domain.exceptions import (
    InvalidMagicLinkError,
    MagicLinkAlreadyUsedError,
    MagicLinkExpiredError,
    UserNotFoundError,
)
from src.modules.users.domain.ports import MagicLinkEmailQueue
from src.modules.users.domain.repository import MagicLinkRepository, UserRepository


class RequestMagicLinkHandler:
    """Handle magic link request."""

    def __init__(
        self,
        user_repository: UserRepository,
        magic_link_repository: MagicLinkRepository,
        token_service: TokenService,
        magic_link_email_queue: MagicLinkEmailQueue,
    ):
        self.user_repository = user_repository
        self.magic_link_repository = magic_link_repository
        self.token_service = token_service
        self.magic_link_email_queue = magic_link_email_queue
        self.logger = logger

    async def handle(self, command: RequestMagicLinkCommand) -> MagicLink:
        """Handle magic link request.

        Creates user if not exists, then creates a magic link.
        """
        # Get or create user
        user = await self.user_repository.get_by_email(command.email)
        if not user:
            # Create new user
            user = User(
                id=str(uuid4()),
                email=command.email,
            )
            user.add_domain_event(UserCreatedEvent(user_id=user.id, email=user.email))
            await self.user_repository.create(user)
            self.logger.info(f"Created new user: {command.email}")

        # Invalidate existing magic links
        await self.magic_link_repository.invalidate_all_for_email(command.email)

        # Create new magic link with UTC timezone
        token = self.token_service.create_magic_link_token(command.email)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.MAGIC_LINK_EXPIRE_MINUTES
        )

        magic_link = MagicLink(
            id=str(uuid4()),
            email=command.email,
            token=token,
            expires_at=expires_at,
        )
        magic_link.add_domain_event(
            MagicLinkRequestedEvent(
                email=command.email,
                magic_link_id=magic_link.id,
            )
        )

        await self.magic_link_repository.create(magic_link)
        self.logger.info(f"Created magic link for: {command.email}")

        await self.magic_link_email_queue.enqueue(
            magic_link_id=magic_link.id,
            email=command.email,
        )
        BusinessEvents.magic_link_email_enqueued(
            email=command.email,
            magic_link_id=magic_link.id,
        )

        # 本地开发环境：打印登录链接到日志，方便调试
        if settings.ENVIRONMENT == "local":
            login_url = f"{settings.FRONTEND_HOST}/auth/callback?token={token}"
            self.logger.warning(f"[DEV LOGIN] 点击此链接登录: {login_url}")

        return magic_link


class ConsumeMagicLinkHandler:
    """Handle magic link consumption."""

    def __init__(
        self,
        user_repository: UserRepository,
        magic_link_repository: MagicLinkRepository,
        token_service: TokenService,
    ):
        self.user_repository = user_repository
        self.magic_link_repository = magic_link_repository
        self.token_service = token_service
        self.logger = logger

    async def handle(self, command: ConsumeMagicLinkCommand) -> tuple[User, str]:
        """Consume magic link and return user with access token."""
        # Get magic link
        magic_link = await self.magic_link_repository.get_by_token(command.token)
        if not magic_link:
            self.logger.warning("Magic link not found for token")
            raise InvalidMagicLinkError()

        # Check if already used
        if magic_link.is_used:
            self.logger.warning(
                f"Magic link already used: email={magic_link.email}, "
                f"used_at={magic_link.used_at}"
            )
            raise MagicLinkAlreadyUsedError()

        # Check if expired
        now = datetime.now(UTC)
        if now > magic_link.expires_at:
            self.logger.warning(
                f"Magic link expired: email={magic_link.email}, "
                f"expires_at={magic_link.expires_at}, now={now}"
            )
            raise MagicLinkExpiredError()

        # Get user
        user = await self.user_repository.get_by_email(magic_link.email)
        if not user:
            raise UserNotFoundError(email=magic_link.email)

        # Mark magic link as used
        magic_link.mark_as_used()
        await self.magic_link_repository.update(magic_link)

        # Update user last login
        user.update_last_login()
        await self.user_repository.update(user)

        # Create access token
        access_token = self.token_service.create_access_token(
            subject=user.id,
            extra_claims={"email": user.email},
        )

        self.logger.info(f"User logged in: {user.email}")

        return user, access_token


class UpdateProfileHandler:
    """Handle user profile update."""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
        self.logger = logger

    async def handle(self, command: UpdateProfileCommand) -> User:
        """Update user profile."""
        user = await self.user_repository.get_by_id(command.user_id)
        if not user:
            raise UserNotFoundError(user_id=command.user_id)

        updated_fields = user.update_profile(
            display_name=command.display_name,
            timezone=command.timezone,
        )

        if updated_fields:
            await self.user_repository.update(user)
            self.logger.info(f"Updated profile for user {user.id}: {updated_fields}")

        return user
