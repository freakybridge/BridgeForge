#!/usr/bin/env python3
"""BridgeForge harness regression checks.

The checks generate a tiny Codex-shaped fixture under `.runtime/harness/` and
exercise the parts that are easy to miss in the source repo:

* D6 rule pre-commit checks in a real `.codex/rules/` layout.
* D8 dogfood mirror checks in a factory-shaped fixture.
* settings.json matcher coverage for Edit|Write|MultiEdit.
* Root pre-commit coverage for both Claude and Codex dogfood gates.
* high-confidence `skills/**/SKILL.md` local reference health.

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
CODEX_FIXTURE = RUNTIME_ROOT / "downstream-codex"


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
    shutil.copytree(src, dst)


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
    }
    missing: list[str] = []
    for block in settings.get("hooks", {}).get("PostToolUse", []):
        tokens = _matcher_tokens(block.get("matcher", ""))
        commands = {
            hook.get("command", "")
            for hook in block.get("hooks", [])
            if isinstance(hook, dict)
        }
        if not required_commands.intersection(commands):
            continue
        if not {"Edit", "Write", "MultiEdit"}.issubset(tokens):
            missing.extend(sorted(required_commands.intersection(commands)))
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
        'for CONFIG_DIR in .claude .codex; do',
        '$CONFIG_DIR/scripts/memory_rebuild_index.py',
    ]
    missing = [needle for needle in required if needle not in precommit]
    bad_quoted_args = [
        '.claude/hooks/rule_size_check.py --pre-commit',
        '.claude/hooks/rule_index_check.py --pre-commit',
        '.codex/hooks/rule_size_check.py --pre-commit',
        '.codex/hooks/rule_index_check.py --pre-commit',
    ]
    broken = [needle for needle in bad_quoted_args if needle in precommit]
    ok = not missing and not broken
    detail = "root pre-commit covers Claude and Codex gates"
    if missing:
        detail = "missing root pre-commit entries: " + ", ".join(missing)
    if broken:
        detail += "; quoted script+arg entries still present: " + ", ".join(broken)
    return CheckResult("root_precommit_dual_agent_gates", ok, detail)


def _build_switch_fixture() -> Path:
    fixture = build_codex_fixture()
    scripts_dir = fixture / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    shutil.copy2(CODEX_TEMPLATE / "scripts" / "bridgeforge_switch.py", scripts_dir / "bridgeforge_switch.py")

    add = run(["git", "add", "-A"], fixture)
    if add.returncode != 0:
        raise RuntimeError(f"git add failed: {add.stderr.strip()}")
    commit = run(
        [
            "git",
            "-c",
            "user.name=BridgeForge Harness",
            "-c",
            "user.email=harness@example.invalid",
            "commit",
            "-m",
            "baseline",
        ],
        fixture,
    )
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip()}")
    return fixture


def _dirty_agents_md(fixture: Path) -> str:
    marker = "\nLOCAL DIRTY SWITCH MARKER\n"
    path = fixture / "AGENTS.md"
    path.write_text(path.read_text(encoding="utf-8") + marker, encoding="utf-8")
    return marker


def check_switch_blocked_guidance() -> CheckResult:
    fixture = _build_switch_fixture()
    marker = _dirty_agents_md(fixture)
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
    unchanged = marker in (fixture / "AGENTS.md").read_text(encoding="utf-8")
    ok = (
        r.returncode == 2
        and "strong protection blocked this switch" in text
        and "--interactive" in text
        and "--apply-blocked PATH" in text
        and "No files were changed" in text
        and unchanged
    )
    return CheckResult(
        "switch_blocked_guidance",
        ok,
        "blocked switch exits 2 with per-file guidance and leaves dirty file unchanged"
        if ok
        else f"expected exit 2 + guidance + unchanged file, got exit {r.returncode}",
    )


def check_switch_keep_blocked_decision() -> CheckResult:
    fixture = _build_switch_fixture()
    marker = _dirty_agents_md(fixture)
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--keep-blocked",
            "AGENTS.md",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    kept = marker in (fixture / "AGENTS.md").read_text(encoding="utf-8")
    ok = r.returncode == 0 and "Validation passed" in text and kept
    return CheckResult(
        "switch_keep_blocked_decision",
        ok,
        "explicit keep-blocked continues switch and preserves reviewed dirty file"
        if ok
        else f"expected exit 0 + preserved marker, got exit {r.returncode}: {text.strip()}",
    )


def check_switch_apply_blocked_decision() -> CheckResult:
    fixture = _build_switch_fixture()
    marker = _dirty_agents_md(fixture)
    r = run(
        [
            sys.executable,
            "scripts/bridgeforge_switch.py",
            "codex",
            "--template-root",
            str(REPO_ROOT),
            "--apply-blocked",
            "AGENTS.md",
        ],
        fixture,
    )
    text = r.stdout + r.stderr
    overwritten = marker not in (fixture / "AGENTS.md").read_text(encoding="utf-8")
    ok = r.returncode == 0 and "Validation passed" in text and overwritten
    return CheckResult(
        "switch_apply_blocked_decision",
        ok,
        "explicit apply-blocked continues switch and overwrites reviewed dirty file"
        if ok
        else f"expected exit 0 + overwritten marker, got exit {r.returncode}: {text.strip()}",
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
    if norm.startswith(("docs/", "templates/", "skills/", "scripts/")) or norm in {
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
        REPO_ROOT / "docs",
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


CHECKS = {
    "rule-index": check_rule_index_missing,
    "rule-size": check_rule_size_over_limit,
    "mirror-missing": check_mirror_missing_hook,
    "mirror-noop": check_mirror_no_templates_noop,
    "settings-matchers": check_settings_multiedit_matchers,
    "root-precommit": check_root_precommit_dual_agent_gates,
    "skill-refs": check_skill_references,
    "switch-apply": check_switch_apply_blocked_decision,
    "switch-blocked": check_switch_blocked_guidance,
    "switch-keep": check_switch_keep_blocked_decision,
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
