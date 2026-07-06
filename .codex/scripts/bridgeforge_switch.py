#!/usr/bin/env python3
"""Switch a project between BridgeForge Claude and Codex skeletons.

This script is intentionally conservative:
- it only supports the explicit agents "claude" and "codex";
- it checks git working tree status for files it will delete/overwrite;
- it supports --dry-run with the same protection checks as a real run;
- it does not stage, commit, push, or attempt rollback.
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

AGENTS = ("claude", "codex")


@dataclass(frozen=True)
class AgentSpec:
    name: str
    entry: str
    config_dir: str
    other_entry: str
    other_config_dir: str


SPECS = {
    "claude": AgentSpec("claude", "CLAUDE.md", ".claude", "AGENTS.md", ".codex"),
    "codex": AgentSpec("codex", "AGENTS.md", ".codex", "CLAUDE.md", ".claude"),
}


@dataclass(frozen=True)
class CopyItem:
    src: Path
    dst: Path


@dataclass
class Plan:
    agent: str
    template_root: Path
    project_root: Path
    delete_paths: list[Path]
    copy_items: list[CopyItem]
    blocked_paths: list[Path]
    unknown_old_paths: list[Path]
    git_available: bool
    git_error: str | None
    python_command: str | None


def _posix(path: Path) -> str:
    return path.as_posix().rstrip("/")


def _rel(path: Path, root: Path) -> str:
    try:
        return _posix(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return _posix(path)


def _print(title: str, items: list[str]) -> None:
    if not items:
        print(f"{title}: none")
        return
    print(f"{title}:")
    for item in items:
        print(f"  - {item}")


def _candidate_roots(project_root: Path, script_path: Path, explicit: str | None) -> list[Path]:
    raw: list[Path] = []
    if explicit:
        raw.append(Path(explicit))
    env = os.environ.get("BRIDGEFORGE_HOME")
    if env:
        raw.append(Path(env))
    raw.append(project_root)
    raw.extend(project_root.parents)
    raw.append(script_path.parent)
    raw.extend(script_path.parents)

    home = Path.home()
    raw.extend([
        home / ".claude" / "skills" / "bridgeforge",
        home / ".codex" / "skills" / "bridgeforge",
        home / ".agents" / "skills" / "bridgeforge",
    ])

    seen: set[Path] = set()
    out: list[Path] = []
    for p in raw:
        try:
            resolved = p.expanduser().resolve()
        except Exception:
            resolved = p.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def find_template_root(project_root: Path, script_path: Path, explicit: str | None) -> Path:
    for root in _candidate_roots(project_root, script_path, explicit):
        if (root / "templates" / "claude").is_dir() and (root / "templates" / "codex").is_dir():
            return root
    raise SystemExit(
        "ERROR: cannot find BridgeForge template root. Set BRIDGEFORGE_HOME or pass --template-root."
    )


def git_dirty_paths(project_root: Path) -> tuple[set[str], bool, str | None]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=project_root,
            capture_output=True,
            text=False,
            timeout=20,
        )
    except Exception as exc:
        return set(), False, str(exc)
    if result.returncode != 0:
        msg = result.stderr.decode("utf-8", errors="replace").strip()
        return set(), False, msg or "git status failed"

    dirty: set[str] = set()
    chunks = result.stdout.split(b"\0")
    i = 0
    while i < len(chunks):
        chunk = chunks[i]
        i += 1
        if not chunk:
            continue
        text = chunk.decode("utf-8", errors="replace")
        status = text[:2]
        path = text[3:]
        if status.startswith("R") or status.startswith("C"):
            if i < len(chunks) and chunks[i]:
                path = chunks[i].decode("utf-8", errors="replace")
                i += 1
        if path:
            dirty.add(path.replace("\\", "/"))
    return dirty, True, None


def choose_python_command(project_root: Path) -> str | None:
    windows_venv = project_root / ".venv" / "Scripts" / "python.exe"
    if windows_venv.is_file():
        return ".venv/Scripts/python.exe"
    unix_venv = project_root / ".venv" / "bin" / "python"
    if unix_venv.is_file():
        return ".venv/bin/python"
    try:
        result = subprocess.run(
            ["python", "-c", ""],
            cwd=project_root,
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return "python"
    except Exception:
        return None
    return None


def is_dirty(path: Path, project_root: Path, dirty: set[str]) -> bool:
    rel = _rel(path, project_root)
    if not rel or rel == ".":
        return bool(dirty)
    prefix = rel.rstrip("/") + "/"
    return rel in dirty or any(p.startswith(prefix) for p in dirty)


def _add_tree(copy_items: list[CopyItem], src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.exists():
        return
    for src in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        if "__pycache__" in src.parts or src.suffix == ".pyc":
            continue
        rel = src.relative_to(src_dir)
        copy_items.append(CopyItem(src, dst_dir / rel))


def build_copy_items(template_dir: Path, project_root: Path, spec: AgentSpec) -> list[CopyItem]:
    items: list[CopyItem] = []
    entry = template_dir / spec.entry
    if entry.is_file():
        items.append(CopyItem(entry, project_root / spec.entry))

    for name in ("rules", "hooks", "scripts", "memory"):
        _add_tree(items, template_dir / name, project_root / spec.config_dir / name)

    settings = template_dir / "settings.json"
    if settings.is_file():
        items.append(CopyItem(settings, project_root / spec.config_dir / "settings.json"))

    # Keep a stable command target for slash commands.
    switch_script = template_dir / "scripts" / "bridgeforge_switch.py"
    if switch_script.is_file():
        items.append(CopyItem(switch_script, project_root / "scripts" / "bridgeforge_switch.py"))

    _add_tree(items, template_dir / ".githooks", project_root / ".githooks")
    return items


def old_managed_paths(template_root: Path, project_root: Path, agent: str) -> set[Path]:
    spec = SPECS[agent]
    template_dir = template_root / "templates" / agent
    paths = {project_root / spec.entry}
    for item in build_copy_items(template_dir, project_root, spec):
        if item.dst.parts and spec.config_dir in item.dst.parts:
            paths.add(item.dst)
    return paths


def unknown_files_under(root: Path, managed: set[Path]) -> list[Path]:
    if not root.is_dir():
        return []
    managed_resolved = {p.resolve() for p in managed}
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.resolve() not in managed_resolved:
            out.append(p)
    return sorted(out)


def build_plan(agent: str, project_root: Path, template_root: Path) -> Plan:
    spec = SPECS[agent]
    template_dir = template_root / "templates" / agent
    if not template_dir.is_dir():
        raise SystemExit(f"ERROR: missing template directory: {template_dir}")

    old_agent = "codex" if agent == "claude" else "claude"
    delete_paths = sorted(p for p in old_managed_paths(template_root, project_root, old_agent) if p.exists())
    unknown_old_paths = unknown_files_under(project_root / spec.other_config_dir, set(delete_paths))
    copy_items = build_copy_items(template_dir, project_root, spec)

    dirty, git_available, git_error = git_dirty_paths(project_root)
    protected = [p for p in delete_paths if p.exists()]
    protected.extend(item.dst for item in copy_items if item.dst.exists())

    blocked: list[Path] = []
    if git_available:
        blocked = sorted({p for p in protected if is_dirty(p, project_root, dirty)})
    else:
        # Without git, strong protection cannot distinguish safe overwrites.
        blocked = sorted({p for p in protected if p.exists()})
    blocked = sorted(set(blocked).union(unknown_old_paths))

    python_command = choose_python_command(project_root)
    return Plan(agent, template_root, project_root, delete_paths, copy_items, blocked, unknown_old_paths, git_available, git_error, python_command)


def describe_plan(plan: Plan) -> None:
    new_files: list[str] = []
    overwrite_files: list[str] = []
    for item in plan.copy_items:
        rel = _rel(item.dst, plan.project_root)
        if item.dst.exists():
            overwrite_files.append(rel)
        else:
            new_files.append(rel)

    delete_existing = [_rel(p, plan.project_root) for p in plan.delete_paths if p.exists()]
    blocked = [_rel(p, plan.project_root) for p in plan.blocked_paths]
    unknown = [_rel(p, plan.project_root) for p in plan.unknown_old_paths]

    print(f"BridgeForge switch target: {plan.agent}")
    print(f"Project root: {plan.project_root}")
    print(f"Template root: {plan.template_root}")
    if not plan.git_available:
        print(f"Git protection: unavailable ({plan.git_error}); existing target files are treated as blocked.")
    else:
        print("Git protection: enabled")
    print(f"Python hook command: {plan.python_command or 'unavailable'}")
    _print("Will delete", delete_existing)
    _print("Will overwrite", overwrite_files)
    _print("Will create", new_files)
    _print("Unknown old-agent files", unknown)
    _print("Blocked by strong protection", blocked)


def remove_empty_dirs(path: Path, stop_at: Path) -> None:
    current = path
    stop = stop_at.resolve()
    while current.exists() and current.is_dir() and current.resolve() != stop:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def adapt_settings(path: Path, python_command: str | None) -> None:
    if not path.is_file() or not python_command:
        return
    original = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(original)
    except Exception:
        tokens_pattern = r"(?:\.venv/Scripts/python\.exe|\.venv/bin/python|python3|python)"
        text = re.sub(
            rf'("command"\s*:\s*")({tokens_pattern})(?=\s)',
            rf"\1{python_command}",
            original,
        )
        path.write_text(text, encoding="utf-8")
        return
    tokens = (".venv/Scripts/python.exe", ".venv/bin/python", "python3", "python")

    def adapt(value):
        if isinstance(value, str):
            for token in tokens:
                if value == token or value.startswith(token + " "):
                    return python_command + value[len(token):]
            return value
        if isinstance(value, list):
            return [adapt(v) for v in value]
        if isinstance(value, dict):
            return {k: adapt(v) for k, v in value.items()}
        return value

    path.write_text(json.dumps(adapt(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_plan(plan: Plan) -> None:
    if plan.blocked_paths:
        describe_plan(plan)
        raise SystemExit("ERROR: strong protection blocked this switch. Commit, stash, or clean the listed files first.")

    for path in plan.delete_paths:
        if not path.exists():
            continue
        if path.is_dir():
            remove_empty_dirs(path, plan.project_root)
        else:
            path.unlink()
            remove_empty_dirs(path.parent, plan.project_root)

    for item in plan.copy_items:
        item.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.src, item.dst)
        if item.dst.name == "settings.json" and item.dst.parent.name in (".claude", ".codex"):
            adapt_settings(item.dst, plan.python_command)


def validate(plan: Plan) -> list[str]:
    spec = SPECS[plan.agent]
    problems: list[str] = []
    checks = [
        (plan.project_root / spec.entry, "missing target entry file"),
        (plan.project_root / spec.config_dir, "missing target config directory"),
        (plan.project_root / spec.config_dir / "settings.json", "missing target settings.json"),
        (plan.project_root / spec.config_dir / "scripts" / "bridgeforge_switch.py", "missing config copy of switch script"),
        (plan.project_root / "scripts" / "bridgeforge_switch.py", "missing root switch script"),
    ]
    for path, message in checks:
        if not path.exists():
            problems.append(f"{message}: {_rel(path, plan.project_root)}")
    for path, message in [
        (plan.project_root / spec.other_entry, "other agent entry still exists"),
    ]:
        if path.exists():
            problems.append(f"{message}: {_rel(path, plan.project_root)}")
    return problems


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Switch BridgeForge project skeleton between claude and codex.")
    parser.add_argument("agent", choices=AGENTS, help="target agent skeleton")
    parser.add_argument("--dry-run", action="store_true", help="show plan and protection results without changing files")
    parser.add_argument("--project-root", default=".", help="project root to switch (default: current directory)")
    parser.add_argument("--template-root", help="BridgeForge repository root containing templates/claude and templates/codex")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    script_path = Path(__file__).resolve()
    template_root = find_template_root(project_root, script_path, args.template_root)
    if project_root == template_root:
        raise SystemExit("ERROR: refusing to switch the BridgeForge source repository itself.")
    plan = build_plan(args.agent, project_root, template_root)

    if args.dry_run:
        describe_plan(plan)
        return 2 if plan.blocked_paths else 0

    apply_plan(plan)
    problems = validate(plan)
    if problems:
        print("Switch completed, but validation found problems:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Switch completed: {args.agent}")
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
