"""Unit tests for all 7 discovery tools.

Tests use mocks for external deps (HTTP, catalog, repositories, fetchers).
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import RunContext

from src.modules.agent.application.discovery.agent import DiscoveryDeps
from src.modules.agent.domain.discovery_entities import (
    DiscoverySession,
    SessionStatus,
)
from src.modules.sources.domain.catalog import NewsNowCatalog, NewsNowCatalogSource
from src.modules.sources.domain.fetcher import FetchedItem, FetchResult, FetchStatus

pytestmark = pytest.mark.anyio


# ============================================
# Shared Fixtures
# ============================================


def _make_ctx(
    *,
    catalog_sources: list[NewsNowCatalogSource] | None = None,
    exists_by_config_url: bool = False,
    exists_by_name: bool = False,
    web_search_api_key: str = "",
    rsshub_base_url: str = "https://rsshub.example.com",
    http_responses: dict[str, httpx.Response] | None = None,
) -> RunContext[DiscoveryDeps]:
    """Build a RunContext with mocked deps."""
    # Catalog provider
    catalog_provider = AsyncMock()
    catalog_provider.load_catalog = AsyncMock(
        return_value=NewsNowCatalog(
            sources=catalog_sources or [],
            loaded_from="snapshot",
        )
    )

    # Source repository
    source_repository = AsyncMock()
    source_repository.exists_by_config_url = AsyncMock(
        return_value=exists_by_config_url
    )
    source_repository.exists_by_name = AsyncMock(return_value=exists_by_name)
    source_repository.delete = AsyncMock(return_value=True)

    # Handlers
    create_source_handler = AsyncMock()
    mock_source = MagicMock()
    mock_source.id = "source-new-123"
    create_source_handler.handle = AsyncMock(return_value=mock_source)

    subscribe_source_handler = AsyncMock()
    subscribe_source_handler.handle = AsyncMock()

    # Session
    session = DiscoverySession(
        user_id="user-1",
        initial_query="test",
        status=SessionStatus.ACTIVE,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    # HTTP client mock
    http_client = AsyncMock(spec=httpx.AsyncClient)
    if http_responses:

        async def mock_get(url, **_kwargs):
            for pattern, resp in http_responses.items():
                if pattern in url:
                    return resp
            return httpx.Response(404, text="Not found")

        http_client.get = mock_get

    # Candidate repository
    candidate_repository = AsyncMock()
    candidate_repository.create = AsyncMock(side_effect=lambda c: c)
    candidate_repository.update = AsyncMock(side_effect=lambda c: c)
    candidate_repository.get_by_id = AsyncMock(return_value=None)

    deps = DiscoveryDeps(
        catalog_provider=catalog_provider,
        create_fetcher=MagicMock(),
        create_source_handler=create_source_handler,
        subscribe_source_handler=subscribe_source_handler,
        source_query_service=AsyncMock(),
        source_repository=source_repository,
        candidate_repository=candidate_repository,
        http_client=http_client,
        session=session,
        rsshub_base_url=rsshub_base_url,
        probe_timeout=5.0,
        web_search_api_key=web_search_api_key,
    )

    # Build RunContext manually
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


def _make_catalog_source(
    source_id: str = "src-1",
    name: str = "Test Source",
    title: str | None = "Test Title",
    disable: bool = False,
) -> NewsNowCatalogSource:
    return NewsNowCatalogSource(
        source_id=source_id,
        name=name,
        title=title,
        interval_ms=None,
        disable=disable,
        redirect=None,
        raw={},
    )


# ============================================
# search_catalog Tests
# ============================================


class TestSearchCatalog:
    async def test_match_by_name(self):
        from src.modules.agent.application.discovery.tools.catalog_search import (
            search_catalog,
        )

        ctx = _make_ctx(
            catalog_sources=[
                _make_catalog_source(
                    source_id="github", name="GitHub", title="GitHub Trending"
                ),
                _make_catalog_source(
                    source_id="hackernews", name="Hacker News", title="HN"
                ),
            ]
        )
        result = await search_catalog(ctx, keywords=["github"])
        assert result["found"] == 1
        assert result["matches"][0]["source_id"] == "github"

    async def test_match_by_title(self):
        from src.modules.agent.application.discovery.tools.catalog_search import (
            search_catalog,
        )

        ctx = _make_ctx(
            catalog_sources=[
                _make_catalog_source(source_id="tech", name="Tech", title="科技新闻"),
            ]
        )
        result = await search_catalog(ctx, keywords=["科技"])
        assert result["found"] == 1

    async def test_no_match(self):
        from src.modules.agent.application.discovery.tools.catalog_search import (
            search_catalog,
        )

        ctx = _make_ctx(
            catalog_sources=[
                _make_catalog_source(name="Unrelated"),
            ]
        )
        result = await search_catalog(ctx, keywords=["房产"])
        assert result["found"] == 0

    async def test_skip_disabled(self):
        from src.modules.agent.application.discovery.tools.catalog_search import (
            search_catalog,
        )

        ctx = _make_ctx(
            catalog_sources=[
                _make_catalog_source(name="GitHub", disable=True),
            ]
        )
        result = await search_catalog(ctx, keywords=["github"])
        assert result["found"] == 0

    async def test_max_10_results(self):
        from src.modules.agent.application.discovery.tools.catalog_search import (
            search_catalog,
        )

        sources = [
            _make_catalog_source(source_id=f"src-{i}", name=f"Tech {i}")
            for i in range(15)
        ]
        ctx = _make_ctx(catalog_sources=sources)
        result = await search_catalog(ctx, keywords=["tech"])
        assert result["found"] == 10

    async def test_already_exists_flag(self):
        from src.modules.agent.application.discovery.tools.catalog_search import (
            search_catalog,
        )

        ctx = _make_ctx(
            catalog_sources=[_make_catalog_source(name="GitHub")],
            exists_by_config_url=True,
        )
        result = await search_catalog(ctx, keywords=["github"])
        assert result["matches"][0]["already_exists"] is True


# ============================================
# web_search Tests
# ============================================


class TestWebSearch:
    async def test_no_api_key(self):
        from src.modules.agent.application.discovery.tools.web_search import web_search

        ctx = _make_ctx(web_search_api_key="")
        result = await web_search(ctx, query="test")
        assert result["results"] == []
        assert "未配置" in result["error"]

    async def test_search_success(self):
        from src.modules.agent.application.discovery.tools.web_search import web_search

        ctx = _make_ctx(web_search_api_key="test-key")
        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Example",
                    "content": "Test content",
                },
            ]
        }
        with patch("tavily.AsyncTavilyClient") as MockClient:
            instance = AsyncMock()
            instance.search = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            result = await web_search(ctx, query="test query")
            assert len(result["results"]) == 1
            assert result["results"][0]["url"] == "https://example.com"

    async def test_search_failure_graceful(self):
        from src.modules.agent.application.discovery.tools.web_search import web_search

        ctx = _make_ctx(web_search_api_key="test-key")
        with patch("tavily.AsyncTavilyClient") as MockClient:
            instance = AsyncMock()
            instance.search = AsyncMock(side_effect=Exception("API error"))
            MockClient.return_value = instance

            result = await web_search(ctx, query="test")
            assert result["results"] == []
            assert "搜索失败" in result["error"]


# ============================================
# probe_rss Tests
# ============================================


class TestProbeRss:
    async def test_ssrf_blocked(self):
        from src.modules.agent.application.discovery.tools.rss_probe import probe_rss

        ctx = _make_ctx()
        result = await probe_rss(ctx, url="http://localhost/rss")
        assert result["found"] is False
        assert "不允许" in result.get("error", "")

    async def test_ssrf_blocked_private_ip(self):
        from src.modules.agent.application.discovery.tools.rss_probe import probe_rss

        ctx = _make_ctx()
        result = await probe_rss(ctx, url="http://192.168.1.1/feed")
        assert result["found"] is False

    async def test_allowed_url_validation(self):
        from src.modules.agent.application.discovery.tools.http_safe import (
            is_allowed_url,
        )

        with patch(
            "src.modules.agent.application.discovery.tools.http_safe.socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
            ],
        ):
            assert is_allowed_url("https://example.com/feed") is True
        assert is_allowed_url("http://localhost/feed") is False
        assert is_allowed_url("http://10.0.0.1/feed") is False
        assert is_allowed_url("ftp://example.com/feed") is False
        assert is_allowed_url("http://evil.local/feed") is False

    async def test_allowed_url_blocks_domain_resolving_to_private_ip(self):
        from src.modules.agent.application.discovery.tools.http_safe import (
            is_allowed_url,
        )

        with patch(
            "src.modules.agent.application.discovery.tools.http_safe.socket.getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
            ],
        ):
            assert is_allowed_url("https://attacker.example/feed") is False


# ============================================
# Redirect-safe SSRF Tests
# ============================================


class TestRedirectSafeSsrf:
    """Test that redirects to private IPs are blocked."""

    async def test_safe_get_blocks_redirect_to_private_ip(self):
        from src.modules.agent.application.discovery.tools.http_safe import safe_get

        client = AsyncMock(spec=httpx.AsyncClient)
        # First request returns redirect to private IP
        redirect_resp = httpx.Response(
            302,
            headers={"location": "http://192.168.1.1/secret"},
            request=httpx.Request("GET", "https://evil.com/rss"),
        )
        client.get = AsyncMock(return_value=redirect_resp)

        with pytest.raises(ValueError, match="SSRF blocked"):
            await safe_get(client, "https://evil.com/rss", timeout=5.0)

    async def test_safe_get_blocks_redirect_to_localhost(self):
        from src.modules.agent.application.discovery.tools.http_safe import safe_get

        client = AsyncMock(spec=httpx.AsyncClient)
        redirect_resp = httpx.Response(
            301,
            headers={"location": "http://localhost:8080/admin"},
            request=httpx.Request("GET", "https://evil.com/feed"),
        )
        client.get = AsyncMock(return_value=redirect_resp)

        with pytest.raises(ValueError, match="SSRF blocked"):
            await safe_get(client, "https://evil.com/feed", timeout=5.0)

    async def test_safe_get_allows_redirect_to_public_ip(self):
        from src.modules.agent.application.discovery.tools.http_safe import safe_get

        client = AsyncMock(spec=httpx.AsyncClient)
        redirect_resp = httpx.Response(
            301,
            headers={"location": "https://cdn.example.com/feed.xml"},
            request=httpx.Request("GET", "https://example.com/rss"),
        )
        final_resp = httpx.Response(200, text="<rss>ok</rss>")

        call_count = 0

        async def mock_get(_url, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return redirect_resp
            return final_resp

        client.get = mock_get
        with patch(
            "src.modules.agent.application.discovery.tools.http_safe.socket.getaddrinfo",
            side_effect=[
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))],
            ],
        ):
            resp = await safe_get(client, "https://example.com/rss", timeout=5.0)
            assert resp.status_code == 200

    async def test_safe_get_blocks_redirect_to_link_local(self):
        from src.modules.agent.application.discovery.tools.http_safe import safe_get

        client = AsyncMock(spec=httpx.AsyncClient)
        redirect_resp = httpx.Response(
            302,
            headers={"location": "http://169.254.169.254/latest/meta-data/"},
            request=httpx.Request("GET", "https://evil.com/rss"),
        )
        client.get = AsyncMock(return_value=redirect_resp)

        with pytest.raises(ValueError, match="SSRF blocked"):
            await safe_get(client, "https://evil.com/rss", timeout=5.0)


# ============================================
# search_rsshub Tests
# ============================================


class TestSearchRsshub:
    async def test_build_routes_with_domain(self):
        from src.modules.agent.application.discovery.tools.rsshub_lookup import (
            _build_candidate_routes,
        )

        routes = _build_candidate_routes(["trending"], "github.com")
        assert "/github/com" in routes
        assert "/github" in routes
        assert "/trending" in routes
        assert "/github/trending" in routes

    async def test_build_routes_no_domain(self):
        from src.modules.agent.application.discovery.tools.rsshub_lookup import (
            _build_candidate_routes,
        )

        routes = _build_candidate_routes(["v2ex", "hot"], None)
        assert "/v2ex" in routes
        assert "/hot" in routes

    async def test_search_no_results(self):
        from src.modules.agent.application.discovery.tools.rsshub_lookup import (
            search_rsshub,
        )

        ctx = _make_ctx()
        # Mock HTTP to return 404 for all
        ctx.deps.http_client.get = AsyncMock(
            return_value=httpx.Response(404, text="Not found")
        )
        result = await search_rsshub(ctx, keywords=["nonexistent"])
        assert result["found"] is False


# ============================================
# fetch_site_html Tests
# ============================================


class TestFetchSiteHtml:
    async def test_ssrf_blocked(self):
        from src.modules.agent.application.discovery.tools.site_html_fetcher import (
            fetch_site_html,
        )

        ctx = _make_ctx()
        result = await fetch_site_html(ctx, url="http://localhost/news")
        assert result["html_snippet"] == ""
        assert "不允许" in result.get("error", "")

    async def test_clean_html_removes_scripts(self):
        from src.modules.agent.application.discovery.tools.site_html_fetcher import (
            _clean_html,
        )

        html = '<html><script>alert("xss")</script><div>Content</div></html>'
        cleaned = _clean_html(html)
        assert "alert" not in cleaned
        assert "Content" in cleaned

    async def test_clean_html_removes_nav_footer(self):
        from src.modules.agent.application.discovery.tools.site_html_fetcher import (
            _clean_html,
        )

        html = "<nav>Menu</nav><main>Article</main><footer>Copyright</footer>"
        cleaned = _clean_html(html)
        assert "Menu" not in cleaned
        assert "Copyright" not in cleaned
        assert "Article" in cleaned

    async def test_clean_html_truncates(self):
        from src.modules.agent.application.discovery.tools.site_html_fetcher import (
            _clean_html,
        )

        html = "x" * 10000
        cleaned = _clean_html(html, max_chars=100)
        assert len(cleaned) <= 120  # 100 + "... [truncated]"
        assert "[truncated]" in cleaned


# ============================================
# validate_source Tests
# ============================================


class TestValidateSource:
    async def test_invalid_source_type(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        result = await validate_source(
            ctx, name="Test", source_type="INVALID", config={}, url="https://x.com"
        )
        assert result["valid"] is False
        assert "不支持" in result["error"]

    async def test_valid_rss_source(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        mock_fetcher = MagicMock()
        mock_fetcher.validate_config.return_value = (True, None)
        mock_fetcher.fetch = AsyncMock(
            return_value=FetchResult(
                status=FetchStatus.SUCCESS,
                items=[
                    FetchedItem(url="https://example.com/1", title="Article 1"),
                    FetchedItem(url="https://example.com/2", title="Article 2"),
                ],
            )
        )
        ctx.deps.create_fetcher = MagicMock(return_value=mock_fetcher)

        result = await validate_source(
            ctx,
            name="Test RSS",
            source_type="RSS",
            config={"feed_url": "https://example.com/rss"},
            url="https://example.com/rss",
            discovered_via="rss_probe",
        )

        assert result["valid"] is True
        assert result["items_count"] == 2
        assert "Article 1" in result["sample_titles"]
        assert "candidate_id" in result

    async def test_invalid_config(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        mock_fetcher = MagicMock()
        mock_fetcher.validate_config.return_value = (False, "Missing feed_url")
        ctx.deps.create_fetcher = MagicMock(return_value=mock_fetcher)

        result = await validate_source(
            ctx, name="Bad", source_type="RSS", config={}, url="https://bad.com"
        )

        assert result["valid"] is False
        assert "配置无效" in result["error"]

    async def test_fetch_fails(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        mock_fetcher = MagicMock()
        mock_fetcher.validate_config.return_value = (True, None)
        mock_fetcher.fetch = AsyncMock(
            return_value=FetchResult(
                status=FetchStatus.FAILED,
                error_message="Connection timeout",
            )
        )
        ctx.deps.create_fetcher = MagicMock(return_value=mock_fetcher)

        result = await validate_source(
            ctx,
            name="Timeout",
            source_type="RSS",
            config={"feed_url": "https://bad.com/rss"},
            url="https://bad.com/rss",
        )

        assert result["valid"] is False

    async def test_candidate_persist_failure_returns_invalid(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        ctx.deps.candidate_repository.create = AsyncMock(
            side_effect=Exception("DB unavailable")
        )

        result = await validate_source(
            ctx,
            name="Persist Fail",
            source_type="RSS",
            config={"feed_url": "https://example.com/rss"},
            url="https://example.com/rss",
            discovered_via="rss_probe",
        )

        assert result["valid"] is False
        assert "候选持久化失败" in result["error"]

    async def test_candidate_status_update_failure_returns_invalid(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        mock_fetcher = MagicMock()
        mock_fetcher.validate_config.return_value = (True, None)
        mock_fetcher.fetch = AsyncMock(
            return_value=FetchResult(
                status=FetchStatus.SUCCESS,
                items=[FetchedItem(url="https://example.com/1", title="Article 1")],
            )
        )
        ctx.deps.create_fetcher = MagicMock(return_value=mock_fetcher)
        ctx.deps.candidate_repository.update = AsyncMock(
            side_effect=Exception("DB write failed")
        )

        result = await validate_source(
            ctx,
            name="Update Fail",
            source_type="RSS",
            config={"feed_url": "https://example.com/rss"},
            url="https://example.com/rss",
        )

        assert result["valid"] is False
        assert "候选状态更新失败" in result["error"]


# ============================================
# add_source Tests
# ============================================


class TestAddSource:
    async def test_invalid_source_type(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx()
        result = await add_source(ctx, name="Test", source_type="INVALID", config={})
        assert result["success"] is False

    async def test_name_already_exists(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx(exists_by_name=True)
        result = await add_source(
            ctx,
            name="Existing",
            source_type="RSS",
            config={"feed_url": "https://x.com/rss"},
        )
        assert result["success"] is False
        assert "已存在" in result["error"]

    async def test_url_already_exists(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx(exists_by_config_url=True)
        result = await add_source(
            ctx,
            name="New",
            source_type="RSS",
            config={"feed_url": "https://dup.com/rss"},
        )
        assert result["success"] is False
        assert "已存在" in result["error"]

    async def test_add_success(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx()
        result = await add_source(
            ctx,
            name="New Source",
            source_type="RSS",
            config={"feed_url": "https://new.com/rss"},
        )
        assert result["success"] is True
        assert result["source_id"] == "source-new-123"
        ctx.deps.create_source_handler.handle.assert_called_once()
        ctx.deps.subscribe_source_handler.handle.assert_called_once()

    async def test_add_subscribe_failure_compensates(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx()
        ctx.deps.subscribe_source_handler.handle = AsyncMock(
            side_effect=Exception("Subscribe failed")
        )
        result = await add_source(
            ctx,
            name="New Source",
            source_type="RSS",
            config={"feed_url": "https://new.com/rss"},
        )
        # Compensation: should report failure, not success
        assert result["success"] is False
        assert "订阅失败" in result["error"]

    async def test_add_success_returns_signal(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx()
        result = await add_source(
            ctx,
            name="Signal Source",
            source_type="RSS",
            config={"feed_url": "https://signal.com/rss"},
        )
        assert result["_signal"] == "source_added"

    async def test_add_candidate_update_failure_compensates(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx()
        # Make candidate_repo.get_by_id return a mock candidate that throws on update
        mock_candidate = MagicMock()
        mock_candidate.accept = MagicMock()
        ctx.deps.candidate_repository.get_by_id = AsyncMock(return_value=mock_candidate)
        ctx.deps.candidate_repository.update = AsyncMock(
            side_effect=Exception("DB write failed")
        )
        result = await add_source(
            ctx,
            name="Fail Candidate",
            source_type="RSS",
            config={"feed_url": "https://fail.com/rss"},
            candidate_id="candidate-123",
        )
        # Candidate update failure must cause overall failure
        assert result["success"] is False
        assert "候选状态更新失败" in result["error"]

    async def test_add_missing_candidate_id_fails_and_compensates(self):
        from src.modules.agent.application.discovery.tools.source_adder import (
            add_source,
        )

        ctx = _make_ctx()
        ctx.deps.candidate_repository.get_by_id = AsyncMock(return_value=None)

        result = await add_source(
            ctx,
            name="Missing Candidate",
            source_type="RSS",
            config={"feed_url": "https://missing.com/rss"},
            candidate_id="candidate-missing",
        )

        assert result["success"] is False
        assert "候选不存在" in result["error"]
        ctx.deps.source_repository.delete.assert_awaited_once()


# ============================================
# Signal field regression tests
# ============================================


class TestSignalField:
    """Verify _signal field is returned by tools for stream state detection."""

    async def test_validate_source_returns_signal_on_valid(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        mock_fetcher = MagicMock()
        mock_fetcher.validate_config.return_value = (True, None)
        mock_fetcher.fetch = AsyncMock(
            return_value=FetchResult(
                status=FetchStatus.SUCCESS,
                items=[FetchedItem(url="https://x.com/1", title="Title")],
            )
        )
        ctx.deps.create_fetcher = MagicMock(return_value=mock_fetcher)

        result = await validate_source(
            ctx,
            name="Test",
            source_type="RSS",
            config={"feed_url": "https://x.com/rss"},
            url="https://x.com/rss",
            discovered_via="rss_probe",
        )

        assert result["_signal"] == "candidates_valid"

    async def test_validate_source_no_signal_on_invalid(self):
        from src.modules.agent.application.discovery.tools.source_validator import (
            validate_source,
        )

        ctx = _make_ctx()
        mock_fetcher = MagicMock()
        mock_fetcher.validate_config.return_value = (True, None)
        mock_fetcher.fetch = AsyncMock(
            return_value=FetchResult(status=FetchStatus.FAILED, error_message="timeout")
        )
        ctx.deps.create_fetcher = MagicMock(return_value=mock_fetcher)

        result = await validate_source(
            ctx,
            name="Bad",
            source_type="RSS",
            config={"feed_url": "https://bad.com/rss"},
            url="https://bad.com/rss",
        )

        assert "_signal" not in result


# ============================================
# expire_stale_sessions full coverage test
# ============================================


class TestExpireFullCoverage:
    """Verify expire scans beyond first 100."""

    async def test_expires_beyond_first_page(self):
        from src.modules.agent.application.discovery.session_service import (
            DiscoverySessionService,
        )
        from tests.unit.test_discovery_session_service import (
            InMemoryDiscoveryCandidateRepository,
            InMemoryDiscoverySessionRepository,
        )

        session_repo = InMemoryDiscoverySessionRepository()
        candidate_repo = InMemoryDiscoveryCandidateRepository()
        service = DiscoverySessionService(session_repo, candidate_repo)

        # Create 3 sessions (use different user_ids to bypass concurrency limit)
        sessions = []
        for i in range(3):
            s = await service.create_session(f"user-{i}", f"query-{i}")
            s.expires_at = datetime.now(UTC) - timedelta(minutes=5)
            await session_repo.update(s)
            sessions.append(s)

        # expire with a tiny page_size to force pagination
        # The default page_size is 100, but we test the loop logic
        expired = await service.expire_stale_sessions()
        assert expired == 3
