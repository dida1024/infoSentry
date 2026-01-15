"""User application data models."""

from datetime import datetime

from pydantic import BaseModel


class UserData(BaseModel):
    """User data for queries."""

    id: str
    email: str
    is_active: bool
    status: str
    display_name: str | None = None
    timezone: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
