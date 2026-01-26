"""add ingest_logs table

Revision ID: 0002_add_ingest_logs
Revises: 0001_init
Create Date: 2025-01-06

根据 PRD_v0.md 第 5.1 节建议，添加 ingest_logs 表用于：
- 监控抓取健康状况
- 排查抓取失败原因
- 符合可观测性要求
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_add_ingest_logs"
down_revision = "0001_init"
branch_labels = None
depends_on = None

# Enums
ingest_status_enum = sa.Enum("success", "partial", "failed", name="ingeststatus")


def upgrade() -> None:
    # Ingest logs table
    op.create_table(
        "ingest_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", ingest_status_enum, nullable=False),
        sa.Column("items_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_duplicate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_ingest_logs_source_id", "ingest_logs", ["source_id"])
    op.create_index("ix_ingest_logs_started_at", "ingest_logs", ["started_at"])
    op.create_index("ix_ingest_logs_status", "ingest_logs", ["status"])
    op.create_index(
        "ix_ingest_logs_source_started",
        "ingest_logs",
        ["source_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_table("ingest_logs")
    ingest_status_enum.drop(op.get_bind(), checkfirst=True)
