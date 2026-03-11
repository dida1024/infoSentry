#!/usr/bin/env python3
"""infoSentry CLI — 纯标准库实现的 API 客户端工具。

无需安装任何第三方依赖，仅使用 Python 标准库。

Usage:
    python3 scripts/infosentry.py goals list
    python3 scripts/infosentry.py goals get <goal_id>
    python3 scripts/infosentry.py sources list
    python3 scripts/infosentry.py notifications list [--cursor xxx] [--goal_id xxx] [--status xxx]
    python3 scripts/infosentry.py raw GET /some/endpoint
    python3 scripts/infosentry.py raw POST /some/endpoint '{"key": "value"}'
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_FILE = Path(
    os.environ.get("INFOSENTRY_CONFIG", str(Path.home() / ".infosentry" / "config.json"))
)


def load_config() -> dict:
    """加载配置文件。"""
    if not CONFIG_FILE.exists():
        print("❌ 配置文件不存在。请先运行 setup.py 进行配置。", file=sys.stderr)
        print(f"   python3 scripts/setup.py", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def api_request(
    method: str,
    path: str,
    data: dict | None = None,
    params: dict | None = None,
) -> dict:
    """发送 API 请求。

    Args:
        method: HTTP 方法 (GET, POST, PUT, DELETE)
        path: API 路径 (以 / 开头)
        data: 请求体 JSON 数据
        params: URL 查询参数

    Returns:
        解析后的 JSON 响应字典
    """
    config = load_config()
    base_url = config["base_url"]
    api_key = config["api_key"]

    url = f"{base_url}{path}"

    # 添加查询参数
    if params:
        query_parts = []
        for k, v in params.items():
            if v is not None:
                query_parts.append(f"{urllib.request.quote(str(k))}={urllib.request.quote(str(v))}")
        if query_parts:
            url = f"{url}?{'&'.join(query_parts)}"

    # 构造请求
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        method=method.upper(),
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
            return response_data
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        try:
            error_json = json.loads(error_body)
            print(f"❌ HTTP {e.code}: {json.dumps(error_json, indent=2, ensure_ascii=False)}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"❌ HTTP {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ 连接失败: {e.reason}", file=sys.stderr)
        sys.exit(1)


def pp(data: dict) -> None:
    """Pretty-print JSON data."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ── Command handlers ─────────────────────────────────────────────────────────


def cmd_goals_list(args: argparse.Namespace) -> None:
    """列出目标。"""
    params = {}
    if args.status:
        params["status"] = args.status
    if args.page:
        params["page"] = args.page
    if args.page_size:
        params["page_size"] = args.page_size
    result = api_request("GET", "/goals", params=params)
    pp(result)


def cmd_goals_get(args: argparse.Namespace) -> None:
    """获取目标详情。"""
    result = api_request("GET", f"/goals/{args.goal_id}")
    pp(result)


def cmd_sources_list(args: argparse.Namespace) -> None:
    """列出信息源。"""
    params = {}
    if args.page:
        params["page"] = args.page
    if args.page_size:
        params["page_size"] = args.page_size
    result = api_request("GET", "/sources", params=params)
    pp(result)


def cmd_notifications_list(args: argparse.Namespace) -> None:
    """列出通知。"""
    params = {}
    if args.cursor:
        params["cursor"] = args.cursor
    if args.goal_id:
        params["goal_id"] = args.goal_id
    if args.status:
        params["status"] = args.status
    result = api_request("GET", "/notifications", params=params)
    pp(result)


def cmd_raw(args: argparse.Namespace) -> None:
    """发送原始 API 请求。"""
    data = None
    if args.body:
        try:
            data = json.loads(args.body)
        except json.JSONDecodeError:
            print("❌ 请求体不是有效的 JSON", file=sys.stderr)
            sys.exit(1)

    result = api_request(args.method, args.path, data=data)
    pp(result)


# ── Argument parser ──────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="infosentry",
        description="infoSentry CLI — 与 infoSentry 平台交互的命令行工具",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # goals
    goals_parser = subparsers.add_parser("goals", help="目标管理")
    goals_sub = goals_parser.add_subparsers(dest="action")

    goals_list = goals_sub.add_parser("list", help="列出目标")
    goals_list.add_argument("--status", choices=["active", "paused", "archived"])
    goals_list.add_argument("--page", type=int)
    goals_list.add_argument("--page_size", type=int)
    goals_list.set_defaults(func=cmd_goals_list)

    goals_get = goals_sub.add_parser("get", help="获取目标详情")
    goals_get.add_argument("goal_id", help="目标 ID")
    goals_get.set_defaults(func=cmd_goals_get)

    # sources
    sources_parser = subparsers.add_parser("sources", help="信息源管理")
    sources_sub = sources_parser.add_subparsers(dest="action")

    sources_list = sources_sub.add_parser("list", help="列出信息源")
    sources_list.add_argument("--page", type=int)
    sources_list.add_argument("--page_size", type=int)
    sources_list.set_defaults(func=cmd_sources_list)

    # notifications
    notif_parser = subparsers.add_parser("notifications", help="通知管理")
    notif_sub = notif_parser.add_subparsers(dest="action")

    notif_list = notif_sub.add_parser("list", help="列出通知")
    notif_list.add_argument("--cursor", help="分页游标")
    notif_list.add_argument("--goal_id", help="按 Goal ID 过滤")
    notif_list.add_argument("--status", help="状态过滤")
    notif_list.set_defaults(func=cmd_notifications_list)

    # raw
    raw_parser = subparsers.add_parser("raw", help="发送原始 API 请求")
    raw_parser.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    raw_parser.add_argument("path", help="API 路径，例如 /goals")
    raw_parser.add_argument("body", nargs="?", help="JSON 请求体")
    raw_parser.set_defaults(func=cmd_raw)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, "func"):
        args.func(args)
    else:
        # Sub-command without action
        parser.parse_args([args.command, "--help"])


if __name__ == "__main__":
    main()
