"""Filesystem-based prompt store.

Prompts are stored as `.prompty` files with a frontmatter section delimited by:

---            (line 1)
{ ... JSON ... }   (JSON is a YAML 1.2 subset; keeps stdlib-only parsing)
---            (end frontmatter)

And a body containing [SYSTEM]/[USER] blocks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

import structlog

from src.core.domain.ports.prompt_store import (
    PromptDefinition,
    PromptMessage,
    PromptMessageTemplate,
    PromptNotFoundError,
    PromptParseError,
    PromptRenderError,
    PromptStore,
    PromptVarSpec,
    PromptVarType,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class _PromptKey:
    name: str
    version: str
    language: str


_FRONTMATTER_DELIM = "---"
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


class FileSystemPromptStore(PromptStore):
    """Load prompts from filesystem and render them with variables."""

    def __init__(self, base_dir: Path, *, default_language: str = "zh-CN") -> None:
        self._base_dir = base_dir
        self._default_language = default_language
        self._index: dict[_PromptKey, Path] = {}
        self._cache: dict[_PromptKey, PromptDefinition] = {}
        self._indexed: bool = False

    def get(
        self,
        *,
        name: str,
        version: str | None = None,
        language: str | None = None,
    ) -> PromptDefinition:
        self._ensure_index()
        lang = (language or self._default_language).strip()

        if version is None:
            # Pick the latest semantic version for this name/lang.
            candidates = [
                k for k in self._index.keys() if k.name == name and k.language == lang
            ]
            if not candidates:
                raise PromptNotFoundError(
                    f"Prompt not found: name={name}, language={lang}"
                )
            chosen = max(candidates, key=lambda k: _parse_semver(k.version))
            return self._load_cached(chosen)

        key = _PromptKey(name=name, version=version, language=lang)
        if key not in self._index:
            raise PromptNotFoundError(
                f"Prompt not found: name={name}, version={version}, language={lang}"
            )
        return self._load_cached(key)

    def render_messages(
        self,
        *,
        name: str,
        variables: Mapping[str, object],
        version: str | None = None,
        language: str | None = None,
    ) -> list[PromptMessage]:
        prompt = self.get(name=name, version=version, language=language)
        rendered_vars = _coerce_and_fill_vars(prompt.vars, variables)
        messages: list[PromptMessage] = []
        for mt in prompt.messages:
            content = _render_template(mt.content_template, rendered_vars)
            messages.append(PromptMessage(role=mt.role, content=content))
        return messages

    def _ensure_index(self) -> None:
        if self._indexed:
            return

        base = self._base_dir
        if not base.exists() or not base.is_dir():
            raise PromptNotFoundError(f"Prompts directory not found: {base}")

        count = 0
        for path in base.rglob("*.prompty"):
            try:
                meta = _read_frontmatter_only(path)
                key = _PromptKey(
                    name=_require_str(meta, "name", path),
                    version=_require_str(meta, "version", path),
                    language=_require_str(meta, "language", path),
                )
                self._index[key] = path
                count += 1
            except PromptParseError:
                raise
            except Exception as e:  # noqa: BLE001
                raise PromptParseError(f"Failed to index prompt file: {path}") from e

        self._indexed = True
        logger.info("prompt_store_indexed", base_dir=str(base), count=count)

    def _load_cached(self, key: _PromptKey) -> PromptDefinition:
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        path = self._index.get(key)
        if path is None:
            raise PromptNotFoundError(
                f"Prompt not found in index: name={key.name}, version={key.version}, language={key.language}"
            )

        prompt = _load_prompty_file(path)
        # Sanity: ensure metadata matches key
        if (
            prompt.name != key.name
            or prompt.version != key.version
            or prompt.language != key.language
        ):
            raise PromptParseError(
                f"Prompt metadata mismatch for {path}: "
                f"expected ({key.name},{key.version},{key.language}) "
                f"got ({prompt.name},{prompt.version},{prompt.language})"
            )

        self._cache[key] = prompt
        return prompt


def _parse_semver(version: str) -> tuple[int, int, int, str]:
    """Parse semver-ish string: MAJOR.MINOR.PATCH[-suffix]."""
    v = version.strip()
    main, _, suffix = v.partition("-")
    parts = main.split(".")
    if len(parts) != 3:
        return (0, 0, 0, v)
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
    except ValueError:
        return (0, 0, 0, v)
    return (major, minor, patch, suffix)


def _read_frontmatter_only(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm_text, _body = _split_frontmatter(text, path)
    try:
        data = json.loads(fm_text)
    except json.JSONDecodeError as e:
        raise PromptParseError(f"Invalid frontmatter JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise PromptParseError(f"Frontmatter must be an object in {path}")
    return data


def _load_prompty_file(path: Path) -> PromptDefinition:
    text = path.read_text(encoding="utf-8")
    fm_text, body_text = _split_frontmatter(text, path)

    try:
        meta_raw = json.loads(fm_text)
    except json.JSONDecodeError as e:
        raise PromptParseError(f"Invalid frontmatter JSON in {path}: {e}") from e
    if not isinstance(meta_raw, dict):
        raise PromptParseError(f"Frontmatter must be an object in {path}")

    schema = meta_raw.get("schema", 1)
    if schema != 1:
        raise PromptParseError(f"Unsupported schema={schema} in {path}")

    name = _require_str(meta_raw, "name", path)
    version = _require_str(meta_raw, "version", path)
    language = _require_str(meta_raw, "language", path)

    tags_raw = meta_raw.get("tags", [])
    tags = _coerce_str_list(tags_raw, field="tags", path=path)

    vars_raw = meta_raw.get("vars", {})
    vars_spec = _parse_vars(vars_raw, path)

    fmt = meta_raw.get("format", "system_user_blocks")
    if fmt != "system_user_blocks":
        raise PromptParseError(f"Unsupported format={fmt!r} in {path}")

    system_text, user_text = _split_system_user(body_text)
    if not user_text.strip():
        raise PromptParseError(f"Missing [USER] block in {path}")

    messages: list[PromptMessageTemplate] = []
    if system_text and system_text.strip():
        messages.append(PromptMessageTemplate(role="system", content_template=system_text))
    messages.append(PromptMessageTemplate(role="user", content_template=user_text))

    output_raw = meta_raw.get("output", {})
    output_response_format = None
    if isinstance(output_raw, dict):
        rf = output_raw.get("response_format")
        if isinstance(rf, str) and rf.strip():
            output_response_format = rf.strip()

    return PromptDefinition(
        name=name,
        version=version,
        language=language,
        tags=tuple(tags),
        vars=vars_spec,
        messages=tuple(messages),
        output_response_format=output_response_format,
    )


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines:
        raise PromptParseError(f"Empty prompt file: {path}")

    if lines[0].strip() != _FRONTMATTER_DELIM:
        raise PromptParseError(
            f"Prompt file must start with '{_FRONTMATTER_DELIM}': {path}"
        )

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        raise PromptParseError(f"Missing closing frontmatter delimiter in {path}")

    fm_text = "\n".join(lines[1:end_idx]).strip()
    body_text = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    if not fm_text:
        raise PromptParseError(f"Empty frontmatter in {path}")
    return fm_text, body_text


def _split_system_user(text: str) -> tuple[str | None, str]:
    """Extract [SYSTEM]/[USER] blocks from body text."""

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

    system_text = "\n".join(system_lines).strip() or None
    user_text = "\n".join(user_lines).strip()
    return system_text, user_text


def _render_template(template: str, variables: Mapping[str, str]) -> str:
    """Render template using {{ var }} placeholders."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise PromptRenderError(f"Missing variable: {key}")
        return variables[key]

    rendered = _PLACEHOLDER_RE.sub(repl, template)
    if "{{" in rendered and "}}" in rendered:
        # A best-effort guardrail for forgotten placeholders.
        raise PromptRenderError("Unresolved placeholders remain after rendering")
    return rendered


