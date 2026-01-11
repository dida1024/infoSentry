"""边界 LLM 判别服务。

根据 AGENT_RUNTIME_SPEC.md 第 6 节设计：
- 调用 cheap model（如 gpt-4o-mini）进行边界判别
- 输出结构化 JSON
- Schema 校验
- 失败降级
"""

import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import settings
from src.modules.items.application.budget_service import BudgetService
from src.modules.users.application.budget_service import UserBudgetUsageService


class BoundaryJudgeOutput(BaseModel):
    """边界判别输出 Schema。"""

    label: str = Field(..., pattern="^(IMMEDIATE|BATCH)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertain: bool = Field(default=False)
    reason: str = Field(..., min_length=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class LLMJudgeService:
    """LLM 边界判别服务。

    职责：
    - 调用 LLM 进行边界判别
    - 验证输出 Schema
    - 记录 token 使用
    - 处理失败降级
    """

    SYSTEM_PROMPT = """你是一个信息推送助手，帮助用户判断新闻是否值得立即推送。

你需要根据用户的目标描述和新闻内容，判断这条新闻应该：
- IMMEDIATE: 立即推送（非常相关且时效性强）
- BATCH: 稍后批量推送（相关但不紧急）

输出必须是严格的 JSON 格式：
{
  "label": "IMMEDIATE" 或 "BATCH",
  "confidence": 0.0-1.0 的置信度,
  "uncertain": 是否不确定 (true/false),
  "reason": "判断理由（中文）",
  "evidence": [
    {"type": "TERM_HIT", "value": "命中的关键词"},
    {"type": "SOURCE", "value": "来源"},
    {"type": "TIME", "value": "时间因素"}
  ]
}

注意：
1. 只输出 JSON，不要有其他文字
2. 如果不确定，设置 uncertain=true 并降级为 BATCH
3. confidence 代表你对判断的确信程度
"""

    def __init__(
        self,
        budget_service: BudgetService | None = None,
        user_budget_service: UserBudgetUsageService | None = None,
        openai_client: AsyncOpenAI | None = None,
    ):
        self.budget_service = budget_service
        self.user_budget_service = user_budget_service
        self._client = openai_client

    @property
    def client(self) -> AsyncOpenAI:
        """获取 OpenAI 客户端（延迟初始化）。"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
            )
        return self._client

    async def judge_boundary(
        self,
        prompt: str | None = None,
        goal_description: str = "",
        item_title: str = "",
        item_snippet: str = "",
        match_score: float = 0,
        match_reasons: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> BoundaryJudgeOutput | None:
        """执行边界判别。

        Args:
            prompt: 自定义 prompt（可选）
            goal_description: 目标描述
            item_title: 新闻标题
            item_snippet: 新闻摘要
            match_score: 匹配分数
            match_reasons: 匹配原因

        Returns:
            BoundaryJudgeOutput | None: 判别结果或 None（失败时）
        """
        # 检查预算
        if self.budget_service:
            is_allowed, reason = await self.budget_service.check_judge_budget()
            if not is_allowed:
                logger.warning(f"Judge budget exhausted: {reason}")
                return None

        # 构建用户 prompt
        if not prompt:
            prompt = self._build_user_prompt(
                goal_description,
                item_title,
                item_snippet,
                match_score,
                match_reasons,
            )

        try:
            result, tokens_used = await self._call_llm(prompt)

            # 记录 token 使用
            if self.budget_service and tokens_used > 0:
                await self.budget_service.record_judge_usage(tokens_used)
            if self.user_budget_service and user_id and tokens_used > 0:
                await self.user_budget_service.record_judge_usage(
                    user_id=user_id,
                    tokens=tokens_used,
                )

            # 验证 Schema
            validated = self._validate_output(result)

            if validated:
                return validated
            else:
                logger.warning("Judge output validation failed")
                return None

        except Exception as e:
            logger.exception(f"Judge LLM call failed: {e}")
            return None

    def _build_user_prompt(
        self,
        goal_description: str,
        item_title: str,
        item_snippet: str,
        match_score: float,
        match_reasons: dict[str, Any] | None,
    ) -> str:
        """构建用户 prompt。"""
        reasons_str = ""
        if match_reasons:
            summary = match_reasons.get("summary", "")
            if summary:
                reasons_str = f"\n匹配原因：{summary}"

        return f"""请判断以下新闻是否应该立即推送给用户。

用户目标：{goal_description}

新闻标题：{item_title}
新闻摘要：{item_snippet or "无"}

匹配分数：{match_score:.2f} (0-1，越高越相关)
{reasons_str}

请根据以上信息判断这条新闻应该 IMMEDIATE（立即推送）还是 BATCH（批量推送）。"""

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def _call_llm(self, user_prompt: str) -> tuple[str, int]:
        """调用 LLM API。"""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_JUDGE_MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        return content, tokens_used

    def _validate_output(self, raw_output: str) -> BoundaryJudgeOutput | None:
        """验证输出 Schema。"""
        try:
            data = json.loads(raw_output)
            return BoundaryJudgeOutput(**data)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
            return None
        except ValidationError as e:
            logger.warning(f"Schema validation error: {e}")
            return None


class MockLLMJudgeService:
    """Mock LLM 服务（用于测试）。"""

    def __init__(self, default_label: str = "BATCH"):
        self.default_label = default_label

    async def judge_boundary(self, **kwargs: Any) -> BoundaryJudgeOutput:
        """返回 mock 结果。

        Args:
            **kwargs: 判别参数（被忽略）

        Returns:
            BoundaryJudgeOutput: Mock 的判别结果
        """
        return BoundaryJudgeOutput(
            label=self.default_label,
            confidence=0.7,
            uncertain=False,
            reason="Mock判断",
            evidence=[],
        )
