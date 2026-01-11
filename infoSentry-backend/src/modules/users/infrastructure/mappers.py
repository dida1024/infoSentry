"""User entity-model mappers."""

from src.core.infrastructure.database.mapper import BaseMapper
from src.modules.users.domain.entities import MagicLink, User, UserBudgetDaily
from src.modules.users.infrastructure.models import (
    MagicLinkModel,
    UserBudgetDailyModel,
    UserModel,
)


class UserMapper(BaseMapper[User, UserModel]):
    """User entity-model mapper."""

    def to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            is_active=model.is_active,
            status=model.status,
            last_login_at=model.last_login_at,
            display_name=model.display_name,
            timezone=model.timezone,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            email=entity.email,
            is_active=entity.is_active,
            status=entity.status,
            last_login_at=entity.last_login_at,
            display_name=entity.display_name,
            timezone=entity.timezone,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )


class MagicLinkMapper(BaseMapper[MagicLink, MagicLinkModel]):
    """Magic link entity-model mapper."""

    def to_domain(self, model: MagicLinkModel) -> MagicLink:
        return MagicLink(
            id=model.id,
            email=model.email,
            token=model.token,
            expires_at=model.expires_at,
            is_used=model.is_used,
            used_at=model.used_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: MagicLink) -> MagicLinkModel:
        return MagicLinkModel(
            id=entity.id,
            email=entity.email,
            token=entity.token,
            expires_at=entity.expires_at,
            is_used=entity.is_used,
            used_at=entity.used_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )


class UserBudgetDailyMapper(BaseMapper[UserBudgetDaily, UserBudgetDailyModel]):
    """UserBudgetDaily entity-model mapper."""

    def to_domain(self, model: UserBudgetDailyModel) -> UserBudgetDaily:
        return UserBudgetDaily(
            id=model.id,
            user_id=model.user_id,
            date=model.date,
            embedding_tokens_est=model.embedding_tokens_est,
            judge_tokens_est=model.judge_tokens_est,
            usd_est=model.usd_est,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: UserBudgetDaily) -> UserBudgetDailyModel:
        return UserBudgetDailyModel(
            id=entity.id,
            user_id=entity.user_id,
            date=entity.date,
            embedding_tokens_est=entity.embedding_tokens_est,
            judge_tokens_est=entity.judge_tokens_est,
            usd_est=entity.usd_est,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )
