"""Source module dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.sources.application.handlers import (
    CreateSourceHandler,
    DeleteSourceHandler,
    DisableSourceHandler,
    EnableSourceHandler,
    SubscribeSourceHandler,
    UpdateSourceHandler,
)
from src.modules.sources.infrastructure.mappers import (
    SourceMapper,
    SourceSubscriptionMapper,
)
from src.modules.sources.infrastructure.repositories import (
    PostgreSQLSourceRepository,
    PostgreSQLSourceSubscriptionRepository,
)


def get_source_mapper() -> SourceMapper:
    return SourceMapper()


def get_source_subscription_mapper() -> SourceSubscriptionMapper:
    return SourceSubscriptionMapper()


async def get_source_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: SourceMapper = Depends(get_source_mapper),
) -> PostgreSQLSourceRepository:
    return PostgreSQLSourceRepository(session, mapper, get_event_bus())


async def get_source_subscription_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: SourceSubscriptionMapper = Depends(get_source_subscription_mapper),
) -> PostgreSQLSourceSubscriptionRepository:
    return PostgreSQLSourceSubscriptionRepository(session, mapper, get_event_bus())


async def get_create_source_handler(
    source_repository: PostgreSQLSourceRepository = Depends(get_source_repository),
    subscription_repository: PostgreSQLSourceSubscriptionRepository = Depends(
        get_source_subscription_repository
    ),
) -> CreateSourceHandler:
    return CreateSourceHandler(source_repository, subscription_repository)


async def get_update_source_handler(
    source_repository: PostgreSQLSourceRepository = Depends(get_source_repository),
) -> UpdateSourceHandler:
    return UpdateSourceHandler(source_repository)


async def get_enable_source_handler(
    subscription_repository: PostgreSQLSourceSubscriptionRepository = Depends(
        get_source_subscription_repository
    ),
) -> EnableSourceHandler:
    return EnableSourceHandler(subscription_repository)


async def get_disable_source_handler(
    subscription_repository: PostgreSQLSourceSubscriptionRepository = Depends(
        get_source_subscription_repository
    ),
) -> DisableSourceHandler:
    return DisableSourceHandler(subscription_repository)


async def get_delete_source_handler(
    source_repository: PostgreSQLSourceRepository = Depends(get_source_repository),
    subscription_repository: PostgreSQLSourceSubscriptionRepository = Depends(
        get_source_subscription_repository
    ),
) -> DeleteSourceHandler:
    return DeleteSourceHandler(source_repository, subscription_repository)


async def get_subscribe_source_handler(
    source_repository: PostgreSQLSourceRepository = Depends(get_source_repository),
    subscription_repository: PostgreSQLSourceSubscriptionRepository = Depends(
        get_source_subscription_repository
    ),
) -> SubscribeSourceHandler:
    return SubscribeSourceHandler(source_repository, subscription_repository)
