"""add discovery session tables

Revision ID: 0009_add_discovery_sessions
Revises: 0008_add_topic_key_and_item_time
Create Date: 2026-03-20
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_add_discovery_sessions"
down_revision = "0008_add_topic_key_and_item_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, index=True, server_default="active"),
        sa.Column("initial_query", sa.Text, nullable=False),
        sa.Column("messages_json", sa.JSON, nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_discovery_sessions_user_created",
        "discovery_sessions",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "discovery_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("discovery_sessions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("config_json", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="discovered"),
        sa.Column("validation_result_json", sa.JSON, nullable=True),
        sa.Column("discovered_via", sa.String(30), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_discovery_candidates_session",
        "discovery_candidates",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_discovery_candidates_session", table_name="discovery_candidates")
    op.drop_table("discovery_candidates")
    op.drop_index("ix_discovery_sessions_user_created", table_name="discovery_sessions")
    op.drop_table("discovery_sessions")
