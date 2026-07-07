#!/usr/bin/env python3
"""Switch a project between BridgeForge Claude and Codex skeletons.

Switch semantics are intentionally narrow:
- archive the currently active opposite agent skeleton, then remove its live paths;
- restore the target agent from this project's local archive when available;
- otherwise install the target agent skeleton from BridgeForge templates;
- merge memory into the target agent, with non-identical conflicts requiring review;
- never auto-migrate hooks, skills, rules, or entry files from the old agent.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


AGENTS = ("claude", "codex")
ARCHIVE_ROOT = Path(".bridgeforge") / "archive"
GENERATED_MEMORY_FILES = {"MEMORY.md", "MEMORY_COLD.md"}


@dataclass(frozen=True)
class AgentSpec:
    name: str
    entry: str
    config_dir: str
    project_skill_dir: str | None = None


SPECS = {
    "claude": AgentSpec("claude", "CLAUDE.md", ".claude"),
    "codex": AgentSpec("codex", "AGENTS.md", ".codex", ".agents/skills"),
}


@dataclass(frozen=True)
class CopyItem:
    src: Path
    dst: Path


@dataclass(frozen=True)
class MemoryConflict:
    rel: str
    old_path: Path
    target_path: Path
    reason: str


@dataclass
class MemoryPlan:
    old_dir: Path | None
    target_source_dir: Path | None
    target_live_dir: Path
    auto_copy: list[tuple[Path, str]] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    conflicts: list[MemoryConflict] = field(default_factory=list)


@dataclass
class SettingsPlan:
    old_settings: Path | None
    target_source_settings: Path | None
    target_live_settings: Path
    candidates: list[str] = field(default_factory=list)
    archived_only: list[str] = field(default_factory=list)


@dataclass
class Plan:
    agent: str
    old_agent: str
    project_root: Path
    template_root: Path
    target_source_kind: str
    target_source_root: Path
    archive_paths: list[Path]
    target_copy_items: list[CopyItem]
    target_conflicts: list[Path]
    archive_only_surfaces: list[str]
    memory: MemoryPlan
    settings: SettingsPlan
    already_target: bool = False
    python_command: str | None = None


@dataclass(frozen=True)
class Decisions:
    skip_settings_migration: bool
    migrate_settings: set[str]
    memory_conflicts: dict[str, str]


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


def _agent_paths(spec: AgentSpec, project_root: Path) -> list[Path]:
    paths = [project_root / spec.entry, project_root / spec.config_dir]
    if spec.project_skill_dir:
        paths.append(project_root / spec.project_skill_dir)
    return paths


def _existing_agent_paths(spec: AgentSpec, project_root: Path) -> list[Path]:
    return [path for path in _agent_paths(spec, project_root) if path.exists()]


def _is_complete_agent(spec: AgentSpec, project_root: Path) -> bool:
    return (project_root / spec.entry).is_file() and (project_root / spec.config_dir).is_dir()


def _archive_agent_root(project_root: Path, agent: str) -> Path:
    return project_root / ARCHIVE_ROOT / agent


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


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
        home / ".agents" / "bridgeforge-home",
    ])

    seen: set[Path] = set()
    out: list[Path] = []
    for path in raw:
        try:
            resolved = path.expanduser().resolve()
        except Exception:
            resolved = path.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def find_template_root(project_root: Path, script_path: Path, explicit: str | None) -> Path:
    for root in _candidate_roots(project_root, script_path, explicit):
        if (root / "templates" / "claude").is_dir() and (root / "templates" / "codex").is_dir():
            return root
    raise SystemExit("ERROR: cannot find BridgeForge template root. Set BRIDGEFORGE_HOME or pass --template-root.")


def choose_python_command(project_root: Path) -> str | None:
    windows_venv = project_root / ".venv" / "Scripts" / "python.exe"
    if windows_venv.is_file():
        return ".venv/Scripts/python.exe"
    unix_venv = project_root / ".venv" / "bin" / "python"
    if unix_venv.is_file():
        return ".venv/bin/python"
    try:
        result = subprocess.run(["python", "-c", ""], cwd=project_root, capture_output=True, timeout=10)
        if result.returncode == 0:
            return "python"
    except Exception:
        return None
    return None


def latest_archive(project_root: Path, agent: str) -> Path | None:
    root = _archive_agent_root(project_root, agent)
    if not root.is_dir():
        return None
    dirs = sorted(path for path in root.iterdir() if path.is_dir())
    if not dirs:
        return None
    if len(dirs) > 1:
        rels = ", ".join(_rel(path, project_root) for path in dirs)
        raise SystemExit(f"ERROR: multiple {agent} archives found. Keep only one before switching: {rels}")
    return dirs[0]


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _add_tree(copy_items: list[CopyItem], src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.exists():
        return
    for src in sorted(path for path in src_dir.rglob("*") if path.is_file()):
        if "__pycache__" in src.parts or src.suffix == ".pyc":
            continue
        copy_items.append(CopyItem(src, dst_dir / src.relative_to(src_dir)))


def template_copy_items(template_root: Path, project_root: Path, agent: str) -> list[CopyItem]:
    spec = SPECS[agent]
    template_dir = template_root / "templates" / agent
    items: list[CopyItem] = []
    entry = template_dir / spec.entry
    if entry.is_file():
        items.append(CopyItem(entry, project_root / spec.entry))
    for name in ("rules", "hooks", "scripts", "memory"):
        _add_tree(items, template_dir / name, project_root / spec.config_dir / name)
    settings = template_dir / "settings.json"
    if settings.is_file():
        items.append(CopyItem(settings, project_root / spec.config_dir / "settings.json"))
    if not (project_root / "scripts" / "bridgeforge_switch.py").exists():
        switch_script = template_dir / "scripts" / "bridgeforge_switch.py"
        if switch_script.is_file():
            items.append(CopyItem(switch_script, project_root / "scripts" / "bridgeforge_switch.py"))
    if not (project_root / ".githooks").exists():
        _add_tree(items, template_dir / ".githooks", project_root / ".githooks")
    return items


def archive_copy_items(archive_dir: Path, project_root: Path) -> list[CopyItem]:
    items: list[CopyItem] = []
    for src in sorted(path for path in archive_dir.rglob("*") if path.is_file()):
        if "__pycache__" in src.parts or src.suffix == ".pyc":
            continue
        items.append(CopyItem(src, project_root / src.relative_to(archive_dir)))
    return items


def _source_memory_dir(source_kind: str, source_root: Path, agent: str) -> Path | None:
    if source_kind == "archive":
        path = source_root / SPECS[agent].config_dir / "memory"
    else:
        path = source_root / "memory"
    return path if path.is_dir() else None


def _source_settings(source_kind: str, source_root: Path, agent: str) -> Path | None:
    if source_kind == "archive":
        path = source_root / SPECS[agent].config_dir / "settings.json"
    else:
        path = source_root / "settings.json"
    return path if path.is_file() else None


def _note_files(memory_dir: Path | None) -> dict[str, Path]:
    if not memory_dir or not memory_dir.is_dir():
        return {}
    out: dict[str, Path] = {}
    for path in sorted(memory_dir.rglob("*.md")):
        if path.name in GENERATED_MEMORY_FILES:
            continue
        out[_posix(path.relative_to(memory_dir))] = path
    return out


def _normalized_content(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").strip()


def _similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.86


def build_memory_plan(
    project_root: Path,
    old_agent: str,
    target_agent: str,
    source_kind: str,
    source_root: Path,
) -> MemoryPlan:
    old_dir = project_root / SPECS[old_agent].config_dir / "memory"
    target_source_dir = _source_memory_dir(source_kind, source_root, target_agent)
    target_live_dir = project_root / SPECS[target_agent].config_dir / "memory"
    plan = MemoryPlan(
        old_dir=old_dir if old_dir.is_dir() else None,
        target_source_dir=target_source_dir,
        target_live_dir=target_live_dir,
    )

    old_notes = _note_files(plan.old_dir)
    target_notes = _note_files(plan.target_source_dir)
    target_by_content = {_normalized_content(path): rel for rel, path in target_notes.items()}

    for rel, old_path in old_notes.items():
        old_text = _normalized_content(old_path)
        if old_text in target_by_content:
            plan.duplicates.append(rel)
            continue
        if rel in target_notes:
            plan.conflicts.append(MemoryConflict(rel, old_path, target_notes[rel], "same relative path differs"))
            continue
        similar_rel = None
        similar_path = None
        for target_rel, target_path in target_notes.items():
            if _similar(old_text, _normalized_content(target_path)):
                similar_rel = target_rel
                similar_path = target_path
                break
        if similar_path is not None and similar_rel is not None:
            plan.conflicts.append(MemoryConflict(rel, old_path, similar_path, f"similar to {similar_rel}"))
            continue
        plan.auto_copy.append((old_path, rel))
    return plan


def _load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"__unparsed__": path.read_text(encoding="utf-8", errors="replace")}
    return data if isinstance(data, dict) else {"__non_object__": data}


def _setting_item_token(key: str, item: Any) -> str:
    return f"{key}[]={json.dumps(item, ensure_ascii=False, sort_keys=True)}"


def _settings_candidates(old_data: dict[str, Any], target_data: dict[str, Any]) -> tuple[list[str], list[str]]:
    candidates: list[str] = []
    archived_only: list[str] = []
    for key in sorted(old_data):
        old_value = old_data.get(key)
        target_value = target_data.get(key)
        if old_value == target_value:
            continue
        if key == "hooks":
            archived_only.append("hooks")
            continue
        if key in {"permissions", "env"} and isinstance(old_value, dict):
            target_dict = target_value if isinstance(target_value, dict) else {}
            for subkey in sorted(old_value):
                if old_value.get(subkey) != target_dict.get(subkey):
                    candidates.append(f"{key}.{subkey}")
            continue
        if isinstance(old_value, list):
            target_list = target_value if isinstance(target_value, list) else []
            seen = {_json_key(item) for item in target_list}
            for item in old_value:
                if _json_key(item) not in seen:
                    candidates.append(_setting_item_token(key, item))
            continue
        candidates.append(key)
    return candidates, archived_only


def build_settings_plan(
    project_root: Path,
    old_agent: str,
    target_agent: str,
    source_kind: str,
    source_root: Path,
) -> SettingsPlan:
    old_settings = project_root / SPECS[old_agent].config_dir / "settings.json"
    target_source_settings = _source_settings(source_kind, source_root, target_agent)
    target_live_settings = project_root / SPECS[target_agent].config_dir / "settings.json"
    plan = SettingsPlan(
        old_settings=old_settings if old_settings.is_file() else None,
        target_source_settings=target_source_settings,
        target_live_settings=target_live_settings,
    )
    old_data = _load_json(plan.old_settings)
    target_data = _load_json(plan.target_source_settings)
    plan.candidates, plan.archived_only = _settings_candidates(old_data, target_data)
    return plan


def build_plan(agent: str, project_root: Path, template_root: Path) -> Plan:
    target_spec = SPECS[agent]
    old_agent = "codex" if agent == "claude" else "claude"
    old_spec = SPECS[old_agent]
    old_paths = _existing_agent_paths(old_spec, project_root)
    target_paths = _existing_agent_paths(target_spec, project_root)
    old_present = bool(old_paths)
    target_complete = _is_complete_agent(target_spec, project_root)

    if target_complete and not old_present:
        archive_dir = latest_archive(project_root, agent)
        source_root = archive_dir or (template_root / "templates" / agent)
        source_kind = "archive" if archive_dir and _is_under(archive_dir, project_root / ARCHIVE_ROOT) else "template"
        return Plan(
            agent=agent,
            old_agent=old_agent,
            project_root=project_root,
            template_root=template_root,
            target_source_kind=source_kind,
            target_source_root=source_root,
            archive_paths=[],
            target_copy_items=[],
            target_conflicts=[],
            archive_only_surfaces=[],
            memory=MemoryPlan(None, None, project_root / target_spec.config_dir / "memory"),
            settings=SettingsPlan(None, None, project_root / target_spec.config_dir / "settings.json"),
            already_target=True,
            python_command=choose_python_command(project_root),
        )

    target_conflicts = target_paths
    archive_dir = latest_archive(project_root, agent)
    if archive_dir is not None:
        source_kind = "archive"
        source_root = archive_dir
        copy_items = archive_copy_items(archive_dir, project_root)
    else:
        source_kind = "template"
        source_root = template_root / "templates" / agent
        copy_items = template_copy_items(template_root, project_root, agent)

    archive_paths = old_paths
    archive_only = [
        "hooks: archived only, never auto-migrated",
        "skills: archived only, never auto-migrated",
        "rules: archived only, never auto-migrated",
        "entry file: archived only, never auto-migrated",
    ]
    memory = build_memory_plan(project_root, old_agent, agent, source_kind, source_root)
    settings = build_settings_plan(project_root, old_agent, agent, source_kind, source_root)
    return Plan(
        agent=agent,
        old_agent=old_agent,
        project_root=project_root,
        template_root=template_root,
        target_source_kind=source_kind,
        target_source_root=source_root,
        archive_paths=archive_paths,
        target_copy_items=copy_items,
        target_conflicts=target_conflicts,
        archive_only_surfaces=archive_only,
        memory=memory,
        settings=settings,
        python_command=choose_python_command(project_root),
    )


def describe_plan(plan: Plan, decisions: Decisions | None = None) -> None:
    print(f"BridgeForge switch target: {plan.agent}")
    print(f"Project root: {plan.project_root}")
    print(f"Template root: {plan.template_root}")
    print(f"Target source: {plan.target_source_kind} ({_rel(plan.target_source_root, plan.project_root)})")
    print(f"Python hook command: {plan.python_command or 'unavailable'}")
    if plan.already_target:
        print("Already target agent: yes; switch is equivalent to normal /bridgeforge update/adopt flow.")
        return

    _print("Will archive old agent paths", [_rel(path, plan.project_root) for path in plan.archive_paths])
    _print("Will delete old agent live paths after archive", [_rel(path, plan.project_root) for path in plan.archive_paths])
    _print("Will restore/install target files", [_rel(item.dst, plan.project_root) for item in plan.target_copy_items])
    _print("Target path conflicts", [_rel(path, plan.project_root) for path in plan.target_conflicts])
    _print("Archived-only surfaces", plan.archive_only_surfaces)
    _print("Memory duplicate notes skipped", plan.memory.duplicates)
    _print("Memory notes copied automatically", [rel for _, rel in plan.memory.auto_copy])
    _print("Memory conflicts requiring confirmation", [f"{c.rel} ({c.reason})" for c in plan.memory.conflicts])
    _print("Settings migration candidates", plan.settings.candidates)
    _print("Settings archived-only entries", plan.settings.archived_only)
    if decisions:
        _print("Settings selected for migration", sorted(decisions.migrate_settings))
        if decisions.skip_settings_migration:
            print("Settings migration: explicitly skipped")


def pending_confirmations(plan: Plan, decisions: Decisions) -> list[str]:
    pending: list[str] = []
    if plan.target_conflicts:
        pending.append("target path conflicts")
    undecided_memory = [c.rel for c in plan.memory.conflicts if c.rel not in decisions.memory_conflicts]
    if undecided_memory:
        pending.append("memory conflicts: " + ", ".join(undecided_memory))
    if plan.settings.candidates and not decisions.skip_settings_migration:
        undecided_settings = [key for key in plan.settings.candidates if key not in decisions.migrate_settings]
        if undecided_settings:
            pending.append("settings migration candidates: " + ", ".join(undecided_settings))
    return pending


def _prompt_choice(label: str, prompt: str, choices: dict[str, str], default: str) -> str:
    rendered = "/".join(choices)
    while True:
        answer = input(f"{label}: {prompt} [{rendered}] default={default}: ").strip().lower()
        if not answer:
            return default
        if answer in choices:
            return choices[answer]
        print("Please choose one of: " + ", ".join(sorted(choices)))


def resolve_interactively(plan: Plan, decisions: Decisions) -> Decisions:
    if not sys.stdin.isatty():
        return decisions
    migrate_settings = set(decisions.migrate_settings)
    memory_conflicts = dict(decisions.memory_conflicts)
    skip_settings = decisions.skip_settings_migration

    for key in plan.settings.candidates:
        if skip_settings or key in migrate_settings:
            continue
        choice = _prompt_choice(key, "migrate old settings key into target settings?", {"y": "yes", "n": "no", "a": "abort"}, "n")
        if choice == "yes":
            migrate_settings.add(key)
        elif choice == "abort":
            raise SystemExit("ERROR: switch aborted by user.")
    if plan.settings.candidates:
        skip_settings = True

    for conflict in plan.memory.conflicts:
        if conflict.rel in memory_conflicts:
            continue
        choice = _prompt_choice(
            conflict.rel,
            "memory conflict: keep target, copy old as side file, append old, or abort?",
            {"k": "keep-target", "c": "copy-old", "a": "append-old", "x": "abort"},
            "k",
        )
        if choice == "abort":
            raise SystemExit("ERROR: switch aborted by user.")
        memory_conflicts[conflict.rel] = choice

    if (plan.archive_paths or plan.target_copy_items) and sys.stdin.isatty():
        choice = _prompt_choice("switch", "apply this plan?", {"y": "yes", "n": "no"}, "n")
        if choice != "yes":
            raise SystemExit("ERROR: switch aborted by user.")

    return Decisions(skip_settings, migrate_settings, memory_conflicts)


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _remove_empty_dirs(path: Path, stop_at: Path) -> None:
    current = path
    stop = stop_at.resolve()
    while current.exists() and current.is_dir() and current.resolve() != stop:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def _copy_path(src: Path, dst: Path) -> None:
    if src.is_dir() and not src.is_symlink():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _safe_archive_staging(project_root: Path, agent: str, stamp: str) -> Path:
    staging = project_root / ARCHIVE_ROOT / f".staging-{agent}-{stamp}-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    return staging


def stage_old_agent(plan: Plan, stamp: str) -> Path | None:
    if not plan.archive_paths:
        return None
    staging = _safe_archive_staging(plan.project_root, plan.old_agent, stamp)
    for path in plan.archive_paths:
        rel = path.relative_to(plan.project_root)
        _copy_path(path, staging / rel)
    return staging


def finalize_old_archive(plan: Plan, staging: Path | None, stamp: str) -> Path | None:
    if staging is None:
        return None

    agent_root = _archive_agent_root(plan.project_root, plan.old_agent)
    backup = None
    if agent_root.exists():
        backup = plan.project_root / ARCHIVE_ROOT / f".previous-{plan.old_agent}-{stamp}-{os.getpid()}"
        if backup.exists():
            shutil.rmtree(backup)
        shutil.move(str(agent_root), str(backup))
    final = agent_root / stamp
    final.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(staging), str(final))
    except Exception:
        if backup is not None and backup.exists() and not agent_root.exists():
            shutil.move(str(backup), str(agent_root))
        raise

    for path in plan.archive_paths:
        _remove_path(path)
        _remove_empty_dirs(path.parent, plan.project_root)

    if backup is not None and backup.exists():
        shutil.rmtree(backup)
    return final


def _staged_old_path(plan: Plan, staging: Path | None, path: Path | None) -> Path | None:
    if path is None or staging is None:
        return path
    try:
        rel = path.relative_to(plan.project_root)
    except ValueError:
        return path
    return staging / rel


def install_target(plan: Plan) -> None:
    for item in plan.target_copy_items:
        item.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.src, item.dst)
        if item.dst.name == "settings.json" and item.dst.parent.name in (".claude", ".codex"):
            adapt_settings(item.dst, plan.python_command)


def adapt_settings(path: Path, python_command: str | None) -> None:
    if not path.is_file() or not python_command:
        return
    original = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(original)
    except Exception:
        tokens_pattern = r"(?:\.venv/Scripts/python\.exe|\.venv/bin/python|python3|python)"
        text = re.sub(rf'("command"\s*:\s*")({tokens_pattern})(?=\s)', rf"\1{python_command}", original)
        path.write_text(text, encoding="utf-8")
        return
    tokens = (".venv/Scripts/python.exe", ".venv/bin/python", "python3", "python")

    def adapt(value: Any) -> Any:
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


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _merge_value(target: Any, old: Any) -> Any:
    if isinstance(target, dict) and isinstance(old, dict):
        merged = dict(target)
        for key, old_value in old.items():
            if key in merged:
                merged[key] = _merge_value(merged[key], old_value)
            else:
                merged[key] = old_value
        return merged
    if isinstance(target, list) and isinstance(old, list):
        seen = {_json_key(item) for item in target}
        merged = list(target)
        for item in old:
            key = _json_key(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)
        return merged
    return old


def _apply_setting_candidate(target_data: dict[str, Any], old_data: dict[str, Any], candidate: str) -> None:
    if "[]=" in candidate:
        key, raw_item = candidate.split("[]=", 1)
        if not isinstance(old_data.get(key), list):
            return
        try:
            item = json.loads(raw_item)
        except Exception:
            return
        target_list = target_data.get(key)
        if not isinstance(target_list, list):
            target_list = []
        if _json_key(item) not in {_json_key(existing) for existing in target_list}:
            target_list.append(item)
        target_data[key] = target_list
        return

    if "." in candidate:
        key, subkey = candidate.split(".", 1)
        old_container = old_data.get(key)
        if not isinstance(old_container, dict) or subkey not in old_container:
            return
        target_container = target_data.get(key)
        if not isinstance(target_container, dict):
            target_container = {}
        old_value = old_container[subkey]
        if subkey in target_container:
            target_container[subkey] = _merge_value(target_container[subkey], old_value)
        else:
            target_container[subkey] = old_value
        target_data[key] = target_container
        return

    if candidate not in old_data:
        return
    old_value = old_data[candidate]
    if candidate in target_data:
        target_data[candidate] = _merge_value(target_data[candidate], old_value)
    else:
        target_data[candidate] = old_value


def apply_settings_migration(plan: Plan, decisions: Decisions, staging: Path | None) -> None:
    if not decisions.migrate_settings:
        return
    old_data = _load_json(_staged_old_path(plan, staging, plan.settings.old_settings))
    target_data = _load_json(plan.settings.target_live_settings)
    for candidate in sorted(decisions.migrate_settings):
        _apply_setting_candidate(target_data, old_data, candidate)
    plan.settings.target_live_settings.parent.mkdir(parents=True, exist_ok=True)
    plan.settings.target_live_settings.write_text(
        json.dumps(target_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _unique_side_file(target_dir: Path, rel: str, old_agent: str) -> Path:
    raw = Path(rel)
    stem = raw.stem or "memory"
    suffix = raw.suffix or ".md"
    parent = target_dir / raw.parent
    candidate = parent / f"{stem}.from-{old_agent}{suffix}"
    i = 2
    while candidate.exists():
        candidate = parent / f"{stem}.from-{old_agent}-{i}{suffix}"
        i += 1
    return candidate


def _append_memory(target_path: Path, old_path: Path, old_agent: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    current = target_path.read_text(encoding="utf-8", errors="replace") if target_path.exists() else ""
    addition = old_path.read_text(encoding="utf-8", errors="replace")
    header = f"\n\n---\n\n## Imported from {old_agent} memory\n\n"
    target_path.write_text(current.rstrip() + header + addition.strip() + "\n", encoding="utf-8")


def apply_memory_merge(plan: Plan, decisions: Decisions, staging: Path | None) -> None:
    target_dir = plan.memory.target_live_dir
    for old_path, rel in plan.memory.auto_copy:
        old_path = _staged_old_path(plan, staging, old_path) or old_path
        dst = target_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_path, dst)

    for conflict in plan.memory.conflicts:
        action = decisions.memory_conflicts.get(conflict.rel)
        old_path = _staged_old_path(plan, staging, conflict.old_path) or conflict.old_path
        if action == "keep-target":
            continue
        if action == "copy-old":
            dst = _unique_side_file(target_dir, conflict.rel, plan.old_agent)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_path, dst)
        elif action == "append-old":
            live_target = target_dir / _posix(conflict.target_path.relative_to(plan.memory.target_source_dir or conflict.target_path.parent))
            if not live_target.exists():
                live_target = target_dir / conflict.rel
            _append_memory(live_target, old_path, plan.old_agent)
        elif action:
            raise SystemExit(f"ERROR: unsupported memory conflict action for {conflict.rel}: {action}")


def validate(plan: Plan) -> list[str]:
    if plan.already_target:
        return []
    spec = SPECS[plan.agent]
    problems: list[str] = []
    for path, message in [
        (plan.project_root / spec.entry, "missing target entry file"),
        (plan.project_root / spec.config_dir, "missing target config directory"),
        (plan.project_root / spec.config_dir / "settings.json", "missing target settings.json"),
    ]:
        if not path.exists():
            problems.append(f"{message}: {_rel(path, plan.project_root)}")
    old_spec = SPECS[plan.old_agent]
    for path in _agent_paths(old_spec, plan.project_root):
        if path.exists():
            problems.append(f"old agent live path still exists: {_rel(path, plan.project_root)}")
    return problems


def apply_plan(plan: Plan, decisions: Decisions) -> None:
    stamp = _timestamp()
    staging = stage_old_agent(plan, stamp)
    install_target(plan)
    apply_memory_merge(plan, decisions, staging)
    apply_settings_migration(plan, decisions, staging)
    finalize_old_archive(plan, staging, stamp)


def parse_memory_decision(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("expected REL=keep-target|copy-old|append-old")
    rel, action = raw.split("=", 1)
    rel = rel.replace("\\", "/").strip("/")
    action = action.strip()
    if action not in {"keep-target", "copy-old", "append-old"}:
        raise argparse.ArgumentTypeError("unsupported memory conflict action")
    return rel, action


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Switch BridgeForge project skeleton between claude and codex.")
    parser.add_argument("agent", choices=AGENTS, help="target agent skeleton")
    parser.add_argument("--dry-run", action="store_true", help="show the complete plan without changing files")
    parser.add_argument("--interactive", action="store_true", help="ask for settings and memory decisions in a real terminal")
    parser.add_argument("--skip-settings-migration", action="store_true", help="confirm that no old settings keys should migrate")
    parser.add_argument("--migrate-setting", action="append", default=[], metavar="KEY", help="migrate one old settings top-level key")
    parser.add_argument(
        "--memory-conflict",
        action="append",
        default=[],
        type=parse_memory_decision,
        metavar="REL=ACTION",
        help="resolve one memory conflict with keep-target, copy-old, or append-old",
    )
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

    decisions = Decisions(
        skip_settings_migration=args.skip_settings_migration,
        migrate_settings={key.strip() for key in args.migrate_setting if key.strip()},
        memory_conflicts=dict(args.memory_conflict),
    )
    plan = build_plan(args.agent, project_root, template_root)
    describe_plan(plan, decisions)

    if plan.already_target:
        return 0
    if args.dry_run:
        return 2 if pending_confirmations(plan, decisions) else 0

    if args.interactive:
        decisions = resolve_interactively(plan, decisions)

    pending = pending_confirmations(plan, decisions)
    if pending:
        print("ERROR: switch requires explicit user decisions before changing files.", file=sys.stderr)
        for item in pending:
            print(f"  - {item}", file=sys.stderr)
        print("No files were changed by this failed run.", file=sys.stderr)
        return 2

    apply_plan(plan, decisions)
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
