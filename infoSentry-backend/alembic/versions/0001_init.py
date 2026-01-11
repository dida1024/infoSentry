"""init all tables

Revision ID: 0001_init
Revises:
Create Date: 2025-01-05
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

# Enums
user_status_enum = sa.Enum("active", "inactive", "suspended", name="userstatus")
source_type_enum = sa.Enum("NEWSNOW", "RSS", "SITE", name="sourcetype")
goal_status_enum = sa.Enum("active", "paused", "archived", name="goalstatus")
priority_mode_enum = sa.Enum("STRICT", "SOFT", name="prioritymode")
term_type_enum = sa.Enum("must", "negative", name="termtype")
embedding_status_enum = sa.Enum("pending", "done", "skipped_budget", "failed", name="embeddingstatus")
push_decision_enum = sa.Enum("IMMEDIATE", "BATCH", "DIGEST", "IGNORE", name="pushdecision")
push_status_enum = sa.Enum("PENDING", "SENT", "FAILED", "SKIPPED", "READ", name="pushstatus")
push_channel_enum = sa.Enum("EMAIL", "IN_APP", name="pushchannel")
feedback_type_enum = sa.Enum("LIKE", "DISLIKE", name="feedbacktype")
agent_trigger_enum = sa.Enum("MatchComputed", "BatchWindowTick", "DigestTick", name="agenttrigger")
agent_run_status_enum = sa.Enum("RUNNING", "SUCCESS", "TIMEOUT", "ERROR", "FALLBACK", name="agentrunstatus")
tool_call_status_enum = sa.Enum("SUCCESS", "ERROR", name="toolcallstatus")
action_type_enum = sa.Enum("EMIT_DECISION", "ENQUEUE_EMAIL", "SUGGEST_TUNING", name="actiontype")


def upgrade() -> None:
    # Create pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", user_status_enum, nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=False, server_default="Asia/Shanghai"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    
    # Auth magic links table
    op.create_table(
        "auth_magic_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_auth_magic_links_email", "auth_magic_links", ["email"])
    op.create_index("ix_auth_magic_links_token", "auth_magic_links", ["token"], unique=True)
    
    # Sources table
    op.create_table(
        "sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("type", source_type_enum, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fetch_interval_sec", sa.Integer(), nullable=False, server_default="1800"),
        sa.Column("next_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("empty_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_sources_name", "sources", ["name"], unique=True)
    op.create_index("ix_sources_type", "sources", ["type"])
    op.create_index("ix_sources_enabled", "sources", ["enabled"])
    op.create_index("ix_sources_next_fetch_at", "sources", ["next_fetch_at"])
    
    # Goals table
    op.create_table(
        "goals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", goal_status_enum, nullable=False),
        sa.Column("priority_mode", priority_mode_enum, nullable=False),
        sa.Column("time_window_days", sa.Integer(), nullable=False, server_default="7"),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    op.create_index("ix_goals_status", "goals", ["status"])
    
    # Goal push configs table
    op.create_table(
        "goal_push_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("goal_id", sa.String(), nullable=False),
        sa.Column("batch_windows", sa.JSON(), nullable=False, server_default='["12:30", "18:30"]'),
        sa.Column("digest_send_time", sa.String(), nullable=False, server_default="09:00"),
        sa.Column("immediate_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("batch_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_goal_push_configs_goal_id", "goal_push_configs", ["goal_id"], unique=True)
    
    # Goal priority terms table
    op.create_table(
        "goal_priority_terms",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("goal_id", sa.String(), nullable=False),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("term_type", term_type_enum, nullable=False),
    )
    op.create_index("ix_goal_priority_terms_goal_id", "goal_priority_terms", ["goal_id"])
    
    # Items table
    op.create_table(
        "items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("url_hash", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_status", embedding_status_enum, nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
    )
    op.create_index("ix_items_source_id", "items", ["source_id"])
    op.create_index("ix_items_url_hash", "items", ["url_hash"], unique=True)
    op.create_index("ix_items_published_at", "items", ["published_at"])
    op.create_index("ix_items_ingested_at", "items", ["ingested_at"])
    op.create_index("ix_items_embedding_status", "items", ["embedding_status"])
    
    # Goal item matches table
    op.create_table(
        "goal_item_matches",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("goal_id", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("features_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("reasons_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_goal_item_matches_goal_id", "goal_item_matches", ["goal_id"])
    op.create_index("ix_goal_item_matches_item_id", "goal_item_matches", ["item_id"])
    op.create_index("ix_goal_item_matches_score", "goal_item_matches", ["match_score"])
    op.create_unique_constraint("uq_goal_item_matches_goal_item", "goal_item_matches", ["goal_id", "item_id"])
    
    # Push decisions table
    op.create_table(
        "push_decisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("goal_id", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("decision", push_decision_enum, nullable=False),
        sa.Column("status", push_status_enum, nullable=False),
        sa.Column("channel", push_channel_enum, nullable=False),
        sa.Column("reason_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=True),
    )
    op.create_index("ix_push_decisions_goal_id", "push_decisions", ["goal_id"])
    op.create_index("ix_push_decisions_item_id", "push_decisions", ["item_id"])
    op.create_index("ix_push_decisions_decision", "push_decisions", ["decision"])
    op.create_index("ix_push_decisions_status", "push_decisions", ["status"])
    op.create_index("ix_push_decisions_decided_at", "push_decisions", ["decided_at"])
    op.create_index("ix_push_decisions_dedupe_key", "push_decisions", ["dedupe_key"], unique=True)
    
    # Click events table
    op.create_table(
        "click_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("goal_id", sa.String(), nullable=True),
        sa.Column("channel", push_channel_enum, nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
    )
    op.create_index("ix_click_events_item_id", "click_events", ["item_id"])
    op.create_index("ix_click_events_goal_id", "click_events", ["goal_id"])
    op.create_index("ix_click_events_clicked_at", "click_events", ["clicked_at"])
    
    # Item feedback table
    op.create_table(
        "item_feedback",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("item_id", sa.String(), nullable=False),
        sa.Column("goal_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("feedback", feedback_type_enum, nullable=False),
        sa.Column("block_source", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_item_feedback_item_id", "item_feedback", ["item_id"])
    op.create_index("ix_item_feedback_goal_id", "item_feedback", ["goal_id"])
    op.create_index("ix_item_feedback_user_id", "item_feedback", ["user_id"])
    
    # Blocked sources table
    op.create_table(
        "blocked_sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("goal_id", sa.String(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_blocked_sources_user_id", "blocked_sources", ["user_id"])
    op.create_index("ix_blocked_sources_goal_id", "blocked_sources", ["goal_id"])
    op.create_index("ix_blocked_sources_source_id", "blocked_sources", ["source_id"])
    
    # Agent runs table
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("trigger", agent_trigger_enum, nullable=False),
        sa.Column("goal_id", sa.String(), nullable=True),
        sa.Column("status", agent_run_status_enum, nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=True),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("output_snapshot_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("final_actions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("budget_snapshot_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("llm_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_agent_runs_trigger", "agent_runs", ["trigger"])
    op.create_index("ix_agent_runs_goal_id", "agent_runs", ["goal_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    
    # Agent tool calls table
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("output_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", tool_call_status_enum, nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_agent_tool_calls_run_id", "agent_tool_calls", ["run_id"])
    
    # Agent action ledger table
    op.create_table(
        "agent_action_ledger",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("action_type", action_type_enum, nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_agent_action_ledger_run_id", "agent_action_ledger", ["run_id"])
    
    # Budget daily table
    op.create_table(
        "budget_daily",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("date", sa.String(), nullable=False),
        sa.Column("embedding_tokens_est", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("judge_tokens_est", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usd_est", sa.Float(), nullable=False, server_default="0"),
        sa.Column("embedding_disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("judge_disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_budget_daily_date", "budget_daily", ["date"], unique=True)


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table("budget_daily")
    op.drop_table("agent_action_ledger")
    op.drop_table("agent_tool_calls")
    op.drop_table("agent_runs")
    op.drop_table("blocked_sources")
    op.drop_table("item_feedback")
    op.drop_table("click_events")
    op.drop_table("push_decisions")
    op.drop_table("goal_item_matches")
    op.drop_table("items")
    op.drop_table("goal_priority_terms")
    op.drop_table("goal_push_configs")
    op.drop_table("goals")
    op.drop_table("sources")
    op.drop_table("auth_magic_links")
    op.drop_table("users")
    
    # Drop enums
    action_type_enum.drop(op.get_bind(), checkfirst=True)
    tool_call_status_enum.drop(op.get_bind(), checkfirst=True)
    agent_run_status_enum.drop(op.get_bind(), checkfirst=True)
    agent_trigger_enum.drop(op.get_bind(), checkfirst=True)
    feedback_type_enum.drop(op.get_bind(), checkfirst=True)
    push_channel_enum.drop(op.get_bind(), checkfirst=True)
    push_status_enum.drop(op.get_bind(), checkfirst=True)
    push_decision_enum.drop(op.get_bind(), checkfirst=True)
    embedding_status_enum.drop(op.get_bind(), checkfirst=True)
    term_type_enum.drop(op.get_bind(), checkfirst=True)
    priority_mode_enum.drop(op.get_bind(), checkfirst=True)
    goal_status_enum.drop(op.get_bind(), checkfirst=True)
    source_type_enum.drop(op.get_bind(), checkfirst=True)
    user_status_enum.drop(op.get_bind(), checkfirst=True)

