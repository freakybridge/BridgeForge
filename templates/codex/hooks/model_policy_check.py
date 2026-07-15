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
import json
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
        "model": "gpt-5.6-terra",
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
    "mechanical-sync-worker.toml": {
        "name": "mechanical-sync-worker",
        "model": "gpt-5.6-luna",
        "model_reasoning_effort": "low",
    },
}

ROUTE_AGENT_MODES = {
    "main": {"main"},
    "light-explorer": {"read-only"},
    "implementation-worker": {"implementation"},
    "review-auditor": {"audit"},
    "mechanical-sync-worker": {"controlled-write"},
}
ROUTING_MANIFEST = "skill-routing.json"
REQUIRED_ROUTE_AGENTS = {
    ("archive-scan", "scan-and-candidate-table"): "light-explorer",
    ("collab", "independent-implementation"): "implementation-worker",
    ("collab", "independent-review"): "review-auditor",
    ("debate", "adversarial-review"): "review-auditor",
    ("develop", "implementation"): "implementation-worker",
    ("develop", "delivery-review"): "review-auditor",
    ("escalate", "external-blind-spot-review"): "review-auditor",
    ("find-doc", "search-and-candidate-summary"): "light-explorer",
    ("find-memory", "search-and-candidate-summary"): "light-explorer",
    ("git-sync", "safe-mechanical-sync"): "mechanical-sync-worker",
    ("harvest", "product-change-review"): "review-auditor",
}

USER_CONFIG_GUARD_MARKERS = (
    'Path.home() / ".codex" / "config.toml"',
    "Blocked write to user-level Codex model configuration",
)
USER_CONFIG_GUARD_MATCHERS = ("Bash", "PowerShell", "Write|Edit|MultiEdit")

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
    issues.extend(_check_routing_manifest(root, label))
    return issues


def _check_user_config_guard(root: Path, label: str) -> list[str]:
    path = root / "hooks" / "user_config_write_guard.py"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"{label}/hooks/user_config_write_guard.py missing or unreadable: {exc}"]

    issues = [
        f"{label}/hooks/user_config_write_guard.py missing marker {marker!r}"
        for marker in USER_CONFIG_GUARD_MARKERS
        if marker not in text
    ]
    settings = root / "settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [*issues, f"{label}/settings.json unreadable: {exc}"]

    blocks = data.get("hooks", {}).get("PreToolUse", [])
    if not isinstance(blocks, list):
        return [*issues, f"{label}/settings.json PreToolUse must be a list"]
    for matcher in USER_CONFIG_GUARD_MATCHERS:
        matching = [block for block in blocks if isinstance(block, dict) and block.get("matcher") == matcher]
        commands = [
            hook.get("command", "")
            for block in matching
            for hook in block.get("hooks", [])
            if isinstance(hook, dict)
        ]
        if not any(str(command).endswith(".codex/hooks/user_config_write_guard.py") for command in commands):
            issues.append(f"{label}/settings.json must register user_config_write_guard.py for {matcher}")
    return issues


