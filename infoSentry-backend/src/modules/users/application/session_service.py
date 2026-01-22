"""Device session helpers for refresh-token based auth."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.core.config import settings
from src.modules.users.domain.entities import DeviceSession


@dataclass(frozen=True)
class RefreshTokenPayload:
    """Refresh token payload returned to interfaces."""

    token: str
    expires_at: datetime


def generate_refresh_token() -> str:
    """Generate a refresh token string."""
    return secrets.token_urlsafe(settings.REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token using HMAC-SHA256."""
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, token.encode("utf-8"), hashlib.sha256).hexdigest()


def refresh_expires_at(now: datetime | None = None) -> datetime:
    """Compute refresh token expiry."""
    current = now or datetime.now(UTC)
    return current + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def is_refresh_risky(
    session: DeviceSession,
    ip_address: str | None,
    user_agent: str | None,
) -> bool:
    """Check whether a refresh request is risky."""
    if settings.REFRESH_STRICT_IP:
        if ip_address is None or session.ip_address is None:
            return True
        if ip_address != session.ip_address:
            return True

    if settings.REFRESH_STRICT_UA:
        if user_agent is None or session.user_agent is None:
            return True
        if user_agent != session.user_agent:
            return True

    return False
