"""add source_subscriptions table

Revision ID: 0005_add_source_subscriptions
Revises: 0004_add_source_owner_private
Create Date: 2026-01-21
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_add_source_subscriptions"
down_revision = "0004_add_source_owner_private"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "source_id",
            name="uq_source_subscriptions_user_source",
        ),
    )
    op.create_index(
        "ix_source_subscriptions_user_id",
        "source_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_source_subscriptions_source_id",
        "source_subscriptions",
        ["source_id"],
    )
    op.create_index(
        "ix_source_subscriptions_enabled",
        "source_subscriptions",
        ["enabled"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_subscriptions_enabled",
        table_name="source_subscriptions",
    )
    op.drop_index(
        "ix_source_subscriptions_source_id",
        table_name="source_subscriptions",
    )
    op.drop_index(
        "ix_source_subscriptions_user_id",
        table_name="source_subscriptions",
    )
    op.drop_table("source_subscriptions")
