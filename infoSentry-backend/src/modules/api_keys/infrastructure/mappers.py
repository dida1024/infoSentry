"""API Key entity-model mappers."""

from src.core.infrastructure.database.mapper import BaseMapper
from src.modules.api_keys.domain.entities import ApiKey
from src.modules.api_keys.infrastructure.models import ApiKeyModel


class ApiKeyMapper(BaseMapper[ApiKey, ApiKeyModel]):
    """API Key entity-model mapper."""

    def to_domain(self, model: ApiKeyModel) -> ApiKey:
        return ApiKey(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            key_prefix=model.key_prefix,
            key_hash=model.key_hash,
            scopes=model.scopes,
            expires_at=model.expires_at,
            last_used_at=model.last_used_at,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_deleted=model.is_deleted,
        )

    def to_model(self, entity: ApiKey) -> ApiKeyModel:
        return ApiKeyModel(
            id=entity.id,
            user_id=entity.user_id,
            name=entity.name,
            key_prefix=entity.key_prefix,
            key_hash=entity.key_hash,
            scopes=entity.scopes,
            expires_at=entity.expires_at,
            last_used_at=entity.last_used_at,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            is_deleted=entity.is_deleted,
        )
