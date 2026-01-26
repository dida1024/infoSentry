"""add user_budget_daily table

Revision ID: 0003_add_user_budget_daily
Revises: 0002_add_ingest_logs
Create Date: 2026-01-11
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_add_user_budget_daily"
down_revision = "0002_add_ingest_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_budget_daily",
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
        sa.Column("date", sa.String(), nullable=False),
        sa.Column(
            "embedding_tokens_est",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "judge_tokens_est",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "usd_est",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.UniqueConstraint("user_id", "date", name="uq_user_budget_daily_user_date"),
    )
    op.create_index("ix_user_budget_daily_user_id", "user_budget_daily", ["user_id"])
    op.create_index("ix_user_budget_daily_date", "user_budget_daily", ["date"])


def downgrade() -> None:
    op.drop_index("ix_user_budget_daily_date", table_name="user_budget_daily")
    op.drop_index("ix_user_budget_daily_user_id", table_name="user_budget_daily")
    op.drop_table("user_budget_daily")
