"""Discovery module infrastructure dependencies."""

from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.domain.events import get_event_bus
from src.core.infrastructure.database.session import get_db_session
from src.modules.agent.infrastructure.discovery.mappers import (
    DiscoveryCandidateMapper,
    DiscoverySessionMapper,
)
from src.modules.agent.infrastructure.discovery.repositories import (
    PostgreSQLDiscoveryCandidateRepository,
    PostgreSQLDiscoverySessionRepository,
)
from src.modules.sources.domain.catalog import NewsNowCatalogProvider
from src.modules.sources.infrastructure.newsnow_catalog_provider import (
    InfrastructureNewsNowCatalogProvider,
)

if TYPE_CHECKING:
    from src.modules.agent.application.discovery.agent import FetcherCreator


def get_discovery_session_mapper() -> DiscoverySessionMapper:
    return DiscoverySessionMapper()


def get_discovery_candidate_mapper() -> DiscoveryCandidateMapper:
    return DiscoveryCandidateMapper()


async def get_discovery_session_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: DiscoverySessionMapper = Depends(get_discovery_session_mapper),
) -> PostgreSQLDiscoverySessionRepository:
    return PostgreSQLDiscoverySessionRepository(session, mapper, get_event_bus())


async def get_discovery_candidate_repository(
    session: AsyncSession = Depends(get_db_session),
    mapper: DiscoveryCandidateMapper = Depends(get_discovery_candidate_mapper),
) -> PostgreSQLDiscoveryCandidateRepository:
    return PostgreSQLDiscoveryCandidateRepository(session, mapper, get_event_bus())


def get_catalog_provider() -> NewsNowCatalogProvider:
    return InfrastructureNewsNowCatalogProvider()


def get_fetcher_creator() -> "FetcherCreator":
    from src.modules.sources.infrastructure.fetchers.factory import FetcherFactory

    return FetcherFactory.create
