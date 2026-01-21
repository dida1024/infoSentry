"""Magic link email queue adapter."""

from src.modules.users.domain.ports import MagicLinkEmailQueue
from src.modules.users.tasks import send_magic_link_email


class CeleryMagicLinkEmailQueue(MagicLinkEmailQueue):
    """Celery-backed magic link email queue."""

    async def enqueue(self, magic_link_id: str, email: str) -> None:
        send_magic_link_email.delay(magic_link_id=magic_link_id, email=email)