def _coerce_and_fill_vars(
    specs: Mapping[str, PromptVarSpec],
    variables: Mapping[str, object],
) -> dict[str, str]:
    rendered: dict[str, str] = {}
    for name, spec in specs.items():
        if name in variables:
            value = variables[name]
        else:
            if spec.default is not None:
                value = spec.default
            elif spec.required:
                raise PromptRenderError(f"Missing required variable: {name}")
            else:
                value = ""
        rendered[name] = _coerce_var_value(value, spec.type)
    return rendered


def _coerce_var_value(value: object, var_type: PromptVarType) -> str:
    if var_type == "string":
        return str(value)
    if var_type == "int":
        if isinstance(value, bool):
            raise PromptRenderError("Invalid int value (bool)")
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str):
            try:
                return str(int(value.strip()))
            except ValueError as e:
                raise PromptRenderError(f"Invalid int value: {value!r}") from e
        raise PromptRenderError(f"Invalid int value: {type(value).__name__}")
    if var_type == "float":
        if isinstance(value, bool):
            raise PromptRenderError("Invalid float value (bool)")
        if isinstance(value, (int, float)):
            return str(float(value))
        if isinstance(value, str):
            try:
                return str(float(value.strip()))
            except ValueError as e:
                raise PromptRenderError(f"Invalid float value: {value!r}") from e
        raise PromptRenderError(f"Invalid float value: {type(value).__name__}")
    if var_type == "bool":
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes", "y"):
                return "true"
            if v in ("false", "0", "no", "n"):
                return "false"
        raise PromptRenderError(f"Invalid bool value: {value!r}")
    if var_type == "json":
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except TypeError as e:
            raise PromptRenderError("Invalid json value") from e
    raise PromptRenderError(f"Unsupported var type: {var_type}")


def _parse_vars(vars_raw: Any, path: Path) -> dict[str, PromptVarSpec]:
    if vars_raw is None:
        return {}
    if not isinstance(vars_raw, dict):
        raise PromptParseError(f"vars must be an object in {path}")

    specs: dict[str, PromptVarSpec] = {}
    for var_name, spec_raw in vars_raw.items():
        if not isinstance(var_name, str) or not var_name.strip():
            raise PromptParseError(f"Invalid var name in {path}")
        if not isinstance(spec_raw, dict):
            raise PromptParseError(f"vars.{var_name} must be an object in {path}")

        t = spec_raw.get("type", "string")
        if not isinstance(t, str):
            raise PromptParseError(f"vars.{var_name}.type must be a string in {path}")
        if t not in ("string", "int", "float", "bool", "json"):
            raise PromptParseError(f"Unsupported vars.{var_name}.type={t!r} in {path}")
        var_type = cast(PromptVarType, t)

        required_val = spec_raw.get("required", False)
        if not isinstance(required_val, bool):
            raise PromptParseError(f"vars.{var_name}.required must be bool in {path}")

        default_val = spec_raw.get("default", None)
        specs[var_name] = PromptVarSpec(
            type=var_type,
            required=required_val,
            default=default_val,
        )
    return specs


def _coerce_str_list(value: Any, *, field: str, path: Path) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise PromptParseError(f"{field} must be a list in {path}")
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        else:
            raise PromptParseError(f"{field} must contain non-empty strings in {path}")
    return out


def _require_str(meta: Mapping[str, Any], field: str, path: Path) -> str:
    v = meta.get(field)
    if not isinstance(v, str) or not v.strip():
        raise PromptParseError(f"Missing/invalid {field} in {path}")
    return v.strip()

