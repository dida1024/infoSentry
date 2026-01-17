"""目标草稿生成服务单元测试。

测试覆盖：
- GoalDraftOutput Schema 验证
- GoalDraftService 输入校验
- LLM 调用 Mock 测试
- 输出清洗/去重/裁剪
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.config import settings
from src.core.infrastructure.ai.prompting.file_store import FileSystemPromptStore
from src.modules.goals.application.goal_draft_service import (
    GoalDraftGenerationError,
    GoalDraftNotAvailableError,
    GoalDraftOutput,
    GoalDraftService,
)

pytestmark = pytest.mark.anyio


def _prompt_store() -> FileSystemPromptStore:
    base_dir = Path(__file__).resolve().parents[2] / "prompts"
    return FileSystemPromptStore(base_dir=base_dir)


class TestGoalDraftOutput:
    def test_default_values(self) -> None:
        output = GoalDraftOutput()
        assert output.name == ""
        assert output.description == ""
        assert output.keywords == []

    def test_valid_output(self) -> None:
        output = GoalDraftOutput(
            name="AI 投融资观察",
            description="关注 AI 行业投融资与头部公司动态。",
            keywords=["AI 投融资", "OpenAI", "大模型"],
        )
        assert output.name == "AI 投融资观察"
        assert "关注" in output.description
        assert output.keywords == ["AI 投融资", "OpenAI", "大模型"]


class TestGoalDraftService:
    async def test_llm_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "LLM_ENABLED", False)
        service = GoalDraftService(
            prompt_store=_prompt_store(), openai_client=AsyncMock()
        )
        with pytest.raises(GoalDraftNotAvailableError):
            await service.generate_draft("关注 AI 行业投融资")

    async def test_short_intent_raises_value_error(self) -> None:
        service = GoalDraftService(
            prompt_store=_prompt_store(), openai_client=AsyncMock()
        )
        with pytest.raises(ValueError):
            await service.generate_draft("太短")

    def test_build_user_prompt(self) -> None:
        service = GoalDraftService(
            prompt_store=_prompt_store(), openai_client=AsyncMock()
        )
        prompt = service._build_user_prompt(intent="关注 AI 芯片", max_keywords=5)
        assert "关注 AI 芯片" in prompt
        assert "5" in prompt

    async def test_generate_draft_with_mock_client(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"name":"AI 投融资观察","description":"关注 AI 行业投融资、头部公司与基金动向。",'
                        '"keywords":["AI 投融资","OpenAI","Anthropic","融资","监管政策"]}'
                    )
                )
            )
        ]
        mock_response.usage = MagicMock(total_tokens=80)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = GoalDraftService(
            prompt_store=_prompt_store(), openai_client=mock_client
        )
        result = await service.generate_draft(
            intent="关注 AI 行业投融资", max_keywords=5
        )

        assert result.name == "AI 投融资观察"
        assert "关注" in result.description
        assert len(result.keywords) <= 5
        assert "AI 投融资" in result.keywords
        mock_client.chat.completions.create.assert_called_once()

    async def test_generate_draft_api_failure_raises(self) -> None:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        service = GoalDraftService(
            prompt_store=_prompt_store(), openai_client=mock_client
        )
        with pytest.raises(GoalDraftGenerationError):
            await service.generate_draft(intent="关注 AI 行业投融资", max_keywords=5)

    async def test_generate_draft_keyword_dedup_and_trim(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=(
                        '{"name":"  AI  目标  ","description":"  关注：AI  \\n  ",'
                        '"keywords":["AI","AI","  ","超超超超超超超超超超超超超超超超超超超超超超超超超超超超超","大模型"]}'
                    )
                )
            )
        ]
        mock_response.usage = MagicMock(total_tokens=60)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service = GoalDraftService(
            prompt_store=_prompt_store(), openai_client=mock_client
        )
        result = await service.generate_draft(intent="关注 AI", max_keywords=5)

        # name 去掉换行/多余空格
        assert "\n" not in result.name
        assert result.name.strip() == result.name

        # keywords 去重/过滤空白/裁剪长度
        assert result.keywords.count("AI") == 1
        assert all(k.strip() for k in result.keywords)
        assert all(len(k) <= 30 for k in result.keywords)
