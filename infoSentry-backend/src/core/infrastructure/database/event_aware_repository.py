"""Event-aware repository base class."""

from typing import Protocol

from src.core.domain.events import DomainEvent, EventBus


class EventSourcedEntity(Protocol):
    def get_domain_events(self) -> list[DomainEvent]: ...
    def clear_domain_events(self) -> None: ...


class EventAwareRepository[T: EventSourcedEntity]:
    """Repository base class that publishes domain events after persistence operations."""

    def __init__(self, event_publisher: EventBus) -> None:
        self._event_publisher = event_publisher

    async def _publish_events_from_entity(self, entity: T) -> None:
        """Publish all domain events from an entity."""
        events = entity.get_domain_events()
        if events:
            await self._event_publisher.publish_all(events)
            entity.clear_domain_events()
