"""Prompt storage and rendering port.

This port allows application services to load prompts (system/user messages)
from an external store (e.g. filesystem) without depending on infrastructure.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

PromptRole = Literal["system", "user", "assistant", "developer", "tool"]


class PromptStoreError(Exception):
    """Base error for prompt store."""


class PromptNotFoundError(PromptStoreError):
    """Raised when a prompt cannot be found by name/version/language."""


class PromptParseError(PromptStoreError):
    """Raised when a prompt file cannot be parsed."""


class PromptRenderError(PromptStoreError):
    """Raised when a prompt cannot be rendered with given variables."""


PromptVarType = Literal["string", "int", "float", "bool", "json"]


@dataclass(frozen=True)
class PromptVarSpec:
    """Prompt variable specification."""

    type: PromptVarType
    required: bool
    default: object | None = None


@dataclass(frozen=True)
class PromptMessage:
    """A rendered prompt message."""

    role: PromptRole
    content: str


@dataclass(frozen=True)
class PromptMessageTemplate:
    """A message template containing placeholders (e.g. {{ var }})."""

    role: PromptRole
    content_template: str


@dataclass(frozen=True)
class PromptDefinition:
    """Prompt definition loaded from store."""

    name: str
    version: str
    language: str
    tags: tuple[str, ...]
    vars: Mapping[str, PromptVarSpec]
    messages: tuple[PromptMessageTemplate, ...]
    output_response_format: str | None = None


class PromptStore(Protocol):
    """Prompt store interface."""

    def get(
        self,
        *,
        name: str,
        version: str | None = None,
        language: str | None = None,
    ) -> PromptDefinition: ...

    def render_messages(
        self,
        *,
        name: str,
        variables: Mapping[str, object],
        version: str | None = None,
        language: str | None = None,
    ) -> list[PromptMessage]: ...
