"""目标草稿生成服务。

根据用户的意图（想关注什么），调用 LLM 生成一个简短的目标草稿：
- 目标名称
- 目标描述
- 建议关键词

该能力用于「新建目标」页面的一键填充，不应输出过长文本。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Final

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import settings
from src.core.domain.ports.prompt_store import PromptStore

logger = structlog.get_logger(__name__)


class GoalDraftServiceError(Exception):
    """目标草稿生成服务异常基类。"""


class GoalDraftNotAvailableError(GoalDraftServiceError):
    """AI 功能不可用（关闭/未配置）。"""


class GoalDraftGenerationError(GoalDraftServiceError):
    """AI 生成失败（调用失败或输出不可解析）。"""


class GoalDraftOutput(BaseModel):
    """目标草稿输出 Schema。"""

    name: str = Field(default="")
    description: str = Field(default="")
    keywords: list[str] = Field(default_factory=list)


class GoalDraftService:
    """目标草稿生成服务。"""

    # 限制长度：避免生成“太长”的描述，便于用户快速微调
    _MAX_NAME_CHARS: Final[int] = 100
    _MAX_DESCRIPTION_CHARS: Final[int] = 280
    _MAX_KEYWORD_CHARS: Final[int] = 30

    SYSTEM_PROMPT: Final[str] = """你是一个信息追踪产品的助理。用户会用一句话描述想关注什么，请你生成一个“追踪目标”的草稿。

要求：
1) 输出必须是严格 JSON，且只输出 JSON，不要任何解释文字
2) 目标名称：简洁、可读、可直接作为目标名，尽量 8-18 个中文字符（必要时包含英文专有名词），不要太泛（不要用“新闻/动态/信息”这类空词堆砌）
3) 目标描述：1-2 句话，尽量 <= 120 个中文字符，说明关注范围与重点，不要写成论文
4) 关键词：3-6 个，优先中文关键词，必要时包含英文专有名词；避免过泛词；每个关键词尽量 2-8 个字

输出 JSON 结构：
{"name": "...", "description": "...", "keywords": ["...", "..."]}
"""

    def __init__(
        self,
        prompt_store: PromptStore,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        self._prompt_store = prompt_store
        self._client = openai_client
        self._log = logger.bind(service="GoalDraftService")

    @property
    def client(self) -> AsyncOpenAI:
        """获取 OpenAI 客户端（延迟初始化）。"""
        if self._client is None:
            if not settings.LLM_ENABLED:
                raise GoalDraftNotAvailableError("LLM feature disabled")
            if not settings.OPENAI_API_KEY:
                raise GoalDraftNotAvailableError("OPENAI_API_KEY not configured")
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
            )
        return self._client

    async def generate_draft(self, intent: str, max_keywords: int = 5) -> GoalDraftOutput:
        """根据用户意图生成目标草稿。"""
        if not settings.LLM_ENABLED:
            raise GoalDraftNotAvailableError("LLM feature disabled")

        normalized_intent = intent.strip()
        if len(normalized_intent) < 3:
            raise ValueError("intent too short")

        messages = self._build_messages(intent=normalized_intent, max_keywords=max_keywords)

        try:
            raw_output, tokens_used = await self._call_llm(messages)
            self._log.info("goal_draft_llm_completed", tokens_used=tokens_used)
        except GoalDraftNotAvailableError:
            raise
        except Exception as e:  # noqa: BLE001
            self._log.exception("goal_draft_llm_call_failed", error=str(e))
            raise GoalDraftGenerationError("LLM call failed") from e

        output = self._validate_output(raw_output)
        return self._sanitize_output(output, normalized_intent, max_keywords)

    def _build_messages(self, *, intent: str, max_keywords: int) -> list[dict[str, str]]:
        """构建 messages（支持文件化 prompt）。"""
        if settings.PROMPTS_ENABLED:
            rendered = self._prompt_store.render_messages(
                name="goals.goal_draft",
                variables={
                    "intent": intent,
                    "max_keywords": max_keywords,
                },
            )
            return [{"role": m.role, "content": m.content} for m in rendered]

        # 回退：使用代码内 prompt（仅用于紧急回滚）
        user_prompt = self._build_user_prompt(intent, max_keywords)
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def _build_user_prompt(self, intent: str, max_keywords: int) -> str:
        """构建用户 prompt（回退用）。"""
        return f"""用户意图：
{intent}

请生成一个目标草稿，关键词数量不超过 {max_keywords}。"""

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True,
    )
    async def _call_llm(self, messages: Sequence[dict[str, str]]) -> tuple[str, int]:
        """调用 LLM API。"""
        response = await self.client.chat.completions.create(
            model=settings.OPENAI_JUDGE_MODEL,
            messages=list(messages),
            temperature=0.4,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        return content, tokens_used

    def _validate_output(self, raw_output: str) -> GoalDraftOutput:
        """验证并解析 LLM 输出。"""
        if not raw_output.strip():
            raise GoalDraftGenerationError("Empty output from LLM")

        try:
            data = json.loads(raw_output)
            return GoalDraftOutput(**data)
        except json.JSONDecodeError as e:
            self._log.warning("goal_draft_json_decode_error", error=str(e))
            raise GoalDraftGenerationError("Invalid JSON from LLM") from e
        except ValidationError as e:
            self._log.warning("goal_draft_schema_validation_error", error=str(e))
            raise GoalDraftGenerationError("Invalid schema from LLM") from e

    def _sanitize_output(
        self,
        output: GoalDraftOutput,
        intent: str,
        max_keywords: int,
    ) -> GoalDraftOutput:
        """清理输出、去重、并进行长度裁剪。"""
        name = (output.name or "").replace("\n", " ").strip()
        description = (output.description or "").strip()

        # keywords 清洗、去重、裁剪
        cleaned_keywords: list[str] = []
        seen: set[str] = set()
        for kw in output.keywords:
            if not kw:
                continue
            k = kw.strip()
            if not k:
                continue
            if len(k) > self._MAX_KEYWORD_CHARS:
                k = k[: self._MAX_KEYWORD_CHARS].strip()
            if not k or k in seen:
                continue
            seen.add(k)
            cleaned_keywords.append(k)

        cleaned_keywords = cleaned_keywords[:max_keywords]

        # 长度限制（避免太长）
        if len(name) > self._MAX_NAME_CHARS:
            name = name[: self._MAX_NAME_CHARS].strip()
        if len(description) > self._MAX_DESCRIPTION_CHARS:
            description = description[: self._MAX_DESCRIPTION_CHARS].strip()

        # 最小兜底：保证前端有可回填内容
        if not name:
            base = intent[: min(20, len(intent))].strip()
            name = f"{base}追踪" if base else "信息追踪"
            if len(name) > self._MAX_NAME_CHARS:
                name = name[: self._MAX_NAME_CHARS].strip()
        if not description:
            description = f"关注：{intent}。"
            if len(description) > self._MAX_DESCRIPTION_CHARS:
                description = description[: self._MAX_DESCRIPTION_CHARS].strip()

        return GoalDraftOutput(
            name=name,
            description=description,
            keywords=cleaned_keywords,
        )

