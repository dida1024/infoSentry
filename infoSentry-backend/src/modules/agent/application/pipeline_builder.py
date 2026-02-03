"""Pipeline builder to construct agent pipelines from settings."""

from typing import Any

from src.core.config import settings
from src.modules.agent.application.llm_service import LLMJudgeService
from src.modules.agent.application.nodes import (
    NodePipeline,
    create_immediate_pipeline,
)
from src.modules.agent.application.state import ThresholdConfig
from src.modules.agent.application.tools import ToolRegistry


class PipelineBuilder:
    """Builds pipelines for different triggers."""

    def __init__(self, *, tools: ToolRegistry, llm_service: LLMJudgeService | None):
        self.tools = tools
        self.llm_service = llm_service

    def build_immediate(self, *, redis_client: Any | None = None) -> NodePipeline:
        """Construct immediate pipeline using settings thresholds."""
        thresholds = ThresholdConfig(
            immediate_threshold=settings.IMMEDIATE_THRESHOLD,
            boundary_lower=settings.BOUNDARY_LOW,
            batch_threshold=settings.BATCH_THRESHOLD,
        )
        return create_immediate_pipeline(
            tools=self.tools,
            llm_service=self.llm_service,
            redis_client=redis_client,
            thresholds=thresholds,
        )
