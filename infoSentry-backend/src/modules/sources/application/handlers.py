"""Source command handlers."""

from uuid import uuid4

from loguru import logger

from src.core.config import settings
from src.modules.sources.application.commands import (
    CreateSourceCommand,
    DeleteSourceCommand,
    DisableSourceCommand,
    EnableSourceCommand,
    UpdateSourceCommand,
)
from src.modules.sources.domain.entities import Source, SourceType
from src.modules.sources.domain.events import SourceCreatedEvent
from src.modules.sources.domain.exceptions import (
    SourceAlreadyExistsError,
    SourceNotFoundError,
)
from src.modules.sources.domain.repository import SourceRepository


class CreateSourceHandler:
    """Handle source creation."""

    def __init__(self, source_repository: SourceRepository):
        self.source_repository = source_repository
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

        await self.source_repository.create(source)
        self.logger.info(f"Created source: {source.name} ({source.type.value})")

        return source


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

    def __init__(self, source_repository: SourceRepository):
        self.source_repository = source_repository
        self.logger = logger

    async def handle(self, command: EnableSourceCommand) -> Source:
        """Enable a source."""
        source = await self.source_repository.get_by_id(command.source_id)
        if not source:
            raise SourceNotFoundError(source_id=command.source_id)

        source.enable()
        await self.source_repository.update(source)
        self.logger.info(f"Enabled source: {source.name}")

        return source


class DisableSourceHandler:
    """Handle source disable."""

    def __init__(self, source_repository: SourceRepository):
        self.source_repository = source_repository
        self.logger = logger

    async def handle(self, command: DisableSourceCommand) -> Source:
        """Disable a source."""
        source = await self.source_repository.get_by_id(command.source_id)
        if not source:
            raise SourceNotFoundError(source_id=command.source_id)

        source.disable()
        await self.source_repository.update(source)
        self.logger.info(f"Disabled source: {source.name}")

        return source


class DeleteSourceHandler:
    """Handle source deletion."""

    def __init__(self, source_repository: SourceRepository):
        self.source_repository = source_repository
        self.logger = logger

    async def handle(self, command: DeleteSourceCommand) -> bool:
        """Delete a source (soft delete)."""
        source = await self.source_repository.get_by_id(command.source_id)
        if not source:
            raise SourceNotFoundError(source_id=command.source_id)

        success = await self.source_repository.delete(source)
        if success:
            self.logger.info(f"Deleted source: {source.name}")

        return success
