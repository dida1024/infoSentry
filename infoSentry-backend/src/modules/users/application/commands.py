"""User application commands."""

from pydantic import BaseModel, EmailStr


class RequestMagicLinkCommand(BaseModel):
    """Request magic link for login."""

    email: EmailStr


class ConsumeMagicLinkCommand(BaseModel):
    """Consume magic link to complete login."""

    token: str
    ip_address: str | None = None
    user_agent: str | None = None


class UpdateProfileCommand(BaseModel):
    """Update user profile."""

    user_id: str
    display_name: str | None = None
    timezone: str | None = None


class RefreshSessionCommand(BaseModel):
    """Refresh device session using refresh token."""

    refresh_token: str
    ip_address: str | None = None
    user_agent: str | None = None


class RevokeSessionCommand(BaseModel):
    """Revoke device session using refresh token."""

    refresh_token: str
