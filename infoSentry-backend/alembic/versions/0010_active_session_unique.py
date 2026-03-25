"""Add unique constraint for active discovery sessions per user.

Revision ID: 0010_active_session_unique
Revises: 0009_add_discovery_sessions
Create Date: 2026-03-23
"""

from alembic import op

revision = "0010_active_session_unique"
down_revision = "0009_add_discovery_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial unique index: at most one active/waiting_user session per user
    op.execute(
        """
        CREATE UNIQUE INDEX uq_discovery_sessions_active_per_user
        ON discovery_sessions (user_id)
        WHERE status IN ('active', 'waiting_user')
        AND is_deleted = false
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_discovery_sessions_active_per_user")
