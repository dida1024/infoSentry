"""Goal application data models."""

from datetime import datetime

from pydantic import BaseModel, Field


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
