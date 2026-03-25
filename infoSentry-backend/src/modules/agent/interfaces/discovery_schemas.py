"""Discovery API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Create a new discovery session."""

    query: str = Field(
        ..., min_length=1, max_length=500, description="User's natural language query"
    )


class SendMessageRequest(BaseModel):
    """Send a message in an existing session."""

    content: str = Field(
        ..., min_length=1, max_length=2000, description="User message content"
    )


class SessionMessageResponse(BaseModel):
    """A message in a discovery conversation."""

    role: str
    content: str
    timestamp: datetime
    metadata: dict[str, Any] | None = None


class CandidateResponse(BaseModel):
    """A discovered candidate source."""

    id: str
    source_type: str
    name: str
    url: str
    status: str
    discovered_via: str
    validation_result: dict[str, Any] | None = None
    source_id: str | None = None


class SessionResponse(BaseModel):
    """Discovery session response."""

    id: str
    status: str
    initial_query: str
    messages: list[SessionMessageResponse] = []
    candidates: list[CandidateResponse] = []
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None


class SessionListItemResponse(BaseModel):
    """Lightweight session item for list view."""

    id: str
    status: str
    initial_query: str
    created_at: datetime
    updated_at: datetime
