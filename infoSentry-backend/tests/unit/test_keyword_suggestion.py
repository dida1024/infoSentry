"""关键词建议服务单元测试。

测试覆盖：
- KeywordSuggestionService 输入验证
- KeywordSuggestionOutput Schema 验证
- LLM 调用 Mock 测试
- 错误处理
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.infrastructure.ai.prompting.file_store import FileSystemPromptStore
from src.modules.goals.application.keyword_service import (
    KeywordSuggestionOutput,
    KeywordSuggestionService,
    MockKeywordSuggestionService,
)

# 使用 anyio 作为异步测试后端
pytestmark = pytest.mark.anyio


def _prompt_store() -> FileSystemPromptStore:
    base_dir = Path(__file__).resolve().parents[2] / "prompts"
    return FileSystemPromptStore(base_dir=base_dir)


# ============================================
# KeywordSuggestionOutput 测试
# ============================================


class TestKeywordSuggestionOutput:
    """KeywordSuggestionOutput Schema 测试。"""

    def test_valid_output(self):
        """测试有效输出。"""
        output = KeywordSuggestionOutput(
            keywords=["AI", "大模型", "GPT"]
        )
        assert output.keywords == ["AI", "大模型", "GPT"]

    def test_empty_keywords(self):
        """测试空关键词列表。"""
        output = KeywordSuggestionOutput(keywords=[])
        assert output.keywords == []

    def test_default_keywords(self):
        """测试默认值。"""
        output = KeywordSuggestionOutput()
        assert output.keywords == []


# ============================================
# KeywordSuggestionService 测试
# ============================================


class TestKeywordSuggestionService:
    """KeywordSuggestionService 测试。"""

    async def test_short_description_returns_empty(self):
        """测试过短描述返回空列表。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        result = await service.suggest_keywords("太短")
        assert result == []

    async def test_empty_description_returns_empty(self):
        """测试空描述返回空列表。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        result = await service.suggest_keywords("")
        assert result == []

    async def test_whitespace_description_returns_empty(self):
        """测试纯空格描述返回空列表。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        result = await service.suggest_keywords("         ")
        assert result == []

    def test_build_user_prompt(self):
        """测试用户 prompt 构建。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        prompt = service._build_user_prompt(
            description="追踪 AI 领域的技术突破",
            max_keywords=5,
        )
        assert "追踪 AI 领域的技术突破" in prompt
        assert "5" in prompt

    def test_validate_output_valid_json(self):
        """测试有效 JSON 验证。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        result = service._validate_output(
            '{"keywords": ["AI", "机器学习", "深度学习"]}',
            max_keywords=5,
        )
        assert result == ["AI", "机器学习", "深度学习"]

    def test_validate_output_exceeds_max(self):
        """测试超过最大数量时截断。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        result = service._validate_output(
            '{"keywords": ["A", "B", "C", "D", "E", "F"]}',
            max_keywords=3,
        )
        assert len(result) == 3
        assert result == ["A", "B", "C"]

    def test_validate_output_invalid_json(self):
        """测试无效 JSON 返回空列表。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        result = service._validate_output("not json", max_keywords=5)
        assert result == []

    def test_validate_output_missing_keywords(self):
        """测试缺少 keywords 字段。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        # KeywordSuggestionOutput 有默认值，所以会返回空列表
        result = service._validate_output('{}', max_keywords=5)
        assert result == []

    def test_validate_output_empty_strings_filtered(self):
        """测试空字符串被过滤。"""
        service = KeywordSuggestionService(prompt_store=_prompt_store())
        result = service._validate_output(
            '{"keywords": ["AI", "", "  ", "GPT"]}',
            max_keywords=5,
        )
        assert result == ["AI", "GPT"]

    async def test_suggest_keywords_with_mock_client(self):
        """测试使用 Mock OpenAI 客户端。"""
        # 创建 Mock 响应
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"keywords": ["AI", "大模型", "GPT", "Claude"]}'
                )
            )
        ]
        mock_response.usage = MagicMock(total_tokens=50)

        # 创建 Mock 客户端
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = KeywordSuggestionService(prompt_store=_prompt_store(), openai_client=mock_client)
        result = await service.suggest_keywords(
            description="追踪 AI 领域的重要新闻和技术突破",
            max_keywords=5,
        )

        assert result == ["AI", "大模型", "GPT", "Claude"]
        mock_client.chat.completions.create.assert_called_once()

    async def test_suggest_keywords_api_failure(self):
        """测试 API 调用失败返回空列表。"""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        service = KeywordSuggestionService(prompt_store=_prompt_store(), openai_client=mock_client)
        result = await service.suggest_keywords(
            description="追踪 AI 领域的重要新闻和技术突破",
            max_keywords=5,
        )

        assert result == []

    async def test_suggest_keywords_max_keywords_limit(self):
        """测试最大关键词数量限制。"""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"keywords": ["A", "B", "C", "D", "E", "F", "G"]}'
                )
            )
        ]
        mock_response.usage = MagicMock(total_tokens=30)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = KeywordSuggestionService(prompt_store=_prompt_store(), openai_client=mock_client)
        result = await service.suggest_keywords(
            description="追踪技术领域的新闻动态",
            max_keywords=3,
        )

        assert len(result) == 3


# ============================================
# MockKeywordSuggestionService 测试
# ============================================


class TestMockKeywordSuggestionService:
    """MockKeywordSuggestionService 测试。"""

    async def test_default_keywords(self):
        """测试默认关键词。"""
        service = MockKeywordSuggestionService()
        result = await service.suggest_keywords(
            description="任意描述",
            max_keywords=5,
        )
        assert result == ["AI", "大模型", "技术"]

    async def test_custom_keywords(self):
        """测试自定义关键词。"""
        service = MockKeywordSuggestionService(
            default_keywords=["Python", "FastAPI", "异步"]
        )
        result = await service.suggest_keywords(
            description="任意描述",
            max_keywords=5,
        )
        assert result == ["Python", "FastAPI", "异步"]

    async def test_respects_max_keywords(self):
        """测试遵循最大关键词限制。"""
        service = MockKeywordSuggestionService(
            default_keywords=["A", "B", "C", "D", "E"]
        )
        result = await service.suggest_keywords(
            description="任意描述",
            max_keywords=2,
        )
        assert len(result) == 2
        assert result == ["A", "B"]
