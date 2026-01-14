"""Core application dependencies.

These functions define application-level dependency boundaries and are overridden
by infrastructure in `main.py`.
"""

from __future__ import annotations

from typing import NoReturn

from src.core.domain.ports.prompt_store import PromptStore


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


async def get_prompt_store() -> PromptStore:
    _missing_dependency("PromptStore")

