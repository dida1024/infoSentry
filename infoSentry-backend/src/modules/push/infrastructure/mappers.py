"""Push entity-model mappers."""

from src.modules.push.domain.entities import (
    BlockedSource,
    ClickEvent,
    ItemFeedback,
    PushDecisionRecord,
)
from src.modules.push.infrastructure.models import (
    BlockedSourceModel,
    ClickEventModel,
    ItemFeedbackModel,
    PushDecisionModel,
)


class PushDecisionMapper:
    """PushDecision entity-model mapper."""

    def to_entity(self, model: PushDecisionModel) -> PushDecisionRecord:
        """Convert model to entity."""
        return PushDecisionRecord(
            id=model.id,
            goal_id=model.goal_id,
            item_id=model.item_id,
            decision=model.decision,
            status=model.status,
            channel=model.channel,
            reason_json=model.reason_json,
            decided_at=model.decided_at,
            sent_at=model.sent_at,
            dedupe_key=model.dedupe_key,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self, entity: PushDecisionRecord) -> PushDecisionModel:
        """Convert entity to model."""
        return PushDecisionModel(
            id=entity.id,
            goal_id=entity.goal_id,
            item_id=entity.item_id,
            decision=entity.decision,
            status=entity.status,
            channel=entity.channel,
            reason_json=entity.reason_json,
            decided_at=entity.decided_at,
            sent_at=entity.sent_at,
            dedupe_key=entity.dedupe_key,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class ClickEventMapper:
    """ClickEvent entity-model mapper."""

    def to_entity(self, model: ClickEventModel) -> ClickEvent:
        """Convert model to entity."""
        return ClickEvent(
            id=model.id,
            item_id=model.item_id,
            goal_id=model.goal_id,
            channel=model.channel,
            clicked_at=model.clicked_at,
            user_agent=model.user_agent,
            ip_address=model.ip_address,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self, entity: ClickEvent) -> ClickEventModel:
        """Convert entity to model."""
        return ClickEventModel(
            id=entity.id,
            item_id=entity.item_id,
            goal_id=entity.goal_id,
            channel=entity.channel,
            clicked_at=entity.clicked_at,
            user_agent=entity.user_agent,
            ip_address=entity.ip_address,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class ItemFeedbackMapper:
    """ItemFeedback entity-model mapper."""

    def to_entity(self, model: ItemFeedbackModel) -> ItemFeedback:
        """Convert model to entity."""
        return ItemFeedback(
            id=model.id,
            item_id=model.item_id,
            goal_id=model.goal_id,
            user_id=model.user_id,
            feedback=model.feedback,
            block_source=model.block_source,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self, entity: ItemFeedback) -> ItemFeedbackModel:
        """Convert entity to model."""
        return ItemFeedbackModel(
            id=entity.id,
            item_id=entity.item_id,
            goal_id=entity.goal_id,
            user_id=entity.user_id,
            feedback=entity.feedback,
            block_source=entity.block_source,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class BlockedSourceMapper:
    """BlockedSource entity-model mapper."""

    def to_entity(self, model: BlockedSourceModel) -> BlockedSource:
        """Convert model to entity."""
        return BlockedSource(
            id=model.id,
            user_id=model.user_id,
            goal_id=model.goal_id,
            source_id=model.source_id,
            blocked_at=model.blocked_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self, entity: BlockedSource) -> BlockedSourceModel:
        """Convert entity to model."""
        return BlockedSourceModel(
            id=entity.id,
            user_id=entity.user_id,
            goal_id=entity.goal_id,
            source_id=entity.source_id,
            blocked_at=entity.blocked_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
