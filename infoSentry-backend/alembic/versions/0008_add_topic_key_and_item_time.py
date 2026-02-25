"""add topic_key and item_time for stable deduped match query

Revision ID: 0008_add_topic_key_and_item_time
Revises: 0007_add_api_keys
Create Date: 2026-02-25
"""

import sqlalchemy as sa

from alembic import op
from src.core.domain.url_topic import build_topic_key

# revision identifiers, used by Alembic.
revision = "0008_add_topic_key_and_item_time"
down_revision = "0007_add_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("topic_key", sa.String(length=32), nullable=True))
    op.create_index("ix_items_topic_key", "items", ["topic_key"], unique=False)

    op.add_column(
        "goal_item_matches",
        sa.Column("topic_key", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "goal_item_matches",
        sa.Column("item_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_goal_item_matches_topic_key",
        "goal_item_matches",
        ["topic_key"],
        unique=False,
    )
    op.create_index(
        "ix_goal_item_matches_item_time",
        "goal_item_matches",
        ["item_time"],
        unique=False,
    )

    op.create_index(
        "ix_gim_goal_topic_score_comp",
        "goal_item_matches",
        ["goal_id", "topic_key", "match_score", "computed_at"],
        unique=False,
    )
    op.create_index(
        "ix_gim_goal_item_time_score",
        "goal_item_matches",
        ["goal_id", "item_time", "match_score"],
        unique=False,
    )
    op.create_index(
        "ix_gim_goal_computed_at",
        "goal_item_matches",
        ["goal_id", "computed_at"],
        unique=False,
    )

    bind = op.get_bind()

    select_items = sa.text("SELECT id, url FROM items WHERE topic_key IS NULL")
    update_items = sa.text(
        "UPDATE items SET topic_key = :topic_key WHERE id = :item_id"
    )

    rows = bind.execute(select_items).all()
    for start in range(0, len(rows), 1000):
        batch = rows[start : start + 1000]
        payload = [
            {
                "item_id": row[0],
                "topic_key": build_topic_key(row[1] if row[1] is not None else ""),
            }
            for row in batch
        ]
        bind.execute(update_items, payload)

    bind.execute(
        sa.text(
            """
            UPDATE goal_item_matches AS gim
            SET topic_key = i.topic_key,
                item_time = COALESCE(i.published_at, i.ingested_at, gim.computed_at)
            FROM items AS i
            WHERE gim.item_id = i.id
              AND (gim.topic_key IS NULL OR gim.item_time IS NULL)
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE goal_item_matches
            SET topic_key = LEFT(md5(CONCAT('item:', item_id)), 32),
                item_time = COALESCE(item_time, computed_at)
            WHERE topic_key IS NULL OR item_time IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_gim_goal_computed_at", table_name="goal_item_matches")
    op.drop_index("ix_gim_goal_item_time_score", table_name="goal_item_matches")
    op.drop_index("ix_gim_goal_topic_score_comp", table_name="goal_item_matches")

    op.drop_index("ix_goal_item_matches_item_time", table_name="goal_item_matches")
    op.drop_index("ix_goal_item_matches_topic_key", table_name="goal_item_matches")
    op.drop_column("goal_item_matches", "item_time")
    op.drop_column("goal_item_matches", "topic_key")

    op.drop_index("ix_items_topic_key", table_name="items")
    op.drop_column("items", "topic_key")
