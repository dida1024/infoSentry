"""API Key repository implementations."""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from src.core.domain.events import EventBus
from src.core.domain.exceptions import EntityNotFoundError
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.api_keys.domain.entities import ApiKey
from src.modules.api_keys.domain.repository import ApiKeyRepository
from src.modules.api_keys.infrastructure.mappers import ApiKeyMapper
from src.modules.api_keys.infrastructure.models import ApiKeyModel


class PostgreSQLApiKeyRepository(EventAwareRepository[ApiKey], ApiKeyRepository):
    """PostgreSQL API Key repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: ApiKeyMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper

    async def get_by_id(self, key_id: str) -> ApiKey | None:
        statement = select(ApiKeyModel).where(
            ApiKeyModel.id == key_id,
            col(ApiKeyModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        """Get key by hash. Returns active AND revoked keys (not deleted).

        The service layer decides if the key is usable (active, not expired).
        """
        statement = select(ApiKeyModel).where(
            ApiKeyModel.key_hash == key_hash,
            col(ApiKeyModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def list_by_user(self, user_id: str) -> list[ApiKey]:
        statement = (
            select(ApiKeyModel)
            .where(
                ApiKeyModel.user_id == user_id,
                col(ApiKeyModel.is_deleted).is_(False),
            )
            .order_by(col(ApiKeyModel.created_at).desc())
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def count_active_by_user(self, user_id: str) -> int:
        statement = (
            select(func.count())
            .where(
                ApiKeyModel.user_id == user_id,
                col(ApiKeyModel.is_deleted).is_(False),
                col(ApiKeyModel.is_active).is_(True),
            )
            .select_from(ApiKeyModel)
        )
        result = await self.session.execute(statement)
        return result.scalar_one() or 0

    async def update_last_used(self, key_id: str, used_at: datetime) -> None:
        statement = select(ApiKeyModel).where(ApiKeyModel.id == key_id)
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        if model:
            model.last_used_at = used_at
            self.session.add(model)
            await self.session.flush()

    async def create(self, api_key: ApiKey) -> ApiKey:
        model = self.mapper.to_model(api_key)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(api_key)
        return self.mapper.to_domain(model)

    async def update(self, api_key: ApiKey) -> ApiKey:
        statement = select(ApiKeyModel).where(ApiKeyModel.id == api_key.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise EntityNotFoundError("ApiKey", api_key.id)

        existing.user_id = api_key.user_id
        existing.name = api_key.name
        existing.key_prefix = api_key.key_prefix
        existing.key_hash = api_key.key_hash
        existing.scopes = api_key.scopes
        existing.expires_at = api_key.expires_at
        existing.last_used_at = api_key.last_used_at
        existing.is_active = api_key.is_active
        existing.updated_at = api_key.updated_at
        existing.is_deleted = api_key.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(api_key)
        return self.mapper.to_domain(existing)

    async def delete(self, api_key: ApiKey | str) -> bool:
        key_id = api_key.id if isinstance(api_key, ApiKey) else api_key
        statement = select(ApiKeyModel).where(
            ApiKeyModel.id == key_id,
            col(ApiKeyModel.is_deleted).is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        if not model:
            return False

        model.is_deleted = True
        self.session.add(model)
        await self.session.flush()
        return True

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 10,
        include_deleted: bool = False,
    ) -> tuple[list[ApiKey], int]:
        statement = select(
            ApiKeyModel, func.count(col(ApiKeyModel.id)).over().label("total_count")
        )

        if not include_deleted:
            statement = statement.where(col(ApiKeyModel.is_deleted).is_(False))

        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(col(ApiKeyModel.created_at).desc())
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.ApiKeyModel for row in rows]
        return self.mapper.to_domain_list(models), total_count
