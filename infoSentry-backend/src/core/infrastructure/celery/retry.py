"""Celery task retry helpers."""

from __future__ import annotations

from kombu.exceptions import OperationalError as KombuOperationalError
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from src.core.infrastructure.redis.client import RedisUnavailableError


class RetryableTaskError(RuntimeError):
    """Explicitly retryable task error."""


DEFAULT_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RetryableTaskError,
    RedisUnavailableError,
    RedisError,
    KombuOperationalError,
    SQLAlchemyError,
    TimeoutError,
)
