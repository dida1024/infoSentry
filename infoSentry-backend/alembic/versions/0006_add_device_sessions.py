"""add user_device_sessions table

Revision ID: 0006_add_device_sessions
Revises: 0005_add_source_subscriptions
Create Date: 2026-01-22
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_add_device_sessions"
down_revision = "0005_add_source_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_device_sessions",
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
        sa.Column("refresh_token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_device_sessions_user_id",
        "user_device_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_user_device_sessions_refresh_token_hash",
        "user_device_sessions",
        ["refresh_token_hash"],
    )
    op.create_index(
        "ix_user_device_sessions_device_id",
        "user_device_sessions",
        ["device_id"],
    )
    op.create_index(
        "ix_user_device_sessions_expires_at",
        "user_device_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_device_sessions_expires_at",
        table_name="user_device_sessions",
    )
    op.drop_index(
        "ix_user_device_sessions_device_id",
        table_name="user_device_sessions",
    )
    op.drop_index(
        "ix_user_device_sessions_refresh_token_hash",
        table_name="user_device_sessions",
    )
    op.drop_index(
        "ix_user_device_sessions_user_id",
        table_name="user_device_sessions",
    )
    op.drop_table("user_device_sessions")
