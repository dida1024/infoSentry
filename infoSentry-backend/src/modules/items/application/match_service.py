"""匹配计算服务。

计算 Item 与 Goal 的匹配分数，支持：
- 语义相似度（cosine similarity）
- priority_terms 命中
- 时效性（recency）
- 来源可信度（source_trust）
- 可解释的 match_reasons
"""

import hashlib
import inspect
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger
from openai import AsyncOpenAI

from src.core.config import settings
from src.core.domain.events import EventBus
from src.core.domain.ports.business_logger import BusinessEventLogger
from src.core.domain.ports.kv import KVClient

if TYPE_CHECKING:
    pass
from src.modules.goals.domain.entities import (
    Goal,
    GoalPriorityTerm,
    PriorityMode,
    TermType,
)
from src.modules.goals.domain.repository import (
    GoalPriorityTermRepository,
    GoalRepository,
)
from src.modules.items.domain.entities import GoalItemMatch, Item
from src.modules.items.domain.events import MatchComputedEvent
from src.modules.items.domain.repository import GoalItemMatchRepository, ItemRepository
from src.modules.push.domain.entities import FeedbackType
from src.modules.push.domain.repository import (
    BlockedSourceRepository,
    ItemFeedbackRepository,
)


@dataclass
class MatchFeatures:
    """匹配特征值。"""

    cosine_similarity: float = 0.0  # 语义相似度 [0, 1]
    term_hits: int = 0  # priority_terms 命中数
    term_hit_details: list[dict] = field(default_factory=list)  # 命中详情
    negative_hits: int = 0  # negative_terms 命中数
    negative_hit_details: list[dict] = field(default_factory=list)  # 负面命中详情
    recency_score: float = 0.0  # 时效性分数 [0, 1]
    source_trust: float = 0.8  # 来源可信度 [0, 1]，默认 0.8
    # 反馈信号
    feedback_boost: float = 0.0  # 反馈调整值 [-0.2, 0.2]
    source_like_ratio: float | None = None  # 该来源的好评率
    has_source_dislike: bool = False  # 该来源是否被 dislike 过

    def to_dict(self) -> dict[str, Any]:
        return {
            "cosine_similarity": round(self.cosine_similarity, 4),
            "term_hits": self.term_hits,
            "term_hit_details": self.term_hit_details,
            "negative_hits": self.negative_hits,
            "negative_hit_details": self.negative_hit_details,
            "recency_score": round(self.recency_score, 4),
            "source_trust": round(self.source_trust, 4),
            "feedback_boost": round(self.feedback_boost, 4),
            "source_like_ratio": round(self.source_like_ratio, 4)
            if self.source_like_ratio is not None
            else None,
            "has_source_dislike": self.has_source_dislike,
        }


@dataclass
class MatchReasons:
    """匹配原因（可解释性）。"""

    summary: str = ""  # 简短摘要
    evidence: list[dict] = field(default_factory=list)  # 证据列表
    is_blocked: bool = False  # 是否被阻止
    block_reason: str | None = None  # 阻止原因

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "evidence": self.evidence,
            "is_blocked": self.is_blocked,
            "block_reason": self.block_reason,
        }


@dataclass
class MatchResult:
    """匹配结果。"""

    goal_id: str
    item_id: str
    score: float
    features: MatchFeatures
    reasons: MatchReasons

    @property
    def is_valid(self) -> bool:
        """是否是有效匹配（未被阻止）。"""
        return not self.reasons.is_blocked


