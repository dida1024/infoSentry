"""Alembic environment configuration."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from src.core.config import settings

# Import all models to ensure they are registered
from src.modules.users.infrastructure.models import UserModel, MagicLinkModel
from src.modules.sources.infrastructure.models import SourceModel, IngestLogModel
from src.modules.goals.infrastructure.models import (
    GoalModel,
    GoalPushConfigModel,
    GoalPriorityTermModel,
)
from src.modules.items.infrastructure.models import ItemModel, GoalItemMatchModel
from src.modules.push.infrastructure.models import (
    PushDecisionModel,
    ClickEventModel,
    ItemFeedbackModel,
    BlockedSourceModel,
)
from src.modules.agent.infrastructure.models import (
    AgentRunModel,
    AgentToolCallModel,
    AgentActionLedgerModel,
    BudgetDailyModel,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