def _load_routing_manifest(path: Path) -> tuple[dict[str, object], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"cannot read valid JSON: {exc}"
    if not isinstance(data, dict):
        return {}, "must contain a JSON object"
    return data, None


def _source_skill_names() -> set[str] | None:
    skills = REPO_ROOT / "skills"
    if not skills.is_dir():
        return None
    return {path.parent.name for path in skills.glob("*/SKILL.md") if path.is_file()}


def _check_routing_manifest(root: Path, label: str) -> list[str]:
    path = root / ROUTING_MANIFEST
    if not path.is_file():
        return [f"{label}/{ROUTING_MANIFEST} missing"]
    data, err = _load_routing_manifest(path)
    if err:
        return [f"{label}/{ROUTING_MANIFEST} {err}"]

    issues: list[str] = []
    if data.get("schema_version") != 1:
        issues.append(f"{label}/{ROUTING_MANIFEST} schema_version must be 1")
    if not isinstance(data.get("dispatch_contract"), str) or not data["dispatch_contract"].strip():
        issues.append(f"{label}/{ROUTING_MANIFEST} dispatch_contract must be non-empty")
    entries = data.get("skills")
    if not isinstance(entries, list):
        return [*issues, f"{label}/{ROUTING_MANIFEST} skills must be a list"]

    skill_names: set[str] = set()
    seen_routes: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        prefix = f"{label}/{ROUTING_MANIFEST} skills[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{prefix} must be an object")
            continue
        skill = entry.get("skill")
        stage = entry.get("stage")
        agent = entry.get("agent")
        mode = entry.get("mode")
        root_must_do = entry.get("root_must_do")
        if not all(isinstance(value, str) and value.strip() for value in (skill, stage, agent, mode, root_must_do)):
            issues.append(f"{prefix} requires non-empty skill, stage, agent, mode and root_must_do")
            continue
        skill_names.add(skill)
        route_key = (skill, stage)
        if route_key in seen_routes:
            issues.append(f"{prefix} duplicates route {skill}/{stage}")
        seen_routes.add(route_key)
        allowed_modes = ROUTE_AGENT_MODES.get(agent)
        if allowed_modes is None:
            issues.append(f"{prefix} agent {agent!r} is not allowed")
        elif mode not in allowed_modes:
            issues.append(f"{prefix} agent {agent!r} requires mode in {sorted(allowed_modes)!r}, got {mode!r}")
        if agent == "xhigh-auditor":
            issues.append(f"{prefix} must not auto-route to xhigh-auditor")

    source_names = _source_skill_names()
    if source_names is not None and skill_names != source_names:
        issues.append(
            f"{label}/{ROUTING_MANIFEST} skill coverage must match skills/ exactly: "
            f"missing={sorted(source_names - skill_names)!r}, extra={sorted(skill_names - source_names)!r}"
        )
    elif source_names is None and len(skill_names) != 18:
        issues.append(f"{label}/{ROUTING_MANIFEST} must cover 18 product skills, got {len(skill_names)}")

    git_sync = [entry for entry in entries if isinstance(entry, dict) and entry.get("skill") == "git-sync"]
    if len(git_sync) != 1 or git_sync[0].get("agent") != "mechanical-sync-worker":
        issues.append(f"{label}/{ROUTING_MANIFEST} git-sync must have one mechanical-sync-worker route")
    routes = {
        (entry.get("skill"), entry.get("stage")): entry.get("agent")
        for entry in entries
        if isinstance(entry, dict)
    }
    for route, expected_agent in REQUIRED_ROUTE_AGENTS.items():
        if routes.get(route) != expected_agent:
            issues.append(f"{label}/{ROUTING_MANIFEST} {route[0]}/{route[1]} must use {expected_agent}")

    global_entries = data.get("global_entries")
    if not isinstance(global_entries, list):
        return [*issues, f"{label}/{ROUTING_MANIFEST} global_entries must be a list"]
    bridgeforge = [entry for entry in global_entries if isinstance(entry, dict) and entry.get("skill") == "bridgeforge"]
    if len(bridgeforge) != 1 or bridgeforge[0].get("agent") != "main" or bridgeforge[0].get("mode") != "main":
        issues.append(f"{label}/{ROUTING_MANIFEST} bridgeforge must remain a main/main global entry")
    if any(isinstance(entry, dict) and entry.get("agent") == "xhigh-auditor" for entry in global_entries):
        issues.append(f"{label}/{ROUTING_MANIFEST} global_entries must not auto-route to xhigh-auditor")
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
        if root.exists():
            issues.extend(_check_user_config_guard(root, label))

    dogfood_manifest, dogfood_error = _load_routing_manifest(REPO_ROOT / ".codex" / ROUTING_MANIFEST)
    template_manifest, template_error = _load_routing_manifest(REPO_ROOT / "templates" / "codex" / ROUTING_MANIFEST)
    if dogfood_error is None and template_error is None:
        if json.dumps(dogfood_manifest, ensure_ascii=False, sort_keys=True) != json.dumps(template_manifest, ensure_ascii=False, sort_keys=True):
            issues.append(".codex and templates/codex skill-routing.json must be structurally identical")

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
