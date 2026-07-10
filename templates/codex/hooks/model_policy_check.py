#!/usr/bin/env python3
"""Check Codex model / reasoning-effort routing policy.

SessionStart mode is check-only and non-blocking: report drift, change nothing,
exit 0. Pre-commit mode is a hard gate: if the committed Codex skeleton would
lose the default model policy, exit 2.

The hook validates both the live dogfood layer (`.codex/`) and, when present,
the product template layer (`templates/codex/`). Downstream projects normally
only have `.codex/`, so the template target self-gates away.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

EXPECTED_CONFIG = {
    "model": "gpt-5.6-terra",
    "model_reasoning_effort": "medium",
}

EXPECTED_AGENTS = {
    "light-explorer.toml": {
        "name": "light-explorer",
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "low",
    },
    "implementation-worker.toml": {
        "name": "implementation-worker",
        "model": "gpt-5.6-sol",
        "model_reasoning_effort": "high",
    },
    "review-auditor.toml": {
        "name": "review-auditor",
        "model": "gpt-5.6-sol",
        "model_reasoning_effort": "high",
    },
    "xhigh-auditor.toml": {
        "name": "xhigh-auditor",
        "model": "gpt-5.6-sol",
        "model_reasoning_effort": "xhigh",
    },
}

CONFIRMATION_PATTERNS = (
    "explicit user confirmation",
    "xhigh requires user confirmation",
    "用户确认",
)


def _load_toml(path: Path) -> tuple[dict[str, object], str | None]:
    text: str
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {}, f"cannot read: {exc}"

    try:
        import tomllib  # Python 3.11+

        return tomllib.loads(text), None
    except ModuleNotFoundError:
        return _parse_toml_scalars(text), None
    except Exception as exc:
        return {}, f"invalid TOML: {exc}"


def _parse_toml_scalars(text: str) -> dict[str, object]:
    """Small fallback for old Python: enough for top-level string scalars."""
    out: dict[str, object] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            i += 1
            continue

        triple = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*"""(.*)$', stripped)
        if triple:
            key = triple.group(1)
            rest = triple.group(2)
            chunks: list[str] = []
            if rest.endswith('"""') and len(rest) >= 3:
                chunks.append(rest[:-3])
            else:
                if rest:
                    chunks.append(rest)
                i += 1
                while i < len(lines):
                    chunk = lines[i]
                    if chunk.endswith('"""'):
                        chunks.append(chunk[:-3])
                        break
                    chunks.append(chunk)
                    i += 1
            out[key] = "\n".join(chunks)
            i += 1
            continue

        scalar = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"', stripped)
        if scalar:
            out[scalar.group(1)] = scalar.group(2)
        i += 1
    return out


def _get_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


def _check_config(root: Path, label: str) -> list[str]:
    path = root / "config.toml"
    if not path.is_file():
        return [f"{label}/config.toml missing"]

    data, err = _load_toml(path)
    if err:
        return [f"{label}/config.toml {err}"]

    issues: list[str] = []
    for key, expected in EXPECTED_CONFIG.items():
        actual = _get_string(data, key)
        if actual != expected:
            issues.append(f"{label}/config.toml {key} must be {expected!r}, got {actual!r}")
    return issues


def _check_agent(root: Path, label: str, filename: str, expected: dict[str, str]) -> list[str]:
    path = root / "agents" / filename
    if not path.is_file():
        return [f"{label}/agents/{filename} missing"]

    data, err = _load_toml(path)
    if err:
        return [f"{label}/agents/{filename} {err}"]

    issues: list[str] = []
    for key, expected_value in expected.items():
        actual = _get_string(data, key)
        if actual != expected_value:
            issues.append(
                f"{label}/agents/{filename} {key} must be {expected_value!r}, got {actual!r}"
            )

    if expected.get("model_reasoning_effort") == "xhigh":
        description = _get_string(data, "description").lower()
        instructions = _get_string(data, "developer_instructions").lower()
        if not any(pattern.lower() in description for pattern in CONFIRMATION_PATTERNS):
            issues.append(
                f"{label}/agents/{filename} description must state that xhigh requires explicit user confirmation"
            )
        if not any(pattern.lower() in instructions for pattern in CONFIRMATION_PATTERNS):
            issues.append(
                f"{label}/agents/{filename} developer_instructions must state that xhigh requires explicit user confirmation"
            )
    return issues


def _check_target(root: Path, label: str) -> list[str]:
    if not root.exists():
        return []

    issues = _check_config(root, label)
    for filename, expected in EXPECTED_AGENTS.items():
        issues.extend(_check_agent(root, label, filename, expected))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-commit", action="store_true", help="exit 2 on policy drift")
    args = parser.parse_args()

    targets = [
        (REPO_ROOT / ".codex", ".codex"),
        (REPO_ROOT / "templates" / "codex", "templates/codex"),
    ]

    issues: list[str] = []
    for root, label in targets:
        issues.extend(_check_target(root, label))

    if not issues:
        return 0

    stream = sys.stderr if args.pre_commit else sys.stdout
    prefix = "[model-policy] pre-commit hard gate" if args.pre_commit else "[model-policy]"
    print(f"{prefix}: Codex model routing policy drift detected:", file=stream)
    for issue in issues:
        print(f"[model-policy]   {issue}", file=stream)
    print(
        "[model-policy] FIX: restore config.toml defaults and .codex/agents/*.toml roles, "
        "or update the policy hook and CHANGELOG in the same product change.",
        file=stream,
    )
    return 2 if args.pre_commit else 0


if __name__ == "__main__":
    sys.exit(main())
