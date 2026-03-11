#!/usr/bin/env python3
"""infoSentry Skill — 首次配置脚本。

交互式收集 base_url 和 api_key，保存到 ~/.infosentry/config.json。

Usage:
    python3 scripts/setup.py
"""

import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".infosentry"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    """加载现有配置（如果存在）。"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    """保存配置到文件。"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    # 限制文件权限（仅所有者可读写）
    os.chmod(CONFIG_FILE, 0o600)
    print(f"\n✅ 配置已保存到 {CONFIG_FILE}")


def prompt_value(name: str, current: str | None, hint: str) -> str:
    """交互式输入一个配置值。"""
    if current:
        user_input = input(f"{name} [{current}]: ").strip()
        return user_input if user_input else current
    else:
        while True:
            user_input = input(f"{name} ({hint}): ").strip()
            if user_input:
                return user_input
            print(f"  ⚠️  {name} 不能为空，请重新输入。")


def verify_connection(base_url: str, api_key: str) -> bool:
    """验证 API 连接是否可用。"""
    import urllib.request
    import urllib.error

    url = f"{base_url.rstrip('/')}/goals"
    req = urllib.request.Request(url, headers={"X-API-Key": api_key})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("  ✅ 连接成功！API Key 验证通过。")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  ❌ API Key 无效，请检查后重试。")
        elif e.code == 403:
            print("  ⚠️  API Key 有效但缺少 goals:read 权限。")
            return True  # Key is valid, just missing scope
        else:
            print(f"  ⚠️  服务器返回 HTTP {e.code}。请检查 URL 是否正确。")
    except urllib.error.URLError as e:
        print(f"  ❌ 无法连接到服务器：{e.reason}")
    except Exception as e:
        print(f"  ❌ 连接失败：{e}")

    return False


def main() -> None:
    print("=" * 50)
    print("  infoSentry Skill 配置向导")
    print("=" * 50)
    print()

    config = load_config()

    # 收集 base_url
    print("📡 配置 API 地址")
    base_url = prompt_value(
        "Base URL",
        config.get("base_url"),
        "例如 https://your-domain.com/api/v1",
    )

    # 收集 api_key
    print("\n🔑 配置 API Key")
    print("  提示：在 infoSentry 的 设置 > 开发者中心 中创建 API Key")
    api_key = prompt_value(
        "API Key",
        config.get("api_key"),
        "以 isk_ 开头",
    )

    # 验证
    print("\n🔍 验证连接...")
    verify_connection(base_url, api_key)

    # 保存
    config["base_url"] = base_url.rstrip("/")
    config["api_key"] = api_key
    save_config(config)

    print("\n🎉 配置完成！现在可以使用 infosentry.py 工具了。")
    print(f"   示例：python3 scripts/infosentry.py goals list")


if __name__ == "__main__":
    main()
