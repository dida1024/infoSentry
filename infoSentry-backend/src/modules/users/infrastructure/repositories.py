"""User repository implementations."""

from datetime import datetime

from loguru import logger
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.domain.events import EventBus
from src.core.infrastructure.database.event_aware_repository import EventAwareRepository
from src.modules.users.domain.entities import MagicLink, User, UserBudgetDaily
from src.modules.users.domain.repository import (
    MagicLinkRepository,
    UserBudgetDailyRepository,
    UserRepository,
)
from src.modules.users.infrastructure.mappers import (
    MagicLinkMapper,
    UserBudgetDailyMapper,
    UserMapper,
)
from src.modules.users.infrastructure.models import (
    MagicLinkModel,
    UserBudgetDailyModel,
    UserModel,
)


class PostgreSQLUserRepository(EventAwareRepository[User], UserRepository):
    """PostgreSQL user repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: UserMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, user_id: str) -> User | None:
        statement = select(UserModel).where(
            UserModel.id == user_id,
            UserModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        statement = select(UserModel).where(
            UserModel.email == email,
            UserModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def exists_by_email(self, email: str) -> bool:
        statement = select(UserModel).where(
            UserModel.email == email,
            UserModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def create(self, user: User) -> User:
        model = self.mapper.to_model(user)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(user)
        return self.mapper.to_domain(model)

    async def update(self, user: User) -> User:
        statement = select(UserModel).where(UserModel.id == user.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"User with id {user.id} not found")

        existing.email = user.email
        existing.is_active = user.is_active
        existing.status = user.status
        existing.last_login_at = user.last_login_at
        existing.display_name = user.display_name
        existing.timezone = user.timezone
        existing.updated_at = user.updated_at
        existing.is_deleted = user.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(user)
        return self.mapper.to_domain(existing)

    async def delete(self, user: User | str) -> bool:
        user_id = user.id if isinstance(user, User) else user
        statement = select(UserModel).where(
            UserModel.id == user_id,
            UserModel.is_deleted.is_(False),
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
    ) -> tuple[list[User], int]:
        statement = select(
            UserModel, func.count(UserModel.id).over().label("total_count")
        )

        if not include_deleted:
            statement = statement.where(UserModel.is_deleted.is_(False))

        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(UserModel.created_at.desc())
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.UserModel for row in rows]
        users = self.mapper.to_domain_list(models)
        return users, total_count


class PostgreSQLMagicLinkRepository(
    EventAwareRepository[MagicLink], MagicLinkRepository
):
    """PostgreSQL magic link repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: MagicLinkMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, magic_link_id: str) -> MagicLink | None:
        statement = select(MagicLinkModel).where(
            MagicLinkModel.id == magic_link_id,
            MagicLinkModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_token(self, token: str) -> MagicLink | None:
        statement = select(MagicLinkModel).where(
            MagicLinkModel.token == token,
            MagicLinkModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_valid_by_email(self, email: str) -> MagicLink | None:
        statement = select(MagicLinkModel).where(
            MagicLinkModel.email == email,
            MagicLinkModel.is_used.is_(False),
            MagicLinkModel.expires_at > datetime.now(),
            MagicLinkModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def invalidate_all_for_email(self, email: str) -> int:
        statement = select(MagicLinkModel).where(
            MagicLinkModel.email == email,
            MagicLinkModel.is_used.is_(False),
            MagicLinkModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()

        count = 0
        for model in models:
            model.is_used = True
            model.used_at = datetime.now()
            self.session.add(model)
            count += 1

        await self.session.flush()
        return count

    async def create(self, magic_link: MagicLink) -> MagicLink:
        model = self.mapper.to_model(magic_link)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(magic_link)
        return self.mapper.to_domain(model)

    async def update(self, magic_link: MagicLink) -> MagicLink:
        statement = select(MagicLinkModel).where(MagicLinkModel.id == magic_link.id)
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"MagicLink with id {magic_link.id} not found")

        existing.is_used = magic_link.is_used
        existing.used_at = magic_link.used_at
        existing.updated_at = magic_link.updated_at
        existing.is_deleted = magic_link.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(magic_link)
        return self.mapper.to_domain(existing)

    async def delete(self, magic_link: MagicLink | str) -> bool:
        link_id = magic_link.id if isinstance(magic_link, MagicLink) else magic_link
        statement = select(MagicLinkModel).where(
            MagicLinkModel.id == link_id,
            MagicLinkModel.is_deleted.is_(False),
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
    ) -> tuple[list[MagicLink], int]:
        statement = select(
            MagicLinkModel, func.count(MagicLinkModel.id).over().label("total_count")
        )

        if not include_deleted:
            statement = statement.where(MagicLinkModel.is_deleted.is_(False))

        statement = (
            statement.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(MagicLinkModel.created_at.desc())
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.MagicLinkModel for row in rows]
        return self.mapper.to_domain_list(models), total_count


class PostgreSQLUserBudgetDailyRepository(
    EventAwareRepository[UserBudgetDaily], UserBudgetDailyRepository
):
    """PostgreSQL user budget daily repository implementation."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: UserBudgetDailyMapper,
        event_publisher: EventBus,
    ):
        super().__init__(event_publisher)
        self.session = session
        self.mapper = mapper
        self.logger = logger

    async def get_by_id(self, budget_id: str) -> UserBudgetDaily | None:
        statement = select(UserBudgetDailyModel).where(
            UserBudgetDailyModel.id == budget_id,
            UserBudgetDailyModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_by_user_and_date(
        self, user_id: str, date: str
    ) -> UserBudgetDaily | None:
        statement = select(UserBudgetDailyModel).where(
            UserBudgetDailyModel.user_id == user_id,
            UserBudgetDailyModel.date == date,
            UserBudgetDailyModel.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        model = result.scalar_one_or_none()
        return self.mapper.to_domain(model) if model else None

    async def get_or_create(self, user_id: str, date: str) -> UserBudgetDaily:
        existing = await self.get_by_user_and_date(user_id, date)
        if existing:
            return existing

        budget = UserBudgetDaily(user_id=user_id, date=date)
        return await self.create(budget)

    async def list_by_user_date_range(
        self, user_id: str, start_date: str, end_date: str
    ) -> list[UserBudgetDaily]:
        statement = (
            select(UserBudgetDailyModel)
            .where(
                UserBudgetDailyModel.user_id == user_id,
                UserBudgetDailyModel.date >= start_date,
                UserBudgetDailyModel.date <= end_date,
                UserBudgetDailyModel.is_deleted.is_(False),
            )
            .order_by(UserBudgetDailyModel.date.asc())
        )
        result = await self.session.execute(statement)
        models = result.scalars().all()
        return self.mapper.to_domain_list(list(models))

    async def create(self, budget: UserBudgetDaily) -> UserBudgetDaily:
        model = self.mapper.to_model(budget)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        await self._publish_events_from_entity(budget)
        return self.mapper.to_domain(model)

    async def update(self, budget: UserBudgetDaily) -> UserBudgetDaily:
        statement = select(UserBudgetDailyModel).where(
            UserBudgetDailyModel.id == budget.id
        )
        result = await self.session.execute(statement)
        existing = result.scalar_one_or_none()
        if not existing:
            raise ValueError(f"UserBudgetDaily with id {budget.id} not found")

        existing.embedding_tokens_est = budget.embedding_tokens_est
        existing.judge_tokens_est = budget.judge_tokens_est
        existing.usd_est = budget.usd_est
        existing.updated_at = budget.updated_at
        existing.is_deleted = budget.is_deleted

        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        await self._publish_events_from_entity(budget)
        return self.mapper.to_domain(existing)

    async def delete(self, budget: UserBudgetDaily | str) -> bool:
        budget_id = budget.id if isinstance(budget, UserBudgetDaily) else budget
        statement = select(UserBudgetDailyModel).where(
            UserBudgetDailyModel.id == budget_id,
            UserBudgetDailyModel.is_deleted.is_(False),
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
    ) -> tuple[list[UserBudgetDaily], int]:
        statement = select(
            UserBudgetDailyModel,
            func.count(UserBudgetDailyModel.id).over().label("total_count"),
        )

        if not include_deleted:
            statement = statement.where(UserBudgetDailyModel.is_deleted.is_(False))

        statement = (
            statement.order_by(UserBudgetDailyModel.date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.session.execute(statement)
        rows = result.all()

        if not rows:
            return [], 0

        total_count = rows[0].total_count
        models = [row.UserBudgetDailyModel for row in rows]
        return self.mapper.to_domain_list(models), total_count
