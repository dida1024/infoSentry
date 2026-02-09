"""API Keys module application dependencies.

Provides service and repository without importing infrastructure.
"""

from typing import NoReturn

from fastapi import Depends

from src.modules.api_keys.application.service import ApiKeyService
from src.modules.api_keys.domain.repository import ApiKeyRepository


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_api_key_repository() -> ApiKeyRepository:
    _missing_dependency("ApiKeyRepository")


async def get_api_key_service(
    repository: ApiKeyRepository = Depends(get_api_key_repository),
) -> ApiKeyService:
    return ApiKeyService(repository=repository)
