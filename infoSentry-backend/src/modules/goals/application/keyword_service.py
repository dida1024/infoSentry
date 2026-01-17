"""关键词建议服务。

根据目标描述调用 LLM 生成建议的优选关键词。
"""

import json
from collections.abc import Sequence

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
from src.core.domain.ports.prompt_store import PromptStore


class KeywordSuggestionOutput(BaseModel):
    """关键词建议输出 Schema。"""

    keywords: list[str] = Field(default_factory=list)


class KeywordSuggestionService:
    """关键词建议服务。

    职责：
    - 调用 LLM 根据描述生成关键词
    - 验证输出 Schema
    - 处理失败情况
    """

    SYSTEM_PROMPT = """你是一个信息追踪专家。根据用户的目标描述，提取最相关的关键词或短语。

要求：
1. 关键词应该能够有效识别相关新闻/文章
2. 包含核心概念、相关技术、关键人物/公司等
3. 避免过于宽泛的词（如"新闻"、"信息"、"动态"）
4. 优先中文关键词，必要时可包含英文专有名词
5. 每个关键词应简洁有力，通常 2-6 个字

输出必须是严格的 JSON 格式：
{"keywords": ["关键词1", "关键词2", ...]}

注意：只输出 JSON，不要有其他文字。"""

    def __init__(
        self,
        prompt_store: PromptStore,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        self._prompt_store = prompt_store
        self._client = openai_client
        self._logger = logger.bind(service="KeywordSuggestionService")

    @property
    def client(self) -> AsyncOpenAI:
        """获取 OpenAI 客户端（延迟初始化）。"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
            )
        return self._client

    async def suggest_keywords(
        self,
        description: str,
        max_keywords: int = 5,
    ) -> list[str]:
        """根据描述生成建议的优选关键词。

        Args:
            description: 目标描述文本
            max_keywords: 最大关键词数量（1-10）

        Returns:
            list[str]: 建议的关键词列表，失败时返回空列表
        """
        if not description or len(description.strip()) < 10:
            self._logger.warning("Description too short for keyword suggestion")
            return []

        messages = self._build_messages(
            description=description, max_keywords=max_keywords
        )

        try:
            result, tokens_used = await self._call_llm(messages)
            self._logger.info(f"Keyword suggestion completed, tokens: {tokens_used}")

            keywords = self._validate_output(result, max_keywords)
            return keywords

        except Exception as e:
            self._logger.exception(f"Keyword suggestion failed: {e}")
            return []

    def _build_messages(
        self, *, description: str, max_keywords: int
    ) -> list[dict[str, str]]:
        """构建 messages（支持文件化 prompt）。"""
        if settings.PROMPTS_ENABLED:
            rendered = self._prompt_store.render_messages(
                name="goals.keyword_suggestion",
                variables={
                    "description": description,
                    "max_keywords": max_keywords,
                },
            )
            return [{"role": m.role, "content": m.content} for m in rendered]

        # 回退：使用代码内 prompt（仅用于紧急回滚）
        user_prompt = self._build_user_prompt(description, max_keywords)
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def _build_user_prompt(self, description: str, max_keywords: int) -> str:
        """构建用户 prompt（回退用）。"""
        return f"""请根据以下目标描述，提取 {max_keywords} 个最相关的关键词用于追踪相关信息。

目标描述：
{description}

请提取关键词："""

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
            temperature=0.5,
            max_tokens=200,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0

        return content, tokens_used

    def _validate_output(self, raw_output: str, max_keywords: int) -> list[str]:
        """验证并处理输出。"""
        try:
            data = json.loads(raw_output)
            output = KeywordSuggestionOutput(**data)

            # 清理和限制关键词
            keywords = [kw.strip() for kw in output.keywords if kw and kw.strip()][
                :max_keywords
            ]

            return keywords

        except json.JSONDecodeError as e:
            self._logger.warning(f"JSON decode error: {e}")
            return []
        except ValidationError as e:
            self._logger.warning(f"Schema validation error: {e}")
            return []


class MockKeywordSuggestionService:
    """Mock 关键词建议服务（用于测试）。"""

    def __init__(self, default_keywords: list[str] | None = None):
        self.default_keywords = default_keywords or ["AI", "大模型", "技术"]

    async def suggest_keywords(
        self,
        description: str,
        max_keywords: int = 5,
    ) -> list[str]:
        """返回 mock 结果。"""
        return self.default_keywords[:max_keywords]
