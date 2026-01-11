"""Aggregate root base class with enhanced domain event support."""

from typing import TYPE_CHECKING

from src.core.domain.base_entity import BaseEntity

if TYPE_CHECKING:
    from src.core.domain.events import DomainEvent


class AggregateRoot(BaseEntity):
    """Base class for aggregate roots with enhanced domain event capabilities."""

    def __init__(self, **data):
        super().__init__(**data)

    def add_domain_event(self, event: "DomainEvent") -> None:
        """Add a domain event to be published."""
        self._add_domain_event(event)

    def has_domain_events(self) -> bool:
        """Check if there are any unpublished domain events."""
        return len(self._domain_events) > 0

    def get_domain_events_count(self) -> int:
        """Get the count of unpublished domain events."""
        return len(self._domain_events)

    def mark_events_as_committed(self) -> None:
        """Mark all domain events as committed (clear them)."""
        self.clear_domain_events()
