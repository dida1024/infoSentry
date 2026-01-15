"""Goal application data models."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.modules.goals.domain.entities import GoalStatus, PriorityMode


class GoalStatsData(BaseModel):
    """Goal statistics data."""

    total_matches: int = 0
    immediate_count: int = 0
    batch_count: int = 0
    digest_count: int = 0


class GoalData(BaseModel):
    """Goal data for queries."""

    id: str
    name: str
    description: str
    priority_mode: PriorityMode
    status: GoalStatus
    priority_terms: list[str] | None = None
    negative_terms: list[str] | None = None
    batch_windows: list[str] | None = None
    digest_send_time: str | None = None
    stats: GoalStatsData | None = None
    created_at: datetime
    updated_at: datetime


class GoalListData(BaseModel):
    """Goal list query result."""

    items: list[GoalData]
    total: int
    page: int
    page_size: int


class ItemData(BaseModel):
    """Item data for match results."""

    id: str
    url: str
    title: str
    snippet: str | None = None
    summary: str | None = None
    published_at: datetime | None = None
    ingested_at: datetime
    source_name: str | None = None


class GoalMatchData(BaseModel):
    """Goal-Item match data."""

    id: str
    goal_id: str
    item_id: str
    match_score: float
    features_json: dict = Field(default_factory=dict)
    reasons_json: dict = Field(default_factory=dict)
    computed_at: datetime
    item: ItemData | None = None


class GoalMatchListData(BaseModel):
    """Goal match list query result."""

    items: list[GoalMatchData]
    total: int
    page: int
    page_size: int
