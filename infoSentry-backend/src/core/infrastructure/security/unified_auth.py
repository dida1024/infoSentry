"""Unified authentication dependency: JWT + API Key dual-mode.

Provides a single ``get_current_auth`` dependency that transparently handles
both JWT Bearer tokens and ``X-API-Key`` header authentication.

"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from src.core.application.security import AuthContext
from src.core.domain.auth_scope import AuthScope
from src.core.infrastructure.security.jwt import decode_token
from src.modules.api_keys.application.dependencies import get_api_key_service
from src.modules.api_keys.application.service import ApiKeyInvalidError, ApiKeyService


async def get_current_auth(
    request: Request,
    api_key_service: ApiKeyService = Depends(get_api_key_service),
) -> AuthContext:
    """Unified auth dependency: try API Key header first, then JWT Bearer.

    Priority order:
      1. ``X-API-Key`` header  → API Key authentication
      2. ``Authorization: Bearer <token>`` → JWT authentication

    Returns:
        AuthContext with ``user_id``, auth method, and granted scopes.

    Raises:
        HTTPException 401 when no valid credentials are provided.
    """
    auth_header = request.headers.get("Authorization")

    # ── 1. Try X-API-Key header ──────────────────────────────────────────
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        try:
            return await _authenticate_api_key(api_key_header, api_key_service)
        except HTTPException as api_key_error:
            # Only auth failures (401) may fall back to JWT.
            if (
                api_key_error.status_code == status.HTTP_401_UNAUTHORIZED
                and auth_header
                and auth_header.lower().startswith("bearer ")
            ):
                token = auth_header[7:]
                return _authenticate_jwt(token)
            raise api_key_error

    # ── 2. Fall back to JWT Bearer ───────────────────────────────────────
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:]  # Strip "Bearer " prefix
        return _authenticate_jwt(token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Authentication required. "
            "Provide either X-API-Key header or Authorization: Bearer token."
        ),
        headers={"WWW-Authenticate": "Bearer"},
    )


# ── Private helpers ──────────────────────────────────────────────────────────


async def _authenticate_api_key(
    raw_key: str,
    service: ApiKeyService,
) -> AuthContext:
    """Validate *raw_key* via :class:`ApiKeyService`."""
    try:
        api_key = await service.validate_key(raw_key)
    except ApiKeyInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    return AuthContext(
        user_id=api_key.user_id,
        auth_method="api_key",
        scopes=frozenset(api_key.scopes),
        api_key_id=api_key.id,
    )


def _authenticate_jwt(token: str) -> AuthContext:
    """Decode a JWT token and return an ``AuthContext``.

    JWT users are the account owner, so they get **all** scopes.
    """
    payload = decode_token(token)  # raises HTTPException on failure
    user_id = payload.get_subject()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return AuthContext(
        user_id=user_id,
        auth_method="jwt",
        scopes=frozenset(scope.value for scope in AuthScope),
    )


# ── Public dependency helpers ────────────────────────────────────────────────


def get_current_user_id_from_auth(
    auth: AuthContext = Depends(get_current_auth),
) -> str:
    """Extract ``user_id`` from :class:`AuthContext`.

    Drop-in replacement for the old ``get_current_user_id`` dependency.
    """
    return auth.user_id


async def get_current_user_id_from_jwt_only(request: Request) -> str:
    """JWT-only dependency used by API Key management endpoints."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT Bearer token required for this endpoint",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header[7:]
    auth = _authenticate_jwt(token)
    return auth.user_id
