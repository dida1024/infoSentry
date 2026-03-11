"""infosentry-skill E2E 测试。

对运行中的 infoSentry API 执行端到端测试，验证 skill 的 CLI 工具
和 setup 脚本能正确与后端交互。

前置条件：
    - infoSentry API 正在运行（默认 http://localhost:18000）
    - PostgreSQL / Redis 正常

运行方式：
    # 从项目根目录
    cd infosentry-skill
    python -m pytest tests/test_e2e_skill.py -v

    # 指定 API 地址
    API_BASE_URL=http://your-host:18000/api/v1 python -m pytest tests/ -v

环境变量：
    API_BASE_URL  — API 基地址（默认 http://localhost:18000/api/v1）
    SECRET_KEY    — JWT 签名密钥（默认从 ../.env 读取）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

# ── 常量 ───────────────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
CLI_SCRIPT = SCRIPTS_DIR / "infosentry.py"
SETUP_SCRIPT = SCRIPTS_DIR / "setup.py"

DEFAULT_API_BASE = "http://localhost:18000/api/v1"
TEST_USER_ID = "e2e-skill-test-user"


# ── 辅助函数 ───────────────────────────────────────────────────────────────────


def _get_api_base() -> str:
    return os.environ.get("API_BASE_URL", DEFAULT_API_BASE)


def _get_secret_key() -> str:
    """从环境变量或 .env 文件获取 SECRET_KEY。"""
    key = os.environ.get("SECRET_KEY")
    if key:
        return key

    env_file = SKILL_DIR.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("SECRET_KEY="):
                return line.split("=", 1)[1].strip()

    pytest.skip("SECRET_KEY 未配置，无法生成测试 JWT")
    return ""  # unreachable


def _create_jwt(user_id: str, secret_key: str) -> str:
    """用标准库 + hmac 创建最小 JWT（HS256）。"""
    import base64
    import hashlib
    import hmac

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")

    exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": user_id, "exp": exp}).encode()
    ).rstrip(b"=")

    signing_input = header + b"." + payload
    signature = base64.urlsafe_b64encode(
        hmac.new(secret_key.encode(), signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")

    return (signing_input + b"." + signature).decode()


def _api_request(
    method: str,
    path: str,
    base_url: str,
    *,
    token: str | None = None,
    api_key: str | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """直接发 HTTP 请求到 API。"""
    url = f"{base_url}{path}"
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["X-API-Key"] = api_key

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, {"raw": body_text}


def _run_cli(*args: str, config_path: str) -> subprocess.CompletedProcess[str]:
    """运行 skill CLI 脚本。"""
    env = os.environ.copy()
    # 覆盖 config 文件路径（通过猴子补丁方式不方便，改用环境变量注入）
    env["INFOSENTRY_CONFIG"] = config_path
    return subprocess.run(
        [sys.executable, str(CLI_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api_base() -> str:
    """API 基地址。"""
    base = _get_api_base()
    # 健康检查
    health_url = base.rsplit("/api", 1)[0] + "/health"
    try:
        req = urllib.request.Request(health_url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get("status") != "healthy":
                pytest.skip(f"API 不健康: {data}")
    except Exception as e:
        pytest.skip(f"API 不可达 ({health_url}): {e}")
    return base


@pytest.fixture(scope="module")
def jwt_token() -> str:
    """为测试用户创建 JWT。"""
    secret = _get_secret_key()
    return _create_jwt(TEST_USER_ID, secret)


@pytest.fixture(scope="module")
def api_key_raw(api_base: str, jwt_token: str) -> str:
    """通过 API 创建一个测试用 API Key，返回原始密钥。"""
    status, body = _api_request(
        "POST",
        "/keys",
        api_base,
        token=jwt_token,
        data={
            "name": "E2E Skill Test Key",
            "scopes": [
                "goals:read",
                "goals:write",
                "sources:read",
                "notifications:read",
            ],
        },
    )
    assert status in (200, 201), f"创建 API Key 失败: {status} {body}"
    raw_key = body.get("data", {}).get("raw_key")
    assert raw_key and raw_key.startswith("isk_"), f"无效的 raw_key: {body}"
    return raw_key


@pytest.fixture(scope="module")
def config_file(api_base: str, api_key_raw: str) -> str:
    """创建临时 config.json 供 CLI 使用。"""
    config = {"base_url": api_base, "api_key": api_key_raw}
    tmpdir = tempfile.mkdtemp(prefix="infosentry_test_")
    config_path = os.path.join(tmpdir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)
    return config_path


# ── 测试：API Key 认证 ────────────────────────────────────────────────────────


class TestApiKeyAuth:
    """验证 API Key 认证机制。"""

    def test_api_key_rejected_without_header(self, api_base: str) -> None:
        """无认证头应被拒绝。"""
        status, _ = _api_request("GET", "/goals", api_base)
        assert status in (401, 403)

    def test_api_key_rejected_with_invalid_key(self, api_base: str) -> None:
        """无效 API Key 应被拒绝。"""
        status, _ = _api_request(
            "GET", "/goals", api_base, api_key="isk_invalid_key_12345"
        )
        assert status in (401, 403)

    def test_api_key_accepted_with_valid_key(
        self, api_base: str, api_key_raw: str
    ) -> None:
        """有效 API Key 应能访问有权限的端点。"""
        status, body = _api_request(
            "GET", "/goals", api_base, api_key=api_key_raw
        )
        assert status == 200, f"期望 200，得到 {status}: {body}"

    def test_api_key_scope_enforcement(
        self, api_base: str, jwt_token: str
    ) -> None:
        """API Key 的 scope 应被正确执行。"""
        # 创建一个只有 goals:read 的 key
        status, body = _api_request(
            "POST",
            "/keys",
            api_base,
            token=jwt_token,
            data={
                "name": "Read-Only Test Key",
                "scopes": ["goals:read"],
            },
        )
        assert status in (200, 201), f"创建 Read-Only Key 失败: {status} {body}"
        read_only_key = body["data"]["raw_key"]

        # 读取应成功
        status, _ = _api_request(
            "GET", "/goals", api_base, api_key=read_only_key
        )
        assert status == 200

        # 写入应被拒绝（scope 不足）
        status, _ = _api_request(
            "POST",
            "/goals",
            api_base,
            api_key=read_only_key,
            data={"name": "Should Fail"},
        )
        assert status == 403, f"期望 403，得到 {status}"

        # 清理：撤销 key
        key_id = body["data"]["key"]["id"]
        _api_request("DELETE", f"/keys/{key_id}", api_base, token=jwt_token)


# ── 测试：CLI 工具 ────────────────────────────────────────────────────────────


class TestCliTool:
    """验证 infosentry.py CLI 工具。"""

    def test_cli_help(self) -> None:
        """CLI 无参数时应显示帮助信息。"""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "infosentry" in result.stdout.lower() or "子命令" in result.stdout

    def test_cli_goals_list(self, config_file: str) -> None:
        """goals list 应返回有效 JSON。"""
        result = _run_cli("goals", "list", config_path=config_file)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_cli_sources_list(self, config_file: str) -> None:
        """sources list 应返回有效 JSON。"""
        result = _run_cli("sources", "list", config_path=config_file)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_cli_notifications_list(self, config_file: str) -> None:
        """notifications list 应返回有效 JSON。"""
        result = _run_cli("notifications", "list", config_path=config_file)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_cli_raw_get(self, config_file: str) -> None:
        """raw GET 应返回有效 JSON。"""
        result = _run_cli("raw", "GET", "/goals", config_path=config_file)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_cli_goals_list_with_filter(self, config_file: str) -> None:
        """goals list --status active 应正常工作。"""
        result = _run_cli(
            "goals", "list", "--status", "active", config_path=config_file
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        json.loads(result.stdout)  # 能解析即可

    def test_cli_missing_config(self) -> None:
        """缺少 config 时应报错并退出 1。"""
        result = _run_cli(config_path="/nonexistent/config.json")
        # 无子命令 → 帮助输出（returncode 0）或者缺 config 报错
        # 有子命令时才会真正读 config
        result2 = _run_cli("goals", "list", config_path="/nonexistent/config.json")
        assert result2.returncode != 0
        assert "配置文件不存在" in result2.stderr or "config" in result2.stderr.lower()


# ── 测试：setup.py 验证 ───────────────────────────────────────────────────────


class TestSetupScript:
    """验证 setup.py 的连接验证功能。"""

    def test_setup_verify_with_valid_key(
        self, api_base: str, api_key_raw: str
    ) -> None:
        """setup.py 的验证逻辑应能成功连接。"""
        # 直接导入 setup 模块的 verify_connection 函数
        import importlib.util

        spec = importlib.util.spec_from_file_location("setup", str(SETUP_SCRIPT))
        assert spec and spec.loader
        setup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_module)

        result = setup_module.verify_connection(api_base, api_key_raw)
        assert result is True, "验证连接应成功"

    def test_setup_verify_with_invalid_key(self, api_base: str) -> None:
        """setup.py 的验证逻辑应拒绝无效 key。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("setup", str(SETUP_SCRIPT))
        assert spec and spec.loader
        setup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_module)

        result = setup_module.verify_connection(api_base, "isk_invalid_key")
        assert result is False, "无效 key 验证应失败"

    def test_setup_verify_with_bad_url(self) -> None:
        """setup.py 的验证逻辑应处理无效 URL。"""
        import importlib.util

        spec = importlib.util.spec_from_file_location("setup", str(SETUP_SCRIPT))
        assert spec and spec.loader
        setup_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_module)

        result = setup_module.verify_connection(
            "http://localhost:99999", "isk_whatever"
        )
        assert result is False, "无效 URL 验证应失败"
