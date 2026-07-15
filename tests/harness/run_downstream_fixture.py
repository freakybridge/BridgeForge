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

Generated fixture directories are disposable and are never product source.
"""
from __future__ import annotations

import argparse
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


def run(cmd: list[str], cwd: Path, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
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
    shutil.copy2(CODEX_TEMPLATE / "config.toml", codex_dir / "config.toml")
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
    project_skill = fixture / ".agents" / "skills" / "project-only" / "SKILL.md"
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
        and (codex_archives[0] / ".agents" / "skills" / "project-only" / "SKILL.md").exists()
        and "Validation passed" in text
    )
    return CheckResult(
        "switch_codex_to_claude_archive_scope",
        ok,
        "Codex to Claude archives AGENTS.md, .codex, and .agents/skills, then removes empty .agents"
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
    "user-config-write-guard": check_user_config_write_guard,
    "switch-archive": check_switch_archive_restore,
    "switch-claude-cleanup-only": check_switch_claude_complete_target_cleanup_only,
    "switch-codex-archive": check_switch_codex_to_claude_archive_scope,
    "switch-cleanup-only": check_switch_complete_target_cleanup_only,
    "switch-dry-run": check_switch_dry_run_full_plan,
    "switch-memory": check_switch_memory_conflict_decision,
    "switch-no-old": check_switch_no_old_installs_target,
    "switch-partial-target-dir": check_switch_partial_target_dir_conflict_stops,
    "switch-partial-target": check_switch_partial_target_conflict_stops,
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
