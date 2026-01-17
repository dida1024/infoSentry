"""Prompting dependencies (infrastructure)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.core.config import settings
from src.core.infrastructure.ai.prompting.file_store import FileSystemPromptStore


@lru_cache(maxsize=1)
def get_prompt_store() -> FileSystemPromptStore:
    return FileSystemPromptStore(
        base_dir=Path(settings.PROMPTS_DIR).resolve(),
        default_language=settings.PROMPTS_DEFAULT_LANGUAGE,
    )
