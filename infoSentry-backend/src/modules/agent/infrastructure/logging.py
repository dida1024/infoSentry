"""Structlog-based implementation of LoggingPort."""

import structlog

from src.modules.agent.application.logging_port import LoggingPort, ScoreTrace


class StructlogLoggingPort(LoggingPort):
    """Logging adapter using structlog."""

    def __init__(self) -> None:
        self._logger = structlog.get_logger("business")

    def info(self, event: str, **fields: object) -> None:
        self._logger.bind(event=event).info(event, **fields)

    def log_score_trace(self, trace: ScoreTrace) -> None:
        self._logger.bind(event="push_score_trace").info(
            "push_score_trace", **trace.model_dump()
        )
