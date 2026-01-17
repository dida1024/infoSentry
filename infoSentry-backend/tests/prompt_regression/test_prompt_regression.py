"""Prompt regression tests.

This suite validates:
- prompts can be loaded from filesystem
- variable placeholders are rendered (no {{ var }} left)
- key guardrail phrases remain present (diff-friendly regression)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.infrastructure.ai.prompting.file_store import FileSystemPromptStore


def _backend_root() -> Path:
    # .../infoSentry-backend/tests/prompt_regression/test_prompt_regression.py
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"Invalid eval file (not an object): {path}")
    return data


def test_prompt_regression_rendering() -> None:
    root = _backend_root()
    store = FileSystemPromptStore(base_dir=root / "prompts")

    evals_dir = root / "evals" / "prompt_regression"
    files = sorted(evals_dir.glob("*.json"))
    assert files, f"No eval files found under: {evals_dir}"

    for f in files:
        data = _load_json(f)
        prompt = data.get("prompt", {})
        assert isinstance(prompt, dict), f"Missing prompt object in {f}"

        name = prompt.get("name")
        assert isinstance(name, str) and name.strip(), f"Missing prompt.name in {f}"
        language = prompt.get("language")
        if language is not None:
            assert isinstance(language, str) and language.strip(), (
                f"Invalid prompt.language in {f}"
            )

        cases = data.get("cases", [])
        assert isinstance(cases, list) and cases, f"Missing cases in {f}"

        for case in cases:
            assert isinstance(case, dict), f"Invalid case entry in {f}"
            case_name = case.get("name", "<unnamed>")
            vars_raw = case.get("vars", {})
            assert isinstance(vars_raw, dict), (
                f"Invalid vars for case={case_name} in {f}"
            )

            rendered = store.render_messages(
                name=name,
                language=language,
                variables=vars_raw,
            )
            combined = "\n\n".join(
                [f"[{m.role.upper()}]\n{m.content}" for m in rendered]
            )

            # Generic guardrail: no unresolved placeholders.
            assert "{{" not in combined and "}}" not in combined, (
                f"Unresolved placeholders in {f} case={case_name}"
            )

            assertions = case.get("assertions", {})
            assert isinstance(assertions, dict), (
                f"Invalid assertions for case={case_name} in {f}"
            )
            rendered_assert = assertions.get("rendered", {})
            assert isinstance(rendered_assert, dict), (
                f"Invalid assertions.rendered for case={case_name} in {f}"
            )

            must_contain = rendered_assert.get("must_contain", [])
            must_not_contain = rendered_assert.get("must_not_contain", [])
            assert isinstance(must_contain, list), (
                f"Invalid must_contain for case={case_name} in {f}"
            )
            assert isinstance(must_not_contain, list), (
                f"Invalid must_not_contain for case={case_name} in {f}"
            )

            for s in must_contain:
                assert isinstance(s, str) and s, (
                    f"Invalid must_contain entry for case={case_name} in {f}"
                )
                assert s in combined, (
                    f"Missing required text in {f} case={case_name}: {s!r}"
                )

            for s in must_not_contain:
                assert isinstance(s, str) and s, (
                    f"Invalid must_not_contain entry for case={case_name} in {f}"
                )
                assert s not in combined, (
                    f"Found forbidden text in {f} case={case_name}: {s!r}"
                )
