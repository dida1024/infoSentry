"""User application commands."""

from pydantic import BaseModel, EmailStr


class RequestMagicLinkCommand(BaseModel):
    """Request magic link for login."""

    email: EmailStr


class ConsumeMagicLinkCommand(BaseModel):
    """Consume magic link to complete login."""

    token: str


class UpdateProfileCommand(BaseModel):
    """Update user profile."""

    user_id: str
    display_name: str | None = None
    timezone: str | None = None
