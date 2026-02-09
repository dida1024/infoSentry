"""Application-level security dependencies.

Defines auth dependencies without importing infrastructure.
The actual implementations are injected via FastAPI dependency_overrides in main.py.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, NoReturn

from fastapi import Depends, HTTPException, status

from src.core.domain.auth_scope import AuthScope


def _missing_dependency(name: str) -> NoReturn:
    raise RuntimeError(f"Missing dependency override for {name}")


@dataclass(frozen=True)
class AuthContext:
    """Authentication context for the current request."""

    user_id: str
    auth_method: str  # "jwt" | "api_key"
    scopes: frozenset[str]
    api_key_id: str | None = None

    def has_scope(self, scope: AuthScope | str) -> bool:
        return str(scope) in self.scopes


async def get_current_auth() -> AuthContext:
    """Get the current auth context (JWT or API Key)."""
    _missing_dependency("get_current_auth")


async def get_current_user_id() -> str:
    """Get the current authenticated user ID.

    This stub is overridden in main.py to use the unified auth system
    (which supports both JWT Bearer and API Key authentication).
    """
    _missing_dependency("get_current_user_id")


async def get_current_jwt_user_id() -> str:
    """Get the current user ID with JWT-only auth."""
    _missing_dependency("get_current_jwt_user_id")


def require_scope(scope: AuthScope) -> Callable[..., Coroutine[Any, Any, AuthContext]]:
    """FastAPI dependency factory requiring a specific auth scope."""

    async def _check_scope(
        auth: AuthContext = Depends(get_current_auth),
    ) -> AuthContext:
        if not auth.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope.value}",
            )
        return auth

    _check_scope.__name__ = f"require_scope_{scope.value.replace(':', '_')}"
    _check_scope.__qualname__ = _check_scope.__name__
    return _check_scope
