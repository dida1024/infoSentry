"""Embedding 服务。

调用 OpenAI API 生成文本向量嵌入，支持：
- 批量嵌入
- 预算熔断检查
- 错误重试
"""

from loguru import logger
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import settings
from src.core.infrastructure.logging import BusinessEvents
from src.modules.items.domain.entities import Item
from src.modules.items.domain.repository import ItemRepository


class EmbeddingResult:
    """嵌入结果。"""

    def __init__(
        self,
        item_id: str,
        success: bool,
        embedding: list[float] | None = None,
        tokens_used: int = 0,
        error: str | None = None,
    ):
        self.item_id = item_id
        self.success = success
        self.embedding = embedding
        self.tokens_used = tokens_used
        self.error = error


class EmbeddingService:
    """Embedding 服务。

    职责：
    - 调用 OpenAI API 生成嵌入向量
    - 检查预算熔断状态
    - 更新 Item 的嵌入状态
    """

    def __init__(
        self,
        item_repository: ItemRepository,
        budget_service: "BudgetService | None" = None,
        openai_client: AsyncOpenAI | None = None,
    ):
        self.item_repository = item_repository
        self.budget_service = budget_service
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

    async def embed_item(self, item: Item) -> EmbeddingResult:
        """为单个 Item 生成嵌入向量。

        Args:
            item: 要嵌入的 Item

        Returns:
            EmbeddingResult: 嵌入结果
        """
        # 1. 检查是否启用嵌入
        if not settings.EMBEDDING_ENABLED:
            logger.info(f"Embedding disabled, skipping item {item.id}")
            item.mark_embedding_skipped_budget()
            await self.item_repository.update(item)
            return EmbeddingResult(
                item_id=item.id,
                success=False,
                error="Embedding disabled",
            )

        # 2. 检查预算熔断
        if self.budget_service:
            is_allowed, reason = await self.budget_service.check_embedding_budget()
            if not is_allowed:
                logger.warning(f"Embedding budget exhausted: {reason}")
                item.mark_embedding_skipped_budget()
                await self.item_repository.update(item)
                return EmbeddingResult(
                    item_id=item.id,
                    success=False,
                    error=f"Budget exhausted: {reason}",
                )

        # 3. 准备文本
        text = self._prepare_text(item)
        if not text:
            logger.warning(f"Item {item.id} has no text to embed")
            item.mark_embedding_failed()
            await self.item_repository.update(item)
            return EmbeddingResult(
                item_id=item.id,
                success=False,
                error="No text to embed",
            )

        # 4. 调用 OpenAI API
        try:
            embedding, tokens_used = await self._generate_embedding(text)

            # 5. 更新 Item
            item.mark_embedding_done(embedding, settings.OPENAI_EMBED_MODEL)
            await self.item_repository.update(item)

            # 6. 记录预算使用
            if self.budget_service:
                await self.budget_service.record_embedding_usage(tokens_used)

            logger.info(f"Embedded item {item.id}, tokens: {tokens_used}")

            # 记录业务事件
            BusinessEvents.item_embedded(
                item_id=item.id,
                tokens_used=tokens_used,
                model=settings.OPENAI_EMBED_MODEL,
            )

            return EmbeddingResult(
                item_id=item.id,
                success=True,
                embedding=embedding,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.exception(f"Failed to embed item {item.id}: {e}")
            item.mark_embedding_failed()
            await self.item_repository.update(item)
            return EmbeddingResult(
                item_id=item.id,
                success=False,
                error=str(e),
            )

    async def embed_items_batch(
        self,
        items: list[Item],
        batch_size: int = 20,
    ) -> list[EmbeddingResult]:
        """批量嵌入多个 Item。

        Args:
            items: 要嵌入的 Item 列表
            batch_size: 每批大小

        Returns:
            嵌入结果列表
        """
        results: list[EmbeddingResult] = []

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            batch_results = await self._embed_batch(batch)
            results.extend(batch_results)

            # 检查是否应该停止（预算耗尽）
            if self.budget_service:
                is_allowed, _ = await self.budget_service.check_embedding_budget()
                if not is_allowed:
                    # 将剩余的标记为 skipped
                    for item in items[i + batch_size :]:
                        item.mark_embedding_skipped_budget()
                        await self.item_repository.update(item)
                        results.append(
                            EmbeddingResult(
                                item_id=item.id,
                                success=False,
                                error="Budget exhausted",
                            )
                        )
                    break

        return results

    async def _embed_batch(self, items: list[Item]) -> list[EmbeddingResult]:
        """内部批量嵌入方法。"""
        results: list[EmbeddingResult] = []

        # 准备文本
        texts_with_items: list[tuple[Item, str]] = []
        for item in items:
            text = self._prepare_text(item)
            if text:
                texts_with_items.append((item, text))
            else:
                item.mark_embedding_failed()
                await self.item_repository.update(item)
                results.append(
                    EmbeddingResult(
                        item_id=item.id,
                        success=False,
                        error="No text to embed",
                    )
                )

        if not texts_with_items:
            return results

        # 批量调用 API
        try:
            texts = [t[1] for t in texts_with_items]
            embeddings, tokens_used = await self._generate_embeddings_batch(texts)

            tokens_per_item = tokens_used // len(texts) if texts else 0

            for (item, _), embedding in zip(texts_with_items, embeddings, strict=True):
                item.mark_embedding_done(embedding, settings.OPENAI_EMBED_MODEL)
                await self.item_repository.update(item)
                results.append(
                    EmbeddingResult(
                        item_id=item.id,
                        success=True,
                        embedding=embedding,
                        tokens_used=tokens_per_item,
                    )
                )

            # 记录预算
            if self.budget_service:
                await self.budget_service.record_embedding_usage(tokens_used)

        except Exception as e:
            logger.exception(f"Batch embedding failed: {e}")
            for item, _ in texts_with_items:
                item.mark_embedding_failed()
                await self.item_repository.update(item)
                results.append(
                    EmbeddingResult(
                        item_id=item.id,
                        success=False,
                        error=str(e),
                    )
                )

        return results

    def _prepare_text(self, item: Item) -> str:
        """准备用于嵌入的文本。"""
        parts = []

        if item.title:
            parts.append(item.title)

        if item.snippet:
            parts.append(item.snippet)

        if item.summary:
            parts.append(item.summary)

        text = " ".join(parts).strip()

        # 限制长度（OpenAI 有 token 限制）
        if len(text) > settings.EMBED_MAX_CHARS:
            text = text[: settings.EMBED_MAX_CHARS]

        return text

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _generate_embedding(self, text: str) -> tuple[list[float], int]:
        """调用 OpenAI API 生成单个嵌入。"""
        response = await self.client.embeddings.create(
            model=settings.OPENAI_EMBED_MODEL,
            input=text,
        )

        embedding = response.data[0].embedding
        tokens_used = response.usage.total_tokens if response.usage else 0

        return embedding, tokens_used

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _generate_embeddings_batch(
        self, texts: list[str]
    ) -> tuple[list[list[float]], int]:
        """调用 OpenAI API 批量生成嵌入。"""
        response = await self.client.embeddings.create(
            model=settings.OPENAI_EMBED_MODEL,
            input=texts,
        )

        embeddings = [item.embedding for item in response.data]
        tokens_used = response.usage.total_tokens if response.usage else 0

        return embeddings, tokens_used


# 导入类型提示
from src.modules.items.application.budget_service import BudgetService  # noqa: E402
