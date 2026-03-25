"""Discovery module application dependencies (stubs for DI override)."""

from typing import NoReturn

from fastapi import Depends

from src.modules.agent.application.discovery.agent import FetcherCreator
from src.modules.agent.application.discovery.session_service import (
    DiscoverySessionService,
)
from src.modules.agent.domain.repository import (
    DiscoveryCandidateRepository,
    DiscoverySessionRepository,
)
from src.modules.sources.domain.catalog import NewsNowCatalogProvider


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_discovery_session_repository() -> DiscoverySessionRepository:
    _missing_dependency("DiscoverySessionRepository")


async def get_discovery_candidate_repository() -> DiscoveryCandidateRepository:
    _missing_dependency("DiscoveryCandidateRepository")


async def get_catalog_provider() -> NewsNowCatalogProvider:
    _missing_dependency("NewsNowCatalogProvider")


def get_fetcher_creator() -> FetcherCreator:
    _missing_dependency("FetcherCreator")


async def get_discovery_session_service(
    session_repo: DiscoverySessionRepository = Depends(
        get_discovery_session_repository
    ),
    candidate_repo: DiscoveryCandidateRepository = Depends(
        get_discovery_candidate_repository
    ),
) -> DiscoverySessionService:
    return DiscoverySessionService(session_repo, candidate_repo)
