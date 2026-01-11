"""Item entity-model mappers."""

from src.core.infrastructure.database.mapper import BaseMapper
from src.modules.items.domain.entities import GoalItemMatch, Item
from src.modules.items.infrastructure.models import GoalItemMatchModel, ItemModel


class ItemMapper(BaseMapper[Item, ItemModel]):
    """Item entity-model mapper."""

    def to_domain(self, model: ItemModel) -> Item:
        return Item(
            id=model.id,
            source_id=model.source_id,
            url=model.url,
            url_hash=model.url_hash,
            title=model.title,
            snippet=model.snippet,
            summary=model.summary,
            published_at=model.published_at,
            ingested_at=model.ingested_at,
            embedding=model.embedding,
            embedding_status=model.embedding_status,
            embedding_model=model.embedding_model,
            raw_data=model.raw_data,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: Item) -> ItemModel:
        return ItemModel(
            id=entity.id,
            source_id=entity.source_id,
            url=entity.url,
            url_hash=entity.url_hash,
            title=entity.title,
            snippet=entity.snippet,
            summary=entity.summary,
            published_at=entity.published_at,
            ingested_at=entity.ingested_at,
            embedding=entity.embedding,
            embedding_status=entity.embedding_status,
            embedding_model=entity.embedding_model,
            raw_data=entity.raw_data,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )


class GoalItemMatchMapper(BaseMapper[GoalItemMatch, GoalItemMatchModel]):
    """Goal-Item match mapper."""

    def to_domain(self, model: GoalItemMatchModel) -> GoalItemMatch:
        return GoalItemMatch(
            id=model.id,
            goal_id=model.goal_id,
            item_id=model.item_id,
            match_score=model.match_score,
            features_json=model.features_json,
            reasons_json=model.reasons_json,
            computed_at=model.computed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: GoalItemMatch) -> GoalItemMatchModel:
        return GoalItemMatchModel(
            id=entity.id,
            goal_id=entity.goal_id,
            item_id=entity.item_id,
            match_score=entity.match_score,
            features_json=entity.features_json,
            reasons_json=entity.reasons_json,
            computed_at=entity.computed_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )
