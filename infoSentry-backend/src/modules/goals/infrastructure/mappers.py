"""Goal entity-model mappers."""

from src.core.infrastructure.database.mapper import BaseMapper
from src.modules.goals.domain.entities import Goal, GoalPriorityTerm, GoalPushConfig
from src.modules.goals.infrastructure.models import (
    GoalModel,
    GoalPriorityTermModel,
    GoalPushConfigModel,
)


class GoalMapper(BaseMapper[Goal, GoalModel]):
    """Goal entity-model mapper."""

    def to_domain(self, model: GoalModel) -> Goal:
        return Goal(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            description=model.description,
            status=model.status,
            priority_mode=model.priority_mode,
            time_window_days=model.time_window_days,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: Goal) -> GoalModel:
        return GoalModel(
            id=entity.id,
            user_id=entity.user_id,
            name=entity.name,
            description=entity.description,
            status=entity.status,
            priority_mode=entity.priority_mode,
            time_window_days=entity.time_window_days,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )


class GoalPushConfigMapper(BaseMapper[GoalPushConfig, GoalPushConfigModel]):
    """Goal push config mapper."""

    def to_domain(self, model: GoalPushConfigModel) -> GoalPushConfig:
        return GoalPushConfig(
            id=model.id,
            goal_id=model.goal_id,
            batch_windows=model.batch_windows,
            digest_send_time=model.digest_send_time,
            immediate_enabled=model.immediate_enabled,
            batch_enabled=model.batch_enabled,
            digest_enabled=model.digest_enabled,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: GoalPushConfig) -> GoalPushConfigModel:
        return GoalPushConfigModel(
            id=entity.id,
            goal_id=entity.goal_id,
            batch_windows=entity.batch_windows,
            digest_send_time=entity.digest_send_time,
            immediate_enabled=entity.immediate_enabled,
            batch_enabled=entity.batch_enabled,
            digest_enabled=entity.digest_enabled,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )


class GoalPriorityTermMapper(BaseMapper[GoalPriorityTerm, GoalPriorityTermModel]):
    """Goal priority term mapper."""

    def to_domain(self, model: GoalPriorityTermModel) -> GoalPriorityTerm:
        return GoalPriorityTerm(
            id=model.id,
            goal_id=model.goal_id,
            term=model.term,
            term_type=model.term_type,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: GoalPriorityTerm) -> GoalPriorityTermModel:
        return GoalPriorityTermModel(
            id=entity.id,
            goal_id=entity.goal_id,
            term=entity.term,
            term_type=entity.term_type,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )
