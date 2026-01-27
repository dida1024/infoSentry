"""Domain events infrastructure."""

import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol, TypeVar, cast
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field


class DomainEvent(BaseModel, ABC):
    """Base class for all domain events."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_version: int = Field(default=1)

    model_config = ConfigDict(frozen=True)

    @property
    def event_type(self) -> str:
        """Return the event type name."""
        return self.__class__.__name__


class DomainEventHandler(ABC):
    """Base class for domain event handlers."""

    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle the domain event."""
        pass


class EventBusProtocol(Protocol):
    """Protocol for event bus implementations."""

    def subscribe(
        self, event_type: type[DomainEvent], handler: DomainEventHandler
    ) -> None: ...

    def unsubscribe(
        self, event_type: type[DomainEvent], handler: DomainEventHandler
    ) -> None: ...

    async def publish(self, event: DomainEvent) -> None: ...

    async def publish_all(self, events: list[DomainEvent]) -> None: ...

    def clear_handlers(self) -> None: ...


HandlerFunc = Callable[[DomainEvent], Awaitable[None] | None]
THandlerFunc = TypeVar("THandlerFunc", bound=HandlerFunc)


class EventBus:
    """Event bus for publishing and subscribing to domain events."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[DomainEventHandler]] = {}

    def subscribe(
        self, event_type: type[DomainEvent], handler: DomainEventHandler
    ) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(
            f"Subscribed handler {handler.__class__.__name__} to {event_type.__name__}"
        )

    def unsubscribe(
        self, event_type: type[DomainEvent], handler: DomainEventHandler
    ) -> None:
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def publish(self, event: DomainEvent) -> None:
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        logger.debug(f"Publishing event {event.event_type} to {len(handlers)} handlers")

        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                logger.error(
                    f"Error handling event {event.event_type} "
                    f"by {handler.__class__.__name__}: {e}"
                )

    async def publish_all(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)

    def clear_handlers(self) -> None:
        self._handlers.clear()

    def get_handlers_count(self, event_type: type[DomainEvent] | None = None) -> int:
        if event_type is not None:
            return len(self._handlers.get(event_type, []))
        return sum(len(handlers) for handlers in self._handlers.values())

    def has_handlers(self, event_type: type[DomainEvent]) -> bool:
        return bool(self._handlers.get(event_type))


# SimpleEventBus 是 EventBus 的别名，用于明确表示这是一个简单的同进程事件总线
# 未来可能会有分布式事件总线实现
SimpleEventBus = EventBus

_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_global_event_bus() -> None:
    """Reset the global event bus instance."""
    global _event_bus
    if _event_bus is not None:
        _event_bus.clear_handlers()
    _event_bus = EventBus()


def subscribe_to_event(
    event_type: type[DomainEvent],
) -> Callable[[THandlerFunc], THandlerFunc]:
    """Decorator to subscribe a function as an event handler."""

    def decorator(handler_func: THandlerFunc) -> THandlerFunc:
        class FunctionHandler(DomainEventHandler):
            async def handle(self, event: DomainEvent) -> None:
                result = handler_func(event)
                if inspect.isawaitable(result):
                    await cast(Awaitable[None], result)

        get_event_bus().subscribe(event_type, FunctionHandler())
        return handler_func

    return decorator
