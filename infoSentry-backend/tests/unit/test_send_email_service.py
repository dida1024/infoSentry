"""目标邮件发送服务单元测试。

测试覆盖：
- GoalSendEmailService.send_immediately 各种场景
- 速率限制检查
- Dry run 预览模式
- 推送决策创建与更新
- 错误处理（Goal 不存在、无邮箱、超出限制等）
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.modules.goals.application.send_email_service import (
    EmailServiceUnavailableError,
    GoalNotFoundError,
    GoalSendEmailService,
    NoItemsToSendError,
    RateLimitExceededError,
    SendEmailResult,
    UserNoEmailError,
)
from src.modules.goals.interfaces.schemas import (
    EmailPreviewData,
    SendGoalEmailRequest,
    SendGoalEmailResponse,
)
from src.modules.items.domain.entities import GoalItemMatch, RankMode
from src.modules.push.application.email_service import EmailResult
from src.modules.push.domain.entities import (
    PushChannel,
    PushDecision,
    PushDecisionRecord,
    PushStatus,
)

pytestmark = pytest.mark.anyio


# ============================================
# 测试辅助工厂函数
# ============================================


def _make_mock_goal(
    goal_id: str = "goal-1",
    user_id: str = "user-1",
    name: str = "AI 动态",
) -> MagicMock:
    """创建 Mock Goal。"""
    goal = MagicMock()
    goal.id = goal_id
    goal.user_id = user_id
    goal.name = name
    return goal


def _make_mock_user(
    user_id: str = "user-1",
    email: str = "test@example.com",
) -> MagicMock:
    """创建 Mock User。"""
    user = MagicMock()
    user.id = user_id
    user.email = email
    return user


def _make_mock_item(
    item_id: str = "item-1",
    title: str = "Test News",
    snippet: str = "Test content",
    url: str = "https://example.com/news/1",
    source_id: str = "source-1",
) -> MagicMock:
    """创建 Mock Item。"""
    item = MagicMock()
    item.id = item_id
    item.title = title
    item.snippet = snippet
    item.url = url
    item.source_id = source_id
    item.published_at = datetime.now(UTC)
    return item


def _make_mock_source(
    source_id: str = "source-1",
    name: str = "Test Source",
) -> MagicMock:
    """创建 Mock Source。"""
    source = MagicMock()
    source.id = source_id
    source.name = name
    return source


def _make_goal_item_match(
    goal_id: str = "goal-1",
    item_id: str = "item-1",
    score: float = 0.85,
) -> GoalItemMatch:
    """创建 GoalItemMatch 实体。"""
    return GoalItemMatch(
        id=f"match-{item_id}",
        goal_id=goal_id,
        item_id=item_id,
        match_score=score,
        features_json={"cosine_similarity": score},
        reasons_json={"summary": f"匹配分数: {score:.2f}"},
        computed_at=datetime.now(UTC),
    )


def _make_push_decision(
    goal_id: str,
    item_id: str,
    status: PushStatus,
) -> PushDecisionRecord:
    """创建 PushDecisionRecord 实体。"""
    return PushDecisionRecord(
        goal_id=goal_id,
        item_id=item_id,
        decision=PushDecision.IMMEDIATE,
        status=status,
        channel=PushChannel.EMAIL,
        reason_json={"test": True},
        decided_at=datetime.now(UTC),
    )


def _create_service_with_mocks() -> tuple[GoalSendEmailService, dict]:
    """创建带 Mock 依赖的服务实例。"""
    mocks = {
        "goal_repo": AsyncMock(),
        "user_repo": AsyncMock(),
        "match_repo": AsyncMock(),
        "item_repo": AsyncMock(),
        "source_repo": AsyncMock(),
        "decision_repo": AsyncMock(),
        "redis": AsyncMock(),
        "email_service": MagicMock(),
    }
    mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)

    service = GoalSendEmailService(
        goal_repo=mocks["goal_repo"],
        user_repo=mocks["user_repo"],
        match_repo=mocks["match_repo"],
        item_repo=mocks["item_repo"],
        source_repo=mocks["source_repo"],
        decision_repo=mocks["decision_repo"],
        redis_client=mocks["redis"],
        email_service=mocks["email_service"],
    )

    return service, mocks


# ============================================
# Schema 验证测试
# ============================================


class TestSendGoalEmailRequest:
    """SendGoalEmailRequest Schema 测试。"""

    def test_default_values(self) -> None:
        """测试默认值。"""
        request = SendGoalEmailRequest()

        assert request.since is None
        assert request.min_score == 0.0
        assert request.limit == 20
        assert request.include_sent is False
        assert request.dry_run is False

    def test_custom_values(self) -> None:
        """测试自定义值。"""
        since = datetime.now(UTC) - timedelta(hours=12)
        request = SendGoalEmailRequest(
            since=since,
            min_score=0.7,
            limit=10,
            include_sent=True,
            dry_run=True,
        )

        assert request.since == since
        assert request.min_score == 0.7
        assert request.limit == 10
        assert request.include_sent is True
        assert request.dry_run is True

    def test_min_score_validation(self) -> None:
        """测试分数范围验证。"""
        # 有效范围
        request = SendGoalEmailRequest(min_score=0.5)
        assert request.min_score == 0.5

        # 无效范围
        with pytest.raises(ValueError):
            SendGoalEmailRequest(min_score=-0.1)

        with pytest.raises(ValueError):
            SendGoalEmailRequest(min_score=1.5)

    def test_limit_validation(self) -> None:
        """测试限制数量验证。"""
        # 有效范围
        request = SendGoalEmailRequest(limit=30)
        assert request.limit == 30

        # 无效范围
        with pytest.raises(ValueError):
            SendGoalEmailRequest(limit=0)

        with pytest.raises(ValueError):
            SendGoalEmailRequest(limit=100)


class TestSendGoalEmailResponse:
    """SendGoalEmailResponse Schema 测试。"""

    def test_success_response(self) -> None:
        """测试成功响应。"""
        response = SendGoalEmailResponse(
            success=True,
            email_sent=True,
            items_count=5,
            decisions_updated=5,
            preview=None,
            message="邮件发送成功",
        )

        assert response.success is True
        assert response.email_sent is True
        assert response.items_count == 5
        assert response.decisions_updated == 5
        assert response.preview is None

    def test_preview_response(self) -> None:
        """测试预览响应。"""
        preview = EmailPreviewData(
            subject="[手动] 目标推送: AI 动态",
            to_email="test@example.com",
            item_titles=["News 1", "News 2"],
        )
        response = SendGoalEmailResponse(
            success=True,
            email_sent=False,
            items_count=2,
            decisions_updated=0,
            preview=preview,
            message="预览生成成功",
        )

        assert response.email_sent is False
        assert response.preview is not None
        assert response.preview.subject == "[手动] 目标推送: AI 动态"
        assert len(response.preview.item_titles) == 2


class TestEmailPreviewData:
    """EmailPreviewData Schema 测试。"""

    def test_valid_preview(self) -> None:
        """测试有效预览数据。"""
        preview = EmailPreviewData(
            subject="Test Subject",
            to_email="user@example.com",
            item_titles=["Title 1", "Title 2", "Title 3"],
        )

        assert preview.subject == "Test Subject"
        assert preview.to_email == "user@example.com"
        assert len(preview.item_titles) == 3


# ============================================
# SendEmailResult 测试
# ============================================


class TestSendEmailResult:
    """SendEmailResult 测试。"""

    def test_success_result(self) -> None:
        """测试成功结果。"""
        result = SendEmailResult(
            success=True,
            email_sent=True,
            items_count=3,
            decisions_updated=3,
            message="邮件发送成功",
        )

        assert result.success is True
        assert result.email_sent is True
        assert result.items_count == 3

    def test_preview_result(self) -> None:
        """测试预览结果。"""
        result = SendEmailResult(
            success=True,
            email_sent=False,
            items_count=2,
            decisions_updated=0,
            preview_subject="Test Subject",
            preview_to_email="test@example.com",
            preview_item_titles=["Title 1", "Title 2"],
            message="预览生成成功",
        )

        assert result.email_sent is False
        assert result.preview_subject is not None
        assert len(result.preview_item_titles) == 2


# ============================================
# GoalSendEmailService 测试
# ============================================


class TestGoalSendEmailService:
    """GoalSendEmailService 测试。"""

    async def test_send_immediately_success(self) -> None:
        """测试成功发送邮件。"""
        service, mocks = _create_service_with_mocks()

        # 设置 Mock 返回值
        goal = _make_mock_goal()
        user = _make_mock_user()
        item = _make_mock_item()
        source = _make_mock_source()
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(
            return_value=[(match, None)]  # 没有现有决策
        )
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["redis"].rate_limit_check = AsyncMock(return_value=(True, 1))
        mocks["email_service"].is_available = MagicMock(return_value=True)
        mocks["email_service"].send_email = AsyncMock(
            return_value=EmailResult(success=True, message_id="msg-123")
        )
        mocks["decision_repo"].create = AsyncMock()

        # 执行
        result = await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
        )

        # 验证
        assert result.success is True
        assert result.email_sent is True
        assert result.items_count == 1
        assert result.decisions_updated == 1
        mocks["email_service"].send_email.assert_called_once()
        mocks["decision_repo"].create.assert_called_once()
        mocks["redis"].rate_limit_check.assert_called_once()

    async def test_send_immediately_goal_not_found(self) -> None:
        """测试 Goal 不存在。"""
        service, mocks = _create_service_with_mocks()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=None)

        with pytest.raises(GoalNotFoundError):
            await service.send_immediately(
                goal_id="nonexistent",
                user_id="user-1",
            )

    async def test_send_immediately_goal_access_denied(self) -> None:
        """测试 Goal 访问被拒绝（不是所有者）。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal(user_id="other-user")
        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)

        with pytest.raises(GoalNotFoundError):
            await service.send_immediately(
                goal_id="goal-1",
                user_id="user-1",  # 不是 goal 的所有者
            )

    async def test_send_immediately_rate_limit_exceeded(self) -> None:
        """测试速率限制超出。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=5)

        with pytest.raises(RateLimitExceededError):
            await service.send_immediately(
                goal_id="goal-1",
                user_id="user-1",
            )
        mocks["redis"].rate_limit_check.assert_not_called()

    async def test_send_immediately_user_no_email(self) -> None:
        """测试用户无邮箱。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user(email=None)

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)

        with pytest.raises(UserNoEmailError):
            await service.send_immediately(
                goal_id="goal-1",
                user_id="user-1",
            )
        mocks["redis"].rate_limit_check.assert_not_called()

    async def test_send_immediately_no_items(self) -> None:
        """测试没有待发送项目。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=[])

        with pytest.raises(NoItemsToSendError):
            await service.send_immediately(
                goal_id="goal-1",
                user_id="user-1",
            )
        mocks["redis"].rate_limit_check.assert_not_called()

    async def test_send_immediately_dry_run(self) -> None:
        """测试 Dry Run 预览模式。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()
        item = _make_mock_item()
        source = _make_mock_source()
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=[(match, None)])
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)
        # Dry run 不检查速率限制
        mocks["redis"].rate_limit_check = AsyncMock(return_value=(True, 1))

        # 执行 dry run
        result = await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
            dry_run=True,
        )

        # 验证
        assert result.success is True
        assert result.email_sent is False
        assert result.items_count == 1
        assert result.decisions_updated == 0
        assert result.preview_subject is not None
        assert "[手动]" in result.preview_subject
        assert result.preview_to_email == "test@example.com"
        assert len(result.preview_item_titles) == 1

        # 确保没有实际发送
        mocks["email_service"].send_email.assert_not_called()
        mocks["decision_repo"].create.assert_not_called()
        mocks["redis"].get_rate_limit_count.assert_not_called()
        mocks["redis"].rate_limit_check.assert_not_called()

    async def test_send_immediately_email_service_unavailable(self) -> None:
        """测试邮件服务不可用。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()
        item = _make_mock_item()
        source = _make_mock_source()
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=[(match, None)])
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["email_service"].is_available = MagicMock(return_value=False)

        with pytest.raises(EmailServiceUnavailableError):
            await service.send_immediately(
                goal_id="goal-1",
                user_id="user-1",
            )
        mocks["redis"].rate_limit_check.assert_not_called()

    async def test_send_immediately_email_send_failure(self) -> None:
        """测试邮件发送失败。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()
        item = _make_mock_item()
        source = _make_mock_source()
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=[(match, None)])
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["email_service"].is_available = MagicMock(return_value=True)
        mocks["email_service"].send_email = AsyncMock(
            return_value=EmailResult(success=False, error="SMTP Error")
        )

        # 执行
        result = await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
        )

        # 验证 - 失败但不抛异常
        assert result.success is False
        assert result.email_sent is False
        # 服务返回用户友好的消息，不暴露内部错误详情
        assert "邮件发送失败" in result.message

        # 确保没有更新决策
        mocks["decision_repo"].create.assert_not_called()
        mocks["decision_repo"].batch_update_status.assert_not_called()
        mocks["redis"].rate_limit_check.assert_not_called()

    async def test_send_immediately_with_existing_decision(self) -> None:
        """测试更新现有决策。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()
        item = _make_mock_item()
        source = _make_mock_source()
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        # 有现有决策 ID
        service._list_matches_with_decisions = AsyncMock(
            return_value=[(match, "existing-decision-id")]
        )
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["redis"].rate_limit_check = AsyncMock(return_value=(True, 1))
        mocks["email_service"].is_available = MagicMock(return_value=True)
        mocks["email_service"].send_email = AsyncMock(
            return_value=EmailResult(success=True, message_id="msg-123")
        )
        mocks["decision_repo"].batch_update_status = AsyncMock()

        # 执行
        result = await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
        )

        # 验证 - 更新现有决策而不是创建新的
        assert result.success is True
        assert result.decisions_updated == 1
        mocks["decision_repo"].batch_update_status.assert_called_once()
        mocks["decision_repo"].create.assert_not_called()
        mocks["redis"].rate_limit_check.assert_called_once()

    async def test_send_immediately_multiple_items(self) -> None:
        """测试发送多个项目。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()

        # 创建多个匹配
        matches = [(_make_goal_item_match(item_id=f"item-{i}"), None) for i in range(3)]
        items = {f"item-{i}": _make_mock_item(item_id=f"item-{i}") for i in range(3)}
        source = _make_mock_source()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=matches)
        mocks["item_repo"].get_by_id = AsyncMock(side_effect=lambda id: items.get(id))
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["redis"].rate_limit_check = AsyncMock(return_value=(True, 1))
        mocks["email_service"].is_available = MagicMock(return_value=True)
        mocks["email_service"].send_email = AsyncMock(
            return_value=EmailResult(success=True, message_id="msg-123")
        )
        mocks["decision_repo"].create = AsyncMock()

        # 执行
        result = await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
        )

        # 验证
        assert result.success is True
        assert result.items_count == 3
        assert result.decisions_updated == 3
        assert mocks["decision_repo"].create.call_count == 3
        mocks["redis"].rate_limit_check.assert_called_once()

    async def test_send_immediately_with_filters(self) -> None:
        """测试带过滤参数的发送。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()
        item = _make_mock_item()
        source = _make_mock_source()
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=[(match, None)])
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)
        mocks["redis"].get_rate_limit_count = AsyncMock(return_value=0)
        mocks["redis"].rate_limit_check = AsyncMock(return_value=(True, 1))
        mocks["email_service"].is_available = MagicMock(return_value=True)
        mocks["email_service"].send_email = AsyncMock(
            return_value=EmailResult(success=True, message_id="msg-123")
        )
        mocks["decision_repo"].create = AsyncMock()

        since = datetime.now(UTC) - timedelta(hours=6)

        # 执行
        await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
            since=since,
            min_score=0.7,
            limit=10,
            include_sent=True,
        )

        # 验证过滤参数传递
        service._list_matches_with_decisions.assert_called_once_with(
            goal_id="goal-1",
            min_score=0.7,
            since=since,
            limit=10,
            include_sent=True,
        )
        mocks["redis"].rate_limit_check.assert_called_once()

    async def test_list_matches_with_decisions_excludes_sent(self) -> None:
        """测试默认排除已 SENT 决策。"""
        service, mocks = _create_service_with_mocks()

        match_sent = _make_goal_item_match(item_id="item-sent")
        match_pending = _make_goal_item_match(item_id="item-pending")
        match_none = _make_goal_item_match(item_id="item-none")
        matches = [match_sent, match_pending, match_none]

        mocks["match_repo"].list_by_goal = AsyncMock(
            return_value=(matches, len(matches))
        )
        decision_sent = _make_push_decision(
            goal_id="goal-1",
            item_id="item-sent",
            status=PushStatus.SENT,
        )
        decision_pending = _make_push_decision(
            goal_id="goal-1",
            item_id="item-pending",
            status=PushStatus.PENDING,
        )
        mocks["decision_repo"].list_by_goal_and_item_ids = AsyncMock(
            return_value=[decision_sent, decision_pending]
        )

        result = await service._list_matches_with_decisions(
            goal_id="goal-1",
            min_score=0.0,
            since=None,
            limit=10,
            include_sent=False,
        )

        assert result == [
            (match_pending, decision_pending.id),
            (match_none, None),
        ]
        mocks["match_repo"].list_by_goal.assert_called_once_with(
            goal_id="goal-1",
            min_score=0.0,
            since=None,
            rank_mode=RankMode.MATCH_SCORE,
            page=1,
            page_size=20,
        )
        mocks["decision_repo"].list_by_goal_and_item_ids.assert_called_once_with(
            goal_id="goal-1",
            item_ids=["item-sent", "item-pending", "item-none"],
        )

    async def test_list_matches_with_decisions_include_sent(self) -> None:
        """测试 include_sent=True 返回全部决策。"""
        service, mocks = _create_service_with_mocks()

        match_sent = _make_goal_item_match(item_id="item-sent")
        match_pending = _make_goal_item_match(item_id="item-pending")
        match_none = _make_goal_item_match(item_id="item-none")
        matches = [match_sent, match_pending, match_none]

        mocks["match_repo"].list_by_goal = AsyncMock(
            return_value=(matches, len(matches))
        )
        decision_sent = _make_push_decision(
            goal_id="goal-1",
            item_id="item-sent",
            status=PushStatus.SENT,
        )
        decision_pending = _make_push_decision(
            goal_id="goal-1",
            item_id="item-pending",
            status=PushStatus.PENDING,
        )
        mocks["decision_repo"].list_by_goal_and_item_ids = AsyncMock(
            return_value=[decision_sent, decision_pending]
        )

        result = await service._list_matches_with_decisions(
            goal_id="goal-1",
            min_score=0.0,
            since=None,
            limit=10,
            include_sent=True,
        )

        assert result == [
            (match_sent, decision_sent.id),
            (match_pending, decision_pending.id),
            (match_none, None),
        ]


# ============================================
# 集成场景测试
# ============================================


class TestSendEmailIntegrationScenarios:
    """集成场景测试。"""

    async def test_dry_run_does_not_count_rate_limit(self) -> None:
        """测试 Dry run 不计入速率限制。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal()
        user = _make_mock_user()
        item = _make_mock_item()
        source = _make_mock_source()
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=[(match, None)])
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)

        # Dry run
        await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
            dry_run=True,
        )

        # 速率限制不应被调用
        mocks["redis"].get_rate_limit_count.assert_not_called()
        mocks["redis"].rate_limit_check.assert_not_called()

    async def test_email_template_contains_correct_info(self) -> None:
        """测试邮件模板包含正确信息。"""
        service, mocks = _create_service_with_mocks()

        goal = _make_mock_goal(name="AI 投融资追踪")
        user = _make_mock_user(email="investor@example.com")
        item = _make_mock_item(title="OpenAI 融资 10 亿美元")
        source = _make_mock_source(name="TechCrunch")
        match = _make_goal_item_match()

        mocks["goal_repo"].get_by_id = AsyncMock(return_value=goal)
        mocks["user_repo"].get_by_id = AsyncMock(return_value=user)
        service._list_matches_with_decisions = AsyncMock(return_value=[(match, None)])
        mocks["item_repo"].get_by_id = AsyncMock(return_value=item)
        mocks["source_repo"].get_by_id = AsyncMock(return_value=source)

        # Dry run 预览
        result = await service.send_immediately(
            goal_id="goal-1",
            user_id="user-1",
            dry_run=True,
        )

        # 验证预览内容
        assert "AI 投融资追踪" in result.preview_subject
        assert result.preview_to_email == "investor@example.com"
        assert "OpenAI 融资 10 亿美元" in result.preview_item_titles
