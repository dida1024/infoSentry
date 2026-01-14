#!/usr/bin/env python3
"""AI 模型对比脚本（多供应商/多模型）。

目标：
输入一段提示词，并发调用多个模型，收集回复、耗时与 token usage，
将结果输出到文件（Markdown + JSONL），方便对比选型。

用法示例：
  # 1) 直接传 prompt
  uv run python scripts/ai_model_compare.py --config scripts/ai_models.toml --prompt "写一个三段式自我介绍"

  # 2) 从文件读取 prompt
  uv run python scripts/ai_model_compare.py --config scripts/ai_models.toml --prompt-file ./prompt.txt

  # 3) 从 stdin 读取 prompt
  cat ./prompt.txt | uv run python scripts/ai_model_compare.py --config scripts/ai_models.toml --stdin

配置文件（TOML）：
  - 参考 scripts/ai_models.example.toml
  - 支持 api_key_env 或 api_key
  - 如果写入 api_key（明文密钥），请确保配置文件不会被提交到公开仓库/日志系统

提示词文件（--prompt-file）：
  - 支持普通纯文本 prompt
  - 也支持一个文件同时包含 system/user 两段：
    [SYSTEM]
    ...system prompt...
    [/SYSTEM]
    [USER]
    ...user prompt...
    [/USER]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import httpx

# 添加项目根目录到 Python 路径（与项目内其他 scripts 保持一致）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


ProviderType = Literal["openai_compatible", "anthropic", "gemini"]


class ProviderResult(TypedDict, total=False):
    text: str
    finish_reason: str
    usage: Mapping[str, Any]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class RunSettings:
    temperature: float
    max_tokens: int
    timeout_seconds: float
    concurrency: int
    save_raw: bool
    out_dir: Path


@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: ProviderType
    model: str
    base_url: str | None
    api_key_env: str | None
    api_key: str | None
    api_key_optional: bool
    temperature: float | None
    max_tokens: int | None
    timeout_seconds: float | None
    headers: dict[str, str]
    enabled: bool


@dataclass(frozen=True)
class ModelRunResult:
    name: str
    provider: ProviderType
    model: str
    base_url: str | None
    ok: bool
    duration_ms: int
    text: str | None
    finish_reason: str | None
    usage: Mapping[str, Any] | None
    error: str | None
    raw: Mapping[str, Any] | None


def _coerce_float(value: Any, *, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{field} 必须是数字，实际是：{type(value).__name__}")


def _coerce_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} 必须是整数，实际是 bool")
    if isinstance(value, int):
        return value
    raise ValueError(f"{field} 必须是整数，实际是：{type(value).__name__}")


def _coerce_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field} 必须是 bool，实际是：{type(value).__name__}")


def _coerce_str(value: Any, *, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError(f"{field} 必须是非空字符串")


def _slugify(text: str) -> str:
    s = text.strip()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-zA-Z0-9\-_]+", "", s)
    return s[:60] or "run"


def _split_system_user(text: str) -> tuple[str | None, str]:
    """从文本中提取 [SYSTEM]/[USER] 两段。

    - 若能解析到 [USER] 段，则返回 (system_or_none, user_text)
    - 否则把整段文本视为 user_text
    """

    start_re = re.compile(r"^\[(system|user)\]\s*$", re.IGNORECASE)
    end_re = re.compile(r"^\[/(system|user)\]\s*$", re.IGNORECASE)

    system_lines: list[str] = []
    user_lines: list[str] = []
    current: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        m_start = start_re.match(stripped)
        if m_start:
            current = m_start.group(1).lower()
            continue
        m_end = end_re.match(stripped)
        if m_end:
            current = None
            continue

        if current == "system":
            system_lines.append(line)
        elif current == "user":
            user_lines.append(line)

    user_text = "\n".join(user_lines).strip()
    if user_text:
        system_text = "\n".join(system_lines).strip() or None
        return system_text, user_text

    return None, text.strip()


def _now_ts() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise ValueError("TOML 顶层必须是 table")
    return data


def load_config(config_path: Path, *, out_dir_override: Path | None) -> tuple[RunSettings, list[ModelSpec]]:
    raw = _load_toml(config_path)

    run_raw = raw.get("run", {})
    if run_raw is None:
        run_raw = {}
    if not isinstance(run_raw, dict):
        raise ValueError("[run] 必须是 table")

    # 全局默认值（都可被 CLI 或 model 覆盖）
    temperature = _coerce_float(run_raw.get("temperature", 0.2), field="run.temperature")
    max_tokens = _coerce_int(run_raw.get("max_tokens", 1024), field="run.max_tokens")
    timeout_seconds = _coerce_float(run_raw.get("timeout_seconds", 60.0), field="run.timeout_seconds")
    concurrency = _coerce_int(run_raw.get("concurrency", 4), field="run.concurrency")
    save_raw = _coerce_bool(run_raw.get("save_raw", False), field="run.save_raw")

    out_dir_raw = run_raw.get("out_dir")
    if out_dir_override is not None:
        out_dir = out_dir_override
    elif isinstance(out_dir_raw, str) and out_dir_raw.strip():
        out_dir = (project_root / out_dir_raw).resolve()
    else:
        out_dir = (project_root / "results" / "ai_model_compare").resolve()

    settings = RunSettings(
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        concurrency=concurrency,
        save_raw=save_raw,
        out_dir=out_dir,
    )

    models_raw = raw.get("models")
    if not isinstance(models_raw, list) or not models_raw:
        raise ValueError("必须在配置中提供至少一个 [[models]]")

    specs: list[ModelSpec] = []
    for idx, item in enumerate(models_raw):
        if not isinstance(item, dict):
            raise ValueError(f"models[{idx}] 必须是 table")

        name = _coerce_str(item.get("name"), field=f"models[{idx}].name")
        provider_raw = item.get("provider", "openai_compatible")
        if provider_raw not in ("openai_compatible", "anthropic", "gemini", "glm"):
            raise ValueError(f"models[{idx}].provider 不支持：{provider_raw}")
        provider = cast(ProviderType, provider_raw)

        model = _coerce_str(item.get("model"), field=f"models[{idx}].model")
        base_url = item.get("base_url")
        if base_url is not None and not isinstance(base_url, str):
            raise ValueError(f"models[{idx}].base_url 必须是字符串或省略")

        api_key_env = item.get("api_key_env")
        if api_key_env is not None and not isinstance(api_key_env, str):
            raise ValueError(f"models[{idx}].api_key_env 必须是字符串或省略")

        api_key = item.get("api_key")
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError(f"models[{idx}].api_key 必须是字符串或省略（不建议写入文件）")

        api_key_optional = _coerce_bool(
            item.get("api_key_optional", False), field=f"models[{idx}].api_key_optional"
        )

        temp_override = item.get("temperature")
        temperature_override = (
            _coerce_float(temp_override, field=f"models[{idx}].temperature") if temp_override is not None else None
        )

        max_tokens_override_raw = item.get("max_tokens")
        max_tokens_override = (
            _coerce_int(max_tokens_override_raw, field=f"models[{idx}].max_tokens")
            if max_tokens_override_raw is not None
            else None
        )

        timeout_override_raw = item.get("timeout_seconds")
        timeout_override = (
            _coerce_float(timeout_override_raw, field=f"models[{idx}].timeout_seconds")
            if timeout_override_raw is not None
            else None
        )

        enabled = _coerce_bool(item.get("enabled", True), field=f"models[{idx}].enabled")

        headers_raw = item.get("headers", {})
        if headers_raw is None:
            headers_raw = {}
        if not isinstance(headers_raw, dict):
            raise ValueError(f"models[{idx}].headers 必须是 table")
        headers: dict[str, str] = {}
        for k, v in headers_raw.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(f"models[{idx}].headers 的 key/value 都必须是字符串")
            headers[k] = v

        specs.append(
            ModelSpec(
                name=name,
                provider=provider,
                model=model,
                base_url=base_url,
                api_key_env=api_key_env,
                api_key=api_key,
                api_key_optional=api_key_optional,
                temperature=temperature_override,
                max_tokens=max_tokens_override,
                timeout_seconds=timeout_override,
                headers=headers,
                enabled=enabled,
            )
        )

    enabled_specs = [s for s in specs if s.enabled]
    if not enabled_specs:
        raise ValueError("所有 models 都被禁用（enabled=false），没有可运行的模型")

    return settings, enabled_specs


def _resolve_api_key(spec: ModelSpec) -> str | None:
    if spec.api_key is not None and spec.api_key.strip():
        return spec.api_key
    if spec.api_key_env is not None and spec.api_key_env.strip():
        value = os.getenv(spec.api_key_env)
        if value is not None and value.strip():
            return value
        if spec.api_key_optional:
            return None
        raise RuntimeError(f"模型 {spec.name} 需要 API Key，但环境变量未设置：{spec.api_key_env}")
    if spec.api_key_optional:
        return None
    raise RuntimeError(f"模型 {spec.name} 需要 API Key，但未提供 api_key_env/api_key")


def _merge_headers(base: Mapping[str, str], extra: Mapping[str, str]) -> dict[str, str]:
    merged: dict[str, str] = dict(base)
    for k, v in extra.items():
        merged[k] = v
    return merged


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


async def _call_openai_compatible(
    client: httpx.AsyncClient,
    *,
    spec: ModelSpec,
    prompt: str,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
    api_key: str | None,
) -> ProviderResult:
    base_url = (spec.base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": spec.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    headers = _merge_headers(
        {"content-type": "application/json"},
        spec.headers,
    )
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    resp = await client.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()

    text: str | None = None
    finish_reason: str | None = None

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice0 = choices[0]
        if isinstance(choice0, dict):
            finish_reason_val = choice0.get("finish_reason")
            if isinstance(finish_reason_val, str):
                finish_reason = finish_reason_val
            msg = choice0.get("message")
            if isinstance(msg, dict):
                content_val = msg.get("content")
                if isinstance(content_val, str):
                    text = content_val

    usage_val = data.get("usage")
    usage: Mapping[str, Any] = usage_val if isinstance(usage_val, dict) else {}

    if text is None:
        raise RuntimeError(f"OpenAI 兼容接口返回无法解析的结构：{_safe_json(data)[:2000]}")

    return ProviderResult(
        text=text,
        finish_reason=finish_reason or "",
        usage=usage,
        raw=data,
    )


async def _call_anthropic(
    client: httpx.AsyncClient,
    *,
    spec: ModelSpec,
    prompt: str,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
    api_key: str | None,
) -> ProviderResult:
    if not api_key and not spec.api_key_optional:
        raise RuntimeError("Anthropic 需要 api_key")

    base_url = (spec.base_url or "https://api.anthropic.com").rstrip("/")
    url = f"{base_url}/v1/messages"

    payload: dict[str, Any] = {
        "model": spec.model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt

    headers = _merge_headers(
        {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        spec.headers,
    )
    if api_key:
        headers["x-api-key"] = api_key

    resp = await client.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()

    content_blocks = data.get("content")
    texts: list[str] = []
    if isinstance(content_blocks, list):
        for b in content_blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and isinstance(b.get("text"), str):
                texts.append(b["text"])

    text = "".join(texts).strip()
    if not text:
        raise RuntimeError(f"Anthropic 返回无法解析的结构：{_safe_json(data)[:2000]}")

    stop_reason = data.get("stop_reason")
    finish_reason = stop_reason if isinstance(stop_reason, str) else ""
    usage_val = data.get("usage")
    usage: Mapping[str, Any] = usage_val if isinstance(usage_val, dict) else {}

    return ProviderResult(
        text=text,
        finish_reason=finish_reason,
        usage=usage,
        raw=data,
    )


async def _call_gemini(
    client: httpx.AsyncClient,
    *,
    spec: ModelSpec,
    prompt: str,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
    api_key: str | None,
) -> ProviderResult:
    if not api_key and not spec.api_key_optional:
        raise RuntimeError("Gemini 需要 api_key")

    base_url = (spec.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    model_path = spec.model.strip()
    if model_path.startswith("models/"):
        model_path = model_path[len("models/") :]
    url = f"{base_url}/models/{model_path}:generateContent"

    payload: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    headers = _merge_headers({"content-type": "application/json"}, spec.headers)
    if api_key:
        headers["x-goog-api-key"] = api_key

    resp = await client.post(url, headers=headers, json=payload, timeout=timeout_seconds)
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates")
    text_parts: list[str] = []
    finish_reason: str = ""

    if isinstance(candidates, list) and candidates:
        cand0 = candidates[0]
        if isinstance(cand0, dict):
            fr = cand0.get("finishReason") or cand0.get("finish_reason")
            if isinstance(fr, str):
                finish_reason = fr
            content = cand0.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    for p in parts:
                        if isinstance(p, dict) and isinstance(p.get("text"), str):
                            text_parts.append(p["text"])

    text = "".join(text_parts).strip()
    if not text:
        raise RuntimeError(f"Gemini 返回无法解析的结构：{_safe_json(data)[:2000]}")

    usage_val = data.get("usageMetadata") or data.get("usage_metadata")
    usage: Mapping[str, Any] = usage_val if isinstance(usage_val, dict) else {}

    return ProviderResult(
        text=text,
        finish_reason=finish_reason,
        usage=usage,
        raw=data,
    )


async def run_one_model(
    *,
    spec: ModelSpec,
    prompt: str,
    system_prompt: str | None,
    run_settings: RunSettings,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> ModelRunResult:
    temperature = spec.temperature if spec.temperature is not None else run_settings.temperature
    max_tokens = spec.max_tokens if spec.max_tokens is not None else run_settings.max_tokens
    timeout_seconds = spec.timeout_seconds if spec.timeout_seconds is not None else run_settings.timeout_seconds

    api_key = _resolve_api_key(spec)

    started = time.perf_counter()
    try:
        async with semaphore:
            # 每个请求单独 timeout，避免某个模型拖死整个对比
            if spec.provider == "openai_compatible":
                result = await _call_openai_compatible(
                    client,
                    spec=spec,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_seconds=timeout_seconds,
                    api_key=api_key,
                )
            elif spec.provider == "anthropic":
                result = await _call_anthropic(
                    client,
                    spec=spec,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_seconds=timeout_seconds,
                    api_key=api_key,
                )
            else:
                result = await _call_gemini(
                    client,
                    spec=spec,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_seconds=timeout_seconds,
                    api_key=api_key,
                )

        duration_ms = int((time.perf_counter() - started) * 1000)
        raw = result.get("raw") if run_settings.save_raw else None
        return ModelRunResult(
            name=spec.name,
            provider=spec.provider,
            model=spec.model,
            base_url=spec.base_url,
            ok=True,
            duration_ms=duration_ms,
            text=result.get("text"),
            finish_reason=result.get("finish_reason"),
            usage=result.get("usage"),
            error=None,
            raw=raw,
        )
    except Exception as e:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return ModelRunResult(
            name=spec.name,
            provider=spec.provider,
            model=spec.model,
            base_url=spec.base_url,
            ok=False,
            duration_ms=duration_ms,
            text=None,
            finish_reason=None,
            usage=None,
            error=str(e),
            raw=None,
        )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_markdown(
    path: Path,
    *,
    run_id: str,
    timestamp: str,
    config_path: Path,
    system_prompt: str | None,
    prompt: str,
    results: list[ModelRunResult],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"## AI 模型对比结果（run_id: {run_id}）")
    lines.append("")
    lines.append(f"- 时间：{timestamp}")
    lines.append(f"- 配置：{config_path}")
    lines.append("")
    if system_prompt:
        lines.append("## System Prompt")
        lines.append("")
        lines.append("```text")
        lines.append(system_prompt)
        lines.append("```")
        lines.append("")

    lines.append("## Prompt")
    lines.append("")
    lines.append("```text")
    lines.append(prompt)
    lines.append("```")
    lines.append("")

    for r in results:
        lines.append(f"## {r.name}")
        lines.append("")
        lines.append(f"- provider: {r.provider}")
        lines.append(f"- model: {r.model}")
        if r.base_url:
            lines.append(f"- base_url: {r.base_url}")
        lines.append(f"- ok: {r.ok}")
        lines.append(f"- duration_ms: {r.duration_ms}")
        if r.usage is not None:
            lines.append(f"- usage: `{json.dumps(r.usage, ensure_ascii=False)}`")
        if r.finish_reason:
            lines.append(f"- finish_reason: {r.finish_reason}")
        if r.error:
            lines.append(f"- error: {r.error}")
        lines.append("")
        if r.text is not None:
            lines.append("```text")
            lines.append(r.text)
            lines.append("```")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI 模型对比脚本（多模型并发调用 + 输出报告）")
    parser.add_argument("--config", type=str, required=True, help="TOML 配置路径（例如 scripts/ai_models.toml）")

    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--prompt", type=str, help="直接提供 prompt 文本")
    group.add_argument(
        "--prompt-file",
        type=str,
        help="从文件读取 prompt（支持 [SYSTEM]/[USER] 分段）",
    )
    group.add_argument("--stdin", action="store_true", help="从 stdin 读取 prompt（读取到 EOF）")

    parser.add_argument("--system", type=str, default=None, help="可选 system prompt")

    parser.add_argument("--temperature", type=float, default=None, help="覆盖配置的 temperature")
    parser.add_argument("--max-tokens", type=int, default=None, help="覆盖配置的 max_tokens")
    parser.add_argument("--timeout-seconds", type=float, default=None, help="覆盖配置的 timeout_seconds")
    parser.add_argument("--concurrency", type=int, default=None, help="覆盖配置的 concurrency")
    parser.add_argument("--save-raw", action="store_true", help="保存原始响应 JSON 到输出（可能很大）")

    parser.add_argument("--out-dir", type=str, default=None, help="输出目录（相对 backend 根目录）")
    parser.add_argument("--out-prefix", type=str, default="ai_compare", help="输出文件名前缀")
    parser.add_argument("--no-markdown", action="store_true", help="不输出 Markdown 报告")
    parser.add_argument("--no-jsonl", action="store_true", help="不输出 JSONL 结果")

    return parser.parse_args()


def _read_prompt_bundle(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.prompt is not None:
        raw = args.prompt
    elif args.prompt_file is not None:
        raw = Path(args.prompt_file).read_text(encoding="utf-8")
    elif args.stdin:
        raw = sys.stdin.read()
    else:
        raise ValueError("必须提供 --prompt/--prompt-file/--stdin 其中之一")

    raw = raw.strip()
    if not raw:
        raise ValueError("prompt 为空")

    system_from_text, user_text = _split_system_user(raw)
    if not user_text:
        raise ValueError("prompt 为空")
    return user_text, system_from_text


async def _main_async() -> int:
    args = _parse_args()

    config_path = (project_root / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    out_dir_override = (project_root / args.out_dir).resolve() if args.out_dir else None

    run_settings, specs = load_config(config_path, out_dir_override=out_dir_override)

    # CLI 覆盖 run settings
    if args.temperature is not None:
        run_settings = RunSettings(
            temperature=float(args.temperature),
            max_tokens=run_settings.max_tokens,
            timeout_seconds=run_settings.timeout_seconds,
            concurrency=run_settings.concurrency,
            save_raw=run_settings.save_raw,
            out_dir=run_settings.out_dir,
        )
    if args.max_tokens is not None:
        run_settings = RunSettings(
            temperature=run_settings.temperature,
            max_tokens=int(args.max_tokens),
            timeout_seconds=run_settings.timeout_seconds,
            concurrency=run_settings.concurrency,
            save_raw=run_settings.save_raw,
            out_dir=run_settings.out_dir,
        )
    if args.timeout_seconds is not None:
        run_settings = RunSettings(
            temperature=run_settings.temperature,
            max_tokens=run_settings.max_tokens,
            timeout_seconds=float(args.timeout_seconds),
            concurrency=run_settings.concurrency,
            save_raw=run_settings.save_raw,
            out_dir=run_settings.out_dir,
        )
    if args.concurrency is not None:
        run_settings = RunSettings(
            temperature=run_settings.temperature,
            max_tokens=run_settings.max_tokens,
            timeout_seconds=run_settings.timeout_seconds,
            concurrency=int(args.concurrency),
            save_raw=run_settings.save_raw,
            out_dir=run_settings.out_dir,
        )
    if args.save_raw:
        run_settings = RunSettings(
            temperature=run_settings.temperature,
            max_tokens=run_settings.max_tokens,
            timeout_seconds=run_settings.timeout_seconds,
            concurrency=run_settings.concurrency,
            save_raw=True,
            out_dir=run_settings.out_dir,
        )

    prompt, system_from_file = _read_prompt_bundle(args)

    system_cli = args.system.strip() if isinstance(args.system, str) and args.system.strip() else None
    system_prompt = system_cli or system_from_file

    ts = _now_ts()
    run_id = f"{ts}_{_slugify(args.out_prefix)}"

    # http client（全局复用连接）
    timeout = httpx.Timeout(run_settings.timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        semaphore = asyncio.Semaphore(run_settings.concurrency)
        tasks = [
            run_one_model(
                spec=spec,
                prompt=prompt,
                system_prompt=system_prompt,
                run_settings=run_settings,
                client=client,
                semaphore=semaphore,
            )
            for spec in specs
        ]
        results = await asyncio.gather(*tasks)

    # 输出排序：先成功、再按耗时
    results_sorted = sorted(results, key=lambda r: (not r.ok, r.duration_ms))

    timestamp_iso = datetime.now(UTC).isoformat()

    rows: list[dict[str, Any]] = []
    for r in results_sorted:
        rows.append(
            {
                "run_id": run_id,
                "timestamp": timestamp_iso,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "name": r.name,
                "provider": r.provider,
                "model": r.model,
                "base_url": r.base_url,
                "ok": r.ok,
                "duration_ms": r.duration_ms,
                "finish_reason": r.finish_reason,
                "usage": dict(r.usage) if isinstance(r.usage, Mapping) else None,
                "text": r.text,
                "error": r.error,
                "raw": dict(r.raw) if isinstance(r.raw, Mapping) else None,
            }
        )

    out_dir = run_settings.out_dir
    out_prefix = _slugify(args.out_prefix)
    md_path = out_dir / f"{out_prefix}_{ts}.md"
    jsonl_path = out_dir / f"{out_prefix}_{ts}.jsonl"

    if not args.no_jsonl:
        _write_jsonl(jsonl_path, rows)
    if not args.no_markdown:
        _write_markdown(
            md_path,
            run_id=run_id,
            timestamp=timestamp_iso,
            config_path=config_path,
            system_prompt=system_prompt,
            prompt=prompt,
            results=results_sorted,
        )

    # 控制台输出一行摘要，方便定位输出文件
    ok_cnt = sum(1 for r in results_sorted if r.ok)
    total_cnt = len(results_sorted)
    print(f"完成：{ok_cnt}/{total_cnt} 成功")
    if not args.no_markdown:
        print(f"Markdown：{md_path}")
    if not args.no_jsonl:
        print(f"JSONL：{jsonl_path}")

    return 0 if ok_cnt > 0 else 2


def main() -> None:
    try:
        code = asyncio.run(_main_async())
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        raise
    except Exception as e:
        print(f"运行失败：{e}", file=sys.stderr)
        raise SystemExit(2) from e
    raise SystemExit(code)


if __name__ == "__main__":
    main()

