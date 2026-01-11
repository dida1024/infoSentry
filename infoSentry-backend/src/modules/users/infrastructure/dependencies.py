"""User module dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.users.application.budget_service import UserBudgetUsageService
from src.modules.users.application.handlers import (
    ConsumeMagicLinkHandler,
    RequestMagicLinkHandler,
    UpdateProfileHandler,
)
from src.modules.users.infrastructure.mappers import (
    MagicLinkMapper,
    UserBudgetDailyMapper,
    UserMapper,
)
from src.modules.users.infrastructure.repositories import (
    PostgreSQLMagicLinkRepository,
    PostgreSQLUserBudgetDailyRepository,
    PostgreSQLUserRepository,
)


def get_user_mapper() -> UserMapper:
    return UserMapper()


def get_magic_link_mapper() -> MagicLinkMapper:
    return MagicLinkMapper()


def get_user_budget_daily_mapper() -> UserBudgetDailyMapper:
    return UserBudgetDailyMapper()


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: UserMapper = Depends(get_user_mapper),
) -> PostgreSQLUserRepository:
    return PostgreSQLUserRepository(session, mapper, get_event_bus())


async def get_magic_link_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: MagicLinkMapper = Depends(get_magic_link_mapper),
) -> PostgreSQLMagicLinkRepository:
    return PostgreSQLMagicLinkRepository(session, mapper, get_event_bus())


async def get_user_budget_daily_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: UserBudgetDailyMapper = Depends(get_user_budget_daily_mapper),
) -> PostgreSQLUserBudgetDailyRepository:
    return PostgreSQLUserBudgetDailyRepository(session, mapper, get_event_bus())


async def get_request_magic_link_handler(
    user_repository: PostgreSQLUserRepository = Depends(get_user_repository),
    magic_link_repository: PostgreSQLMagicLinkRepository = Depends(
        get_magic_link_repository
    ),
) -> RequestMagicLinkHandler:
    return RequestMagicLinkHandler(user_repository, magic_link_repository)


async def get_consume_magic_link_handler(
    user_repository: PostgreSQLUserRepository = Depends(get_user_repository),
    magic_link_repository: PostgreSQLMagicLinkRepository = Depends(
        get_magic_link_repository
    ),
) -> ConsumeMagicLinkHandler:
    return ConsumeMagicLinkHandler(user_repository, magic_link_repository)


async def get_update_profile_handler(
    user_repository: PostgreSQLUserRepository = Depends(get_user_repository),
) -> UpdateProfileHandler:
    return UpdateProfileHandler(user_repository)


async def get_user_budget_usage_service(
    budget_repository: PostgreSQLUserBudgetDailyRepository = Depends(
        get_user_budget_daily_repository
    ),
) -> UserBudgetUsageService:
    return UserBudgetUsageService(budget_repository)
