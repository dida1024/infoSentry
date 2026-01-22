"""User command handlers."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from loguru import logger

from src.core.config import settings
from src.core.domain.ports.token import TokenService
from src.core.infrastructure.logging import BusinessEvents
from src.modules.users.application.commands import (
    ConsumeMagicLinkCommand,
    RefreshSessionCommand,
    RequestMagicLinkCommand,
    RevokeSessionCommand,
    UpdateProfileCommand,
)
from src.modules.users.application.session_service import (
    RefreshTokenPayload,
    generate_refresh_token,
    hash_refresh_token,
    is_refresh_risky,
    refresh_expires_at,
)
from src.modules.users.domain.entities import DeviceSession, MagicLink, User
from src.modules.users.domain.events import MagicLinkRequestedEvent, UserCreatedEvent
from src.modules.users.domain.exceptions import (
    DeviceSessionExpiredError,
    DeviceSessionNotFoundError,
    DeviceSessionRevokedError,
    DeviceSessionRiskBlockedError,
    InvalidMagicLinkError,
    MagicLinkAlreadyUsedError,
    MagicLinkExpiredError,
    UserNotFoundError,
)
from src.modules.users.domain.ports import MagicLinkEmailQueue
from src.modules.users.domain.repository import (
    DeviceSessionRepository,
    MagicLinkRepository,
    UserRepository,
)


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
        device_session_repository: DeviceSessionRepository,
    ):
        self.user_repository = user_repository
        self.magic_link_repository = magic_link_repository
        self.token_service = token_service
        self.device_session_repository = device_session_repository
        self.logger = logger

    async def handle(
        self, command: ConsumeMagicLinkCommand
    ) -> tuple[User, str, RefreshTokenPayload]:
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

        refresh_token = generate_refresh_token()
        refresh_hash = hash_refresh_token(refresh_token)
        refresh_token_expires_at = refresh_expires_at()
        now = datetime.now(UTC)

        device_session = DeviceSession(
            id=str(uuid4()),
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            device_id=str(uuid4()),
            ip_address=command.ip_address,
            user_agent=command.user_agent,
            expires_at=refresh_token_expires_at,
            last_seen_at=now,
        )
        await self.device_session_repository.create(device_session)

        BusinessEvents.device_session_created(
            user_id=user.id,
            session_id=device_session.id,
            device_id=device_session.device_id,
            ip_address=device_session.ip_address,
            user_agent=device_session.user_agent,
            expires_at=device_session.expires_at,
        )
        self.logger.info(f"User logged in: {user.email}")

        return user, access_token, RefreshTokenPayload(
            token=refresh_token,
            expires_at=refresh_token_expires_at,
        )


class RefreshSessionHandler:
    """Handle device session refresh."""

    def __init__(
        self,
        user_repository: UserRepository,
        device_session_repository: DeviceSessionRepository,
        token_service: TokenService,
    ):
        self.user_repository = user_repository
        self.device_session_repository = device_session_repository
        self.token_service = token_service
        self.logger = logger

    async def handle(
        self, command: RefreshSessionCommand
    ) -> tuple[str, RefreshTokenPayload]:
        """Refresh device session and return new access token."""
        refresh_hash = hash_refresh_token(command.refresh_token)
        session = await self.device_session_repository.get_by_refresh_token_hash(
            refresh_hash
        )
        if not session:
            self.logger.warning("Device session not found for refresh token hash")
            raise DeviceSessionNotFoundError()

        now = datetime.now(UTC)
        if session.revoked_at is not None:
            self.logger.warning(
                f"Device session revoked: session_id={session.id}, "
                f"user_id={session.user_id}"
            )
            raise DeviceSessionRevokedError()

        if now > session.expires_at:
            self.logger.warning(
                f"Device session expired: session_id={session.id}, "
                f"expires_at={session.expires_at}, now={now}"
            )
            raise DeviceSessionExpiredError()

        if is_refresh_risky(session, command.ip_address, command.user_agent):
            session.mark_revoked(now)
            await self.device_session_repository.update(session)
            BusinessEvents.device_session_risk_blocked(
                user_id=session.user_id,
                session_id=session.id,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
            raise DeviceSessionRiskBlockedError()

        user = await self.user_repository.get_by_id(session.user_id)
        if not user:
            raise UserNotFoundError(user_id=session.user_id)

        new_refresh_token = generate_refresh_token()
        new_refresh_hash = hash_refresh_token(new_refresh_token)
        new_expires_at = refresh_expires_at(now)

        session.refresh_token_hash = new_refresh_hash
        session.expires_at = new_expires_at
        session.update_last_seen(command.ip_address, command.user_agent, now)
        await self.device_session_repository.update(session)

        BusinessEvents.device_session_refreshed(
            user_id=user.id,
            session_id=session.id,
            device_id=session.device_id,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            expires_at=session.expires_at,
        )

        access_token = self.token_service.create_access_token(
            subject=user.id,
            extra_claims={"email": user.email},
        )

        return access_token, RefreshTokenPayload(
            token=new_refresh_token,
            expires_at=new_expires_at,
        )


class RevokeSessionHandler:
    """Handle device session revocation."""

    def __init__(self, device_session_repository: DeviceSessionRepository):
        self.device_session_repository = device_session_repository
        self.logger = logger

    async def handle(self, command: RevokeSessionCommand) -> bool:
        """Revoke device session and return if it existed."""
        refresh_hash = hash_refresh_token(command.refresh_token)
        session = await self.device_session_repository.get_by_refresh_token_hash(
            refresh_hash
        )
        if not session:
            self.logger.warning("Device session not found for revoke token hash")
            return False

        session.mark_revoked()
        await self.device_session_repository.update(session)
        BusinessEvents.device_session_revoked(
            user_id=session.user_id,
            session_id=session.id,
            device_id=session.device_id,
        )
        return True


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
