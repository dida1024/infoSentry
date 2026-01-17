"""User module application dependencies.

Defines dependency providers for interfaces layer without importing infrastructure.
"""

from typing import NoReturn

from fastapi import Depends

from src.core.domain.ports.token import TokenService
from src.modules.users.application.budget_service import UserBudgetUsageService
from src.modules.users.application.handlers import (
    ConsumeMagicLinkHandler,
    RequestMagicLinkHandler,
    UpdateProfileHandler,
)
from src.modules.users.application.query_service import UserQueryService
from src.modules.users.domain.repository import (
    MagicLinkRepository,
    UserBudgetDailyRepository,
    UserRepository,
)


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_user_repository() -> UserRepository:
    _missing_dependency("UserRepository")


async def get_magic_link_repository() -> MagicLinkRepository:
    _missing_dependency("MagicLinkRepository")


async def get_user_budget_daily_repository() -> UserBudgetDailyRepository:
    _missing_dependency("UserBudgetDailyRepository")


async def get_token_service() -> TokenService:
    _missing_dependency("TokenService")


async def get_request_magic_link_handler(
    user_repository: UserRepository = Depends(get_user_repository),
    magic_link_repository: MagicLinkRepository = Depends(get_magic_link_repository),
    token_service: TokenService = Depends(get_token_service),
) -> RequestMagicLinkHandler:
    return RequestMagicLinkHandler(
        user_repository, magic_link_repository, token_service
    )


async def get_consume_magic_link_handler(
    user_repository: UserRepository = Depends(get_user_repository),
    magic_link_repository: MagicLinkRepository = Depends(get_magic_link_repository),
    token_service: TokenService = Depends(get_token_service),
) -> ConsumeMagicLinkHandler:
    return ConsumeMagicLinkHandler(
        user_repository, magic_link_repository, token_service
    )


async def get_update_profile_handler(
    user_repository: UserRepository = Depends(get_user_repository),
) -> UpdateProfileHandler:
    return UpdateProfileHandler(user_repository)


async def get_user_budget_usage_service(
    budget_repository: UserBudgetDailyRepository = Depends(
        get_user_budget_daily_repository
    ),
) -> UserBudgetUsageService:
    return UserBudgetUsageService(budget_repository)


async def get_user_query_service(
    user_repository: UserRepository = Depends(get_user_repository),
) -> UserQueryService:
    return UserQueryService(user_repository)
