"""API Keys module infrastructure dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.api_keys.infrastructure.mappers import ApiKeyMapper
from src.modules.api_keys.infrastructure.repositories import PostgreSQLApiKeyRepository


def get_api_key_mapper() -> ApiKeyMapper:
    return ApiKeyMapper()


async def get_api_key_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: ApiKeyMapper = Depends(get_api_key_mapper),
) -> PostgreSQLApiKeyRepository:
    return PostgreSQLApiKeyRepository(session, mapper, get_event_bus())
