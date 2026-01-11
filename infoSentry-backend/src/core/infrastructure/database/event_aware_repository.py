"""Event-aware repository base class."""

from typing import TypeVar

from src.core.domain.base_entity import BaseEntity
from src.core.domain.events import EventBus

T = TypeVar("T", bound=BaseEntity)


class EventAwareRepository[T]:
    """Repository base class that publishes domain events after persistence operations."""

    def __init__(self, event_publisher: EventBus):
        self._event_publisher = event_publisher

    async def _publish_events_from_entity(self, entity: T) -> None:
        """Publish all domain events from an entity."""
        events = entity.get_domain_events()
        if events:
            await self._event_publisher.publish_all(events)
            entity.clear_domain_events()
