"""Queue names shared across layers."""

from enum import StrEnum


class Queues(StrEnum):
    """Celery queue names."""

    INGEST = "q_ingest"
    EMBED = "q_embed"
    MATCH = "q_match"
    AGENT = "q_agent"
    EMAIL = "q_email"

    @classmethod
    def all_queues(cls) -> list[str]:
        return [q.value for q in cls]
