"""User module ports."""

from typing import Protocol


class MagicLinkEmailQueue(Protocol):
    """Port for enqueuing magic link emails."""

    async def enqueue(self, magic_link_id: str, email: str) -> None:
        """Enqueue a magic link email for delivery."""
        ...
