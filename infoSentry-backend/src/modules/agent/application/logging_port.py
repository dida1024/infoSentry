"""Logging port interfaces for agent runtime."""

from typing import Protocol

from pydantic import BaseModel


class ScoreTrace(BaseModel):
    """Structured score trace for push decisions."""

    goal_id: str
    item_id: str
    trigger: str
    bucket: str | None
    match_score: float
    adjusted_score: float
    thresholds: dict[str, object]
    llm_boundary: dict[str, object] | None
    push_worthiness: dict[str, object] | None
    boundary_fallback_reason: str | None
    push_worthiness_fallback_reason: str | None
    user_id: str | None = None


class LoggingPort(Protocol):
    """Port for structured business logging."""

    def info(self, event: str, **fields: object) -> None:
        """Log a generic business event."""
        ...

    def log_score_trace(self, trace: ScoreTrace) -> None:
        """Log a score trace event."""
        ...
