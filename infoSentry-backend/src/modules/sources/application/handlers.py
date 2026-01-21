"""Source command handlers."""

from uuid import uuid4

from loguru import logger

from src.core.config import settings
from src.core.domain.exceptions import AuthorizationError
from src.modules.sources.application.commands import (
    CreateSourceCommand,
    DeleteSourceCommand,
    DisableSourceCommand,
    EnableSourceCommand,
    SubscribeSourceCommand,
    UpdateSourceCommand,
)
from src.modules.sources.domain.entities import Source, SourceSubscription, SourceType
from src.modules.sources.domain.events import SourceCreatedEvent
from src.modules.sources.domain.exceptions import (
    SourceAlreadyExistsError,
    SourceNotFoundError,
)
from src.modules.sources.domain.repository import (
    SourceRepository,
    SourceSubscriptionRepository,
)


class CreateSourceHandler:
    """Handle source creation."""

    def __init__(
        self,
        source_repository: SourceRepository,
        subscription_repository: SourceSubscriptionRepository,
    ):
        self.source_repository = source_repository
        self.subscription_repository = subscription_repository
        self.logger = logger

    async def handle(self, command: CreateSourceCommand) -> Source:
        """Create a new source."""
        # Check if name already exists
        if await self.source_repository.exists_by_name(command.name):
            raise SourceAlreadyExistsError(command.name)

        # Determine default fetch interval based on type
        fetch_interval = command.fetch_interval_sec
        if fetch_interval is None:
            if command.type == SourceType.NEWSNOW:
                fetch_interval = settings.NEWSNOW_FETCH_INTERVAL_SEC
            elif command.type == SourceType.RSS:
                fetch_interval = settings.RSS_FETCH_INTERVAL_SEC
            else:
                fetch_interval = settings.NEWSNOW_FETCH_INTERVAL_SEC

        source = Source(
            id=str(uuid4()),
            type=command.type,
            name=command.name,
            owner_id=command.user_id,
            is_private=command.is_private,
            config=command.config,
            fetch_interval_sec=fetch_interval,
        )
        source.add_domain_event(
            SourceCreatedEvent(
                source_id=source.id,
                name=source.name,
                type=source.type.value,
            )
        )

        created_source = await self.source_repository.create(source)
        self.logger.info(f"Created source: {source.name} ({source.type.value})")

        subscription = SourceSubscription(
            user_id=command.user_id,
            source_id=created_source.id,
            enabled=True,
        )
        await self.subscription_repository.create(subscription)

        return created_source


class UpdateSourceHandler:
    """Handle source update."""

    def __init__(self, source_repository: SourceRepository):
        self.source_repository = source_repository
        self.logger = logger

    async def handle(self, command: UpdateSourceCommand) -> Source:
        """Update an existing source."""
        source = await self.source_repository.get_by_id(command.source_id)
        if not source:
            raise SourceNotFoundError(source_id=command.source_id)
        if source.owner_id != command.user_id:
            raise AuthorizationError("No permission to update this source")

        # Check name uniqueness if changed
        if command.name and command.name != source.name:
            if await self.source_repository.exists_by_name(
                command.name, exclude_id=source.id
            ):
                raise SourceAlreadyExistsError(command.name)
            source.update_name(command.name)

        if command.config is not None:
            source.update_config(command.config)

        if command.fetch_interval_sec is not None:
            source.update_fetch_interval(command.fetch_interval_sec)

        await self.source_repository.update(source)
        self.logger.info(f"Updated source: {source.name}")

        return source


class EnableSourceHandler:
    """Handle source enable."""

    def __init__(self, subscription_repository: SourceSubscriptionRepository):
        self.subscription_repository = subscription_repository
        self.logger = logger

    async def handle(self, command: EnableSourceCommand) -> SourceSubscription:
        """Enable a source subscription."""
        subscription = await self.subscription_repository.get_by_user_and_source(
            user_id=command.user_id,
            source_id=command.source_id,
        )
        if not subscription:
            raise SourceNotFoundError(source_id=command.source_id)

        subscription.enable()
        await self.subscription_repository.update(subscription)
        self.logger.info(
            f"Enabled source subscription: {command.source_id} for {command.user_id}"
        )

        return subscription


class DisableSourceHandler:
    """Handle source disable."""

    def __init__(self, subscription_repository: SourceSubscriptionRepository):
        self.subscription_repository = subscription_repository
        self.logger = logger

    async def handle(self, command: DisableSourceCommand) -> SourceSubscription:
        """Disable a source subscription."""
        subscription = await self.subscription_repository.get_by_user_and_source(
            user_id=command.user_id,
            source_id=command.source_id,
        )
        if not subscription:
            raise SourceNotFoundError(source_id=command.source_id)

        subscription.disable()
        await self.subscription_repository.update(subscription)
        self.logger.info(
            f"Disabled source subscription: {command.source_id} for {command.user_id}"
        )

        return subscription


class DeleteSourceHandler:
    """Handle source deletion."""

    def __init__(
        self,
        source_repository: SourceRepository,
        subscription_repository: SourceSubscriptionRepository,
    ):
        self.source_repository = source_repository
        self.subscription_repository = subscription_repository
        self.logger = logger

    async def handle(self, command: DeleteSourceCommand) -> bool:
        """Unsubscribe from a source (public sources cannot be deleted)."""
        source = await self.source_repository.get_by_id(command.source_id)
        if not source:
            raise SourceNotFoundError(source_id=command.source_id)

        subscription = await self.subscription_repository.get_by_user_and_source(
            user_id=command.user_id,
            source_id=command.source_id,
        )
        if not subscription:
            raise SourceNotFoundError(source_id=command.source_id)

        if source.is_private and source.owner_id == command.user_id:
            await self.subscription_repository.delete(subscription)
            await self.source_repository.delete(source)
            self.logger.info(f"Deleted private source: {source.name}")
            return True

        success = await self.subscription_repository.delete(subscription)
        if success:
            self.logger.info(
                f"Unsubscribed source: {source.name} for {command.user_id}"
            )

        return success


class SubscribeSourceHandler:
    """Handle source subscription."""

    def __init__(
        self,
        source_repository: SourceRepository,
        subscription_repository: SourceSubscriptionRepository,
    ):
        self.source_repository = source_repository
        self.subscription_repository = subscription_repository
        self.logger = logger

    async def handle(self, command: SubscribeSourceCommand) -> SourceSubscription:
        """Subscribe to a public source."""
        source = await self.source_repository.get_by_id(command.source_id)
        if not source:
            raise SourceNotFoundError(source_id=command.source_id)
        if source.is_private and source.owner_id != command.user_id:
            raise AuthorizationError("Private source cannot be subscribed")

        existing = await self.subscription_repository.get_by_user_and_source(
            user_id=command.user_id,
            source_id=command.source_id,
            include_deleted=True,
        )
        if existing:
            existing.restore()
            existing.enable()
            updated = await self.subscription_repository.update(existing)
            self.logger.info(
                f"Re-subscribed source: {source.name} for {command.user_id}"
            )
            return updated

        subscription = SourceSubscription(
            user_id=command.user_id,
            source_id=command.source_id,
            enabled=True,
        )
        created = await self.subscription_repository.create(subscription)
        self.logger.info(f"Subscribed source: {source.name} for {command.user_id}")
        return created
