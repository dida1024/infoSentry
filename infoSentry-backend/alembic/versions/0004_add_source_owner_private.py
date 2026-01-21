"""add owner_id and is_private to sources

Revision ID: 0004_add_source_owner_private
Revises: 0003_add_user_budget_daily
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_add_source_owner_private"
down_revision = "0003_add_user_budget_daily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("owner_id", sa.String(), nullable=True))
    op.add_column(
        "sources",
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_sources_owner_id", "sources", ["owner_id"])
    op.create_index("ix_sources_is_private", "sources", ["is_private"])


def downgrade() -> None:
    op.drop_index("ix_sources_is_private", table_name="sources")
    op.drop_index("ix_sources_owner_id", table_name="sources")
    op.drop_column("sources", "is_private")
    op.drop_column("sources", "owner_id")
