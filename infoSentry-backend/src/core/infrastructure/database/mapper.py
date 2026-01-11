"""Base mapper for entity-model conversion."""

from abc import ABC, abstractmethod
from typing import TypeVar

E = TypeVar("E")  # Entity type
M = TypeVar("M")  # Model type


class BaseMapper[E, M](ABC):
    """Base mapper for converting between domain entities and database models."""

    @abstractmethod
    def to_domain(self, model: M) -> E:
        """Convert database model to domain entity."""
        pass

    @abstractmethod
    def to_model(self, entity: E) -> M:
        """Convert domain entity to database model."""
        pass

    def to_domain_list(self, models: list[M]) -> list[E]:
        """Convert list of models to list of entities."""
        return [self.to_domain(model) for model in models]

    def to_model_list(self, entities: list[E]) -> list[M]:
        """Convert list of entities to list of models."""
        return [self.to_model(entity) for entity in entities]
