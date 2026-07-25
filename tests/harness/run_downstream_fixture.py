#!/usr/bin/env python3
"""BridgeForge harness regression checks.

The checks generate a tiny Codex-shaped fixture under `.runtime/harness/` and
exercise the parts that are easy to miss in the source repo:

* D6 rule pre-commit checks in a real `.codex/rules/` layout.
* D8 dogfood mirror checks in a factory-shaped fixture.
* settings.json matcher coverage for Edit|Write|MultiEdit.
* Root pre-commit coverage for both Claude and Codex dogfood gates.
* Repository text surfaces must be UTF-8 without BOM.
* Codex model / reasoning-effort routing policy.
* User-level Codex model configuration must remain read-only to skeleton hooks.
* high-confidence `skills/**/SKILL.md` metadata and local reference health.
* User-skill maintenance contract plus executable missing/divergent no-write checks.

Generated fixture directories are disposable and are never product source.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = REPO_ROOT / ".runtime" / "harness"
CODEX_TEMPLATE = REPO_ROOT / "templates" / "codex"
CLAUDE_TEMPLATE = REPO_ROOT / "templates" / "claude"
CODEX_FIXTURE = RUNTIME_ROOT / "downstream-codex"
SWITCH_FIXTURE = RUNTIME_ROOT / "downstream-switch"
SKILL_METADATA_FIXTURE = RUNTIME_ROOT / "skill-metadata"
USER_SKILL_FIXTURE = RUNTIME_ROOT / "user-skill-distribution"
LAYOUT_MIGRATION_FIXTURE = RUNTIME_ROOT / "layout-migration"
CODEX_GIT_SYNC_REMOTE = RUNTIME_ROOT / "codex-git-sync-remote.git"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _is_under(path: Path, parent: Path) -> bool:
    path_r = path.resolve()
    parent_r = parent.resolve()
    try:
        path_r.relative_to(parent_r)
        return True
    except ValueError:
        return False


def _safe_reset_dir(path: Path) -> None:
    if not _is_under(path, RUNTIME_ROOT):
        raise RuntimeError(f"refuse to reset path outside runtime harness: {path}")
    if path.exists():
        shutil.rmtree(path, onerror=_remove_readonly)
    path.mkdir(parents=True, exist_ok=True)


def _remove_readonly(func, path: str, _exc_info) -> None:
    os.chmod(path, 0o700)
    func(path)


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def run(
    cmd: list[str],
    cwd: Path,
    timeout: int = 20,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )


def run_with_input(
    cmd: list[str],
    cwd: Path,
    input_text: str,
    timeout: int = 20,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def build_codex_fixture(*, include_factory_templates: bool = False) -> Path:
    """Build a disposable Codex downstream fixture."""
    _safe_reset_dir(CODEX_FIXTURE)

    shutil.copy2(CODEX_TEMPLATE / "AGENTS.md", CODEX_FIXTURE / "AGENTS.md")
    shutil.copy2(CODEX_TEMPLATE / "CHANGELOG.md", CODEX_FIXTURE / "CHANGELOG.md")
    shutil.copy2(CODEX_TEMPLATE / "VERSION", CODEX_FIXTURE / "VERSION")

    codex_dir = CODEX_FIXTURE / ".codex"
    codex_dir.mkdir()
    for name in ("hooks", "scripts", "rules", "memory"):
        _copytree(CODEX_TEMPLATE / name, codex_dir / name)
    shutil.copy2(CODEX_TEMPLATE / "settings.json", codex_dir / "settings.json")
    shutil.copy2(REPO_ROOT / "VERSION", codex_dir / ".bridgeforge_version")
    shutil.copy2(CODEX_TEMPLATE / "config.toml", codex_dir / "config.toml")
    shutil.copy2(CODEX_TEMPLATE / "subscription-tier.toml", codex_dir / "subscription-tier.toml")
    shutil.copy2(CODEX_TEMPLATE / "skill-routing.json", codex_dir / "skill-routing.json")
    _copytree(CODEX_TEMPLATE / "agents", codex_dir / "agents")

    _copytree(CODEX_TEMPLATE / ".githooks", CODEX_FIXTURE / ".githooks")

    if include_factory_templates:
        _copytree(CODEX_TEMPLATE / "hooks", CODEX_FIXTURE / "templates" / "codex" / "hooks")

    r = run(["git", "init"], CODEX_FIXTURE)
    if r.returncode != 0:
        raise RuntimeError(f"git init failed: {r.stderr.strip()}")
    return CODEX_FIXTURE


def check_rule_index_missing() -> CheckResult:
    fixture = build_codex_fixture()
    target = fixture / ".codex" / "rules" / "debugging.md"
    target.unlink()
    r = run([sys.executable, ".codex/hooks/rule_index_check.py", "--pre-commit"], fixture)
    ok = r.returncode == 2 and "debugging.md" in (r.stderr + r.stdout)
    return CheckResult(
        "codex_rule_index_missing",
        ok,
        f"expected exit 2 mentioning debugging.md, got exit {r.returncode}",
    )


def check_rule_size_over_limit() -> CheckResult:
    fixture = build_codex_fixture()
    oversized = fixture / ".codex" / "rules" / "oversized_fixture.md"
    oversized.write_text(
        "---\npaths:\n  - src/feature/**\n---\n\n"
        + "\n".join(f"- fixture line {i}" for i in range(560))
        + "\n",
        encoding="utf-8",
    )
    add = run(["git", "add", ".codex/rules/oversized_fixture.md"], fixture)
    if add.returncode != 0:
        return CheckResult("codex_rule_size_over_limit", False, f"git add failed: {add.stderr.strip()}")
    r = run([sys.executable, ".codex/hooks/rule_size_check.py", "--pre-commit"], fixture)
    ok = r.returncode == 2 and "oversized_fixture.md" in (r.stderr + r.stdout)
    return CheckResult(
        "codex_rule_size_over_limit",
        ok,
        f"expected exit 2 mentioning oversized_fixture.md, got exit {r.returncode}",
    )


def check_mirror_missing_hook() -> CheckResult:
    fixture = build_codex_fixture(include_factory_templates=True)
    missing = fixture / ".codex" / "hooks" / "show_state.py"
    missing.unlink()
    r = run([sys.executable, ".codex/hooks/mirror_drift_check.py"], fixture)
    ok = r.returncode == 2 and "show_state.py" in (r.stderr + r.stdout)
    return CheckResult(
        "codex_mirror_missing_hook",
        ok,
        f"expected exit 2 mentioning show_state.py, got exit {r.returncode}",
    )


def check_mirror_no_templates_noop() -> CheckResult:
    fixture = build_codex_fixture(include_factory_templates=False)
    r = run([sys.executable, ".codex/hooks/mirror_drift_check.py"], fixture)
    ok = r.returncode == 0
    return CheckResult(
        "codex_mirror_no_templates_noop",
        ok,
        f"expected no-op exit 0 without templates/codex/hooks, got exit {r.returncode}",
    )


def _matcher_tokens(matcher: str) -> set[str]:
    return {part.strip() for part in matcher.split("|") if part.strip()}


def check_settings_multiedit_matchers() -> CheckResult:
    settings = json.loads((CODEX_TEMPLATE / "settings.json").read_text(encoding="utf-8-sig"))
    required_commands = {
        ".codex/scripts/memory_rebuild_index.py --from-hook",
        ".codex/hooks/memory_lint.py",
        ".codex/hooks/rule_index_check.py",
        ".codex/hooks/rule_size_check.py",
        ".codex/hooks/requirements_check.py",
        ".codex/hooks/fallback_smell_check.py",
        ".codex/hooks/encoding_check.py",
    }
    missing: list[str] = []
    for block in settings.get("hooks", {}).get("PostToolUse", []):
        tokens = _matcher_tokens(block.get("matcher", ""))
        commands = {
            hook.get("command", "")
            for hook in block.get("hooks", [])
            if isinstance(hook, dict)
        }
        matched = {
            required
            for required in required_commands
            if any(command.endswith(required) for command in commands)
        }
        if not matched:
            continue
        if not {"Edit", "Write", "MultiEdit"}.issubset(tokens):
            missing.extend(sorted(matched))
    ok = not missing
    return CheckResult(
        "codex_settings_multiedit_matchers",
        ok,
        "all critical PostToolUse hooks include Edit|Write|MultiEdit" if ok else "matcher missing MultiEdit for: " + ", ".join(missing),
    )


def check_root_precommit_dual_agent_gates() -> CheckResult:
    precommit = (REPO_ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    required = [
        '.claude/hooks/mirror_drift_check.py',
        '.codex/hooks/mirror_drift_check.py',
        '.claude/hooks/rule_size_check.py" --pre-commit',
        '.claude/hooks/rule_index_check.py" --pre-commit',
        '.codex/hooks/rule_size_check.py" --pre-commit',
        '.codex/hooks/rule_index_check.py" --pre-commit',
        '.codex/hooks/model_policy_check.py" --pre-commit',
        '.claude/hooks/encoding_check.py" --pre-commit',
        '.codex/hooks/encoding_check.py" --pre-commit',
        '.claude/hooks/skill_metadata_check.py" --pre-commit',
        '.codex/hooks/skill_metadata_check.py" --pre-commit',
        'for CONFIG_DIR in .claude .codex; do',
        '$CONFIG_DIR/scripts/memory_rebuild_index.py',
    ]
    missing = [needle for needle in required if needle not in precommit]
    bad_quoted_args = [
        '.claude/hooks/rule_size_check.py --pre-commit',
        '.claude/hooks/rule_index_check.py --pre-commit',
        '.codex/hooks/rule_size_check.py --pre-commit',
        '.codex/hooks/rule_index_check.py --pre-commit',
        '.codex/hooks/model_policy_check.py --pre-commit',
        '.claude/hooks/encoding_check.py --pre-commit',
        '.codex/hooks/encoding_check.py --pre-commit',
        '.claude/hooks/skill_metadata_check.py --pre-commit',
        '.codex/hooks/skill_metadata_check.py --pre-commit',
    ]
    broken = [needle for needle in bad_quoted_args if needle in precommit]
    ok = not missing and not broken
    detail = "root pre-commit covers Claude and Codex gates"
    if missing:
        detail = "missing root pre-commit entries: " + ", ".join(missing)
    if broken:
        detail += "; quoted script+arg entries still present: " + ", ".join(broken)
    return CheckResult("root_precommit_dual_agent_gates", ok, detail)


def check_precommit_shebang_bytes() -> CheckResult:
    paths = [
        REPO_ROOT / ".githooks" / "pre-commit",
        REPO_ROOT / "templates" / "claude" / ".githooks" / "pre-commit",
        REPO_ROOT / "templates" / "codex" / ".githooks" / "pre-commit",
    ]
    bad: list[str] = []
    for path in paths:
        rel = path.relative_to(REPO_ROOT).as_posix()
        data = path.read_bytes()
        if data.startswith(b"\xef\xbb\xbf"):
            bad.append(f"{rel}: starts with UTF-8 BOM")
        elif not data.startswith(b"#!"):
            head = data[:4].hex(" ").upper()
            bad.append(f"{rel}: expected shebang bytes 23 21, got {head}")

    ok = not bad
    return CheckResult(
        "precommit_shebang_bytes",
        ok,
        "all pre-commit hooks start with #! and no BOM" if ok else "; ".join(bad),
    )


def check_encoding_no_bom() -> CheckResult:
    source = run([sys.executable, ".codex/hooks/encoding_check.py", "--pre-commit"], REPO_ROOT)
    if source.returncode != 0:
        return CheckResult(
            "encoding_no_bom",
            False,
            f"source tree should not contain UTF-8 BOM, got exit {source.returncode}: {(source.stdout + source.stderr).strip()}",
        )

    fixture = build_codex_fixture()
    target = fixture / ".codex" / "memory" / "_stats.json"
    target.write_bytes(b"\xef\xbb\xbf" + target.read_bytes())
    bad = run([sys.executable, ".codex/hooks/encoding_check.py", "--pre-commit"], fixture)

    ok = bad.returncode == 2 and ".codex/memory/_stats.json" in (bad.stdout + bad.stderr)
    return CheckResult(
        "encoding_no_bom",
        ok,
        "encoding hook passes source and blocks a BOM-prefixed fixture file"
        if ok
        else f"expected fixture BOM to exit 2, got exit {bad.returncode}: {(bad.stdout + bad.stderr).strip()}",
    )


def _shell_guard_payload(command: str) -> str:
    return json.dumps({"tool_input": {"command": command}}, ensure_ascii=False)


def _run_shell_guard(script: Path, command: str) -> subprocess.CompletedProcess[str]:
    return run_with_input([sys.executable, str(script)], REPO_ROOT, _shell_guard_payload(command))


def check_non_ascii_shell_guard() -> CheckResult:
    scripts = [
        CODEX_TEMPLATE / "hooks" / "non_ascii_shell_guard.py",
        CLAUDE_TEMPLATE / "hooks" / "non_ascii_shell_guard.py",
    ]
    cases = [
        ("ascii_pipe_python_stdin", "Write-Output hello | python -", 0),
        ("chinese_here_string_python_stdin", "@'\nprint(\"中文\")\n'@ | python -", 2),
        ("emoji_redirection", '"😀" > out.txt', 2),
        ("chinese_set_content", 'Set-Content README.md -Value "中文"', 2),
        ("chinese_write_output_readonly", 'Write-Output "中文"', 0),
        ("node_inline_write", 'node -e "fs.writeFileSync(\'x.md\', \'中文\')"', 2),
    ]

    failures: list[str] = []
    for script in scripts:
        for label, command, expected in cases:
            result = _run_shell_guard(script, command)
            if result.returncode != expected:
                failures.append(
                    f"{script.relative_to(REPO_ROOT).as_posix()}:{label} "
                    f"expected {expected}, got {result.returncode}: {(result.stdout + result.stderr).strip()}"
                )

    return CheckResult(
        "non_ascii_shell_guard",
        not failures,
        "Claude and Codex guards block risky non-ASCII shell writes and allow safe output"
        if not failures
        else "; ".join(failures),
    )


def check_non_ascii_shell_guard_settings() -> CheckResult:
    expected = {
        CODEX_TEMPLATE / "settings.json": ".codex/hooks/non_ascii_shell_guard.py",
        CLAUDE_TEMPLATE / "settings.json": ".claude/hooks/non_ascii_shell_guard.py",
    }
    missing: list[str] = []
    for settings_path, command_suffix in expected.items():
        settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        found = False
        for block in settings.get("hooks", {}).get("PreToolUse", []):
            if "Bash" not in _matcher_tokens(block.get("matcher", "")):
                continue
            for hook in block.get("hooks", []):
                if isinstance(hook, dict) and hook.get("command", "").endswith(command_suffix):
                    found = True
        if not found:
            missing.append(settings_path.relative_to(REPO_ROOT).as_posix())

    return CheckResult(
        "non_ascii_shell_guard_settings",
        not missing,
        "Claude and Codex settings register non_ascii_shell_guard.py on PreToolUse Bash"
        if not missing
        else "missing guard registration: " + ", ".join(missing),
    )


def check_encoding_garble_scan() -> CheckResult:
    fixture = build_codex_fixture()
    target = fixture / ".codex" / "settings.json"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "Encoding hygiene",
            "?" * 3,
            1,
        ),
        encoding="utf-8",
    )
    result = run([sys.executable, ".codex/hooks/encoding_check.py", "--scan-garble", ".codex"], fixture)
    text = result.stdout + result.stderr
    ok = result.returncode == 2 and ".codex/settings.json" in text and "?" * 3 in text
    return CheckResult(
        "encoding_garble_scan",
        ok,
        "encoding scan reports suspicious question-mark replacement text"
        if ok
        else f"expected garble scan exit 2 mentioning settings.json, got {result.returncode}: {text.strip()}",
    )


def _build_switch_fixture() -> Path:
    _safe_reset_dir(SWITCH_FIXTURE)
    fixture = SWITCH_FIXTURE
    shutil.copy2(CLAUDE_TEMPLATE / "CLAUDE.md", fixture / "CLAUDE.md")
    claude_dir = fixture / ".claude"
    claude_dir.mkdir()
    for name in ("hooks", "scripts", "rules", "memory"):
        _copytree(CLAUDE_TEMPLATE / name, claude_dir / name)
    shutil.copy2(CLAUDE_TEMPLATE / "settings.json", claude_dir / "settings.json")
    shutil.copy2(REPO_ROOT / "VERSION", claude_dir / ".bridgeforge_version")

    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    shutil.copy2(CLAUDE_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")
    return fixture


def _add_codex_archive(fixture: Path, *, shared_memory: str | None = None) -> Path:
    archive = fixture / ".bridgeforge" / "archive" / "codex" / "20260707-153000"
    archive.mkdir(parents=True)
    shutil.copy2(CODEX_TEMPLATE / "AGENTS.md", archive / "AGENTS.md")
    codex_dir = archive / ".codex"
    codex_dir.mkdir()
    for name in ("hooks", "scripts", "rules", "memory"):
        _copytree(CODEX_TEMPLATE / name, codex_dir / name)
    shutil.copy2(CODEX_TEMPLATE / "settings.json", codex_dir / "settings.json")
    shutil.copy2(REPO_ROOT / "VERSION", codex_dir / ".bridgeforge_version")
    shutil.copy2(CODEX_TEMPLATE / "config.toml", codex_dir / "config.toml")
    _copytree(CODEX_TEMPLATE / "agents", codex_dir / "agents")
    if shared_memory is not None:
        (codex_dir / "memory" / "shared.md").write_text(shared_memory, encoding="utf-8")
    else:
        (codex_dir / "memory" / "codex-note.md").write_text("codex note\n", encoding="utf-8")
    return archive


def check_switch_archive_restore() -> CheckResult:
    fixture = _build_switch_fixture()
    _add_codex_archive(fixture)
    (fixture / ".claude" / "memory" / "claude-note.md").write_text("claude note\n", encoding="utf-8")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--skip-settings-migration",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    claude_archives = list((fixture / ".bridgeforge" / "archive" / "claude").glob("*"))
    ok = (
        r.returncode == 0
        and (fixture / "AGENTS.md").exists()
        and (fixture / ".codex").is_dir()
        and not (fixture / "CLAUDE.md").exists()
        and not (fixture / ".claude").exists()
        and len(claude_archives) == 1
        and (claude_archives[0] / "CLAUDE.md").exists()
        and (fixture / ".codex" / "memory" / "codex-note.md").exists()
        and (fixture / ".codex" / "memory" / "claude-note.md").exists()
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_archive_restore",
        ok,
        "switch restores target archive, archives/removes old Claude skeleton, and merges unique memory"
        if ok
        else f"expected successful archive restore switch, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_dry_run_full_plan() -> CheckResult:
    fixture = _build_switch_fixture()
    _add_codex_archive(fixture)
    (fixture / ".claude" / "memory" / "claude-note.md").write_text("claude note\n", encoding="utf-8")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--dry-run",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    ok = (
        r.returncode == 0
        and "Target source: archive" in text
        and "Will archive old agent paths" in text
        and "Memory notes copied automatically" in text
        and "Settings migration candidates" in text
        and "Archived-only surfaces" in text
        and (fixture / "CLAUDE.md").exists()
        and not (fixture / ".codex").exists()
    )
    return CheckResult(
        "switch_dry_run_full_plan",
        ok,
        "dry-run prints the full switch plan and leaves files unchanged"
        if ok
        else f"expected dry-run full plan with no changes, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_complete_target_cleanup_only() -> CheckResult:
    fixture = _build_switch_fixture()
    (fixture / "AGENTS.md").write_text("preexisting codex entry\n", encoding="utf-8")
    codex_dir = fixture / ".codex"
    codex_dir.mkdir()
    (codex_dir / "settings.json").write_text("{}\n", encoding="utf-8")
    (codex_dir / "memory").mkdir()
    (codex_dir / "memory" / "codex-note.md").write_text("codex note\n", encoding="utf-8")
    (fixture / ".claude" / "memory" / "claude-note.md").write_text("claude note\n", encoding="utf-8")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--skip-settings-migration",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    claude_archives = list((fixture / ".bridgeforge" / "archive" / "claude").glob("*"))
    ok = (
        r.returncode == 0
        and "Target source: live" in text
        and "Target path conflicts: none" in text
        and "Will restore/install target files: none" in text
        and not (fixture / "CLAUDE.md").exists()
        and not (fixture / ".claude").exists()
        and (fixture / "AGENTS.md").read_text(encoding="utf-8") == "preexisting codex entry\n"
        and (fixture / ".codex" / "memory" / "codex-note.md").exists()
        and (fixture / ".codex" / "memory" / "claude-note.md").exists()
        and len(claude_archives) == 1
        and (claude_archives[0] / "CLAUDE.md").exists()
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_complete_target_cleanup_only",
        ok,
        "complete target skeleton plus old live skeleton archives/removes only the old skeleton"
        if ok
        else f"expected cleanup-only switch with preserved target files, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_claude_complete_target_cleanup_only() -> CheckResult:
    fixture = build_codex_fixture()
    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")
    (fixture / "CLAUDE.md").write_text("preexisting claude entry\n", encoding="utf-8")
    claude_dir = fixture / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("{}\n", encoding="utf-8")
    (claude_dir / "memory").mkdir()
    (claude_dir / "memory" / "claude-note.md").write_text("claude note\n", encoding="utf-8")
    (fixture / ".codex" / "memory" / "codex-note.md").write_text("codex note\n", encoding="utf-8")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "claude",
            "--template-root",
            str(REPO_ROOT),
            "--skip-settings-migration",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    codex_archives = list((fixture / ".bridgeforge" / "archive" / "codex").glob("*"))
    ok = (
        r.returncode == 0
        and "Target source: live" in text
        and "Target path conflicts: none" in text
        and "Will restore/install target files: none" in text
        and not (fixture / "AGENTS.md").exists()
        and not (fixture / ".codex").exists()
        and (fixture / "CLAUDE.md").read_text(encoding="utf-8") == "preexisting claude entry\n"
        and (fixture / ".claude" / "memory" / "claude-note.md").exists()
        and (fixture / ".claude" / "memory" / "codex-note.md").exists()
        and len(codex_archives) == 1
        and (codex_archives[0] / "AGENTS.md").exists()
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_claude_complete_target_cleanup_only",
        ok,
        "complete Claude target plus old Codex live skeleton archives/removes only the old skeleton"
        if ok
        else f"expected Claude cleanup-only switch with preserved target files, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_partial_target_conflict_stops() -> CheckResult:
    _safe_reset_dir(SWITCH_FIXTURE)
    fixture = SWITCH_FIXTURE
    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir()
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")
    (fixture / "AGENTS.md").write_text("partial codex skeleton\n", encoding="utf-8")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    ok = (
        r.returncode == 2
        and "target path conflicts" in text
        and (fixture / "AGENTS.md").read_text(encoding="utf-8") == "partial codex skeleton\n"
        and not (fixture / ".codex").exists()
    )
    return CheckResult(
        "switch_partial_target_conflict_stops",
        ok,
        "partial target skeleton is treated as a conflict, not as already-active target"
        if ok
        else f"expected partial target conflict stop, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_partial_target_dir_conflict_stops() -> CheckResult:
    fixture = _build_switch_fixture()
    (fixture / "AGENTS.md").write_text("partial codex skeleton\n", encoding="utf-8")
    (fixture / ".codex").mkdir()
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    ok = (
        r.returncode == 2
        and "target path conflicts" in text
        and (fixture / "CLAUDE.md").exists()
        and (fixture / ".claude").is_dir()
        and (fixture / "AGENTS.md").read_text(encoding="utf-8") == "partial codex skeleton\n"
        and (fixture / ".codex").is_dir()
        and not (fixture / ".codex" / "settings.json").exists()
    )
    return CheckResult(
        "switch_partial_target_dir_conflict_stops",
        ok,
        "target entry plus config dir without settings.json is still a conflict"
        if ok
        else f"expected partial target dir conflict stop, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_memory_conflict_decision() -> CheckResult:
    fixture = _build_switch_fixture()
    _add_codex_archive(fixture, shared_memory="codex shared\n")
    (fixture / ".claude" / "memory" / "shared.md").write_text("claude shared\n", encoding="utf-8")
    blocked = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--skip-settings-migration",
        ],
        fixture,
    )
    if blocked.returncode != 2 or not (fixture / "CLAUDE.md").exists():
        return CheckResult(
            "switch_memory_conflict_decision",
            False,
            f"expected first run to stop on memory conflict, got exit {blocked.returncode}",
        )
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--skip-settings-migration",
            "--memory-conflict",
            "shared.md=copy-old",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    side_files = list((fixture / ".codex" / "memory").glob("shared.from-claude*.md"))
    ok = r.returncode == 0 and "Validation passed" in text and len(side_files) == 1
    return CheckResult(
        "switch_memory_conflict_decision",
        ok,
        "non-identical memory conflict stops until an explicit per-file decision is replayed"
        if ok
        else f"expected successful replay with side-file memory copy, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_settings_decision() -> CheckResult:
    fixture = _build_switch_fixture()
    settings = json.loads((fixture / ".claude" / "settings.json").read_text(encoding="utf-8-sig"))
    settings.setdefault("env", {})["BRIDGEFORGE_TEST_FLAG"] = "1"
    (fixture / ".claude" / "settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    blocked = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
        ],
        fixture,
    )
    if blocked.returncode != 2 or not (fixture / "CLAUDE.md").exists() or "env.BRIDGEFORGE_TEST_FLAG" not in (blocked.stdout + blocked.stderr):
        return CheckResult(
            "switch_settings_decision",
            False,
            f"expected first run to stop on settings candidate, got exit {blocked.returncode}",
        )

    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--skip-settings-migration",
            "--migrate-setting",
            "env.BRIDGEFORGE_TEST_FLAG",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    target_settings = json.loads((fixture / ".codex" / "settings.json").read_text(encoding="utf-8-sig"))
    ok = (
        r.returncode == 0
        and target_settings.get("env", {}).get("BRIDGEFORGE_TEST_FLAG") == "1"
        and "hooks" not in target_settings.get("env", {})
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_settings_decision",
        ok,
        "settings migration stops by default and can replay one dotted setting path"
        if ok
        else f"expected selected env setting migration, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_same_agent_noop() -> CheckResult:
    fixture = build_codex_fixture()
    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    ok = r.returncode == 0 and "Already target agent" in text and not (fixture / ".bridgeforge" / "archive" / "codex").exists()
    return CheckResult(
        "switch_same_agent_noop",
        ok,
        "switching to the already-active agent is a no-op and points back to normal /bridgeforge"
        if ok
        else f"expected same-agent no-op, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_codex_to_claude_archive_scope() -> CheckResult:
    fixture = build_codex_fixture()
    project_skill = fixture / ".codex" / "skills" / "project-only" / "SKILL.md"
    project_skill.parent.mkdir(parents=True)
    project_skill.write_text("---\nname: project-only\n---\n", encoding="utf-8")
    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "claude",
            "--template-root",
            str(REPO_ROOT),
            "--skip-settings-migration",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    codex_archives = list((fixture / ".bridgeforge" / "archive" / "codex").glob("*"))
    ok = (
        r.returncode == 0
        and (fixture / "CLAUDE.md").exists()
        and (fixture / ".claude" / "settings.json").exists()
        and not (fixture / "AGENTS.md").exists()
        and not (fixture / ".codex").exists()
        and not (fixture / ".agents").exists()
        and len(codex_archives) == 1
        and (codex_archives[0] / "AGENTS.md").exists()
        and (codex_archives[0] / ".codex" / "settings.json").exists()
        and (codex_archives[0] / ".codex" / "skills" / "project-only" / "SKILL.md").exists()
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_codex_to_claude_archive_scope",
        ok,
        "Codex to Claude archives AGENTS.md and .codex including project-private skills without creating .agents"
        if ok
        else f"expected Codex archive scope and cleanup, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_no_old_installs_target() -> CheckResult:
    _safe_reset_dir(SWITCH_FIXTURE)
    fixture = SWITCH_FIXTURE
    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir()
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    ok = (
        r.returncode == 0
        and (fixture / "AGENTS.md").exists()
        and (fixture / ".codex" / "settings.json").exists()
        and not (fixture / ".bridgeforge" / "archive" / "claude").exists()
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_no_old_installs_target",
        ok,
        "project without an old skeleton can enable the target agent from templates"
        if ok
        else f"expected template install without old archive, got exit {r.returncode}: {text.strip()}",
    )


def _switch_module():
    module_path = REPO_ROOT / "scripts" / "bridgeforge_switch.py"
    spec = importlib.util.spec_from_file_location("bridgeforge_switch_semantic_fixture", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import semantic switch module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _switch_live_digest(fixture: Path, agent: str) -> str:
    entry = "CLAUDE.md" if agent == "claude" else "AGENTS.md"
    config = ".claude" if agent == "claude" else ".codex"
    digest = hashlib.sha256()
    for path in [fixture / entry, *sorted((fixture / config).rglob("*"))]:
        if not path.is_file():
            continue
        digest.update(path.relative_to(fixture).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _semantic_manifest(
    fixture: Path,
    target: str,
    *,
    migration_id: str,
    evidence_level: str = "text-review",
    evidence_command: list[str] | None = None,
) -> tuple[object, dict[str, object]]:
    module = _switch_module()
    plan = module.build_plan(target, fixture.resolve(), REPO_ROOT.resolve())
    manifest = module.build_proposal(plan, migration_id=migration_id)
    projection_index = 0
    for item in manifest["items"]:
        if item["status"] != "blocked":
            continue
        if item["target"]["action"] == "replay-archive":
            target_rel = item["target"]["path"]
            content = plan.archive_files[item["source"]["path"]].read_bytes()
        else:
            projection_index += 1
            config = ".codex" if target == "codex" else ".claude"
            target_rel = f"{config}/rules/semantic-projection-{projection_index}.md"
            content = (
                f"# Migrated constraint {item['constraint_id']}\n\n"
                f"Source: {item['source']['path']}\n"
            ).encode("utf-8")
            item["target"].update(
                {
                    "action": "write",
                    "path": target_rel,
                    "base_sha256": module._sha_bytes(
                        module._target_template_bytes(plan, target_rel)
                    ),
                    "content": content.decode("utf-8"),
                    "content_base64": None,
                    "sha256": module._sha_bytes(content),
                }
            )
        item["target"]["diff"] = module._expected_diff(plan, target_rel, content)
        item["target_owner"] = (
            "user-owned"
            if item["target"]["action"] == "replay-archive"
            else "constraint-generated"
        )
        item["constraint_level"] = "hard"
        item["semantic"] = {
            "classification": "translatable",
            "summary": f"Fixture semantic contract for {item['source']['path']}",
        }
        item["adapter"] = {
            "kind": "manual",
            "source": "fixture user-reviewed semantic adapter",
        }
        item["approval"] = {
            "status": "approved",
            "approved_by": "fixture-user",
        }
        item["evidence"] = {
            "required_level": evidence_level,
            "level": evidence_level,
            "status": "passed" if evidence_level in {"text-review", "static"} else "pending",
            "details": "fixture review",
        }
        if evidence_level in {"contract-smoke", "native-host"}:
            if evidence_command is not None:
                item["evidence"]["command"] = evidence_command
    return plan, manifest


def _write_switch_manifest(fixture: Path, manifest: dict[str, object]) -> Path:
    path = fixture / "approved-semantic-manifest.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _run_semantic_switch(
    fixture: Path,
    target: str,
    manifest: Path | None = None,
    *,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "scripts/bridgeforge_switch.py",
        target,
        "--template-root",
        str(REPO_ROOT),
    ]
    if manifest is not None:
        command.extend(["--manifest", str(manifest)])
    if dry_run:
        command.append("--dry-run")
    return run(command, fixture, env=env)


def check_switch_archive_restore() -> CheckResult:
    fixture = _build_switch_fixture()
    custom = fixture / ".claude" / "memory" / "project-constraint.md"
    custom.write_text("never bypass the project risk gate\n", encoding="utf-8")
    before = _switch_live_digest(fixture, "claude")

    proposal = _run_semantic_switch(fixture, "codex", dry_run=True)
    proposal_text = proposal.stdout + proposal.stderr
    if (
        proposal.returncode != 2
        or "BEGIN_BRIDGEFORGE_MIGRATION_MANIFEST" not in proposal_text
        or _switch_live_digest(fixture, "claude") != before
    ):
        return CheckResult(
            "switch_semantic_manifest_apply",
            False,
            f"unapproved proposal did not fail closed: {proposal_text.strip()}",
        )

    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-semantic-apply",
    )
    manifest_path = _write_switch_manifest(fixture, manifest)
    applied = _run_semantic_switch(fixture, "codex", manifest_path)
    text = applied.stdout + applied.stderr
    receipts = list((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
    required = [
        fixture / ".codex" / "config.toml",
        fixture / ".codex" / ".bridgeforge_version",
        fixture / ".codex" / "subscription-tier.toml",
        fixture / ".codex" / "skill-routing.json",
        fixture / ".codex" / "agents" / "implementation-worker.toml",
    ]
    receipt = json.loads(receipts[0].read_text(encoding="utf-8")) if len(receipts) == 1 else {}
    hard_receipt_items = [
        item
        for item in receipt.get("items", [])
        if item.get("constraint_level") == "hard"
    ]
    ok = (
        applied.returncode == 0
        and all(path.is_file() for path in required)
        and not (fixture / "CLAUDE.md").exists()
        and not (fixture / ".claude").exists()
        and len(receipts) == 1
        and receipt.get("status") == "success"
        and receipt.get("target_agent") == "codex"
        and receipt.get("archive", {}).get("path")
        and hard_receipt_items
        and all(item.get("status") == "applied" for item in hard_receipt_items)
        and all(item.get("evidence", {}).get("status") == "passed" for item in hard_receipt_items)
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_semantic_manifest_apply",
        ok,
        "unapproved analysis is zero-write; approved manifest installs the complete Codex surface and writes one receipt"
        if ok
        else f"semantic apply failed: {text.strip()}",
    )


def check_switch_dry_run_full_plan() -> CheckResult:
    fixture = _build_switch_fixture()
    (fixture / ".claude" / "rules" / "project-hard.md").write_text(
        "MUST preserve this hard rule\n",
        encoding="utf-8",
    )
    before = _switch_live_digest(fixture, "claude")
    result = _run_semantic_switch(fixture, "codex", dry_run=True)
    text = result.stdout + result.stderr
    ok = (
        result.returncode == 2
        and "constraint_id" in text
        and '"constraint_level": "hard"' in text
        and '"source_owner": "unknown-historical"' in text
        and '"required_level": "text-review"' in text
        and _switch_live_digest(fixture, "claude") == before
        and not (fixture / ".codex").exists()
    )
    return CheckResult(
        "switch_semantic_proposal",
        ok,
        "dry-run emits per-item semantic, ownership, hash, adapter, approval, and evidence fields without writes"
        if ok
        else f"semantic proposal contract failed: {text.strip()}",
    )


def check_switch_complete_target_cleanup_only() -> CheckResult:
    fixture = _build_switch_fixture()
    (fixture / "AGENTS.md").write_text("preexisting target\n", encoding="utf-8")
    (fixture / ".codex").mkdir()
    before = _switch_live_digest(fixture, "claude")
    result = _run_semantic_switch(fixture, "codex")
    text = result.stdout + result.stderr
    ok = (
        result.returncode == 2
        and "target live paths already exist" in text
        and _switch_live_digest(fixture, "claude") == before
        and (fixture / "AGENTS.md").read_text(encoding="utf-8") == "preexisting target\n"
    )
    return CheckResult(
        "switch_target_prestate_fail_closed",
        ok,
        "pre-existing target state blocks semantic switch and both live trees remain unchanged"
        if ok
        else f"target pre-state was not fail-closed: {text.strip()}",
    )


def check_switch_claude_complete_target_cleanup_only() -> CheckResult:
    fixture = build_codex_fixture()
    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")
    (fixture / ".codex" / "memory" / "roundtrip.md").write_text(
        "roundtrip constraint\n",
        encoding="utf-8",
    )
    _plan, manifest = _semantic_manifest(
        fixture,
        "claude",
        migration_id="fixture-codex-to-claude",
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "claude", path)
    text = result.stdout + result.stderr
    ok = (
        result.returncode == 0
        and (fixture / "CLAUDE.md").is_file()
        and (fixture / ".claude" / "settings.json").is_file()
        and not (fixture / "AGENTS.md").exists()
        and not (fixture / ".codex").exists()
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_bidirectional_semantic_apply",
        ok,
        "Codex-to-Claude uses the same approved semantic manifest path"
        if ok
        else f"Codex-to-Claude semantic apply failed: {text.strip()}",
    )


def check_switch_partial_target_conflict_stops() -> CheckResult:
    _safe_reset_dir(SWITCH_FIXTURE)
    fixture = SWITCH_FIXTURE
    (fixture / "scripts").mkdir()
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", fixture / "scripts" / "bridgeforge_switch.py")
    (fixture / "AGENTS.md").write_text("partial target\n", encoding="utf-8")
    result = _run_semantic_switch(fixture, "codex")
    ok = (
        result.returncode == 2
        and (fixture / "AGENTS.md").read_text(encoding="utf-8") == "partial target\n"
        and not (fixture / ".codex").exists()
    )
    return CheckResult(
        "switch_partial_target_conflict_stops",
        ok,
        "partial target entry blocks before any mutation"
        if ok
        else f"partial target did not block: {(result.stdout + result.stderr).strip()}",
    )


def check_switch_partial_target_dir_conflict_stops() -> CheckResult:
    fixture = _build_switch_fixture()
    (fixture / ".codex").mkdir()
    before = _switch_live_digest(fixture, "claude")
    result = _run_semantic_switch(fixture, "codex")
    ok = (
        result.returncode == 2
        and _switch_live_digest(fixture, "claude") == before
        and (fixture / ".codex").is_dir()
    )
    return CheckResult(
        "switch_partial_target_dir_conflict_stops",
        ok,
        "partial target config directory blocks with the old live tree unchanged"
        if ok
        else f"partial target directory did not block: {(result.stdout + result.stderr).strip()}",
    )


def check_switch_memory_conflict_decision() -> CheckResult:
    fixture = _build_switch_fixture()
    custom = fixture / ".claude" / "hooks" / "project_hard_gate.py"
    custom.write_text("raise SystemExit(0)\n", encoding="utf-8")
    before = _switch_live_digest(fixture, "claude")
    _plan, weak_manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-evidence-too-weak",
        evidence_level="text-review",
    )
    weak_path = _write_switch_manifest(fixture, weak_manifest)
    weak = _run_semantic_switch(fixture, "codex", weak_path, dry_run=True)
    weak_text = weak.stdout + weak.stderr
    if (
        weak.returncode != 2
        or "evidence level is below the minimum" not in weak_text
        or _switch_live_digest(fixture, "claude") != before
    ):
        return CheckResult(
            "switch_native_evidence_fail_closed",
            False,
            f"hard executable accepted text review evidence: {weak_text.strip()}",
        )
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-native-evidence-failure",
        evidence_level="native-host",
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path)
    text = result.stdout + result.stderr
    ok = (
        result.returncode == 2
        and "sandbox-unavailable" in text
        and _switch_live_digest(fixture, "claude") == before
        and not (fixture / ".codex").exists()
        and not list((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
    )
    return CheckResult(
        "switch_native_evidence_fail_closed",
        ok,
        "native-host evidence is sandbox-unavailable and blocks before live mutation or receipt"
        if ok
        else f"native evidence failure was not fail-closed: {text.strip()}",
    )


def check_switch_settings_decision() -> CheckResult:
    fixture = _build_switch_fixture()
    (fixture / ".claude" / "memory" / "hash-drift.md").write_text(
        "original constraint\n",
        encoding="utf-8",
    )
    before = _switch_live_digest(fixture, "claude")
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-hash-drift",
    )
    path = _write_switch_manifest(fixture, manifest)
    (fixture / ".claude" / "memory" / "hash-drift.md").write_text(
        "changed after approval\n",
        encoding="utf-8",
    )
    changed = _switch_live_digest(fixture, "claude")
    result = _run_semantic_switch(fixture, "codex", path)
    text = result.stdout + result.stderr
    ok = (
        before != changed
        and result.returncode == 2
        and ("snapshots are stale" in text or "exact live" in text)
        and _switch_live_digest(fixture, "claude") == changed
        and not (fixture / ".codex").exists()
    )
    return CheckResult(
        "switch_hash_drift_blocked",
        ok,
        "source drift after approval invalidates the manifest before staging or live mutation"
        if ok
        else f"hash drift was not blocked: {text.strip()}",
    )


def check_switch_codex_to_claude_archive_scope() -> CheckResult:
    failures: list[str] = []
    for fault in (
        "after-old-detach",
        "after-target-entry-enable",
        "after-target-enable",
        "after-archive-finalize",
        "after-receipt",
    ):
        fixture = _build_switch_fixture()
        (fixture / ".claude" / "memory" / "rollback.md").write_text(
            "rollback sentinel\n",
            encoding="utf-8",
        )
        before = _switch_live_digest(fixture, "claude")
        _plan, manifest = _semantic_manifest(
            fixture,
            "codex",
            migration_id=f"fixture-rollback-{fault}",
        )
        path = _write_switch_manifest(fixture, manifest)
        result = _run_semantic_switch(
            fixture,
            "codex",
            path,
            env={"BRIDGEFORGE_SWITCH_FAIL_AT": fault},
        )
        text = result.stdout + result.stderr
        restored = (
            result.returncode == 1
            and "rolled back" in text
            and _switch_live_digest(fixture, "claude") == before
            and not (fixture / "AGENTS.md").exists()
            and not (fixture / ".codex").exists()
            and not list((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
            and not (fixture / ".bridgeforge" / "archive" / "claude").exists()
        )
        if not restored:
            failures.append(f"{fault}: exit={result.returncode} {text.strip()}")
    ok = not failures
    return CheckResult(
        "switch_transaction_rollback",
        ok,
        "all commit mutation fault points restore old live, target/archive pre-state, and remove success receipts"
        if ok
        else "transaction rollback failed: " + "; ".join(failures),
    )


def check_switch_no_old_installs_target() -> CheckResult:
    _safe_reset_dir(SWITCH_FIXTURE)
    fixture = SWITCH_FIXTURE
    (fixture / "scripts").mkdir()
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", fixture / "scripts" / "bridgeforge_switch.py")
    result = _run_semantic_switch(fixture, "codex")
    receipts = list((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
    ok = (
        result.returncode == 0
        and (fixture / "AGENTS.md").is_file()
        and (fixture / ".codex" / "config.toml").is_file()
        and (fixture / ".codex" / ".bridgeforge_version").read_text(
            encoding="utf-8"
        ).strip() == (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        and (fixture / ".codex" / "subscription-tier.toml").is_file()
        and (fixture / ".codex" / "skill-routing.json").is_file()
        and (fixture / ".codex" / "agents" / "review-auditor.toml").is_file()
        and len(receipts) == 1
    )
    return CheckResult(
        "switch_no_old_installs_target",
        ok,
        "empty project installs the complete target surface and records the baseline receipt"
        if ok
        else f"complete target install failed: {(result.stdout + result.stderr).strip()}",
    )


def check_switch_legacy_archive_fail_closed() -> CheckResult:
    fixture = _build_switch_fixture()
    _add_codex_archive(fixture)
    before = _switch_live_digest(fixture, "claude")
    result = _run_semantic_switch(fixture, "codex", dry_run=True)
    text = result.stdout + result.stderr
    ok = (
        result.returncode == 2
        and "Legacy target archive provenance: missing" in text
        and '"origin": "target-archive"' in text
        and '"source_owner": "unknown-historical"' in text
        and _switch_live_digest(fixture, "claude") == before
        and not (fixture / ".codex").exists()
    )
    return CheckResult(
        "switch_legacy_archive_fail_closed",
        ok,
        "legacy target archive without receipt provenance is inventoried item-by-item and blocked"
        if ok
        else f"legacy archive was not fail-closed: {text.strip()}",
    )


def check_switch_roundtrip_lineage() -> CheckResult:
    fixture = _build_switch_fixture()
    (fixture / ".claude" / "memory" / "lineage.md").write_text(
        "lineage sentinel\n",
        encoding="utf-8",
    )
    _plan, first_manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-lineage-forward",
    )
    first_path = _write_switch_manifest(fixture, first_manifest)
    first = _run_semantic_switch(fixture, "codex", first_path)
    if first.returncode != 0:
        return CheckResult(
            "switch_roundtrip_lineage",
            False,
            f"forward migration failed: {(first.stdout + first.stderr).strip()}",
        )

    _plan, return_manifest = _semantic_manifest(
        fixture,
        "claude",
        migration_id="fixture-lineage-return",
    )
    return_path = _write_switch_manifest(fixture, return_manifest)
    returned = _run_semantic_switch(fixture, "claude", return_path)
    receipts = sorted((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
    return_receipt_path = (
        fixture
        / ".bridgeforge"
        / "migrations"
        / "fixture-lineage-return"
        / "receipt.json"
    )
    return_receipt = (
        json.loads(return_receipt_path.read_text(encoding="utf-8"))
        if return_receipt_path.exists()
        else {}
    )
    generated = [
        item
        for item in return_receipt.get("target", {}).get("files", [])
        if item.get("target_owner") == "constraint-generated"
    ]
    second_ok = (
        returned.returncode == 0
        and len(receipts) == 2
        and "fixture-lineage-forward" in return_receipt.get("parent_migration_ids", [])
        and len(generated) == 1
        and not (fixture / ".claude" / "memory" / "lineage.md").exists()
    )
    if not second_ok:
        return CheckResult(
            "switch_roundtrip_lineage",
            False,
            f"second migration failed: {(returned.stdout + returned.stderr).strip()}",
        )

    _plan, third_manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-lineage-third",
    )
    third_path = _write_switch_manifest(fixture, third_manifest)
    third = _run_semantic_switch(fixture, "codex", third_path)
    third_receipt_path = (
        fixture
        / ".bridgeforge"
        / "migrations"
        / "fixture-lineage-third"
        / "receipt.json"
    )
    third_receipt = (
        json.loads(third_receipt_path.read_text(encoding="utf-8"))
        if third_receipt_path.exists()
        else {}
    )
    third_generated = [
        item
        for item in third_receipt.get("target", {}).get("files", [])
        if item.get("target_owner") == "constraint-generated"
    ]
    ok = (
        third.returncode == 0
        and len(
            list((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
        ) == 3
        and "fixture-lineage-return" in third_receipt.get("parent_migration_ids", [])
        and len(third_generated) == 1
        and not (fixture / ".codex" / "memory" / "lineage.md").exists()
    )
    return CheckResult(
        "switch_roundtrip_lineage",
        ok,
        "three-hop roundtrip preserves stable lineage and suppresses generated archive duplicates"
        if ok
        else f"third migration failed: {(third.stdout + third.stderr).strip()}",
    )


def check_switch_evidence_attack_rollback() -> CheckResult:
    failures: list[str] = []

    fixture = _build_switch_fixture()
    source = fixture / ".claude" / "hooks" / "project_gate.py"
    source.write_text("raise SystemExit(0)\n", encoding="utf-8")
    before = _switch_live_digest(fixture, "claude")
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-evidence-stage-tamper",
        evidence_level="contract-smoke",
        evidence_command=[
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "Path('.codex/rules/semantic-projection-1.md').write_text("
                "'tampered by evidence\\n', encoding='utf-8')"
            ),
        ],
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path)
    text = result.stdout + result.stderr
    if not (
        result.returncode == 2
        and "manifest evidence.command is forbidden" in text
        and _switch_live_digest(fixture, "claude") == before
        and not (fixture / ".codex").exists()
    ):
        failures.append("stage tamper: " + text.strip())

    fixture = _build_switch_fixture()
    source = fixture / ".claude" / "hooks" / "project_gate.py"
    original = b"raise SystemExit(0)\n"
    source.write_bytes(original)
    encoded_path = base64.b64encode(str(source.resolve()).encode("utf-8")).decode("ascii")
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-evidence-source-tamper",
        evidence_level="contract-smoke",
        evidence_command=[
            sys.executable,
            "-c",
            (
                "import base64; from pathlib import Path; "
                f"Path(base64.b64decode({encoded_path!r}).decode()).write_text("
                "'mutated old live\\n', encoding='utf-8')"
            ),
        ],
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path)
    text = result.stdout + result.stderr
    if not (
        result.returncode == 2
        and "manifest evidence.command is forbidden" in text
        and source.read_bytes() == original
        and not (fixture / ".codex").exists()
    ):
        failures.append("source tamper: " + text.strip())

    return CheckResult(
        "switch_evidence_attack_rollback",
        not failures,
        "manifest evidence commands never execute; stage/live attack payloads leave old live byte-identical"
        if not failures
        else "; ".join(failures),
    )


def check_switch_manifest_security_binding() -> CheckResult:
    failures: list[str] = []
    module = _switch_module()

    fixture = _build_switch_fixture()
    (fixture / ".claude" / "memory" / "hard.md").write_text(
        "hard constraint\n",
        encoding="utf-8",
    )
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-manifest-downgrade",
    )
    hard = next(item for item in manifest["items"] if item["target"]["action"] == "write")
    hard["source_owner"] = "template-managed"
    hard["constraint_level"] = "platform-detail"
    hard["semantic"]["classification"] = "platform-detail"
    hard["target"] = {
        "action": "not-applicable",
        "path": None,
        "base_sha256": None,
        "sha256": None,
        "content": None,
        "diff": "",
    }
    hard["target_owner"] = None
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path, dry_run=True)
    text = result.stdout + result.stderr
    if not (
        result.returncode == 2
        and (
            "source_owner does not match proven provenance" in text
            or "constraint_level cannot be downgraded" in text
        )
        and (fixture / "CLAUDE.md").exists()
    ):
        failures.append("hard downgrade: " + text.strip())

    fixture = _build_switch_fixture()
    archive = _add_codex_archive(fixture)
    plan = module.build_plan("codex", fixture.resolve(), REPO_ROOT.resolve())
    manifest = module.build_proposal(plan, migration_id="fixture-archive-owner-forgery")
    forged = next(
        item
        for item in manifest["items"]
        if item["source"]["origin"] == "target-archive"
    )
    source_path = plan.archive_files[forged["source"]["path"]]
    target_rel = forged["source"]["path"]
    forged["source_owner"] = "user-owned"
    forged["target_owner"] = "user-owned"
    forged["semantic"] = {
        "classification": "translatable",
        "summary": "forged archive ownership",
    }
    forged["target"].update(
        {
            "action": "replay-archive",
            "path": target_rel,
            "base_sha256": module._sha_bytes(
                module._target_template_bytes(plan, target_rel)
            ),
            "sha256": module._sha_file(source_path),
            "diff": module._expected_diff(plan, target_rel, source_path.read_bytes()),
        }
    )
    forged["adapter"] = {"kind": "manual", "source": "forged"}
    forged["approval"] = {"status": "approved", "approved_by": "fixture-user"}
    forged["evidence"] = {
        "required_level": "text-review",
        "level": "text-review",
        "status": "passed",
        "details": "forged",
    }
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path, dry_run=True)
    text = result.stdout + result.stderr
    if not (
        result.returncode == 2
        and "source_owner does not match proven provenance" in text
        and archive.exists()
        and (fixture / "CLAUDE.md").exists()
    ):
        failures.append("archive owner forgery: " + text.strip())

    return CheckResult(
        "switch_manifest_security_binding",
        not failures,
        "manifest cannot downgrade hard/unknown inventory or forge archive ownership"
        if not failures
        else "; ".join(failures),
    )


def check_switch_path_and_target_evidence_guards() -> CheckResult:
    failures: list[str] = []
    module = _switch_module()

    fixture = _build_switch_fixture()
    for name in ("one.md", "two.md"):
        (fixture / ".claude" / "memory" / name).write_text(
            name + "\n",
            encoding="utf-8",
        )
    plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-windows-path-collision",
    )
    writes = [item for item in manifest["items"] if item["target"]["action"] == "write"]
    second = writes[1]
    collision_rel = writes[0]["target"]["path"].upper().replace(".CODEX", ".codex")
    content = second["target"]["content"].encode("utf-8")
    second["target"].update(
        {
            "path": collision_rel,
            "base_sha256": module._sha_bytes(
                module._target_template_bytes(plan, collision_rel)
            ),
            "sha256": module._sha_bytes(content),
            "diff": module._expected_diff(plan, collision_rel, content),
        }
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path, dry_run=True)
    text = result.stdout + result.stderr
    if not (
        result.returncode == 2
        and "Windows path collision" in text
        and not (fixture / ".codex").exists()
    ):
        failures.append("Windows collision: " + text.strip())

    fixture = _build_switch_fixture()
    (fixture / ".claude" / "memory" / "text-source.md").write_text(
        "text source\n",
        encoding="utf-8",
    )
    plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-target-executable-evidence",
    )
    item = next(item for item in manifest["items"] if item["target"]["action"] == "write")
    target_rel = ".codex/Hooks/project_gate"
    content = b"raise SystemExit(0)\n"
    item["target"].update(
        {
            "path": target_rel,
            "base_sha256": module._sha_bytes(
                module._target_template_bytes(plan, target_rel)
            ),
            "content": content.decode("utf-8"),
            "sha256": module._sha_bytes(content),
            "diff": module._expected_diff(plan, target_rel, content),
        }
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path, dry_run=True)
    text = result.stdout + result.stderr
    if not (
        result.returncode == 2
        and "evidence level is below the minimum" in text
        and not (fixture / ".codex").exists()
    ):
        failures.append("target executable evidence: " + text.strip())

    fixture = _build_switch_fixture()
    (fixture / ".claude" / "memory" / "uppercase-suffix.md").write_text(
        "text source\n",
        encoding="utf-8",
    )
    plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-uppercase-executable-evidence",
    )
    item = next(item for item in manifest["items"] if item["target"]["action"] == "write")
    target_rel = ".codex/rules/project_gate.PY"
    content = b"raise SystemExit(0)\n"
    item["target"].update(
        {
            "path": target_rel,
            "base_sha256": module._sha_bytes(
                module._target_template_bytes(plan, target_rel)
            ),
            "content": content.decode("utf-8"),
            "sha256": module._sha_bytes(content),
            "diff": module._expected_diff(plan, target_rel, content),
        }
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path, dry_run=True)
    text = result.stdout + result.stderr
    if not (
        result.returncode == 2
        and "evidence level is below the minimum" in text
        and not (fixture / ".codex").exists()
    ):
        failures.append("uppercase executable suffix: " + text.strip())

    return CheckResult(
        "switch_path_and_target_evidence_guards",
        not failures,
        "Windows-equivalent collisions and case-insensitive hook/executable evidence bypasses are blocked"
        if not failures
        else "; ".join(failures),
    )


def check_switch_link_boundary() -> CheckResult:
    fixture = _build_switch_fixture()
    link = fixture / "AGENTS.md"
    try:
        os.symlink(fixture / "missing-target", link)
    except OSError as exc:
        source = (REPO_ROOT / "scripts" / "bridgeforge_switch.py").read_text(encoding="utf-8")
        ok = "_assert_no_links" in source and "_assert_project_local" in source
        return CheckResult(
            "switch_link_boundary",
            ok,
            f"platform denied symlink creation; static fail-closed guards present ({exc})",
        )
    result = _run_semantic_switch(fixture, "codex")
    text = result.stdout + result.stderr
    ok = (
        result.returncode == 2
        and ("symlink or junction" in text or "target live paths already exist" in text)
        and link.is_symlink()
        and (fixture / "CLAUDE.md").exists()
    )
    return CheckResult(
        "switch_link_boundary",
        ok,
        "broken target symlink/junction blocks before inventory or mutation"
        if ok
        else f"link boundary failed: {text.strip()}",
    )


def check_switch_constraint_archive_requires_adapter() -> CheckResult:
    fixture = _build_switch_fixture()
    archive = fixture / ".bridgeforge" / "archive" / "codex" / "20260707-153000"
    archive.mkdir(parents=True)
    shutil.copy2(CODEX_TEMPLATE / "AGENTS.md", archive / "AGENTS.md")
    target = archive / "AGENTS.md"
    receipt_dir = fixture / ".bridgeforge" / "migrations" / "fixture-prior-provenance"
    receipt_dir.mkdir(parents=True)
    receipt = {
        "schema_version": 2,
        "migration_id": "fixture-prior-provenance",
        "status": "success",
        "source_agent": "claude",
        "target_agent": "codex",
        "archive": {
            "path": archive.relative_to(fixture).as_posix(),
            "files": [
                {
                    "path": "AGENTS.md",
                    "sha256": "sha256:" + hashlib.sha256(target.read_bytes()).hexdigest(),
                    "source_owner": "constraint-generated",
                    "constraint_id": "bf-fixture-generated",
                    "constraint_level": "hard",
                    "semantic": {
                        "classification": "translatable",
                        "summary": "generated fixture constraint",
                    },
                    "adapter": {
                        "kind": "manual",
                        "source": "old adapter",
                        "id": "fixture-adapter",
                        "version": "1",
                    },
                }
            ],
        },
        "target": {"files": []},
    }
    (receipt_dir / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    module = _switch_module()
    plan = module.build_plan("codex", fixture.resolve(), REPO_ROOT.resolve())
    manifest = module.build_proposal(plan, migration_id="fixture-generated-archive-block")
    generated = next(
        item
        for item in manifest["items"]
        if item["constraint_id"] == "bf-fixture-generated"
    )
    proposal_blocked = (
        generated["target"]["action"] == "unresolved"
        and generated["adapter"]["kind"] == "unavailable"
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(fixture, "codex", path, dry_run=True)
    text = result.stdout + result.stderr
    ok = (
        proposal_blocked
        and result.returncode == 2
        and "no registered adapter is available" in text
        and target.exists()
        and (fixture / "CLAUDE.md").exists()
    )
    return CheckResult(
        "switch_constraint_archive_requires_adapter",
        ok,
        "constraint-generated archive bytes are never replayed without a registered current adapter"
        if ok
        else f"constraint archive replay guard failed: {text.strip()}",
    )


def check_switch_archive_receipt_integrity() -> CheckResult:
    failures: list[str] = []
    cases = {
        "missing": "registered-but-missing",
        "extra": "unregistered-extra",
        "mismatch": "hash-mismatch",
    }
    for case, expected_message in cases.items():
        fixture = build_codex_fixture()
        scripts_dir = fixture / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        shutil.copy2(
            CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py",
            scripts_dir / "bridgeforge_switch.py",
        )
        before = _switch_live_digest(fixture, "codex")
        archive = fixture / ".bridgeforge" / "archive" / "claude" / "20260707-153000"
        archive.mkdir(parents=True)
        rel = ".claude/memory/user-owned.md"
        actual = archive / rel
        if case in {"extra", "mismatch"}:
            actual.parent.mkdir(parents=True)
            actual.write_text("actual archive bytes\n", encoding="utf-8")
        records: list[dict[str, object]] = []
        if case in {"missing", "mismatch"}:
            expected_bytes = (
                b"approved but now missing\n"
                if case == "missing"
                else b"different approved bytes\n"
            )
            records.append(
                {
                    "path": rel,
                    "sha256": "sha256:" + hashlib.sha256(expected_bytes).hexdigest(),
                    "source_owner": "user-owned",
                    "constraint_id": "bf-user-owned-archive",
                    "constraint_level": "hard",
                    "semantic": {
                        "classification": "translatable",
                        "summary": "registered user-owned archive delta",
                    },
                    "adapter": {"kind": "manual", "source": "fixture"},
                }
            )
        receipt_dir = fixture / ".bridgeforge" / "migrations" / f"fixture-archive-{case}"
        receipt_dir.mkdir(parents=True)
        receipt = {
            "schema_version": 2,
            "migration_id": f"fixture-archive-{case}",
            "status": "success",
            "source_agent": "codex",
            "target_agent": "claude",
            "archive": {
                "path": archive.relative_to(fixture).as_posix(),
                "files": records,
            },
            "target": {"files": []},
        }
        (receipt_dir / "receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = _run_semantic_switch(fixture, "claude", dry_run=True)
        text = result.stdout + result.stderr
        if not (
            result.returncode == 2
            and expected_message in text
            and _switch_live_digest(fixture, "codex") == before
            and archive.exists()
            and not (fixture / ".claude").exists()
        ):
            failures.append(f"{case}: {text.strip()}")
    return CheckResult(
        "switch_archive_receipt_integrity",
        not failures,
        "v2 receipt and archive inventory are bidirectionally exact for missing, extra, and hash-drift cases"
        if not failures
        else "; ".join(failures),
    )


def check_switch_backup_toctou() -> CheckResult:
    fixture = _build_switch_fixture()
    source = fixture / ".claude" / "memory" / "toctou.md"
    original = b"approved source bytes\n"
    source.write_bytes(original)
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-backup-toctou",
    )
    module = _switch_module()
    plan = module.build_plan("codex", fixture.resolve(), REPO_ROOT.resolve())
    original_copy = module._copy_agent_snapshot

    def attacked_copy(spec, source_root, snapshot_root):
        original_copy(spec, source_root, snapshot_root)
        if Path(source_root).resolve() == fixture.resolve():
            source.write_bytes(b"concurrent drift during backup\n")

    module._copy_agent_snapshot = attacked_copy
    error = ""
    try:
        module.apply_manifest(plan, manifest)
    except Exception as exc:
        error = str(exc)
    finally:
        module._copy_agent_snapshot = original_copy
    ok = (
        "source live changed while its rollback snapshot was copied" in error
        and source.read_bytes() == original
        and not (fixture / ".codex").exists()
        and not list((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
    )
    return CheckResult(
        "switch_backup_toctou",
        ok,
        "post-copy live and backup snapshots are revalidated; concurrent source drift restores approved bytes"
        if ok
        else f"backup TOCTOU guard failed: {error}",
    )


def check_switch_detached_toctou() -> CheckResult:
    fixture = _build_switch_fixture()
    source = fixture / ".claude" / "memory" / "detached-toctou.md"
    original = b"approved detached bytes\n"
    source.write_bytes(original)
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-detached-toctou",
    )
    module = _switch_module()
    plan = module.build_plan("codex", fixture.resolve(), REPO_ROOT.resolve())
    original_move = module._move_agent_paths

    def attacked_move(spec, source_root, target_root, **kwargs):
        original_move(spec, source_root, target_root, **kwargs)
        if (
            Path(source_root).resolve() == fixture.resolve()
            and Path(target_root).name == ".detached-old"
        ):
            detached = Path(target_root) / ".claude" / "memory" / "detached-toctou.md"
            detached.write_bytes(b"unapproved detached drift\n")

    module._move_agent_paths = attacked_move
    error = ""
    try:
        module.apply_manifest(plan, manifest)
    except Exception as exc:
        error = str(exc)
    finally:
        module._move_agent_paths = original_move
    ok = (
        "detached source differs from the approved source snapshot" in error
        and source.read_bytes() == original
        and not (fixture / ".codex").exists()
        and not list((fixture / ".bridgeforge" / "migrations").glob("*/receipt.json"))
        and not (fixture / ".bridgeforge" / "archive" / "claude").exists()
    )
    return CheckResult(
        "switch_detached_toctou",
        ok,
        "detached source is revalidated before target enable; drift restores the approved backup"
        if ok
        else f"detached TOCTOU guard failed: {error}",
    )


def check_switch_archive_destination_ownership() -> CheckResult:
    failures: list[str] = []

    fixture = _build_switch_fixture()
    source = fixture / ".claude" / "memory" / "archive-collision.md"
    source.write_text("approved source\n", encoding="utf-8")
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-archive-collision",
    )
    module = _switch_module()
    plan = module.build_plan("codex", fixture.resolve(), REPO_ROOT.resolve())
    original_timestamp = module._timestamp
    module._timestamp = lambda: "20260725-235959"
    collision = (
        fixture
        / ".bridgeforge"
        / "archive"
        / "claude"
        / "20260725-235959-fixture-archive-collision"
    )
    collision.mkdir(parents=True)
    sentinel = collision / "preexisting.txt"
    sentinel.write_bytes(b"preexisting archive bytes\n")
    error = ""
    try:
        module.apply_manifest(plan, manifest)
    except Exception as exc:
        error = str(exc)
    finally:
        module._timestamp = original_timestamp
    if not (
        "archive destination already exists" in error
        and sentinel.read_bytes() == b"preexisting archive bytes\n"
        and source.read_text(encoding="utf-8") == "approved source\n"
        and not (fixture / ".codex").exists()
    ):
        failures.append("preexisting destination: " + error)

    fixture = _build_switch_fixture()
    source = fixture / ".claude" / "memory" / "archive-fault.md"
    source.write_text("approved source\n", encoding="utf-8")
    preexisting = fixture / ".bridgeforge" / "archive" / "claude" / "preexisting"
    preexisting.mkdir(parents=True)
    sentinel = preexisting / "sentinel.bin"
    sentinel.write_bytes(b"must survive rollback\n")
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-archive-owned-fault",
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(
        fixture,
        "codex",
        path,
        env={"BRIDGEFORGE_SWITCH_FAIL_AT": "after-archive-finalize"},
    )
    text = result.stdout + result.stderr
    remaining = sorted(
        path.name
        for path in (fixture / ".bridgeforge" / "archive" / "claude").iterdir()
    )
    if not (
        result.returncode == 1
        and "rolled back" in text
        and sentinel.read_bytes() == b"must survive rollback\n"
        and remaining == ["preexisting"]
        and source.read_text(encoding="utf-8") == "approved source\n"
        and not (fixture / ".codex").exists()
    ):
        failures.append("finalize rollback ownership: " + text.strip())

    fixture = _build_switch_fixture()
    source = fixture / ".claude" / "memory" / "empty-parent-fault.md"
    source.write_text("approved source\n", encoding="utf-8")
    preexisting_empty_parent = (
        fixture / ".bridgeforge" / "archive" / "claude"
    )
    preexisting_empty_parent.mkdir(parents=True)
    _plan, manifest = _semantic_manifest(
        fixture,
        "codex",
        migration_id="fixture-empty-archive-parent-fault",
    )
    path = _write_switch_manifest(fixture, manifest)
    result = _run_semantic_switch(
        fixture,
        "codex",
        path,
        env={"BRIDGEFORGE_SWITCH_FAIL_AT": "after-archive-finalize"},
    )
    text = result.stdout + result.stderr
    if not (
        result.returncode == 1
        and "rolled back" in text
        and preexisting_empty_parent.is_dir()
        and not any(preexisting_empty_parent.iterdir())
        and source.read_text(encoding="utf-8") == "approved source\n"
        and not (fixture / ".codex").exists()
    ):
        failures.append("preexisting empty archive parent: " + text.strip())

    return CheckResult(
        "switch_archive_destination_ownership",
        not failures,
        "archive destination/parent ownership is explicit; rollback preserves preexisting data and empty parents"
        if not failures
        else "; ".join(failures),
    )


def _build_layout_migration_fixture(platform: str = "codex") -> Path:
    _safe_reset_dir(LAYOUT_MIGRATION_FIXTURE)
    fixture = LAYOUT_MIGRATION_FIXTURE
    (fixture / f".{platform}").mkdir()
    entry = "AGENTS.md" if platform == "codex" else "CLAUDE.md"
    (fixture / entry).write_text("fixture\n", encoding="utf-8")
    _stage_manifest_skill(fixture / ".agents" / "skills" / "explain", "explain")
    private = fixture / ".agents" / "skills" / "project-only"
    private.mkdir(parents=True)
    (private / "SKILL.md").write_text(
        "---\nname: project-only\n---\n",
        encoding="utf-8",
    )
    return fixture


def _stage_manifest_skill(destination: Path, name: str) -> None:
    manifest = json.loads(
        (REPO_ROOT / "shared-skill-manifest.json").read_text(encoding="utf-8-sig")
    )
    records = manifest["platforms"]["codex"]["skills"]
    record = next(item for item in records if item["name"] == name)
    for file_record in record["files"]:
        source = REPO_ROOT / file_record["source"]
        target = destination / file_record["target"]
        expected = file_record["sha256"].removeprefix("sha256:")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"manifest hash is stale for fixture source: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _run_layout_migration(fixture: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "bridgeforge_migrate_layout.py"),
            "--project-root",
            str(fixture),
            mode,
        ],
        fixture,
    )


def check_layout_migration_dry_run_apply() -> CheckResult:
    fixture = _build_layout_migration_fixture()
    dry_run = _run_layout_migration(fixture, "--dry-run")
    dry_text = dry_run.stdout + dry_run.stderr
    dry_preserved = (
        (fixture / ".agents" / "skills" / "explain" / "SKILL.md").is_file()
        and (fixture / ".agents" / "skills" / "project-only" / "SKILL.md").is_file()
        and not (fixture / ".codex" / "skills").exists()
    )
    applied = _run_layout_migration(fixture, "--apply")
    applied_text = applied.stdout + applied.stderr
    codex_ok = (
        dry_run.returncode == 0
        and '"action": "delete_managed_skill_copy"' in dry_text
        and '"action": "move_project_private_skill"' in dry_text
        and dry_preserved
        and applied.returncode == 0
        and not (fixture / ".agents").exists()
        and (fixture / ".codex" / "skills" / "project-only" / "SKILL.md").is_file()
        and not (fixture / ".codex" / "skills" / "explain").exists()
        and "Migration applied" in applied_text
    )
    claude_fixture = _build_layout_migration_fixture("claude")
    claude_applied = _run_layout_migration(claude_fixture, "--apply")
    claude_text = claude_applied.stdout + claude_applied.stderr
    claude_ok = (
        claude_applied.returncode == 0
        and not (claude_fixture / ".agents").exists()
        and (
            claude_fixture
            / ".claude"
            / "skills"
            / "project-only"
            / "SKILL.md"
        ).is_file()
        and not (
            claude_fixture / ".claude" / "skills" / "explain"
        ).exists()
    )
    ok = codex_ok and claude_ok
    return CheckResult(
        "layout_migration_dry_run_apply",
        ok,
        "dry-run classifies without writes; --apply removes managed copies, moves private skill into .codex/skills, and retires .agents"
        if ok
        else (
            f"expected dry-run/apply migration contract, dry={dry_run.returncode}, "
            f"apply={applied.returncode}, claude={claude_applied.returncode}: "
            f"{(dry_text + applied_text + claude_text).strip()}"
        ),
    )


def check_layout_migration_blockers_are_local() -> CheckResult:
    fixture = _build_layout_migration_fixture()
    for managed_name in ("bridgeforge", "develop"):
        modified = fixture / ".agents" / "skills" / managed_name
        modified.mkdir(parents=True)
        (modified / "SKILL.md").write_text(
            f"locally customized {managed_name}\n",
            encoding="utf-8",
        )
    collision = fixture / ".codex" / "skills" / "project-only"
    collision.mkdir(parents=True)
    (collision / "SKILL.md").write_text("existing\n", encoding="utf-8")
    unknown = fixture / ".agents" / "unknown.txt"
    unknown.write_text("do not delete\n", encoding="utf-8")
    sibling = fixture.parent / "layout-migration-other-project"
    _safe_reset_dir(sibling)
    sibling_marker = sibling / ".agents" / "keep.txt"
    sibling_marker.parent.mkdir(parents=True)
    sibling_marker.write_text("untouched\n", encoding="utf-8")

    applied = _run_layout_migration(fixture, "--apply")
    text = applied.stdout + applied.stderr
    ok = (
        applied.returncode == 2
        and "无法分类内容" in text
        and "目标已存在" in text
        and text.count("与 manifest 文件清单或哈希不一致") == 2
        and unknown.read_text(encoding="utf-8") == "do not delete\n"
        and (fixture / ".agents" / "skills" / "explain" / "SKILL.md").is_file()
        and (fixture / ".agents" / "skills" / "bridgeforge" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        == "locally customized bridgeforge\n"
        and (fixture / ".agents" / "skills" / "develop" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        == "locally customized develop\n"
        and (fixture / ".agents" / "skills" / "project-only" / "SKILL.md").is_file()
        and sibling_marker.read_text(encoding="utf-8") == "untouched\n"
    )
    return CheckResult(
        "layout_migration_blockers_are_local",
        ok,
        "unknown content and destination conflicts block all writes, and another project's .agents remains untouched"
        if ok
        else f"expected local blocker with zero writes, got exit {applied.returncode}: {text.strip()}",
    )


def check_layout_migration_transaction_rollback() -> CheckResult:
    fixture = _build_layout_migration_fixture()
    script = REPO_ROOT / "scripts" / "bridgeforge_migrate_layout.py"
    spec = importlib.util.spec_from_file_location(
        "bridgeforge_migrate_layout_harness",
        script,
    )
    if spec is None or spec.loader is None:
        return CheckResult(
            "layout_migration_transaction_rollback",
            False,
            "could not import migration module",
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    plan = module.build_plan(fixture, script)
    original_remove = module._remove_empty_tree

    def injected_failure(_root: Path) -> None:
        raise OSError("injected failure after staging")

    module._remove_empty_tree = injected_failure
    failed = False
    try:
        module.apply_plan(plan)
    except OSError:
        failed = True
    finally:
        module._remove_empty_tree = original_remove
        sys.modules.pop(spec.name, None)

    ok = (
        failed
        and (fixture / ".agents" / "skills" / "explain" / "SKILL.md").is_file()
        and (fixture / ".agents" / "skills" / "project-only" / "SKILL.md").is_file()
        and not (fixture / ".codex" / "skills" / "project-only").exists()
        and not list(fixture.glob(".bridgeforge-migrate-backup-*"))
    )
    return CheckResult(
        "layout_migration_transaction_rollback",
        ok,
        "failure after delete staging and private move restores both sources and removes temporary backup"
        if ok
        else "injected mid-transaction failure left partial migration state",
    )


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+\.(?:md|py|json|ps1|sh))`")
BARE_SCRIPT_RE = re.compile(r"\b([A-Za-z][\w-]{2,}\.py)\b")


def _strip_fragment(path: str) -> str:
    return path.split("#", 1)[0].split("?", 1)[0].strip()


def _path_parts_from_text(text: str) -> list[str]:
    parts: list[str] = []
    for link in MARKDOWN_LINK_RE.findall(text):
        parts.append(_strip_fragment(link))
    for inline in INLINE_CODE_RE.findall(text):
        for token in re.split(r"\s+", inline.strip()):
            parts.append(_strip_fragment(token))
    return parts


def _looks_generated_or_project_specific(path: str) -> bool:
    if not path or path.startswith(("http://", "https://", "mailto:", "app://")):
        return True
    if any(ch in path for ch in "<>{}$*"):
        return True
    norm = path.replace("\\", "/")
    return norm.startswith(
        (
            "~/.claude/",
            "~/.codex/",
            ".runtime/",
            "doc/",
            "rules/",
            "memory/",
            "MEMORY",
            "TODO-INDEX",
        )
    )


def _candidate_existing_paths(token: str, skill_dir: Path) -> list[Path]:
    norm = token.strip(".,;:)]}").replace("\\", "/")
    if _looks_generated_or_project_specific(norm):
        return []

    if norm.startswith(".claude/"):
        rest = norm[len(".claude/") :]
        return [REPO_ROOT / "templates" / "claude" / rest]
    if norm.startswith(".codex/"):
        rest = norm[len(".codex/") :]
        return [REPO_ROOT / "templates" / "codex" / rest]
    if norm.startswith("references/"):
        return [skill_dir / norm]
    if norm.startswith(("./", "../")):
        return [(skill_dir / norm).resolve()]
    if norm.startswith(("doc/", "templates/", "skills/", "scripts/")) or norm in {
        "README.md",
        "CHANGELOG.md",
        "VERSION",
        "SKILL.md",
    }:
        return [REPO_ROOT / norm]
    return []


def check_skill_references() -> CheckResult:
    missing: list[str] = []
    search_roots = [
        REPO_ROOT / "templates",
        REPO_ROOT / "skills",
        REPO_ROOT / "doc",
        REPO_ROOT / "scripts",
        REPO_ROOT / "tests",
    ]
    all_repo_files = [
        p
        for root in search_roots
        if root.exists()
        for p in root.rglob("*")
    ]
    py_basenames = {p.name for p in all_repo_files if p.is_file() and p.suffix == ".py"}

    for skill_file in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        skill_dir = skill_file.parent

        for token in _path_parts_from_text(text):
            candidates = _candidate_existing_paths(token, skill_dir)
            if candidates and not any(p.exists() for p in candidates):
                rel = skill_file.relative_to(REPO_ROOT).as_posix()
                missing.append(f"{rel}: missing {token}")

        for script_name in BARE_SCRIPT_RE.findall(text):
            if script_name in {"a.py", "b.py", "c.py", "d.py", "e.py"}:
                continue
            if script_name not in py_basenames:
                rel = skill_file.relative_to(REPO_ROOT).as_posix()
                missing.append(f"{rel}: unknown script name {script_name}")

    ok = not missing
    return CheckResult(
        "skill_reference_health",
        ok,
        "no high-confidence missing skill references" if ok else "\n".join(missing),
    )


def check_skill_metadata() -> CheckResult:
    source = run([sys.executable, ".codex/hooks/skill_metadata_check.py", "--pre-commit"], REPO_ROOT)
    if source.returncode != 0:
        return CheckResult(
            "skill_metadata_health",
            False,
            f"source skills metadata should pass, got exit {source.returncode}: {(source.stdout + source.stderr).strip()}",
        )

    _safe_reset_dir(SKILL_METADATA_FIXTURE)
    hook_dir = SKILL_METADATA_FIXTURE / ".codex" / "hooks"
    hook_dir.mkdir(parents=True)
    shutil.copy2(CODEX_TEMPLATE / "hooks" / "skill_metadata_check.py", hook_dir / "skill_metadata_check.py")

    bad_skill = SKILL_METADATA_FIXTURE / "skills" / "bad-skill" / "SKILL.md"
    bad_skill.parent.mkdir(parents=True)
    bad_skill.write_text(
        "---\n"
        "name: bad-skill\n"
        "description: fixture bad skill\n"
        "argument: 无\n"
        "---\n\n"
        "# Bad Skill\n",
        encoding="utf-8",
    )
    bad = run([sys.executable, ".codex/hooks/skill_metadata_check.py", "--pre-commit"], SKILL_METADATA_FIXTURE)

    bad_skill.write_text(
        "---\n"
        "name: bad-skill\n"
        "description: fixture good skill\n"
        "user_invocable: true\n"
        "argument: 无\n"
        "---\n\n"
        "# Good Skill\n",
        encoding="utf-8",
    )
    good = run([sys.executable, ".codex/hooks/skill_metadata_check.py", "--pre-commit"], SKILL_METADATA_FIXTURE)

    ok = (
        bad.returncode == 2
        and "user_invocable: true is required" in (bad.stdout + bad.stderr)
        and good.returncode == 0
    )
    return CheckResult(
        "skill_metadata_health",
        ok,
        "skill metadata hook passes source/good fixture and blocks missing user_invocable"
        if ok
        else (
            f"expected bad exit 2 and good exit 0, got bad={bad.returncode}, "
            f"good={good.returncode}: {(bad.stdout + bad.stderr + good.stdout + good.stderr).strip()}"
        ),
    )


def check_user_skill_distribution() -> CheckResult:
    """Check new user shelves and the managed-ledger drift detector."""
    _safe_reset_dir(USER_SKILL_FIXTURE)
    fake_home = USER_SKILL_FIXTURE / "home"
    fixture_env = {
        "HOME": str(fake_home),
        "USERPROFILE": str(fake_home),
    }

    failures: list[str] = []
    root_skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    maintenance = (REPO_ROOT / "references" / "user-skill-maintenance.md").read_text(
        encoding="utf-8"
    )
    contract_markers = (
        "[references/user-skill-maintenance.md](references/user-skill-maintenance.md)",
        "~/.codex/skills/",
        "~/.claude/skills/",
        "bridgeforge-managed.json",
        "/bridgeforge",
    )
    combined_contract = root_skill + "\n" + maintenance
    missing_markers = [marker for marker in contract_markers if marker not in combined_contract]
    if missing_markers:
        failures.append(f"maintenance contract missing markers: {missing_markers!r}")
    if "~/.agents/skills/" in combined_contract or "~/.bridgeforge/skills/" in combined_contract:
        failures.append("maintenance contract still names a retired runtime source")

    surfaces = (
        ("claude", fake_home / ".claude" / "skills"),
        ("codex", fake_home / ".codex" / "skills"),
    )
    for agent, shelf in surfaces:
        explain = shelf / "explain"
        bridgeforge = shelf / "bridgeforge"
        explain.mkdir(parents=True)
        bridgeforge.mkdir()
        (explain / "SKILL.md").write_text("managed explain\n", encoding="utf-8")
        hidden_hook = explain / ".githooks" / "pre-commit"
        hidden_hook.parent.mkdir()
        hidden_hook.write_text("#!/bin/sh\n", encoding="utf-8")
        (bridgeforge / "SKILL.md").write_text("managed bridgeforge\n", encoding="utf-8")

        def content_hash(skill_root: Path) -> str:
            records = []
            for path in sorted(item for item in skill_root.rglob("*") if item.is_file()):
                rel = path.relative_to(skill_root).as_posix()
                records.append((rel, hashlib.sha256(path.read_bytes()).hexdigest()))
            payload = "".join(f"{rel}\n{digest}\n" for rel, digest in records)
            return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

        ledger = {
            "schema_version": 1,
            "platform": agent,
            "records": {
                "explain": {
                    "source_commit": "a" * 40,
                    "content_hash": content_hash(explain),
                    "installed_at": "2026-07-25T00:00:00Z",
                },
                "bridgeforge": {
                    "source_commit": "a" * 40,
                    "content_hash": content_hash(bridgeforge),
                    "installed_at": "2026-07-25T00:00:00Z",
                },
            },
        }
        platform_root = shelf.parent
        (platform_root / "bridgeforge-managed.json").write_text(
            json.dumps(ledger, indent=2) + "\n",
            encoding="utf-8",
        )
        hook = USER_SKILL_FIXTURE / "project" / f".{agent}" / "hooks" / "skill_sync_check.py"
        hook.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            REPO_ROOT / "templates" / agent / "hooks" / "skill_sync_check.py",
            hook,
        )

        current = run([sys.executable, str(hook)], USER_SKILL_FIXTURE, env=fixture_env)
        if (
            current.returncode != 0
            or current.stdout
            or current.stderr
        ):
            failures.append(
                f"{agent}: current managed ledger should be silent: "
                f"exit={current.returncode} output={(current.stdout + current.stderr).strip()!r}"
            )
            continue

        custom_file = explain / "SKILL.md"
        custom_file.write_text("local customization\n", encoding="utf-8")
        before = custom_file.read_bytes()
        divergent = run([sys.executable, str(hook)], USER_SKILL_FIXTURE, env=fixture_env)
        divergent_output = divergent.stdout + divergent.stderr
        if (
            divergent.returncode != 0
            or "托管 skill 缺失或内容漂移（explain）" not in divergent_output
            or "无参 /bridgeforge" not in divergent_output
            or custom_file.read_bytes() != before
        ):
            failures.append(
                f"{agent}: customization was not reported and preserved: "
                f"exit={divergent.returncode} output={divergent_output.strip()!r}"
            )

    ok = not failures
    return CheckResult(
        "user_skill_distribution",
        ok,
        "maintenance contract uses both new shelves; managed-ledger hooks stay silent when current and report drift without writes"
        if ok
        else "\n".join(failures),
    )


def check_model_policy() -> CheckResult:
    source = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], REPO_ROOT)
    if source.returncode != 0:
        return CheckResult(
            "model_policy_health",
            False,
            f"source model policy should pass, got exit {source.returncode}: {(source.stdout + source.stderr).strip()}",
        )

    fixture = build_codex_fixture()
    good = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], fixture)

    xhigh = fixture / ".codex" / "agents" / "xhigh-auditor.toml"
    text = xhigh.read_text(encoding="utf-8")
    xhigh.write_text(
        text.replace(
            "Use only after explicit user confirmation for xhigh / super-strong reasoning in the current request.",
            "Extra-high-effort audit subagent for rare expert review.",
        ),
        encoding="utf-8",
    )
    bad_description = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], fixture)

    fixture = build_codex_fixture()
    xhigh = fixture / ".codex" / "agents" / "xhigh-auditor.toml"
    text = xhigh.read_text(encoding="utf-8")
    xhigh.write_text(
        text.replace(
            "- You may be spawned only after explicit user confirmation in the current request.\n"
            "- If the parent prompt does not include that confirmation, stop and report that xhigh requires user confirmation.\n",
            "- Run a deep audit when requested by the parent.\n",
        ),
        encoding="utf-8",
    )
    bad_instructions = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], fixture)

    fixture = build_codex_fixture()
    settings_path = fixture / ".codex" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
    for block in settings["hooks"]["PreToolUse"]:
        if block.get("matcher") == "Bash":
            block["hooks"] = [
                hook
                for hook in block["hooks"]
                if not hook.get("command", "").endswith(".codex/hooks/user_config_write_guard.py")
            ]
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bad_registration = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], fixture)

    fixture = build_codex_fixture()
    routing_path = fixture / ".codex" / "skill-routing.json"
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    routing["skills"] = [entry for entry in routing["skills"] if entry["skill"] != "find-doc"]
    routing_path.write_text(json.dumps(routing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bad_missing_find_doc = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], fixture)

    fixture = build_codex_fixture()
    routing_path = fixture / ".codex" / "skill-routing.json"
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    review_route = next(
        entry
        for entry in routing["skills"]
        if entry["skill"] == "develop" and entry["stage"] == "delivery-review"
    )
    review_route["agent"] = "light-explorer"
    review_route["mode"] = "read-only"
    routing_path.write_text(json.dumps(routing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bad_review_luna = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], fixture)

    fixture = build_codex_fixture()
    routing_path = fixture / ".codex" / "skill-routing.json"
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    routing["skills"].append(
        {
            "skill": "find-doc",
            "stage": "forbidden-xhigh",
            "agent": "xhigh-auditor",
            "mode": "audit",
            "root_must_do": "none",
        }
    )
    routing_path.write_text(json.dumps(routing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bad_auto_xhigh = run([sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"], fixture)

    ok = (
        good.returncode == 0
        and bad_description.returncode == 2
        and bad_instructions.returncode == 2
        and bad_registration.returncode == 2
        and bad_missing_find_doc.returncode == 2
        and bad_review_luna.returncode == 2
        and bad_auto_xhigh.returncode == 2
        and "description must state" in (bad_description.stdout + bad_description.stderr)
        and "developer_instructions must state" in (bad_instructions.stdout + bad_instructions.stderr)
        and "must register user_config_write_guard.py for Bash" in (bad_registration.stdout + bad_registration.stderr)
        and "find-doc/search-and-candidate-summary must use light-explorer" in (bad_missing_find_doc.stdout + bad_missing_find_doc.stderr)
        and "develop/delivery-review must use review-auditor" in (bad_review_luna.stdout + bad_review_luna.stderr)
        and "must not auto-route to xhigh-auditor" in (bad_auto_xhigh.stdout + bad_auto_xhigh.stderr)
    )
    return CheckResult(
        "model_policy_health",
        ok,
        "model policy hook passes source/good fixture and blocks xhigh confirmation, guard registration, missing Luna routing, downgraded review, and automatic xhigh routing"
        if ok
        else (
            f"expected good exit 0 and policy bad exit 2 cases, got good={good.returncode}, "
            f"bad_description={bad_description.returncode}, bad_instructions={bad_instructions.returncode}, "
            f"bad_registration={bad_registration.returncode}, bad_missing_find_doc={bad_missing_find_doc.returncode}, "
            f"bad_review_luna={bad_review_luna.returncode}, bad_auto_xhigh={bad_auto_xhigh.returncode}: "
            f"{(good.stdout + good.stderr + bad_description.stdout + bad_description.stderr + bad_instructions.stdout + bad_instructions.stderr + bad_registration.stdout + bad_registration.stderr + bad_missing_find_doc.stdout + bad_missing_find_doc.stderr + bad_review_luna.stdout + bad_review_luna.stderr + bad_auto_xhigh.stdout + bad_auto_xhigh.stderr).strip()}"
        ),
    )


def check_subscription_routing() -> CheckResult:
    script = CODEX_TEMPLATE / "scripts" / "subscription_routing.py"
    command = [
        sys.executable,
        str(script),
        "--project-root",
        str(CODEX_FIXTURE),
        "--template-root",
        str(CODEX_TEMPLATE),
    ]

    fixture = build_codex_fixture()
    high = run([*command, "--tier", "high"], fixture)
    high_policy = run(
        [sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"],
        fixture,
    )
    high_config = (fixture / ".codex" / "config.toml").read_text(encoding="utf-8")
    high_agent = (
        fixture / ".codex" / "agents" / "implementation-worker.toml"
    ).read_text(encoding="utf-8")

    fixture = build_codex_fixture()
    conservative = run([*command, "--tier", "conservative"], fixture)
    conservative_policy = run(
        [sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"],
        fixture,
    )
    conservative_marker = (fixture / ".codex" / "subscription-tier.toml").read_text(
        encoding="utf-8"
    )
    conservative_config = (fixture / ".codex" / "config.toml").read_text(encoding="utf-8")
    conservative_agent = (
        fixture / ".codex" / "agents" / "implementation-worker.toml"
    ).read_text(encoding="utf-8")

    fixture = build_codex_fixture()
    marker = fixture / ".codex" / "subscription-tier.toml"
    marker.unlink()
    missing_marker = run(
        [sys.executable, ".codex/hooks/model_policy_check.py", "--pre-commit"],
        fixture,
    )

    fixture = build_codex_fixture()
    protected_files = [
        fixture / ".codex" / "subscription-tier.toml",
        fixture / ".codex" / "config.toml",
        fixture / ".codex" / "agents" / "implementation-worker.toml",
    ]
    before_invalid = [path.read_bytes() for path in protected_files]
    invalid = run([*command, "--tier", "enterprise"], fixture)
    after_invalid = [path.read_bytes() for path in protected_files]

    user_config = Path.home() / ".codex" / "config.toml"
    user_before = user_config.read_bytes() if user_config.exists() else None
    user_project_block = run(
        [
            sys.executable,
            str(script),
            "--tier",
            "high",
            "--project-root",
            str(Path.home()),
            "--template-root",
            str(CODEX_TEMPLATE),
        ],
        fixture,
    )
    user_template_block = run(
        [
            sys.executable,
            str(script),
            "--tier",
            "high",
            "--project-root",
            str(fixture),
            "--template-root",
            str(Path.home() / ".codex"),
        ],
        fixture,
    )
    user_after = user_config.read_bytes() if user_config.exists() else None

    missing_output = missing_marker.stdout + missing_marker.stderr
    protected_output = (
        user_project_block.stdout
        + user_project_block.stderr
        + user_template_block.stdout
        + user_template_block.stderr
    )
    ok = (
        high.returncode == 0
        and high_policy.returncode == 0
        and 'model_reasoning_effort = "high"' in high_config
        and 'model = "gpt-5.6-sol"' in high_agent
        and conservative.returncode == 0
        and conservative_policy.returncode == 0
        and 'tier = "conservative"' in conservative_marker
        and 'model_reasoning_effort = "medium"' in conservative_config
        and 'model = "gpt-5.6-terra"' in conservative_agent
        and missing_marker.returncode == 2
        and "run /bridgeforge and choose a Codex subscription tier" in missing_output
        and invalid.returncode == 2
        and before_invalid == after_invalid
        and user_project_block.returncode == 2
        and user_template_block.returncode == 2
        and "refusing user-level Codex path" in protected_output
        and user_before == user_after
    )
    return CheckResult(
        "subscription_routing",
        ok,
        "high/conservative tiers apply and pass policy; missing marker, invalid tier, and user-level read/write paths are blocked"
        if ok
        else (
            f"high={high.returncode}/{high_policy.returncode} "
            f"conservative={conservative.returncode}/{conservative_policy.returncode} "
            f"missing={missing_marker.returncode} invalid={invalid.returncode} "
            f"user_project={user_project_block.returncode} "
            f"user_template={user_template_block.returncode} unchanged={user_before == user_after}: "
            f"{(high.stdout + high.stderr + high_policy.stdout + high_policy.stderr + conservative.stdout + conservative.stderr + conservative_policy.stdout + conservative_policy.stderr + missing_output + invalid.stdout + invalid.stderr + protected_output).strip()}"
        ),
    )


def check_user_config_write_guard() -> CheckResult:
    fixture = build_codex_fixture()
    guard = fixture / ".codex" / "hooks" / "user_config_write_guard.py"
    user_config = Path.home() / ".codex" / "config.toml"
    before = user_config.read_bytes() if user_config.exists() else None

    read_payload = json.dumps(
        {
            "tool_name": "PowerShell",
            "tool_input": {"command": f"Get-Content -LiteralPath '{user_config}'"},
        }
    )
    write_payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(user_config)},
        }
    )
    shell_write_payload = json.dumps(
        {
            "tool_name": "PowerShell",
            "tool_input": {"command": f"Set-Content -LiteralPath '{user_config}' -Value 'fixture'"},
        }
    )
    home_write_payload = json.dumps(
        {
            "tool_name": "PowerShell",
            "tool_input": {"command": 'Set-Content -LiteralPath "$HOME\\.codex\\config.toml" -Value fixture'},
        }
    )
    redirect_write_payload = json.dumps(
        {
            "tool_name": "PowerShell",
            "tool_input": {"command": '"fixture" > "$env:USERPROFILE\\.codex\\config.toml"'},
        }
    )
    tilde_write_payload = json.dumps(
        {
            "tool_name": "PowerShell",
            "tool_input": {"command": 'Set-Content -LiteralPath "~\\.codex\\config.toml" -Value fixture'},
        }
    )

    read = run_with_input([sys.executable, str(guard)], fixture, read_payload)
    blocked_write = run_with_input([sys.executable, str(guard)], fixture, write_payload)
    blocked_shell = run_with_input([sys.executable, str(guard)], fixture, shell_write_payload)
    blocked_home = run_with_input([sys.executable, str(guard)], fixture, home_write_payload)
    blocked_redirect = run_with_input([sys.executable, str(guard)], fixture, redirect_write_payload)
    blocked_tilde = run_with_input([sys.executable, str(guard)], fixture, tilde_write_payload)
    after = user_config.read_bytes() if user_config.exists() else None

    settings = json.loads((fixture / ".codex" / "settings.json").read_text(encoding="utf-8-sig"))
    registered = all(
        any(
            hook.get("command", "").endswith(".codex/hooks/user_config_write_guard.py")
            for hook in block.get("hooks", [])
            if isinstance(hook, dict)
        )
        for block in settings.get("hooks", {}).get("PreToolUse", [])
        if block.get("matcher") in {"Bash", "PowerShell", "Write|Edit|MultiEdit"}
    )
    ok = (
        read.returncode == 0
        and blocked_write.returncode == 2
        and blocked_shell.returncode == 2
        and blocked_home.returncode == 2
        and blocked_redirect.returncode == 2
        and blocked_tilde.returncode == 2
        and before == after
        and registered
    )
    return CheckResult(
        "user_config_write_guard",
        ok,
        "user config reads pass, absolute and variable-path writes are blocked, settings registers the guard, and the user config sentinel is unchanged"
        if ok
        else (
            f"read={read.returncode} write={blocked_write.returncode} shell={blocked_shell.returncode} "
            f"home={blocked_home.returncode} redirect={blocked_redirect.returncode} tilde={blocked_tilde.returncode} "
            f"unchanged={before == after} registered={registered}: "
            f"{(read.stdout + read.stderr + blocked_write.stdout + blocked_write.stderr + blocked_shell.stdout + blocked_shell.stderr + blocked_home.stdout + blocked_home.stderr + blocked_redirect.stdout + blocked_redirect.stderr + blocked_tilde.stdout + blocked_tilde.stderr).strip()}"
        ),
    )


def check_codex_git_sync_runner() -> CheckResult:
    fixture = build_codex_fixture()
    _safe_reset_dir(CODEX_GIT_SYNC_REMOTE)

    steps = [
        (["git", "config", "user.email", "fixture@example.invalid"], fixture, "config email"),
        (["git", "config", "user.name", "BridgeForge Fixture"], fixture, "config name"),
        (["git", "add", "."], fixture, "initial add"),
        (["git", "commit", "-m", "chore: initial fixture"], fixture, "initial commit"),
        (["git", "branch", "-M", "main"], fixture, "branch main"),
        (["git", "init", "--bare"], CODEX_GIT_SYNC_REMOTE, "init bare remote"),
        (["git", "remote", "add", "origin", str(CODEX_GIT_SYNC_REMOTE)], fixture, "remote add"),
        (["git", "push", "-u", "origin", "main"], fixture, "initial push"),
    ]
    for cmd, cwd, label in steps:
        result = run(cmd, cwd, timeout=60)
        if result.returncode != 0:
            return CheckResult("codex_git_sync_runner", False, f"{label} failed: {result.stderr.strip()}")

    (fixture / "work.txt").write_text("fixture change\n", encoding="utf-8")
    sync = run(
        [sys.executable, ".codex/scripts/codex_git_sync.py", "--message", "chore: fixture sync"],
        fixture,
        timeout=120,
    )
    status = run(["git", "status", "--porcelain=v1"], fixture)
    ahead = run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], fixture)
    remote_log = run(
        ["git", "--git-dir", str(CODEX_GIT_SYNC_REMOTE), "log", "--oneline", "--max-count=1", "refs/heads/main"],
        fixture,
    )

    ok = (
        sync.returncode == 0
        and status.returncode == 0
        and status.stdout.strip() == ""
        and ahead.returncode == 0
        and ahead.stdout.strip() == "0\t0"
        and "chore: fixture sync" in remote_log.stdout
    )
    return CheckResult(
        "codex_git_sync_runner",
        ok,
        "runner committed, pushed to local bare remote, and left fixture clean"
        if ok
        else (
            f"sync={sync.returncode} status={status.stdout!r} ahead={ahead.stdout!r} "
            f"remote_log={remote_log.stdout!r} output={(sync.stdout + sync.stderr).strip()}"
        ),
    )


CHECKS = {
    "codex-git-sync": check_codex_git_sync_runner,
    "encoding-garble": check_encoding_garble_scan,
    "encoding-no-bom": check_encoding_no_bom,
    "model-policy": check_model_policy,
    "layout-migration": check_layout_migration_dry_run_apply,
    "layout-migration-blockers": check_layout_migration_blockers_are_local,
    "layout-migration-rollback": check_layout_migration_transaction_rollback,
    "non-ascii-shell-guard": check_non_ascii_shell_guard,
    "non-ascii-shell-settings": check_non_ascii_shell_guard_settings,
    "rule-index": check_rule_index_missing,
    "rule-size": check_rule_size_over_limit,
    "mirror-missing": check_mirror_missing_hook,
    "mirror-noop": check_mirror_no_templates_noop,
    "precommit-shebang": check_precommit_shebang_bytes,
    "settings-matchers": check_settings_multiedit_matchers,
    "root-precommit": check_root_precommit_dual_agent_gates,
    "skill-metadata": check_skill_metadata,
    "skill-refs": check_skill_references,
    "user-skill-distribution": check_user_skill_distribution,
    "subscription-routing": check_subscription_routing,
    "user-config-write-guard": check_user_config_write_guard,
    "switch-archive": check_switch_archive_restore,
    "switch-archive-integrity": check_switch_archive_receipt_integrity,
    "switch-archive-ownership": check_switch_archive_destination_ownership,
    "switch-backup-toctou": check_switch_backup_toctou,
    "switch-claude-cleanup-only": check_switch_claude_complete_target_cleanup_only,
    "switch-codex-archive": check_switch_codex_to_claude_archive_scope,
    "switch-cleanup-only": check_switch_complete_target_cleanup_only,
    "switch-dry-run": check_switch_dry_run_full_plan,
    "switch-detached-toctou": check_switch_detached_toctou,
    "switch-evidence-attacks": check_switch_evidence_attack_rollback,
    "switch-link-boundary": check_switch_link_boundary,
    "switch-legacy-archive": check_switch_legacy_archive_fail_closed,
    "switch-manifest-binding": check_switch_manifest_security_binding,
    "switch-memory": check_switch_memory_conflict_decision,
    "switch-no-old": check_switch_no_old_installs_target,
    "switch-partial-target-dir": check_switch_partial_target_dir_conflict_stops,
    "switch-partial-target": check_switch_partial_target_conflict_stops,
    "switch-roundtrip-lineage": check_switch_roundtrip_lineage,
    "switch-path-guards": check_switch_path_and_target_evidence_guards,
    "switch-generated-archive": check_switch_constraint_archive_requires_adapter,
    "switch-same": check_switch_same_agent_noop,
    "switch-settings": check_switch_settings_decision,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        action="append",
        choices=sorted(CHECKS),
        help="Run one case. May be passed multiple times. Default: run all cases.",
    )
    args = parser.parse_args()

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    selected = args.case or sorted(CHECKS)
    results = [CHECKS[name]() for name in selected]

    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")

    failed = [r for r in results if not r.ok]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