class MatchService:
    """匹配计算服务。

    职责：
    - 计算 Item 与所有活跃 Goal 的匹配分数
    - 生成可解释的匹配原因
    - 写入 goal_item_matches
    - 发布 MatchComputed 事件
    """

    # 权重配置（已废弃，保留用于向后兼容）
    WEIGHT_COSINE = 0.40  # 语义相似度权重
    WEIGHT_TERMS = 0.30  # 词条命中权重
    WEIGHT_RECENCY = 0.20  # 时效性权重
    WEIGHT_SOURCE = 0.10  # 来源可信度权重

    # 混合评分策略配置
    # 语义相似度阈值
    SEMANTIC_HIGH_THRESHOLD = 0.75  # 高语义相似度阈值
    SEMANTIC_MEDIUM_THRESHOLD = 0.60  # 中等语义相似度阈值

    # 基础分配置
    BASE_SCORE_HIGH_SEMANTIC = 0.60  # 高语义相似度基础分
    BASE_SCORE_MEDIUM_SEMANTIC_WITH_TERMS = 0.50  # 中等语义+关键词基础分
    BASE_SCORE_MEDIUM_SEMANTIC_NO_TERMS = 0.30  # 中等语义无关键词基础分
    BASE_SCORE_LOW_SEMANTIC = 0.30  # 低语义相似度基础分

    # 语义加分系数
    SEMANTIC_BONUS_HIGH = 0.20  # 高语义相似度加分系数
    SEMANTIC_BONUS_MEDIUM_WITH_TERMS = 0.15  # 中等语义+关键词加分系数
    SEMANTIC_BONUS_MEDIUM_NO_TERMS = 0.20  # 中等语义无关键词加分系数
    SEMANTIC_BONUS_LOW = 0.30  # 低语义相似度加分系数

    # 关键词加分配置
    TERM_BONUS_PER_HIT_HIGH = 0.05  # 高语义时每个关键词加分
    TERM_BONUS_MAX_HIGH = 0.15  # 高语义时关键词最大加分
    TERM_BONUS_PER_HIT_MEDIUM = 0.10  # 中等语义时每个关键词加分
    TERM_BONUS_MAX_MEDIUM = 0.25  # 中等语义时关键词最大加分
    TERM_BONUS_PER_HIT_LOW = 0.15  # 低语义时每个关键词加分
    TERM_BONUS_MAX_LOW = 0.30  # 低语义时关键词最大加分

    # 时效性和来源权重
    RECENCY_WEIGHT = 0.10  # 时效性权重
    SOURCE_WEIGHT = 0.05  # 来源可信度权重

    # 时效性配置
    RECENCY_FULL_SCORE_HOURS = 6  # 6 小时内满分
    RECENCY_HALF_SCORE_HOURS = 48  # 48 小时内半分
    RECENCY_ZERO_SCORE_DAYS = 7  # 7 天后零分

    # Goal embedding 缓存过期时间（秒）- 24小时
    GOAL_EMBEDDING_CACHE_TTL = 86400

    def __init__(
        self,
        goal_repository: GoalRepository,
        term_repository: GoalPriorityTermRepository,
        item_repository: ItemRepository,
        match_repository: GoalItemMatchRepository,
        event_bus: EventBus,
        feedback_repository: ItemFeedbackRepository | None = None,
        blocked_source_repository: BlockedSourceRepository | None = None,
        kv_client: KVClient | None = None,
        business_logger: BusinessEventLogger | None = None,
        openai_client: AsyncOpenAI | None = None,
    ):
        self.goal_repository = goal_repository
        self.term_repository = term_repository
        self.item_repository = item_repository
        self.match_repository = match_repository
        self.event_bus = event_bus
        self.feedback_repository = feedback_repository
        self.blocked_source_repository = blocked_source_repository
        self.kv_client = kv_client
        self.business_logger = business_logger
        self._openai_client = openai_client

    @property
    def openai_client(self) -> AsyncOpenAI:
        """获取 OpenAI 客户端（延迟初始化）。"""
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
            )
        return self._openai_client

    async def aclose(self) -> None:
        """关闭底层 OpenAI 客户端以避免事件循环关闭时的清理错误。"""

        if self._openai_client is not None:
            close_fn = getattr(self._openai_client, "aclose", None) or getattr(
                self._openai_client, "close", None
            )
            if close_fn is None:
                logger.debug("OpenAI client has no close method, skip closing")
            else:
                result = close_fn()
                if inspect.isawaitable(result):
                    await result
            self._openai_client = None

    async def match_item_to_goals(self, item: Item) -> list[MatchResult]:
        """将 Item 与所有活跃 Goal 进行匹配。

        Args:
            item: 要匹配的 Item

        Returns:
            匹配结果列表
        """
        # 获取所有活跃 Goal
        goals = await self.goal_repository.get_active_goals()

        if not goals:
            logger.debug("No active goals to match")
            return []

        results: list[MatchResult] = []

        for goal in goals:
            result = await self.match_item_to_goal(item, goal)
            results.append(result)

            # 保存匹配结果
            if result.score > 0:
                await self._save_match(result)

                # 发布事件
                await self.event_bus.publish(
                    MatchComputedEvent(
                        goal_id=result.goal_id,
                        item_id=result.item_id,
                        score=result.score,
                        features=result.features.to_dict(),
                    )
                )

        return results

    async def match_item_to_goal(self, item: Item, goal: Goal) -> MatchResult:
        """计算 Item 与单个 Goal 的匹配。

        Args:
            item: 要匹配的 Item
            goal: 目标 Goal

        Returns:
            匹配结果
        """
        # 获取 Goal 的 priority_terms
        terms = await self.term_repository.list_by_goal(goal.id)
        must_terms = [t for t in terms if t.term_type == TermType.MUST]
        negative_terms = [t for t in terms if t.term_type == TermType.NEGATIVE]

        # 计算各项特征
        features = MatchFeatures()

        # 1. 语义相似度（需要 embedding）
        features.cosine_similarity = await self._compute_cosine_similarity(item, goal)

        # 2. 词条命中
        text = self._get_item_text(item)
        features.term_hits, features.term_hit_details = self._check_term_hits(
            text, must_terms
        )
        features.negative_hits, features.negative_hit_details = self._check_term_hits(
            text, negative_terms
        )

        # 3. 时效性
        features.recency_score = self._compute_recency_score(item)

        # 4. 来源可信度（暂时固定，后续可扩展）
        features.source_trust = 0.8

        # 5. 反馈信号（影响后续排序）
        await self._apply_feedback_signal(features, item, goal)

        # 生成匹配原因
        reasons = self._generate_reasons(goal, item, features, must_terms)

        # 计算最终分数
        score = self._compute_final_score(goal, features, reasons)

        return MatchResult(
            goal_id=goal.id,
            item_id=item.id,
            score=score,
            features=features,
            reasons=reasons,
        )

    async def _apply_feedback_signal(
        self, features: MatchFeatures, item: Item, goal: Goal
    ) -> None:
        """应用反馈信号到特征。

        根据用户对该来源的历史反馈调整分数：
        - 如果该来源有较多 like，给予正向加分
        - 如果该来源有较多 dislike，给予负向扣分
        - 如果来源被屏蔽，标记 is_blocked
        """
        if not self.feedback_repository:
            return

        # 检查来源是否被屏蔽
        if self.blocked_source_repository:
            is_blocked = await self.blocked_source_repository.is_blocked(
                user_id=goal.user_id,
                source_id=item.source_id,
                goal_id=goal.id,
            )
            if is_blocked:
                # 来源被屏蔽，标记为负面
                features.has_source_dislike = True
                features.feedback_boost = -0.2
                logger.debug(f"Source {item.source_id} is blocked for goal {goal.id}")
                return

        # 查询该来源在该 Goal 下的反馈历史
        # 注意：这里需要按 source_id 聚合反馈，但当前的 feedback 是按 item 记录的
        # 我们可以通过查询同一来源的其他 items 的反馈来估计
        try:
            feedback_list, _ = await self.feedback_repository.list_by_goal(
                goal_id=goal.id,
                page=1,
                page_size=settings.MATCH_FEEDBACK_PAGE_SIZE,
            )

            # 统计同一来源的反馈
            source_likes = 0
            source_dislikes = 0

            # 需要获取 item 信息来检查 source_id
            for fb in feedback_list:
                fb_item = await self.item_repository.get_by_id(fb.item_id)
                if fb_item and fb_item.source_id == item.source_id:
                    if fb.feedback == FeedbackType.LIKE:
                        source_likes += 1
                    elif fb.feedback == FeedbackType.DISLIKE:
                        source_dislikes += 1

            total_feedback = source_likes + source_dislikes
            if total_feedback > 0:
                # 计算好评率
                like_ratio = source_likes / total_feedback
                features.source_like_ratio = like_ratio

                # 根据好评率调整分数
                # like_ratio = 1.0 -> boost = +0.1
                # like_ratio = 0.5 -> boost = 0
                # like_ratio = 0.0 -> boost = -0.1
                features.feedback_boost = (like_ratio - 0.5) * 0.2

                if source_dislikes > 0:
                    features.has_source_dislike = True

                logger.debug(
                    f"Feedback signal for source {item.source_id}: "
                    f"likes={source_likes}, dislikes={source_dislikes}, "
                    f"boost={features.feedback_boost:.4f}"
                )

        except Exception as e:
            logger.warning(f"Failed to apply feedback signal: {e}")

    async def _compute_cosine_similarity(self, item: Item, goal: Goal) -> float:
        """计算语义相似度。

        使用 Item 的 embedding 与 Goal 描述的 embedding 计算余弦相似度。

        Returns:
            余弦相似度 [0, 1]（映射后）
        """
        if item.embedding is None:
            logger.debug(f"Item {item.id} has no embedding, similarity=0")
            return 0.0

        # 获取 Goal 的 embedding
        goal_embedding = await self._get_goal_embedding(goal)
        if goal_embedding is None:
            logger.debug(
                f"Failed to get embedding for goal {goal.id}, using fallback=0.5"
            )
            return 0.5  # 降级：无法获取 Goal embedding 时返回基础分数

        # 计算余弦相似度
        try:
            item_emb = np.array(item.embedding)
            goal_emb = np.array(goal_embedding)

            dot_product = np.dot(item_emb, goal_emb)
            norm_product = np.linalg.norm(item_emb) * np.linalg.norm(goal_emb)

            if norm_product == 0:
                return 0.0

            # 余弦相似度范围是 [-1, 1]，映射到 [0, 1]
            cosine_sim = float(dot_product / norm_product)
            normalized_sim = (cosine_sim + 1) / 2  # [-1, 1] -> [0, 1]

            logger.debug(
                f"Cosine similarity for item={item.id}, goal={goal.id}: "
                f"raw={cosine_sim:.4f}, normalized={normalized_sim:.4f}"
            )

            return normalized_sim

        except Exception as e:
            logger.warning(f"Failed to compute cosine similarity: {e}")
            return 0.5  # 降级

    async def _get_goal_embedding(self, goal: Goal) -> list[float] | None:
        """获取 Goal 的 embedding（带缓存）。

        缓存策略：
        - 使用 Redis 缓存 Goal embedding
        - Key 包含 Goal 描述的 hash，描述变更时自动失效
        - TTL 24 小时

        Args:
            goal: Goal 实体

        Returns:
            Goal 描述的 embedding 向量，失败返回 None
        """
        # 检查是否启用 embedding
        if not settings.EMBEDDING_ENABLED:
            logger.debug("Embedding disabled, cannot get goal embedding")
            return None

        # 准备 Goal 的文本（name + description）
        goal_text = f"{goal.name}. {goal.description}"
        content_hash = hashlib.md5(goal_text.encode()).hexdigest()[:8]

        # 尝试从缓存获取
        cache_key = None
        if self.kv_client:
            cache_key = f"embedding:goal:{goal.id}:{content_hash}"
            try:
                cached = await self.kv_client.get_json(cache_key)
                if cached:
                    logger.debug(f"Goal embedding cache hit for {goal.id}")
                    return cached
            except Exception as e:
                logger.warning(f"Failed to get goal embedding from cache: {e}")

        # 生成新的 embedding
        try:
            response = await self.openai_client.embeddings.create(
                model=settings.OPENAI_EMBED_MODEL,
                input=goal_text,
            )
            embedding = response.data[0].embedding

            logger.info(
                f"Generated embedding for goal {goal.id}, "
                f"tokens={response.usage.total_tokens if response.usage else 0}"
            )

            # 缓存到 Redis
            if self.kv_client and cache_key:
                try:
                    await self.kv_client.set_json(
                        cache_key,
                        embedding,
                        ex=self.GOAL_EMBEDDING_CACHE_TTL,
                    )
                    logger.debug(f"Cached goal embedding for {goal.id}")
                except Exception as e:
                    logger.warning(f"Failed to cache goal embedding: {e}")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for goal {goal.id}: {e}")
            return None

    def _contains_chinese(self, text: str) -> bool:
        """判断文本是否包含中文字符。

        Args:
            text: 要检查的文本

        Returns:
            如果包含中文字符返回 True，否则返回 False
        """
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def _check_term_hits(
        self,
        text: str,
        terms: list[GoalPriorityTerm],
    ) -> tuple[int, list[dict]]:
        """检查词条命中（支持中英文混合匹配）。

        对于中文关键词，使用子串匹配；对于英文关键词，使用词边界匹配。
        """
        text_lower = text.lower()
        hits = 0
        details: list[dict] = []

        for term in terms:
            term_lower = term.term.lower()

            # 判断是否包含中文字符
            if self._contains_chinese(term_lower):
                # 中文使用子串匹配
                if term_lower in text_lower:
                    hits += 1
                    count = text_lower.count(term_lower)

                    # 找出前3个位置
                    positions = []
                    start = 0
                    for _ in range(min(count, 3)):
                        pos = text_lower.find(term_lower, start)
                        if pos != -1:
                            positions.append(pos)
                            start = pos + len(term_lower)

                    details.append(
                        {
                            "term": term.term,
                            "count": count,
                            "positions": positions,
                        }
                    )
            else:
                # 英文使用词边界匹配
                pattern = r"\b" + re.escape(term_lower) + r"\b"
                matches = list(re.finditer(pattern, text_lower))

                if matches:
                    hits += 1
                    details.append(
                        {
                            "term": term.term,
                            "count": len(matches),
                            "positions": [m.start() for m in matches[:3]],
                        }
                    )

        return hits, details

    def _compute_recency_score(self, item: Item) -> float:
        """计算时效性分数。"""
        if item.published_at is None:
            # 没有发布时间，使用入库时间
            pub_time = item.ingested_at
        else:
            pub_time = item.published_at

        # 确保时区
        if pub_time.tzinfo is None:
            pub_time = pub_time.replace(tzinfo=UTC)

        now = datetime.now(UTC)
        age = now - pub_time
        age_hours = age.total_seconds() / 3600

        if age_hours <= self.RECENCY_FULL_SCORE_HOURS:
            return 1.0
        elif age_hours <= self.RECENCY_HALF_SCORE_HOURS:
            # 线性衰减
            return 1.0 - 0.5 * (age_hours - self.RECENCY_FULL_SCORE_HOURS) / (
                self.RECENCY_HALF_SCORE_HOURS - self.RECENCY_FULL_SCORE_HOURS
            )
        elif age.days <= self.RECENCY_ZERO_SCORE_DAYS:
            # 继续衰减
            return 0.5 * (1.0 - (age.days - 2) / (self.RECENCY_ZERO_SCORE_DAYS - 2))
        else:
            return 0.0

    def _get_item_text(self, item: Item) -> str:
        """获取 Item 的文本内容用于匹配。"""
        parts = []
        if item.title:
            parts.append(item.title)
        if item.snippet:
            parts.append(item.snippet)
        if item.summary:
            parts.append(item.summary)
        return " ".join(parts)

    def _generate_reasons(
        self,
        goal: Goal,
        item: Item,
        features: MatchFeatures,
        must_terms: list[GoalPriorityTerm],
    ) -> MatchReasons:
        """生成匹配原因。"""
        reasons = MatchReasons()
        evidence: list[dict] = []

        # 检查负面词命中
        if features.negative_hits > 0:
            reasons.is_blocked = True
            reasons.block_reason = f"命中负面词：{', '.join(d['term'] for d in features.negative_hit_details)}"
            reasons.summary = reasons.block_reason
            return reasons

        # 检查 STRICT 模式
        if goal.priority_mode == PriorityMode.STRICT and must_terms:
            if features.term_hits == 0:
                # STRICT 模式下未命中任何 must term
                reasons.is_blocked = True
                reasons.block_reason = "STRICT 模式下未命中任何优先词"
                reasons.summary = reasons.block_reason
                return reasons

        # 构建证据
        if features.term_hit_details:
            for detail in features.term_hit_details:
                evidence.append(
                    {
                        "type": "TERM_HIT",
                        "term": detail["term"],
                        "count": detail["count"],
                    }
                )

        if features.cosine_similarity > 0.5:
            evidence.append(
                {
                    "type": "SEMANTIC_MATCH",
                    "similarity": round(features.cosine_similarity, 2),
                }
            )

        if features.recency_score > 0.8:
            evidence.append(
                {
                    "type": "FRESH_CONTENT",
                    "score": round(features.recency_score, 2),
                }
            )

        # 添加反馈相关证据
        if features.source_like_ratio is not None:
            evidence.append(
                {
                    "type": "FEEDBACK_SIGNAL",
                    "like_ratio": round(features.source_like_ratio, 2),
                    "boost": round(features.feedback_boost, 3),
                }
            )

        if features.has_source_dislike:
            evidence.append(
                {
                    "type": "SOURCE_DISLIKED",
                    "message": "该来源曾被标记为不相关",
                }
            )

        reasons.evidence = evidence

        # 生成摘要
        summary_parts = []
        if features.term_hits > 0:
            hit_terms = [d["term"] for d in features.term_hit_details]
            summary_parts.append(f"命中关键词「{'、'.join(hit_terms)}」")

        if features.cosine_similarity > 0.6:
            summary_parts.append("语义高度相关")
        elif features.cosine_similarity > 0.4:
            summary_parts.append("语义相关")

        if features.recency_score > 0.8:
            summary_parts.append("新鲜内容")

        # 添加反馈信号到摘要
        if features.feedback_boost > 0.05:
            summary_parts.append("来源口碑良好")
        elif features.feedback_boost < -0.05:
            summary_parts.append("来源曾被标记为不相关")

        reasons.summary = "；".join(summary_parts) if summary_parts else "基础匹配"

        return reasons

    def _compute_final_score(
        self,
        goal: Goal,
        features: MatchFeatures,
        reasons: MatchReasons,
    ) -> float:
        """计算最终匹配分数 - 混合策略。

        采用分层评分策略，让语义相似度和关键词匹配互为补充：
        - 高语义相似度 (≥0.75): 主要依赖语义，关键词作为加分项
        - 中等语义相似度 (0.60-0.75): 需要关键词支持
        - 低语义相似度 (<0.60): 必须有关键词命中
        """
        if reasons.is_blocked:
            return 0.0

        cosine = features.cosine_similarity
        term_hits = features.term_hits
        recency = features.recency_score
        source = features.source_trust

        # 策略1: 高语义相似度 - 语义主导
        if cosine >= self.SEMANTIC_HIGH_THRESHOLD:
            # 基础分 + 语义加分
            base_score = (
                self.BASE_SCORE_HIGH_SEMANTIC + cosine * self.SEMANTIC_BONUS_HIGH
            )

            # 关键词作为加分项
            if term_hits > 0:
                term_bonus = min(
                    term_hits * self.TERM_BONUS_PER_HIT_HIGH, self.TERM_BONUS_MAX_HIGH
                )
                base_score += term_bonus

            score = base_score

        # 策略2: 中等语义相似度 - 需要关键词支持
        elif cosine >= self.SEMANTIC_MEDIUM_THRESHOLD:
            if term_hits > 0:
                # 有关键词命中，给予较高分数
                score = (
                    self.BASE_SCORE_MEDIUM_SEMANTIC_WITH_TERMS
                    + cosine * self.SEMANTIC_BONUS_MEDIUM_WITH_TERMS
                    + min(
                        term_hits * self.TERM_BONUS_PER_HIT_MEDIUM,
                        self.TERM_BONUS_MAX_MEDIUM,
                    )
                )
            else:
                # 无关键词命中，分数受限
                score = (
                    self.BASE_SCORE_MEDIUM_SEMANTIC_NO_TERMS
                    + cosine * self.SEMANTIC_BONUS_MEDIUM_NO_TERMS
                )

        # 策略3: 低语义相似度 - 必须有关键词
        else:
            if term_hits > 0:
                # 关键词主导
                score = self.BASE_SCORE_LOW_SEMANTIC + min(
                    term_hits * self.TERM_BONUS_PER_HIT_LOW, self.TERM_BONUS_MAX_LOW
                )
            else:
                # 很低的分数
                score = cosine * self.SEMANTIC_BONUS_LOW

        # 加入时效性和来源可信度的微调
        score += recency * self.RECENCY_WEIGHT + source * self.SOURCE_WEIGHT

        # 应用反馈调整
        score += features.feedback_boost

        # 确保分数在 [0, 1] 范围
        return max(0.0, min(1.0, score))

    async def _save_match(self, result: MatchResult) -> None:
        """保存匹配结果到数据库。"""
        match = GoalItemMatch(
            goal_id=result.goal_id,
            item_id=result.item_id,
            match_score=result.score,
            features_json=result.features.to_dict(),
            reasons_json=result.reasons.to_dict(),
            computed_at=datetime.now(UTC),
        )

        await self.match_repository.upsert(match)

        logger.debug(
            f"Saved match: goal={result.goal_id}, item={result.item_id}, "
            f"score={result.score:.4f}"
        )

        # 记录高分匹配的业务事件
        if result.score >= settings.BATCH_THRESHOLD and self.business_logger:
            decision = (
                "immediate" if result.score >= settings.IMMEDIATE_THRESHOLD else "batch"
            )
            await self.business_logger.log_event(
                "item_matched",
                {
                    "item_id": result.item_id,
                    "goal_id": result.goal_id,
                    "score": result.score,
                    "decision": decision,
                    "reason": result.reasons.summary,
                },
            )

    async def match_item_by_id(self, item_id: str) -> list[MatchResult]:
        """根据 Item ID 执行匹配。"""
        item = await self.item_repository.get_by_id(item_id)
        if not item:
            logger.warning(f"Item not found: {item_id}")
            return []

        return await self.match_item_to_goals(item)
