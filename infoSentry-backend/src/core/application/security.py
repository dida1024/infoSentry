"""Application-level security dependencies.

Defines auth dependencies without importing infrastructure.
"""

from typing import NoReturn


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_current_user_id() -> str:
    _missing_dependency("get_current_user_id")
