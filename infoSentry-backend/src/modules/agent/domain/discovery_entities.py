"""Discovery session domain entities."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from src.core.domain.base_entity import BaseEntity


class SessionStatus(str, Enum):
    """Discovery session status."""

    ACTIVE = "active"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class MessageRole(str, Enum):
    """Message role in discovery conversation."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class CandidateStatus(str, Enum):
    """Candidate source status."""

    DISCOVERED = "discovered"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SessionMessage(BaseEntity):
    """A message in a discovery conversation.

    Note: uses BaseEntity for id/timestamps but is a value object
    within DiscoverySession's messages_json. Not stored as a separate table.
    """

    model_config = BaseEntity.model_config.copy()
    model_config["extra"] = "allow"

    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    metadata: dict[str, Any] | None = Field(
        default=None, description="Extra metadata (tool_calls, confirm_request, etc.)"
    )


class DiscoverySession(BaseEntity):
    """Discovery session - a conversational session for finding information sources."""

    user_id: str = Field(..., description="Owner user ID")
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE, description="Session status"
    )
    initial_query: str = Field(..., description="User's initial description")
    messages: list[SessionMessage] = Field(
        default_factory=list, description="Full conversation history"
    )
    expires_at: datetime | None = Field(
        default=None, description="Session expiry time"
    )

    def transition_to(self, new_status: SessionStatus) -> None:
        """Transition session to a new status with validation."""
        valid_transitions: dict[SessionStatus, set[SessionStatus]] = {
            SessionStatus.ACTIVE: {
                SessionStatus.WAITING_USER,
                SessionStatus.COMPLETED,
                SessionStatus.FAILED,
                SessionStatus.EXPIRED,
            },
            SessionStatus.WAITING_USER: {
                SessionStatus.ACTIVE,
                SessionStatus.EXPIRED,
            },
        }
        allowed = valid_transitions.get(self.status, set())
        if new_status not in allowed:
            msg = f"Invalid transition: {self.status.value} -> {new_status.value}"
            raise ValueError(msg)
        self.status = new_status
        self._update_timestamp()

    def add_message(self, role: MessageRole, content: str, **metadata: Any) -> None:
        """Append a message to conversation history."""
        msg = SessionMessage(
            role=role,
            content=content,
            metadata=metadata if metadata else None,
        )
        self.messages.append(msg)
        self._update_timestamp()

    def is_expired(self, now: datetime) -> bool:
        """Check if session has expired."""
        return self.expires_at is not None and now >= self.expires_at


class CandidateSource(BaseEntity):
    """A candidate information source discovered during a session."""

    session_id: str = Field(..., description="Parent discovery session ID")
    source_type: str = Field(..., description="Source type: NEWSNOW / RSS / SITE")
    name: str = Field(..., description="Human-readable source name")
    url: str = Field(..., description="Primary URL")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Full source config"
    )
    status: CandidateStatus = Field(
        default=CandidateStatus.DISCOVERED, description="Candidate status"
    )
    validation_result: dict[str, Any] | None = Field(
        default=None, description="Validation result snapshot"
    )
    discovered_via: str = Field(
        ..., description="Discovery channel: catalog/rss_probe/rsshub/site_analysis"
    )
    source_id: str | None = Field(
        default=None, description="Created Source ID after acceptance"
    )

    def mark_valid(self, validation_result: dict[str, Any]) -> None:
        """Mark candidate as validated successfully."""
        self.status = CandidateStatus.VALID
        self.validation_result = validation_result
        self._update_timestamp()

    def mark_invalid(self, validation_result: dict[str, Any]) -> None:
        """Mark candidate as validation failed."""
        self.status = CandidateStatus.INVALID
        self.validation_result = validation_result
        self._update_timestamp()

    def accept(self, source_id: str) -> None:
        """Mark candidate as accepted by user."""
        self.status = CandidateStatus.ACCEPTED
        self.source_id = source_id
        self._update_timestamp()

    def reject(self) -> None:
        """Mark candidate as rejected by user."""
        self.status = CandidateStatus.REJECTED
        self._update_timestamp()
