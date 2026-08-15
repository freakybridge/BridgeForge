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
    # 该 fixture 已是下游项目：根 VERSION 代表下游业务版本，不来自 BridgeForge。
    (CODEX_FIXTURE / "VERSION").write_text("0.1.0\n", encoding="utf-8")

    codex_dir = CODEX_FIXTURE / ".codex"
    codex_dir.mkdir()
    for name in ("hooks", "scripts", "rules", "memory"):
        _copytree(CODEX_TEMPLATE / name, codex_dir / name)
    shutil.copy2(CODEX_TEMPLATE / "settings.json", codex_dir / "settings.json")
    shutil.copy2(CODEX_TEMPLATE / "hooks.json", codex_dir / "hooks.json")
    shutil.copy2(CODEX_TEMPLATE / "managed-skeleton.json", codex_dir / "managed-skeleton.json")
    shutil.copy2(REPO_ROOT / "VERSION", codex_dir / ".bridgeforge_version")
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


def check_rule_index_scope_and_audit() -> CheckResult:
    scope_fixture = build_codex_fixture()
    entry = scope_fixture / "AGENTS.md"
    entry.write_text(
        entry.read_text(encoding="utf-8")
        + "\n## 12. 非索引示例\n\n`rules/not-indexed.md` 仅用于说明。\n",
        encoding="utf-8",
    )
    scoped = run(
        [sys.executable, ".codex/hooks/rule_index_check.py", "--pre-commit"],
        scope_fixture,
    )

    audit_fixture = build_codex_fixture()
    (audit_fixture / ".codex" / "rules" / "debugging.md").unlink()
    audit = run(
        [sys.executable, ".codex/hooks/rule_index_check.py", "--audit-all"],
        audit_fixture,
    )

    malformed_fixture = build_codex_fixture()
    malformed_entry = malformed_fixture / "AGENTS.md"
    malformed_entry.write_text(
        malformed_entry.read_text(encoding="utf-8").replace(
            "## 2. 规则文件索引", "## 2. 已移除的标题", 1
        ),
        encoding="utf-8",
    )
    malformed = run(
        [sys.executable, ".codex/hooks/rule_index_check.py", "--audit-all"],
        malformed_fixture,
    )

    ok = (
        scoped.returncode == 0
        and audit.returncode == 2
        and "debugging.md" in (audit.stderr + audit.stdout)
        and malformed.returncode == 2
        and "规则文件索引" in (malformed.stderr + malformed.stdout)
    )
    return CheckResult(
        "codex_rule_index_scope_and_audit",
        ok,
        "non-index references are ignored; audit blocks missing entries and a missing index section"
        if ok
        else (
            f"scoped={scoped.returncode} audit={audit.returncode} "
            f"malformed={malformed.returncode}"
        ),
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
    hooks = json.loads((CODEX_TEMPLATE / "hooks.json").read_text(encoding="utf-8-sig"))
    post_blocks = hooks.get("hooks", {}).get("PostToolUse", [])
    edit_dispatchers = [
        hook
        for block in post_blocks
        if {"Edit", "Write"}.issubset(_matcher_tokens(block.get("matcher", "")))
        for hook in block.get("hooks", [])
        if isinstance(hook, dict) and "hook_dispatcher.py" in hook.get("command", "")
    ]
    ok = "hooks" not in settings and len(edit_dispatchers) == 1
    return CheckResult(
        "codex_hooks_edit_dispatcher",
        ok,
        "settings has no hooks and hooks.json has one Edit|Write PostTool dispatcher"
        if ok
        else f"settings_hooks={'hooks' in settings} edit_dispatchers={len(edit_dispatchers)}",
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
        '.claude/hooks/encoding_check.py" --pre-commit',
        '.codex/hooks/encoding_check.py" --pre-commit',
        '.claude/hooks/skill_metadata_check.py" --pre-commit',
        '.codex/hooks/skill_metadata_check.py" --pre-commit',
        '.codex/hooks/config_health_check.py" --strict',
        'for CONFIG_DIR in .claude .codex; do',
        '$CONFIG_DIR/scripts/memory_rebuild_index.py',
    ]
    missing = [needle for needle in required if needle not in precommit]
    bad_quoted_args = [
        '.claude/hooks/rule_size_check.py --pre-commit',
        '.claude/hooks/rule_index_check.py --pre-commit',
        '.codex/hooks/rule_size_check.py --pre-commit',
        '.codex/hooks/rule_index_check.py --pre-commit',
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


def check_python_311_hook_baseline() -> CheckResult:
    errors: list[str] = []
    precommits = (
        REPO_ROOT / ".githooks" / "pre-commit",
        CODEX_TEMPLATE / ".githooks" / "pre-commit",
        CLAUDE_TEMPLATE / ".githooks" / "pre-commit",
    )
    for path in precommits:
        text = path.read_text(encoding="utf-8")
        for marker in (
            "sys.version_info >= (3, 11)",
            "project .venv must use Python 3.11+",
            "PATH fallback is forbidden",
        ):
            if marker not in text:
                errors.append(f"{path.relative_to(REPO_ROOT)} missing {marker!r}")

    for path in (
        CODEX_TEMPLATE / "hooks" / "config_health_check.py",
        CLAUDE_TEMPLATE / "hooks" / "config_health_check.py",
    ):
        text = path.read_text(encoding="utf-8")
        if '"python-version"' not in text or "Python 3.11+" not in text:
            errors.append(f"{path.relative_to(REPO_ROOT)} missing Python version health check")
    for path in (
        CODEX_TEMPLATE / "scripts" / "hooks_merge.py",
        CODEX_TEMPLATE / "hooks" / "hook_dispatcher.py",
    ):
        if "MIN_PYTHON = (3, 11)" not in path.read_text(encoding="utf-8"):
            errors.append(f"{path.relative_to(REPO_ROOT)} missing Python 3.11 hard gate")

    template_hooks = json.loads((CODEX_TEMPLATE / "hooks.json").read_text(encoding="utf-8"))
    dogfood_hooks = json.loads((REPO_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    if template_hooks != dogfood_hooks:
        errors.append("Codex dogfood hooks.json must exactly match the template")
    for blocks in template_hooks.get("hooks", {}).values():
        for block in blocks:
            for hook in block.get("hooks", []):
                if ".venv/Scripts/python.exe" not in hook.get("command", ""):
                    errors.append("Codex managed hook command does not use project .venv")

    skill = (REPO_ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
    if skill.index("Step 2.1：项目 Python 3.11+") > skill.index("Step 2.5：当前项目遗留"):
        errors.append("BridgeForge Python preflight runs after a project write path")
    for marker in ("$HOOK_PYTHON", "禁止复制、删除、merge"):
        if marker not in skill:
            errors.append(f"BridgeForge preflight missing {marker!r}")

    return CheckResult(
        "python_311_hook_baseline",
        not errors,
        "Python 3.11+ is locked before writes across hooks and pre-commit"
        if not errors else "; ".join(errors),
    )


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
    target = fixture / ".codex" / "memory" / "MEMORY.md"
    target.write_bytes(b"\xef\xbb\xbf" + target.read_bytes())
    bad = run([sys.executable, ".codex/hooks/encoding_check.py", "--pre-commit"], fixture)

    ok = bad.returncode == 2 and ".codex/memory/MEMORY.md" in (bad.stdout + bad.stderr)
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

    codex_hooks = json.loads((CODEX_TEMPLATE / "hooks.json").read_text(encoding="utf-8-sig"))
    codex_dispatcher = any(
        isinstance(hook, dict) and "hook_dispatcher.py" in hook.get("command", "")
        for block in codex_hooks.get("hooks", {}).get("PreToolUse", [])
        if "Bash" in _matcher_tokens(block.get("matcher", ""))
        for hook in block.get("hooks", [])
    )
    if not codex_dispatcher:
        missing.append("templates/codex/hooks.json")
    return CheckResult(
        "non_ascii_shell_guard_settings",
        not missing,
        "Claude keeps direct registration and Codex routes the guard through hooks.json dispatcher"
        if not missing
        else "missing guard registration: " + ", ".join(missing),
    )


def check_encoding_garble_scan() -> CheckResult:
    fixture = build_codex_fixture()
    target = fixture / ".codex" / "settings.json"
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "acceptEdits",
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


def _build_direct_switch_fixture() -> Path:
    """Build a minimal project with both live host skeletons."""
    _safe_reset_dir(SWITCH_FIXTURE)
    fixture = SWITCH_FIXTURE
    scripts = fixture / "scripts"
    scripts.mkdir()
    shutil.copy2(
        REPO_ROOT / "scripts" / "bridgeforge_switch.py",
        scripts / "bridgeforge_switch.py",
    )
    for host, template, entry in (
        ("claude", CLAUDE_TEMPLATE, "CLAUDE.md"),
        ("codex", CODEX_TEMPLATE, "AGENTS.md"),
    ):
        (fixture / f".{host}").mkdir()
        shutil.copy2(template / entry, fixture / entry)
    return fixture


def _run_direct_switch(
    fixture: Path,
    host: str,
    *,
    attested_host: str | None = None,
    dry_run: bool = False,
    fail_at: str | None = None,
    risk_fingerprint: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "scripts/bridgeforge_switch.py",
        host,
        "--current-host",
        attested_host or host,
        "--project-root",
        str(fixture),
        "--template-root",
        str(REPO_ROOT),
    ]
    if dry_run:
        command.append("--dry-run")
    if risk_fingerprint is not None:
        command.extend(["--confirmed-risk-fingerprint", risk_fingerprint])
    env = {"BRIDGEFORGE_SWITCH_FAIL_AT": fail_at} if fail_at else None
    return run(command, fixture, env=env)


def _switch_snapshot(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[f"dir:{rel}"] = b""
        elif path.is_file():
            snapshot[f"file:{rel}"] = path.read_bytes()
    return snapshot


def _switch_map(fixture: Path, host: str) -> dict[str, object]:
    path = fixture / f".{host}" / ".bridgeforge-map.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_empty_switch_map(
    fixture: Path,
    *,
    source_host: str,
    target_host: str,
) -> None:
    (fixture / f".{target_host}" / ".bridgeforge-map.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "source_host": source_host,
                "target_host": target_host,
                "assets": [],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _direct_switch_module():
    module_path = REPO_ROOT / "scripts" / "bridgeforge_switch.py"
    spec = importlib.util.spec_from_file_location(
        "bridgeforge_switch_direct_fixture",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import direct-sync switch module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_directory_link(link: Path, target: Path) -> tuple[bool, str]:
    try:
        os.symlink(target, link, target_is_directory=True)
        return True, "symlink"
    except OSError as symlink_error:
        if os.name != "nt":
            return False, str(symlink_error)
        result = run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            link.parent,
        )
        if result.returncode == 0:
            return True, "junction"
        return False, (result.stdout + result.stderr).strip()


def _remove_directory_link(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif os.path.lexists(path):
        os.rmdir(path)


def _switch_sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _switch_json_sha(value: object) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _switch_sha(canonical)


def _write_generated_whole_file_map(
    fixture: Path,
    *,
    source_host: str,
    target_host: str,
    asset_id: str,
    source_paths: list[str],
    target_paths: list[str],
) -> None:
    document = {
        "schema_version": 3,
        "source_host": source_host,
        "target_host": target_host,
        "assets": [
            {
                "asset_id": asset_id,
                "asset_type": "portable-text",
                "adapter": {"id": "whole-file", "version": 1},
                "source_members": [
                    {
                        "path": path,
                        "sha256": _switch_sha((fixture / path).read_bytes()),
                    }
                    for path in source_paths
                ],
                "target_members": [
                    {
                        "path": path,
                        "last_generated_sha256": _switch_sha(
                            (fixture / path).read_bytes()
                        ),
                    }
                    for path in target_paths
                ],
                "status": "generated",
            }
        ],
    }
    map_path = fixture / f".{target_host}" / ".bridgeforge-map.json"
    map_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def check_switch_direct_host_mismatch() -> CheckResult:
    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "memory" / "host-check.md"
    source.parent.mkdir()
    source.write_text("host mismatch sentinel\n", encoding="utf-8")
    before = _switch_snapshot(fixture)
    result = _run_direct_switch(
        fixture,
        "codex",
        attested_host="claude",
    )
    output = result.stdout + result.stderr
    ok = (
        result.returncode == 2
        and before == _switch_snapshot(fixture)
        and "--current-host must match" in output
        and "no project files were changed" in output.lower()
    )
    return CheckResult(
        "switch_direct_host_mismatch",
        ok,
        "host/argument mismatch exits 2 before any project write"
        if ok
        else f"mismatch was not zero-write (exit={result.returncode}): {output.strip()}",
    )


def check_switch_direct_bidirectional_maps() -> CheckResult:
    failures: list[str] = []
    cases = (
        (
            "codex",
            ".claude/memory/from-claude.md",
            ".codex/memory/from-claude.md",
            b"claude portable sentinel\n",
            "claude",
        ),
        (
            "claude",
            ".codex/memory/from-codex.md",
            ".claude/memory/from-codex.md",
            b"codex portable sentinel\n",
            "codex",
        ),
    )
    for target_host, source_rel, target_rel, content, source_host in cases:
        fixture = _build_direct_switch_fixture()
        _write_empty_switch_map(
            fixture,
            source_host=source_host,
            target_host=target_host,
        )
        source = fixture / source_rel
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(content)
        source_before = _switch_snapshot(fixture / f".{source_host}")
        result = _run_direct_switch(fixture, target_host)
        target_map_path = fixture / f".{target_host}" / ".bridgeforge-map.json"
        map_bytes = target_map_path.read_bytes() if target_map_path.is_file() else b""
        map_data = _switch_map(fixture, target_host) if map_bytes else {}
        repeated = _run_direct_switch(fixture, target_host)
        serialized = map_bytes.decode("utf-8", errors="replace")
        assets = map_data.get("assets", [])
        generated = [
            asset
            for asset in assets
            if asset.get("status") == "generated"
        ]
        if not (
            result.returncode == 0
            and repeated.returncode == 0
            and (fixture / ".claude").is_dir()
            and (fixture / ".codex").is_dir()
            and _switch_snapshot(fixture / f".{source_host}") == source_before
            and (fixture / target_rel).read_bytes() == content
            and map_data.get("source_host") == source_host
            and map_data.get("target_host") == target_host
            and any(
                member.get("path") == target_rel
                for asset in generated
                for member in asset.get("target_members", [])
            )
            and str(fixture) not in serialized
            and content.decode("utf-8").strip() not in serialized
            and "timestamp" not in serialized
            and target_map_path.read_bytes() == map_bytes
        ):
            failures.append(
                f"{source_host}->{target_host}: "
                f"{(result.stdout + result.stderr + repeated.stdout + repeated.stderr).strip()}"
            )
    return CheckResult(
        "switch_direct_bidirectional_maps",
        not failures,
        "both live skeletons coexist; Claude↔Codex writes the target projection and deterministic target-local map"
        if not failures
        else "; ".join(failures),
    )


def check_switch_direct_whole_file_lifecycle() -> CheckResult:
    fixture = _build_direct_switch_fixture()
    _write_empty_switch_map(
        fixture,
        source_host="claude",
        target_host="codex",
    )
    source = fixture / ".claude" / "memory" / "lifecycle.md"
    target = fixture / ".codex" / "memory" / "lifecycle.md"
    source.parent.mkdir()
    source.write_text("version one\n", encoding="utf-8")
    first = _run_direct_switch(fixture, "codex")
    source.write_text("version two\n", encoding="utf-8")
    updated = _run_direct_switch(fixture, "codex")
    update_ok = target.read_text(encoding="utf-8") == "version two\n"
    source.unlink()
    deleted = _run_direct_switch(fixture, "codex")
    delete_ok = not target.exists()

    source.write_text("owned base\n", encoding="utf-8")
    seeded = _run_direct_switch(fixture, "codex")
    target.write_text("manual target edit\n", encoding="utf-8")
    source.write_text("source changed\n", encoding="utf-8")
    conflicted = _run_direct_switch(fixture, "codex")
    conflict_map = _switch_map(fixture, "codex")
    conflict_assets = [
        asset
        for asset in conflict_map["assets"]
        if asset["status"] == "conflict"
    ]
    ok = (
        all(
            result.returncode == 0
            for result in (first, updated, deleted, seeded, conflicted)
        )
        and update_ok
        and delete_ok
        and target.read_text(encoding="utf-8") == "manual target edit\n"
        and any(
            asset.get("reason") == "interrupted-or-modified"
            for asset in conflict_assets
        )
        and "completed_with_gaps" in conflicted.stdout
    )
    output = "".join(
        result.stdout + result.stderr
        for result in (first, updated, deleted, seeded, conflicted)
    )
    return CheckResult(
        "switch_direct_whole_file_lifecycle",
        ok,
        "whole-file ownership updates and deletes clean projections, but preserves manually modified targets as conflicts"
        if ok
        else f"whole-file lifecycle failed: {output.strip()}",
    )


def check_switch_direct_source_map_projection() -> CheckResult:
    fixture = _build_direct_switch_fixture()
    _write_empty_switch_map(
        fixture,
        source_host="claude",
        target_host="codex",
    )
    original = fixture / ".claude" / "memory" / "roundtrip.md"
    projection = fixture / ".codex" / "memory" / "roundtrip.md"
    original.parent.mkdir()
    original.write_text("original authority\n", encoding="utf-8")
    forward = _run_direct_switch(fixture, "codex")
    clean_return = _run_direct_switch(fixture, "claude")
    clean_map = _switch_map(fixture, "claude")
    clean_echo = [
        asset
        for asset in clean_map["assets"]
        if any(
            member.get("path") == ".codex/memory/roundtrip.md"
            for member in asset["source_members"]
        )
    ]

    projection.write_text("forked projection\n", encoding="utf-8")
    forked_return = _run_direct_switch(fixture, "claude")
    fork_map = _switch_map(fixture, "claude")
    fork_assets = [
        asset
        for asset in fork_map["assets"]
        if asset["status"] == "forked_projection"
    ]
    ok = (
        forward.returncode == 0
        and clean_return.returncode == 0
        and forked_return.returncode == 0
        and not clean_echo
        and original.read_text(encoding="utf-8") == "original authority\n"
        and projection.read_text(encoding="utf-8") == "forked projection\n"
        and any(
            member.get("path") == ".codex/memory/roundtrip.md"
            for asset in fork_assets
            for member in asset["source_members"]
        )
        and "completed_with_gaps" in forked_return.stdout
    )
    output = (
        forward.stdout
        + forward.stderr
        + clean_return.stdout
        + clean_return.stderr
        + forked_return.stdout
        + forked_return.stderr
    )
    return CheckResult(
        "switch_direct_source_map_projection",
        ok,
        "clean generated projections are echo-suppressed; modified projections become non-overwriting forks"
        if ok
        else f"source-map projection handling failed: {output.strip()}",
    )


def check_switch_direct_map_ownership() -> CheckResult:
    failures: list[str] = []

    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "memory" / "unknown.md"
    new_source = fixture / ".claude" / "memory" / "new.md"
    target = fixture / ".codex" / "memory" / "unknown.md"
    new_target = fixture / ".codex" / "memory" / "new.md"
    orphan = fixture / ".codex" / "memory" / "orphan.md"
    source.parent.mkdir()
    target.parent.mkdir()
    source.write_text("source content\n", encoding="utf-8")
    new_source.write_text("independent new content\n", encoding="utf-8")
    target.write_text("user target content\n", encoding="utf-8")
    orphan.write_text("unmapped orphan content\n", encoding="utf-8")
    missing = _run_direct_switch(fixture, "codex")
    missing_map = _switch_map(fixture, "codex")
    mapped_target_paths = {
        member["path"]
        for asset in missing_map["assets"]
        for member in asset["target_members"]
    }
    if not (
        missing.returncode == 0
        and target.read_text(encoding="utf-8") == "user target content\n"
        and new_target.read_text(encoding="utf-8")
        == "independent new content\n"
        and orphan.read_text(encoding="utf-8") == "unmapped orphan content\n"
        and any(
            asset["status"] == "conflict"
            and asset.get("reason") == "target-map-untrusted"
            for asset in missing_map["assets"]
        )
        and any(
            asset["status"] == "created_unowned"
            and asset.get("reason") == "target-map-untrusted"
            and any(
                member["path"] == ".codex/memory/new.md"
                for member in asset["target_members"]
            )
            for asset in missing_map["assets"]
        )
        and all(
            "last_generated_sha256" not in member
            for asset in missing_map["assets"]
            for member in asset["target_members"]
        )
        and ".codex/memory/orphan.md" not in mapped_target_paths
    ):
        failures.append(
            "missing map did not isolate unowned creation from existing targets"
        )

    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "memory" / "unknown.md"
    new_source = fixture / ".claude" / "memory" / "new.md"
    target = fixture / ".codex" / "memory" / "unknown.md"
    new_target = fixture / ".codex" / "memory" / "new.md"
    orphan = fixture / ".codex" / "memory" / "orphan.md"
    source.parent.mkdir()
    target.parent.mkdir()
    source.write_text("source content\n", encoding="utf-8")
    new_source.write_text("independent new content\n", encoding="utf-8")
    target.write_text("user target content\n", encoding="utf-8")
    orphan.write_text("unmapped orphan content\n", encoding="utf-8")
    map_path = fixture / ".codex" / ".bridgeforge-map.json"
    map_path.write_bytes(b"{broken map sentinel")
    corrupt = _run_direct_switch(fixture, "codex")
    output = corrupt.stdout + corrupt.stderr
    if not (
        corrupt.returncode == 0
        and map_path.read_bytes() == b"{broken map sentinel"
        and target.read_text(encoding="utf-8") == "user target content\n"
        and new_target.read_text(encoding="utf-8")
        == "independent new content\n"
        and orphan.read_text(encoding="utf-8") == "unmapped orphan content\n"
        and "assets=conflict:1,created_unowned:1" in output
        and "Target map is invalid and was preserved" in output
    ):
        failures.append(
            "invalid map did not preserve existing targets while creating "
            "an independent absent target"
        )

    return CheckResult(
        "switch_direct_map_ownership",
        not failures,
        "missing/invalid maps allow only unowned creation at absent paths; existing targets stay unmodified, undeleted, and unclaimed"
        if not failures
        else "; ".join(failures),
    )


def check_switch_direct_target_link_toctou() -> CheckResult:
    failures: list[str] = []
    module = _direct_switch_module()

    for label, swap_host_root in (
        ("target-write-parent", False),
        ("target-map-parent", True),
    ):
        fixture = _build_direct_switch_fixture()
        source = fixture / ".claude" / "memory" / f"{label}.md"
        source.parent.mkdir()
        source.write_text(f"{label} sentinel\n", encoding="utf-8")
        plan = module.build_plan(
            "codex",
            fixture.resolve(),
            REPO_ROOT.resolve(),
        )
        outside = RUNTIME_ROOT / f"switch-link-{label}"
        _safe_reset_dir(outside)
        (outside / "outside.bin").write_bytes(b"outside sentinel\n")
        outside_before = _switch_snapshot(outside)

        link = (
            fixture / ".codex"
            if swap_host_root
            else fixture / ".codex" / "memory"
        )
        if swap_host_root:
            link.rmdir()
        linked, link_kind = _create_directory_link(link, outside)
        if not linked:
            failures.append(f"{label}: link setup unavailable: {link_kind}")
            if swap_host_root and not link.exists():
                link.mkdir()
            continue

        error = ""
        try:
            module.apply_plan(plan)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            _remove_directory_link(link)
            if swap_host_root:
                link.mkdir()

        if not (
            (
                "symlink" in error.lower()
                or "junction" in error.lower()
                or "escapes project root" in error.lower()
            )
            and source.read_text(encoding="utf-8")
            == f"{label} sentinel\n"
            and _switch_snapshot(outside) == outside_before
            and not (
                fixture / ".codex" / ".bridgeforge-map.json"
            ).exists()
            and not (outside / f"{label}.md").exists()
        ):
            failures.append(
                f"{label}/{link_kind}: TOCTOU was not zero-write blocked: "
                f"{error}"
            )

    return CheckResult(
        "switch_direct_target_link_toctou",
        not failures,
        "post-plan symlink/junction swaps on target write and map parents are revalidated and blocked before writes"
        if not failures
        else "; ".join(failures),
    )


def check_switch_direct_json_pointer_permissions() -> CheckResult:
    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "settings.json"
    target = fixture / ".codex" / "settings.json"
    source.write_text(
        json.dumps(
            {"permissions": {"allow": ["Read"]}, "claude_only": "source"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    target.write_text(
        json.dumps({"codex_only": {"keep": True}}, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_empty_switch_map(
        fixture,
        source_host="claude",
        target_host="codex",
    )
    first = _run_direct_switch(fixture, "codex")
    first_target = json.loads(target.read_text(encoding="utf-8"))
    source.write_text(
        json.dumps(
            {"permissions": {"allow": ["Read", "Write"]}, "claude_only": "changed"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    updated = _run_direct_switch(fixture, "codex")
    updated_target = json.loads(target.read_text(encoding="utf-8"))
    manual_target = json.loads(json.dumps(updated_target))
    manual_target["permissions"] = {"allow": ["Manual"]}
    target.write_text(
        json.dumps(manual_target, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source.write_text(
        json.dumps(
            {"permissions": {"allow": ["Bash"]}, "claude_only": "again"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    conflicted = _run_direct_switch(fixture, "codex")
    final_target = json.loads(target.read_text(encoding="utf-8"))
    target_map = _switch_map(fixture, "codex")
    permissions_assets = [
        asset
        for asset in target_map["assets"]
        if asset["asset_id"] == "shared-settings:permissions"
    ]
    ok = (
        first.returncode == 0
        and updated.returncode == 0
        and conflicted.returncode == 0
        and first_target["permissions"] == {"allow": ["Read"]}
        and first_target["codex_only"] == {"keep": True}
        and updated_target["permissions"] == {"allow": ["Read", "Write"]}
        and updated_target["codex_only"] == {"keep": True}
        and final_target["permissions"] == {"allow": ["Manual"]}
        and final_target["codex_only"] == {"keep": True}
        and len(permissions_assets) == 1
        and permissions_assets[0]["status"] == "conflict"
        and permissions_assets[0].get("reason") == "interrupted-or-modified"
        and permissions_assets[0]["source_members"][0]["selector"]
        == "/permissions"
    )
    output = (
        first.stdout
        + first.stderr
        + updated.stdout
        + updated.stderr
        + conflicted.stdout
        + conflicted.stderr
    )
    return CheckResult(
        "switch_direct_json_pointer_permissions",
        ok,
        "the /permissions JSON Pointer updates only its owned field and preserves manual selector edits as conflicts"
        if ok
        else f"JSON Pointer ownership failed: {output.strip()}",
    )


def check_switch_direct_cardinality() -> CheckResult:
    failures: list[str] = []

    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "memory" / "one.md"
    left = fixture / ".codex" / "memory" / "left.md"
    right = fixture / ".codex" / "memory" / "right.md"
    source.parent.mkdir()
    left.parent.mkdir()
    source.write_text("base\n", encoding="utf-8")
    left.write_text("base\n", encoding="utf-8")
    right.write_text("base\n", encoding="utf-8")
    _write_generated_whole_file_map(
        fixture,
        source_host="claude",
        target_host="codex",
        asset_id="fixture:one-to-many",
        source_paths=[".claude/memory/one.md"],
        target_paths=[".codex/memory/left.md", ".codex/memory/right.md"],
    )
    source.write_text("one-to-many update\n", encoding="utf-8")
    one_to_many = _run_direct_switch(fixture, "codex")
    if not (
        one_to_many.returncode == 0
        and left.read_text(encoding="utf-8") == "one-to-many update\n"
        and right.read_text(encoding="utf-8") == "one-to-many update\n"
    ):
        failures.append("one-to-many projection failed")

    fixture = _build_direct_switch_fixture()
    first_source = fixture / ".claude" / "memory" / "first.md"
    second_source = fixture / ".claude" / "memory" / "second.md"
    merged = fixture / ".codex" / "memory" / "merged.md"
    first_source.parent.mkdir()
    merged.parent.mkdir()
    for path in (first_source, second_source, merged):
        path.write_text("base\n", encoding="utf-8")
    _write_generated_whole_file_map(
        fixture,
        source_host="claude",
        target_host="codex",
        asset_id="fixture:many-to-one",
        source_paths=[
            ".claude/memory/first.md",
            ".claude/memory/second.md",
        ],
        target_paths=[".codex/memory/merged.md"],
    )
    first_source.write_text("many-to-one update\n", encoding="utf-8")
    second_source.write_text("many-to-one update\n", encoding="utf-8")
    many_to_one = _run_direct_switch(fixture, "codex")
    if not (
        many_to_one.returncode == 0
        and merged.read_text(encoding="utf-8") == "many-to-one update\n"
    ):
        failures.append("many-to-one projection failed")

    return CheckResult(
        "switch_direct_cardinality",
        not failures,
        "trusted whole-file maps preserve one-to-many and byte-identical many-to-one semantic groups"
        if not failures
        else "; ".join(failures),
    )


def check_switch_direct_legacy_root() -> CheckResult:
    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "memory" / "legacy.md"
    source.parent.mkdir()
    source.write_text("portable\n", encoding="utf-8")
    legacy = fixture / ".bridgeforge"
    (legacy / "archive" / "sentinel").mkdir(parents=True)
    (legacy / "archive" / "sentinel" / "raw.bin").write_bytes(
        b"\x00legacy archive bytes\xff"
    )
    (legacy / "migrations.json").write_bytes(b"legacy receipt bytes\n")
    before = _switch_snapshot(legacy)
    result = _run_direct_switch(fixture, "codex")
    output = result.stdout + result.stderr
    ok = (
        result.returncode == 0
        and _switch_snapshot(legacy) == before
        and "legacy project-root .bridgeforge/" in output
        and "was not read, written, or removed" in output
    )
    return CheckResult(
        "switch_direct_legacy_root",
        ok,
        "legacy project-root .bridgeforge is notice-only and remains byte-identical"
        if ok
        else f"legacy root contract failed: {output.strip()}",
    )


def check_switch_direct_rollback() -> CheckResult:
    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "memory" / "rollback.md"
    source.parent.mkdir()
    source.write_text("rollback sentinel\n", encoding="utf-8")
    before = _switch_snapshot(fixture)
    complete = _run_direct_switch(
        fixture,
        "codex",
        fail_at="after-map-replace",
    )
    complete_output = complete.stdout + complete.stderr
    complete_restored = _switch_snapshot(fixture) == before

    fixture = _build_direct_switch_fixture()
    source = fixture / ".claude" / "memory" / "rollback.md"
    source.parent.mkdir()
    source.write_text("rollback sentinel\n", encoding="utf-8")
    incomplete = _run_direct_switch(
        fixture,
        "codex",
        fail_at="after-map-replace,rollback-before-restore",
    )
    incomplete_output = incomplete.stdout + incomplete.stderr
    ok = (
        complete.returncode == 1
        and complete_restored
        and "failed and was fully rolled back" in complete_output
        and "after-map-replace" in complete_output
        and incomplete.returncode == 1
        and "rollback incomplete" in incomplete_output
        and "RECOVERY:" in incomplete_output
        and "rollback-fault:" in incomplete_output
        and "fully rolled back" not in incomplete_output
        and (fixture / ".codex" / "memory" / "rollback.md").is_file()
        and (fixture / ".codex" / ".bridgeforge-map.json").is_file()
    )
    return CheckResult(
        "switch_direct_rollback",
        ok,
        "after-map-replace fully rolls back; an injected restore failure reports rollback incomplete with recovery evidence"
        if ok
        else (
            f"rollback reporting failed: complete={complete.returncode}:"
            f"{complete_output.strip()} incomplete={incomplete.returncode}:"
            f"{incomplete_output.strip()}"
        ),
    )


def check_switch_direct_untranslated() -> CheckResult:
    fixture = _build_direct_switch_fixture()
    source_entry = fixture / "CLAUDE.md"
    target_entry = fixture / "AGENTS.md"
    hook = fixture / ".claude" / "hooks" / "raw_hook.py"
    hook.parent.mkdir()
    raw_hook = b"#!/usr/bin/env python3\nprint('host-only raw sentinel')\n"
    hook.write_bytes(raw_hook)
    source_entry.write_text(
        "Claude-only entry raw sentinel\n",
        encoding="utf-8",
    )
    target_before = target_entry.read_bytes()
    result = _run_direct_switch(fixture, "codex")
    target_map = _switch_map(fixture, "codex")
    serialized = json.dumps(target_map, ensure_ascii=False)
    untranslated_paths = {
        member["path"]
        for asset in target_map["assets"]
        if asset["status"] == "untranslated"
        for member in asset["source_members"]
    }
    ok = (
        result.returncode == 0
        and hook.read_bytes() == raw_hook
        and target_entry.read_bytes() == target_before
        and not (fixture / ".codex" / "hooks" / "raw_hook.py").exists()
        and {"CLAUDE.md", ".claude/hooks/raw_hook.py"}.issubset(
            untranslated_paths
        )
        and "host-only raw sentinel" not in serialized
        and "Claude-only entry raw sentinel" not in serialized
        and "untranslated" in result.stdout
        and "completed_with_gaps" in result.stdout
    )
    return CheckResult(
        "switch_direct_untranslated",
        ok,
        "host-specific entry/hook bytes stay at source and are reported as untranslated without raw-copy leakage"
        if ok
        else f"untranslated asset handling failed: {(result.stdout + result.stderr).strip()}",
    )


def check_switch_direct_portable_rule_candidates() -> CheckResult:
    portable_field = "bridgeforge_portable_rule: true"
    failures: list[str] = []
    module = _direct_switch_module()

    def seed_rules(
        fixture: Path,
        source_host: str,
        target_host: str,
        *,
        include_target: bool = True,
    ) -> tuple[dict[str, str], dict[Path, bytes]]:
        source_rules = fixture / f".{source_host}" / "rules"
        target_rules = fixture / f".{target_host}" / "rules"
        source_rules.mkdir()
        target_rules.mkdir()
        rels = {
            "marked": f".{source_host}/rules/portable.md",
            "missing": f".{source_host}/rules/missing-field.md",
            "duplicate": f".{source_host}/rules/duplicate-field.md",
            "false": f".{source_host}/rules/false-field.md",
            "nonboolean": f".{source_host}/rules/nonboolean-field.md",
            "unclosed": f".{source_host}/rules/unclosed-frontmatter.md",
            "body_field": f".{source_host}/rules/body-field.md",
            "nested": f".{source_host}/rules/nested/portable.md",
            "target": f".{target_host}/rules/portable.md",
        }
        (fixture / rels["marked"]).write_text(
            "---\npaths:\n  - src/portable/**\n"
            f"{portable_field}\n"
            "---\n\n# Portable candidate\n",
            encoding="utf-8",
        )
        (fixture / rels["missing"]).write_text(
            "---\npaths:\n  - src/missing/**\n---\n\n"
            "# Missing portable field\n",
            encoding="utf-8",
        )
        (fixture / rels["duplicate"]).write_text(
            "---\npaths:\n  - src/duplicate/**\n"
            f"{portable_field}\n"
            f"{portable_field}\n"
            "---\n\n# Duplicate portable field\n",
            encoding="utf-8",
        )
        (fixture / rels["false"]).write_text(
            "---\npaths:\n  - src/false/**\n"
            "bridgeforge_portable_rule: false\n"
            "---\n\n# Explicitly non-portable\n",
            encoding="utf-8",
        )
        (fixture / rels["nonboolean"]).write_text(
            "---\npaths:\n  - src/nonboolean/**\n"
            'bridgeforge_portable_rule: "true"\n'
            "---\n\n# String is not a boolean\n",
            encoding="utf-8",
        )
        (fixture / rels["unclosed"]).write_text(
            "---\npaths:\n  - src/unclosed/**\n"
            f"{portable_field}\n\n"
            "# Missing closing frontmatter delimiter\n",
            encoding="utf-8",
        )
        (fixture / rels["body_field"]).write_text(
            "---\npaths:\n  - src/body/**\n---\n\n"
            "# Body example is not metadata\n\n"
            f"{portable_field}\n",
            encoding="utf-8",
        )
        nested = fixture / rels["nested"]
        nested.parent.mkdir()
        nested.write_text(
            "---\npaths:\n  - src/nested/**\n"
            f"{portable_field}\n"
            "---\n\n# Nested candidate is out of scope\n",
            encoding="utf-8",
        )
        if include_target:
            (fixture / rels["target"]).write_bytes(
                b"target-owned same-name Rule sentinel\r\n"
            )
        protected_rels = {
            rel
            for key, rel in rels.items()
            if key != "target" or include_target
        }
        protected = {fixture / rel for rel in protected_rels} | {
            fixture / "AGENTS.md",
            fixture / "CLAUDE.md",
        }
        return rels, {path: path.read_bytes() for path in protected}

    def related_assets(
        assets: list[dict[str, object]],
        source_path: str,
    ) -> list[dict[str, object]]:
        return [
            asset
            for asset in assets
            if any(
                member.get("path") == source_path
                for member in asset.get("source_members", [])
            )
        ]

    def is_unowned_candidate(
        assets: list[dict[str, object]],
        source_path: str,
    ) -> bool:
        related = related_assets(assets, source_path)
        return (
            len(related) == 1
            and related[0].get("asset_type") == "host-specific"
            and related[0].get("status") == "untranslated"
            and related[0].get("adapter", {}).get("id") == "none"
            and related[0].get("target_members") == []
        )

    def protected_unchanged(before: dict[Path, bytes]) -> bool:
        return all(
            path.is_file() and path.read_bytes() == content
            for path, content in before.items()
        )

    for source_host, target_host in (
        ("claude", "codex"),
        ("codex", "claude"),
    ):
        fixture = _build_direct_switch_fixture()
        _write_empty_switch_map(
            fixture,
            source_host=source_host,
            target_host=target_host,
        )
        rels, before = seed_rules(fixture, source_host, target_host)
        result = _run_direct_switch(fixture, target_host)
        target_map = _switch_map(fixture, target_host)
        assets = target_map["assets"]
        if not (
            result.returncode == 0
            and is_unowned_candidate(assets, rels["marked"])
            and not related_assets(assets, rels["nested"])
            and all(
                not related_assets(assets, rels[key])
                for key in (
                    "missing",
                    "duplicate",
                    "false",
                    "nonboolean",
                    "unclosed",
                    "body_field",
                )
            )
            and protected_unchanged(before)
            and "untranslated" in result.stdout
            and "completed_with_gaps" in result.stdout
        ):
            failures.append(
                f"{source_host}->{target_host} discovery boundary or "
                f"byte preservation failed: "
                f"{(result.stdout + result.stderr).strip()}"
            )

    fixture = _build_direct_switch_fixture()
    _write_empty_switch_map(
        fixture,
        source_host="claude",
        target_host="codex",
    )
    rels, before = seed_rules(
        fixture,
        "claude",
        "codex",
        include_target=False,
    )
    absent_target_rules = fixture / ".codex" / "rules"
    absent_tree_before = _switch_snapshot(absent_target_rules)
    absent_plan = module.build_plan(
        "codex",
        fixture.resolve(),
        REPO_ROOT.resolve(),
    )
    absent = _run_direct_switch(fixture, "codex")
    absent_assets = _switch_map(fixture, "codex")["assets"]
    target_rule_prefix = ".codex/rules/"
    if not (
        absent.returncode == 0
        and is_unowned_candidate(absent_assets, rels["marked"])
        and not any(
            path.startswith(target_rule_prefix)
            for path in [*absent_plan.writes, *absent_plan.deletes]
        )
        and _switch_snapshot(absent_target_rules) == absent_tree_before
        and protected_unchanged(before)
    ):
        failures.append(
            "absent target Rule/tree was created or scheduled for ownership"
        )

    fixture = _build_direct_switch_fixture()
    rels, before = seed_rules(fixture, "claude", "codex")
    missing = _run_direct_switch(fixture, "codex")
    missing_assets = _switch_map(fixture, "codex")["assets"]
    if not (
        missing.returncode == 0
        and is_unowned_candidate(missing_assets, rels["marked"])
        and protected_unchanged(before)
    ):
        failures.append(
            "missing target map did not retain an unowned candidate while "
            "preserving Rule/entry bytes"
        )

    fixture = _build_direct_switch_fixture()
    rels, before = seed_rules(fixture, "claude", "codex")
    corrupt_map = fixture / ".codex" / ".bridgeforge-map.json"
    corrupt_bytes = b"{broken portable Rule map sentinel"
    corrupt_map.write_bytes(corrupt_bytes)
    corrupt_plan = module.build_plan(
        "codex",
        fixture.resolve(),
        REPO_ROOT.resolve(),
    )
    corrupt = _run_direct_switch(fixture, "codex")
    corrupt_output = corrupt.stdout + corrupt.stderr
    if not (
        is_unowned_candidate(corrupt_plan.assets, rels["marked"])
        and rels["target"] not in corrupt_plan.writes
        and rels["target"] not in corrupt_plan.deletes
        and corrupt.returncode == 0
        and corrupt_map.read_bytes() == corrupt_bytes
        and protected_unchanged(before)
        and "Target map is invalid and was preserved" in corrupt_output
        and "untranslated" in corrupt_output
    ):
        failures.append(
            "corrupt target map did not stay fail-closed and byte-preserving"
        )

    fixture = _build_direct_switch_fixture()
    _write_empty_switch_map(
        fixture,
        source_host="claude",
        target_host="codex",
    )
    rels, before = seed_rules(fixture, "claude", "codex")
    drift_plan = module.build_plan(
        "codex",
        fixture.resolve(),
        REPO_ROOT.resolve(),
    )
    drift_map = fixture / ".codex" / ".bridgeforge-map.json"
    drifted_map_bytes = drift_map.read_bytes() + b"\n"
    drift_map.write_bytes(drifted_map_bytes)
    drift_error = ""
    try:
        module.apply_plan(drift_plan)
    except Exception as exc:
        drift_error = f"{type(exc).__name__}: {exc}"
    if not (
        is_unowned_candidate(drift_plan.assets, rels["marked"])
        and rels["target"] not in drift_plan.writes
        and rels["target"] not in drift_plan.deletes
        and "target map drift before apply" in drift_error
        and drift_map.read_bytes() == drifted_map_bytes
        and protected_unchanged(before)
    ):
        failures.append(
            "pre-apply target map drift was not rejected before Rule/entry writes: "
            + drift_error
        )

    return CheckResult(
        "switch_direct_portable_rule_candidates",
        not failures,
        "both directions report only a unique true frontmatter field as an "
        "unowned top-level Rule candidate; missing, duplicate, false, "
        "non-boolean, unclosed, body-only, and nested declarations are excluded; "
        "present or absent target Rules and entries remain byte-identical, "
        "including missing/corrupt/drifted map paths"
        if not failures
        else "; ".join(failures),
    )


def check_switch_direct_retired_stall_warning_cleanup() -> CheckResult:
    """Only byte-identical historical stall hooks may be retired."""
    module = _direct_switch_module()
    historical = subprocess.run(
        [
            "git",
            "show",
            "1a7b833^:templates/codex/hooks/stall_warning.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    ).stdout

    failures: list[str] = []
    for target_host, modified in (("codex", False), ("claude", True)):
        fixture = _build_direct_switch_fixture()
        hooks: dict[str, tuple[Path, Path]] = {}
        for host in ("claude", "codex"):
            hook_dir = fixture / f".{host}" / "hooks"
            hook_dir.mkdir()
            retired = hook_dir / "stall_warning.py"
            unrelated = hook_dir / "keep_me.py"
            if host == target_host and not modified:
                retired.write_bytes(historical)
            else:
                retired.write_text(
                    f"locally modified retired {host} hook\n",
                    encoding="utf-8",
                )
            unrelated.write_text(f"unrelated {host} hook\n", encoding="utf-8")
            hooks[host] = (retired, unrelated)

        retired, unrelated = hooks[target_host]
        other_host = "claude" if target_host == "codex" else "codex"
        other_retired, other_unrelated = hooks[other_host]
        target_rel = f".{target_host}/hooks/stall_warning.py"
        other_retired_before = (
            other_retired.read_bytes() if other_retired.exists() else None
        )
        plan = module.build_plan(
            target_host,
            fixture.resolve(),
            REPO_ROOT.resolve(),
        )
        dry_run = _run_direct_switch(fixture, target_host, dry_run=True)
        retired_after_dry_run = retired.exists()
        blocked = _run_direct_switch(fixture, target_host) if not modified else None
        blocked_preserved = retired.exists()
        applied = _run_direct_switch(
            fixture,
            target_host,
            risk_fingerprint=module._risk_fingerprint(plan),
        )
        output = (
            dry_run.stdout
            + dry_run.stderr
            + ((blocked.stdout + blocked.stderr) if blocked is not None else "")
            + applied.stdout
            + applied.stderr
        )
        expected = (
            (target_rel in plan.deletes) is (not modified)
            and dry_run.returncode == 0
            and retired_after_dry_run
            and applied.returncode == 0
            and (
                blocked is None
                or (
                    blocked.returncode == 2
                    and blocked_preserved
                    and "requires the current --confirmed-risk-fingerprint" in output
                )
            )
            and retired.exists() is modified
            and unrelated.read_text(encoding="utf-8")
            == f"unrelated {target_host} hook\n"
            and (
                other_retired.read_bytes() if other_retired.exists() else None
            )
            == other_retired_before
            and other_unrelated.read_text(encoding="utf-8")
            == f"unrelated {other_host} hook\n"
            and (
                f"gap:retired-file-modified:{target_rel}:preserved" in output
                if modified
                else f"retired-managed-file:{target_rel}" in output
            )
        )
        if not expected:
            failures.append(
                f"{target_host} retirement did not follow managed-hash ownership: "
                f"{output.strip()}"
            )

    return CheckResult(
        "switch_direct_retired_stall_warning_cleanup",
        not failures,
        "known historical stall hook is retired; modified hook and unrelated hooks are preserved with an explicit gap"
        if not failures
        else "; ".join(failures),
    )


def check_switch_direct_script_mirrors() -> CheckResult:
    paths = [
        REPO_ROOT / "scripts" / "bridgeforge_switch.py",
        CLAUDE_TEMPLATE / "scripts" / "bridgeforge_switch.py",
        CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py",
        REPO_ROOT / ".codex" / "scripts" / "bridgeforge_switch.py",
        REPO_ROOT / ".claude" / "scripts" / "bridgeforge_switch.py",
    ]
    contents = [path.read_bytes() for path in paths]
    ok = all(content == contents[0] for content in contents[1:])
    return CheckResult(
        "switch_direct_script_mirrors",
        ok,
        "root, both templates, .codex, and .claude switch scripts are byte-identical"
        if ok
        else "switch script mirror drift: "
        + ", ".join(
            f"{path.relative_to(REPO_ROOT)}={_switch_sha(content)}"
            for path, content in zip(paths, contents)
        ),
    )


def check_precommit_merge_preserves_project_extension() -> CheckResult:
    fixture = RUNTIME_ROOT / "precommit-merge"
    _safe_reset_dir(fixture)
    template = CODEX_TEMPLATE / ".githooks" / "pre-commit"
    merger = CODEX_TEMPLATE / "scripts" / "precommit_merge.py"
    target = fixture / ".githooks" / "pre-commit"
    target.parent.mkdir(parents=True)

    managed_begin = b"# >>> BRIDGEFORGE_MANAGED_BEGIN\n"
    managed_end = b"# <<< BRIDGEFORGE_MANAGED_END\n"
    extension_begin = b"# >>> PROJECT_EXTENSION_BEGIN\n"
    extension_end = b"# <<< PROJECT_EXTENSION_END\n"
    template_bytes = template.read_bytes()
    managed_start = template_bytes.index(managed_begin) + len(managed_begin)
    managed_end_start = template_bytes.index(managed_end, managed_start)
    legacy = (
        template_bytes[:managed_start]
        + b"# legacy BridgeForge managed block\nexit 0\n"
        + template_bytes[managed_end_start:]
    )
    extension_start = legacy.index(extension_begin) + len(extension_begin)
    extension_end_start = legacy.index(extension_end, extension_start)
    extension = b"\r\n# downstream version policy\r\npython scripts/bump_version.py\r\n"
    target.write_bytes(legacy[:extension_start] + extension + legacy[extension_end_start:])

    base_command = [
        sys.executable,
        str(merger),
        "--project-root",
        str(fixture),
        "--template-precommit",
        str(template),
    ]
    preview = run(base_command, REPO_ROOT)
    applied = run([*base_command, "--apply", "--confirmed"], REPO_ROOT)
    after = target.read_bytes()
    after_extension_start = after.index(extension_begin) + len(extension_begin)
    after_extension_end = after.index(extension_end, after_extension_start)

    legacy_managed = (
        template_bytes[:template_bytes.index(managed_begin)]
        + template_bytes[managed_start:managed_end_start].replace(
            b"#   \xc2\xb7 exit 2 \xe6\xae\xb5\xe5\xbf\x85\xe9\xa1\xbb\xe5\x9c\xa8\xe5\x8f\x97\xe7\xae\xa1\xe5\x8c\xba\xe5\x9d\x97\xe5\x86\x85\xe7\xab\x8b\xe5\x8d\xb3\xe9\x80\x80\xe5\x87\xba\xef\xbc\x9b\xe9\xa1\xb9\xe7\x9b\xae\xe6\x89\xa9\xe5\xb1\x95\xe4\xbd\x8d\xe4\xba\x8e\xe5\x8f\x97\xe7\xae\xa1\xe5\x8c\xba\xe5\x9d\x97\xe4\xb9\x8b\xe5\x90\x8e\xef\xbc\x8c\xe4\xbf\x9d\xe7\x95\x99\xe5\x85\xb6\xe5\x8e\x9f\xe6\x9c\x89\xe9\x80\x80\xe5\x87\xba\xe7\xa0\x81\xe3\x80\x82\n",
            b"#   \xc2\xb7 exit 2 \xe6\xae\xb5\xe5\xbf\x85\xe9\xa1\xbb\xe7\xbd\xae\xe4\xba\x8e\xe6\x9c\xab\xe8\xa1\x8c exit 0 \xe4\xb9\x8b\xe5\x89\x8d\xef\xbc\x8c\xe5\x90\xa6\xe5\x88\x99\xe8\xa2\xab\xe5\x90\x9e(\xe7\xa1\xac\xe4\xbc\xa42)\xe3\x80\x82\xe9\x95\x9c\xe5\x83\x8f\xe9\x97\xb8\xe7\xbd\xae\xe6\x9c\x80\xe5\x89\x8d\xe3\x80\x82\n",
        )
        + b"exit 0\n"
    )
    legacy_extension = (
        b"\r\n# === Step 2: VERSION bump (project extension) ===\r\n"
        b"set -e\r\n"
        b"python scripts/bump_version.py .git/COMMIT_EDITMSG\r\n"
        b"git add VERSION\r\n"
    )
    target.write_bytes(legacy_managed + legacy_extension)
    legacy_preview = run(base_command, REPO_ROOT)
    legacy_applied = run([*base_command, "--apply", "--confirmed"], REPO_ROOT)
    legacy_after = target.read_bytes()
    legacy_after_extension_start = legacy_after.index(extension_begin) + len(extension_begin)
    legacy_after_extension_end = legacy_after.index(extension_end, legacy_after_extension_start)

    target.write_bytes(
        legacy_managed.replace(
            b"exit 0\n", b"echo project-only-pre-step\nexit 0\n"
        )
        + legacy_extension
    )
    mixed_before = target.read_bytes()
    mixed_blocked = run(base_command, REPO_ROOT)
    mixed_preserved = target.read_bytes() == mixed_before

    target.write_bytes(b"#!/bin/sh\npython scripts/bump_version.py\n")
    unmarked_before = target.read_bytes()
    blocked = run(base_command, REPO_ROOT)

    switch_fixture = _build_direct_switch_fixture()
    switch_hook = switch_fixture / ".githooks" / "pre-commit"
    switch_hook.parent.mkdir()
    switch_hook.write_bytes(b"#!/bin/sh\n# downstream hook must survive switch\n")
    switch_before = switch_hook.read_bytes()
    switch_result = _run_direct_switch(switch_fixture, "codex")

    mirrors = [
        CLAUDE_TEMPLATE / "scripts" / "precommit_merge.py",
        CODEX_TEMPLATE / "scripts" / "precommit_merge.py",
    ]
    marker_paths = [
        REPO_ROOT / ".githooks" / "pre-commit",
        CLAUDE_TEMPLATE / ".githooks" / "pre-commit",
        CODEX_TEMPLATE / ".githooks" / "pre-commit",
    ]
    output = preview.stdout + preview.stderr + applied.stdout + applied.stderr
    ok = (
        preview.returncode == 0
        and applied.returncode == 0
        and after[after_extension_start:after_extension_end] == extension
        and b"legacy BridgeForge managed block" not in after
        and legacy_preview.returncode == 0
        and legacy_applied.returncode == 0
        and legacy_after[legacy_after_extension_start:legacy_after_extension_end] == legacy_extension
        and b"legacy_version_extension_migrated=true" in (legacy_preview.stdout + legacy_preview.stderr).encode()
        and mixed_blocked.returncode == 2
        and mixed_preserved
        and blocked.returncode == 2
        and target.read_bytes() == unmarked_before
        and switch_result.returncode == 0
        and switch_hook.read_bytes() == switch_before
        and mirrors[0].read_bytes() == mirrors[1].read_bytes()
        and all(
            managed_begin in path.read_bytes()
            and managed_end in path.read_bytes()
            and extension_begin in path.read_bytes()
            and extension_end in path.read_bytes()
            and b"exit 0\n# <<< BRIDGEFORGE_MANAGED_END" not in path.read_bytes()
            for path in marker_paths
        )
    )
    return CheckResult(
        "precommit_merge_preserves_project_extension",
        ok,
        "managed block updates, marked and exact historical version extensions survive byte-for-byte, altered legacy hooks block, and switch leaves root hook unchanged"
        if ok
        else f"pre-commit merge contract failed: {output.strip()} / switch={switch_result.stdout.strip()} {switch_result.stderr.strip()}",
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


def _manifest_source_hash(path: Path) -> str:
    """Match the LF Git blob used by the shared-skill manifest."""
    payload = path.read_bytes()
    if b"\0" not in payload:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


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
        if _manifest_source_hash(source) != expected:
            raise RuntimeError(f"manifest hash is stale for fixture source: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _run_layout_migration(
    fixture: Path,
    mode: str,
    plan_fingerprint: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "bridgeforge_migrate_layout.py"),
            "--project-root",
            str(fixture),
            mode,
        ]
    if mode == "--apply":
        command.extend(["--confirmed", "--plan-fingerprint", plan_fingerprint or ""])
    return run(command, fixture)


def _layout_fingerprint(result: subprocess.CompletedProcess[str]) -> str:
    return str(json.loads(result.stdout)["plan_fingerprint"])


def check_layout_migration_dry_run_apply() -> CheckResult:
    fixture = _build_layout_migration_fixture()
    dry_run = _run_layout_migration(fixture, "--dry-run")
    dry_text = dry_run.stdout + dry_run.stderr
    dry_preserved = (
        (fixture / ".agents" / "skills" / "explain" / "SKILL.md").is_file()
        and (fixture / ".agents" / "skills" / "project-only" / "SKILL.md").is_file()
        and not (fixture / ".codex" / "skills").exists()
    )
    applied = _run_layout_migration(fixture, "--apply", _layout_fingerprint(dry_run))
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
    claude_dry = _run_layout_migration(claude_fixture, "--dry-run")
    claude_applied = _run_layout_migration(
        claude_fixture,
        "--apply",
        _layout_fingerprint(claude_dry),
    )
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
    drift_fixture = _build_layout_migration_fixture()
    drift_dry = _run_layout_migration(drift_fixture, "--dry-run")
    drift_source = drift_fixture / ".agents" / "skills" / "project-only" / "SKILL.md"
    drift_source.write_text("drift after plan\n", encoding="utf-8")
    drift_apply = _run_layout_migration(
        drift_fixture,
        "--apply",
        _layout_fingerprint(drift_dry),
    )
    drift_ok = (
        drift_apply.returncode == 2
        and "plan drifted" in (drift_apply.stdout + drift_apply.stderr)
        and drift_source.read_text(encoding="utf-8") == "drift after plan\n"
        and (drift_fixture / ".agents" / "skills" / "explain" / "SKILL.md").is_file()
        and not (drift_fixture / ".codex" / "skills").exists()
    )
    ok = codex_ok and claude_ok and drift_ok
    return CheckResult(
        "layout_migration_dry_run_apply",
        ok,
        "dry-run classifies without writes; confirmed fingerprint apply migrates known content, while input drift is zero-write blocked"
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

    dry_run = _run_layout_migration(fixture, "--dry-run")
    applied = _run_layout_migration(
        fixture,
        "--apply",
        _layout_fingerprint(dry_run),
    )
    text = applied.stdout + applied.stderr
    ok = (
        applied.returncode == 0
        and "无法分类内容" in text
        and "目标已存在" in text
        and text.count("与 manifest 文件清单或哈希不一致") == 2
        and unknown.read_text(encoding="utf-8") == "do not delete\n"
        and not (fixture / ".agents" / "skills" / "explain").exists()
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
        "unknown content and destination conflicts remain as gaps while independent known copies retire; another project's .agents remains untouched"
        if ok
        else f"expected local gaps with scoped safe writes, got exit {applied.returncode}: {text.strip()}",
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
        module.apply_plan(
            plan,
            confirmed=True,
            plan_fingerprint=plan.plan_fingerprint,
        )
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

    if norm == "SKILL.md":
        return [skill_dir / norm]

    if norm.startswith(".claude/"):
        rest = norm[len(".claude/") :]
        return [REPO_ROOT / "templates" / "claude" / rest]
    if norm.startswith(".codex/"):
        rest = norm[len(".codex/") :]
        return [REPO_ROOT / "templates" / "codex" / rest]
    if norm.startswith("references/"):
        return [skill_dir / norm]
    if norm.startswith("scripts/"):
        return [skill_dir / norm, REPO_ROOT / norm]
    if norm.startswith(("./", "../")):
        return [(skill_dir / norm).resolve()]
    if norm.startswith(("doc/", "templates/", "skills/")) or norm in {
        "README.md",
        "CHANGELOG.md",
        "VERSION",
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
        "user_invocable: true\n"
        "---\n\n"
        "# Bad Skill\n",
        encoding="utf-8",
    )
    bad = run([sys.executable, ".codex/hooks/skill_metadata_check.py", "--pre-commit"], SKILL_METADATA_FIXTURE)

    bad_skill.write_text(
        "---\n"
        "name: bad-skill\n"
        "description: fixture OpenAI standard skill\n"
        "---\n\n"
        "# Good Skill\n",
        encoding="utf-8",
    )
    good = run([sys.executable, ".codex/hooks/skill_metadata_check.py", "--pre-commit"], SKILL_METADATA_FIXTURE)

    ok = (
        bad.returncode == 2
        and "legacy invocation metadata requires argument" in (bad.stdout + bad.stderr)
        and good.returncode == 0
    )
    return CheckResult(
        "skill_metadata_health",
        ok,
        "skill metadata hook accepts OpenAI standard metadata and blocks incomplete legacy metadata"
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
    root_skill = (REPO_ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
    maintenance = (REPO_ROOT / "skills" / "bridgeforge" / "references" / "user-skill-maintenance.md").read_text(
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


def check_platform_default() -> CheckResult:
    roots = (REPO_ROOT / ".codex", CODEX_TEMPLATE)
    paths = [
        *(root / "config.toml" for root in roots),
        *(path for root in roots for path in (root / "agents").glob("*.toml")),
    ]
    pinned = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.match(r"\\s*(model|model_reasoning_effort|plan_mode_reasoning_effort)\\s*=", line):
                pinned.append(f"{path.relative_to(REPO_ROOT)}:{number}")
    retired = [
        path
        for root in roots
        for path in (
            root / "subscription-tier.toml",
            root / "scripts" / "subscription_routing.py",
        )
        if path.exists()
    ]
    ok = not pinned and not retired
    return CheckResult(
        "platform_default",
        ok,
        "BridgeForge leaves model and reasoning-effort selection to Codex"
        if ok
        else f"pinned={pinned}; retired routing artifacts={[str(path) for path in retired]}",
    )


def _legacy_check_model_policy() -> CheckResult:
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


def _legacy_check_subscription_routing() -> CheckResult:
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

    hooks = json.loads((fixture / ".codex" / "hooks.json").read_text(encoding="utf-8-sig"))
    registered = any(
        isinstance(hook, dict) and "hook_dispatcher.py" in hook.get("command", "")
        for block in hooks.get("hooks", {}).get("PreToolUse", [])
        for hook in block.get("hooks", [])
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
        "user config reads pass, writes are blocked, hooks.json dispatcher is registered, and the sentinel is unchanged"
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
    shutil.copy2(
        REPO_ROOT / ".codex" / "scripts" / "factory_version_check.py",
        fixture / ".codex" / "scripts" / "factory_version_check.py",
    )

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

    missing_remote = CODEX_GIT_SYNC_REMOTE.with_name("missing-git-sync-remote.git")
    unset_upstream = run(["git", "branch", "--unset-upstream"], fixture)
    remote_unreachable = run(
        ["git", "remote", "set-url", "origin", str(missing_remote)],
        fixture,
    )
    if unset_upstream.returncode != 0 or remote_unreachable.returncode != 0:
        return CheckResult(
            "codex_git_sync_runner",
            False,
            "prepare missing-upstream preflight failed",
        )
    missing_upstream = run(
        [sys.executable, ".codex/scripts/codex_git_sync.py"],
        fixture,
        timeout=60,
    )
    remote_restored = run(
        ["git", "remote", "set-url", "origin", str(CODEX_GIT_SYNC_REMOTE)],
        fixture,
    )
    upstream_restored = run(
        ["git", "branch", "--set-upstream-to=origin/main", "main"],
        fixture,
    )
    if remote_restored.returncode != 0 or upstream_restored.returncode != 0:
        return CheckResult(
            "codex_git_sync_runner",
            False,
            "restore upstream after preflight failed",
        )

    push_disabled = run(["git", "config", "push.default", "nothing"], fixture)
    remote_unreachable = run(
        ["git", "remote", "set-url", "origin", str(missing_remote)],
        fixture,
    )
    if push_disabled.returncode != 0 or remote_unreachable.returncode != 0:
        return CheckResult(
            "codex_git_sync_runner",
            False,
            "prepare missing-push-target preflight failed",
        )
    missing_push_target = run(
        [sys.executable, ".codex/scripts/codex_git_sync.py"],
        fixture,
        timeout=60,
    )
    push_default_restored = run(["git", "config", "--unset", "push.default"], fixture)
    remote_restored = run(
        ["git", "remote", "set-url", "origin", str(CODEX_GIT_SYNC_REMOTE)],
        fixture,
    )
    if push_default_restored.returncode != 0 or remote_restored.returncode != 0:
        return CheckResult(
            "codex_git_sync_runner",
            False,
            "restore push target after preflight failed",
        )

    product_change = fixture / "templates" / "codex" / "AGENTS.md"
    product_change.parent.mkdir(parents=True)
    product_change.write_text("unversioned product change\n", encoding="utf-8")
    remote_unreachable = run(
        ["git", "remote", "set-url", "origin", str(missing_remote)],
        fixture,
    )
    if remote_unreachable.returncode != 0:
        return CheckResult(
            "codex_git_sync_runner",
            False,
            f"set unreachable remote failed: {remote_unreachable.stderr.strip()}",
        )
    message_preflight = run(
        [sys.executable, ".codex/scripts/codex_git_sync.py"],
        fixture,
        timeout=60,
    )
    preflight = run(
        [
            sys.executable,
            ".codex/scripts/codex_git_sync.py",
            "--message",
            "chore: blocked",
        ],
        fixture,
        timeout=60,
    )
    product_change.unlink()
    remote_restored = run(
        ["git", "remote", "set-url", "origin", str(CODEX_GIT_SYNC_REMOTE)],
        fixture,
    )
    if remote_restored.returncode != 0:
        return CheckResult(
            "codex_git_sync_runner",
            False,
            f"restore remote failed: {remote_restored.stderr.strip()}",
        )

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
    head = run(["git", "rev-parse", "HEAD"], fixture)
    missing_upstream_output = missing_upstream.stdout + missing_upstream.stderr
    missing_push_target_output = missing_push_target.stdout + missing_push_target.stderr
    message_preflight_output = message_preflight.stdout + message_preflight.stderr
    preflight_output = preflight.stdout + preflight.stderr
    runner_text = (CODEX_TEMPLATE / "scripts" / "codex_git_sync.py").read_text(
        encoding="utf-8"
    )
    dogfood_runner_text = (
        REPO_ROOT / ".codex" / "scripts" / "codex_git_sync.py"
    ).read_text(encoding="utf-8")

    ok = (
        missing_upstream.returncode == 2
        and "no upstream branch" in missing_upstream_output
        and str(missing_remote) not in missing_upstream_output
        and missing_push_target.returncode == 2
        and "no push target" in missing_push_target_output
        and str(missing_remote) not in missing_push_target_output
        and message_preflight.returncode == 2
        and "commit message is required" in message_preflight_output
        and str(missing_remote) not in message_preflight_output
        and preflight.returncode != 0
        and str(missing_remote) in preflight_output
        and sync.returncode == 0
        and status.returncode == 0
        and status.stdout.strip() == ""
        and ahead.returncode == 0
        and ahead.stdout.strip() == "0\t0"
        and "chore: fixture sync" in remote_log.stdout
        and head.returncode == 0
        and f"commit={head.stdout.strip()}" in sync.stdout
        and "push_target=origin/main" in sync.stdout
        and "push_performed=true" in sync.stdout
        and "working_tree=clean" in sync.stdout
        and "ahead=0 behind=0" in sync.stdout
        and "version 0.1.0 -> 0.1.1 (project)" in sync.stdout
        and (fixture / "VERSION").read_text(encoding="utf-8").strip() == "0.1.1"
        and "## [0.1.1]" in (fixture / "CHANGELOG.md").read_text(encoding="utf-8")
        and "memory_rebuild_index" not in runner_text
        and runner_text == dogfood_runner_text
    )
    return CheckResult(
        "codex_git_sync_runner",
        ok,
        "runner fetched before version writes, bumped the project, emitted complete receipts, and pushed"
        if ok
        else (
            f"missing_upstream={missing_upstream.returncode}/"
            f"{missing_upstream_output.strip()} "
            f"missing_push_target={missing_push_target.returncode}/"
            f"{missing_push_target_output.strip()} "
            f"message_preflight={message_preflight.returncode}/"
            f"{message_preflight_output.strip()} "
            f"version_preflight={preflight.returncode}/{preflight_output.strip()} "
            f"sync={sync.returncode} status={status.stdout!r} ahead={ahead.stdout!r} "
            f"remote_log={remote_log.stdout!r} output={(sync.stdout + sync.stderr).strip()}"
        ),
    )


CHECKS = {
    "codex-git-sync": check_codex_git_sync_runner,
    "encoding-garble": check_encoding_garble_scan,
    "encoding-no-bom": check_encoding_no_bom,
    "platform-default": check_platform_default,
    "layout-migration": check_layout_migration_dry_run_apply,
    "layout-migration-blockers": check_layout_migration_blockers_are_local,
    "layout-migration-rollback": check_layout_migration_transaction_rollback,
    "non-ascii-shell-guard": check_non_ascii_shell_guard,
    "non-ascii-shell-settings": check_non_ascii_shell_guard_settings,
    "rule-index": check_rule_index_missing,
    "rule-index-scope-audit": check_rule_index_scope_and_audit,
    "rule-size": check_rule_size_over_limit,
    "mirror-missing": check_mirror_missing_hook,
    "mirror-noop": check_mirror_no_templates_noop,
    "precommit-merge": check_precommit_merge_preserves_project_extension,
    "precommit-shebang": check_precommit_shebang_bytes,
    "settings-matchers": check_settings_multiedit_matchers,
    "root-precommit": check_root_precommit_dual_agent_gates,
    "python-baseline": check_python_311_hook_baseline,
    "skill-metadata": check_skill_metadata,
    "skill-refs": check_skill_references,
    "user-skill-distribution": check_user_skill_distribution,
    "user-config-write-guard": check_user_config_write_guard,
    "switch-bidirectional": check_switch_direct_bidirectional_maps,
    "switch-cardinality": check_switch_direct_cardinality,
    "switch-host-mismatch": check_switch_direct_host_mismatch,
    "switch-json-pointer": check_switch_direct_json_pointer_permissions,
    "switch-legacy-root": check_switch_direct_legacy_root,
    "switch-map-ownership": check_switch_direct_map_ownership,
    "switch-projection": check_switch_direct_source_map_projection,
    "switch-retired-stall-warning": check_switch_direct_retired_stall_warning_cleanup,
    "switch-rollback": check_switch_direct_rollback,
    "switch-script-mirrors": check_switch_direct_script_mirrors,
    "switch-target-link-toctou": check_switch_direct_target_link_toctou,
    "switch-portable-rule-candidates": check_switch_direct_portable_rule_candidates,
    "switch-untranslated": check_switch_direct_untranslated,
    "switch-whole-file": check_switch_direct_whole_file_lifecycle,
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
