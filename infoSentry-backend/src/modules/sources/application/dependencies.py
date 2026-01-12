"""Source module application dependencies."""

from typing import NoReturn

from fastapi import Depends

from src.modules.sources.application.handlers import (
    CreateSourceHandler,
    DeleteSourceHandler,
    DisableSourceHandler,
    EnableSourceHandler,
    UpdateSourceHandler,
)
from src.modules.sources.domain.repository import SourceRepository


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_source_repository() -> SourceRepository:
    _missing_dependency("SourceRepository")


async def get_create_source_handler(
    source_repository: SourceRepository = Depends(get_source_repository),
) -> CreateSourceHandler:
    return CreateSourceHandler(source_repository)


async def get_update_source_handler(
    source_repository: SourceRepository = Depends(get_source_repository),
) -> UpdateSourceHandler:
    return UpdateSourceHandler(source_repository)


async def get_enable_source_handler(
    source_repository: SourceRepository = Depends(get_source_repository),
) -> EnableSourceHandler:
    return EnableSourceHandler(source_repository)


async def get_disable_source_handler(
    source_repository: SourceRepository = Depends(get_source_repository),
) -> DisableSourceHandler:
    return DisableSourceHandler(source_repository)


async def get_delete_source_handler(
    source_repository: SourceRepository = Depends(get_source_repository),
) -> DeleteSourceHandler:
    return DeleteSourceHandler(source_repository)
