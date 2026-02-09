"""Shared authorization scopes."""

from enum import StrEnum


class AuthScope(StrEnum):
    """Canonical scope names used by JWT/API Key authorization."""

    GOALS_READ = "goals:read"
    GOALS_WRITE = "goals:write"
    SOURCES_READ = "sources:read"
    SOURCES_WRITE = "sources:write"
    NOTIFICATIONS_READ = "notifications:read"
    NOTIFICATIONS_WRITE = "notifications:write"
    AGENT_READ = "agent:read"
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
