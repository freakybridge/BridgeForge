#!/usr/bin/env python3
"""Migrate one Windows project's legacy .agents layout.

The command is deliberately project-scoped. It only inspects <project>/.agents,
moves valid project-private skills to the active skeleton, removes manifest-known
shared skill copies, and removes the empty legacy directory. Unknown content,
links/reparse points, ambiguous targets, and destination conflicts block apply.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


FILE_ATTRIBUTE_REPARSE_POINT = 0x400


@dataclass(frozen=True)
class Action:
    action: str
    source: str
    destination: str | None = None


@dataclass
class MigrationPlan:
    project_root: str
    legacy_root: str
    target_platform: str | None
    manifest: str | None
    actions: list[Action]
    blockers: list[str]
    gaps: list[str]
    input_fingerprint: str
    plan_fingerprint: str


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return True
    return path.is_symlink() or bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


def _archive_ancestor(path: Path) -> bool:
    parts = [part.casefold() for part in path.resolve().parts]
    return any(
        parts[index] == ".bridgeforge" and parts[index + 1] == "archive"
        for index in range(len(parts) - 1)
    )


def _scan_links(root: Path) -> list[Path]:
    links: list[Path] = []
    pending = [root]
    while pending:
        current = pending.pop()
        if _is_reparse_point(current):
            links.append(current)
            continue
        try:
            entries = list(os.scandir(current))
        except OSError:
            links.append(current)
            continue
        for entry in entries:
            path = Path(entry.path)
            if _is_reparse_point(path):
                links.append(path)
            elif entry.is_dir(follow_symlinks=False):
                pending.append(path)
    return sorted(links)


def _manifest_path(script_path: Path) -> Path:
    return script_path.resolve().parent.parent / "bridgeforge-codex-manifest.json"


def _normalize_sha256(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    if normalized.startswith("sha256:"):
        normalized = normalized[7:]
    if len(normalized) != 64:
        return None
    try:
        int(normalized, 16)
    except ValueError:
        return None
    return normalized


def _safe_manifest_target(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    target = Path(value.strip())
    if target.is_absolute() or ".." in target.parts:
        return None
    normalized = target.as_posix()
    if normalized in {"", "."}:
        return None
    return normalized


def _manifest_sha256(path: Path) -> str:
    """Match the LF Git blob bytes used by the shared-skill manifest."""
    payload = path.read_bytes()
    if b"\0" not in payload:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _codex_managed_skills(
    manifest_path: Path,
) -> tuple[dict[str, dict[str, str]], str | None]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"无法读取分发 manifest：{exc}"
    if not isinstance(data, dict):
        return {}, "分发 manifest 根节点不是对象"

    platforms = data.get("platforms")
    codex = platforms.get("codex") if isinstance(platforms, dict) else None
    raw_skills = codex.get("skills") if isinstance(codex, dict) else None
    if not isinstance(raw_skills, list) or not raw_skills:
        return {}, "分发 manifest 未声明 Codex 托管 skill"

    managed: dict[str, dict[str, str]] = {}
    for raw_skill in raw_skills:
        if not isinstance(raw_skill, dict):
            return {}, "分发 manifest 包含无效 Codex skill 记录"
        raw_name = raw_skill.get("name")
        if (
            not isinstance(raw_name, str)
            or not raw_name.strip()
            or raw_name.strip() in {".", ".."}
            or "/" in raw_name
            or "\\" in raw_name
        ):
            return {}, "分发 manifest 包含无效 Codex skill 名称"
        name = raw_name.strip()
        if name in managed:
            return {}, f"分发 manifest 包含重复 Codex skill：{name}"
        raw_files = raw_skill.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            return {}, f"分发 manifest 的 Codex skill 缺少文件清单：{name}"
        files: dict[str, str] = {}
        for raw_file in raw_files:
            if not isinstance(raw_file, dict):
                return {}, f"分发 manifest 的文件记录无效：{name}"
            target = _safe_manifest_target(raw_file.get("target"))
            expected = _normalize_sha256(raw_file.get("sha256"))
            if target is None or expected is None:
                return {}, f"分发 manifest 的文件路径或哈希无效：{name}"
            if target in files:
                return {}, f"分发 manifest 包含重复目标文件：{name}/{target}"
            files[target] = expected
        managed[name] = files
    return managed, None


def _matches_manifest_copy(skill_root: Path, expected: dict[str, str]) -> bool:
    actual_files = sorted(
        path for path in skill_root.rglob("*") if path.is_file()
    )
    actual_paths = {
        path.relative_to(skill_root).as_posix()
        for path in actual_files
    }
    if actual_paths != set(expected):
        return False
    for path in actual_files:
        rel = path.relative_to(skill_root).as_posix()
        if _manifest_sha256(path) != expected[rel]:
            return False
    return True


def _detect_platform(project_root: Path) -> tuple[str | None, str | None]:
    if (project_root / ".codex").is_dir() or (
        project_root / "AGENTS.md"
    ).is_file():
        return "codex", None
    return None, "项目没有可识别的 Codex 骨架，无法判断私有 skill 目标"


def _nonempty_entries(path: Path) -> list[Path]:
    try:
        return sorted(Path(entry.path) for entry in os.scandir(path))
    except OSError:
        return [path]


def _input_fingerprint(root: Path, legacy: Path, manifest_path: Path) -> str:
    evidence: list[dict[str, str]] = []
    if manifest_path.is_file() and not _is_reparse_point(manifest_path):
        evidence.append({"path": "<manifest>", "sha256": _manifest_sha256(manifest_path)})
    if legacy.exists():
        pending = [legacy]
        while pending:
            current = pending.pop()
            rel = _relative(current, root)
            if _is_reparse_point(current):
                evidence.append({"path": rel, "state": "link"})
                continue
            if current.is_file():
                evidence.append({"path": rel, "sha256": hashlib.sha256(current.read_bytes()).hexdigest()})
                continue
            evidence.append({"path": rel, "state": "directory"})
            try:
                pending.extend(sorted((Path(entry.path) for entry in os.scandir(current)), reverse=True))
            except OSError:
                evidence.append({"path": rel, "state": "unreadable"})
    payload = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _plan_fingerprint(plan: MigrationPlan) -> str:
    payload = {
        "project_root": plan.project_root,
        "legacy_root": plan.legacy_root,
        "target_platform": plan.target_platform,
        "manifest": plan.manifest,
        "actions": [asdict(action) for action in plan.actions],
        "blockers": plan.blockers,
        "gaps": plan.gaps,
        "input_fingerprint": plan.input_fingerprint,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_plan(project_root: Path, script_path: Path) -> MigrationPlan:
    root = project_root.resolve()
    legacy = root / ".agents"
    manifest_path = _manifest_path(script_path)
    actions: list[Action] = []
    blockers: list[str] = []
    gaps: list[str] = []

    plan = MigrationPlan(
        project_root=str(root),
        legacy_root=".agents",
        target_platform=None,
        manifest=str(manifest_path),
        actions=actions,
        blockers=blockers,
        gaps=gaps,
        input_fingerprint=_input_fingerprint(root, legacy, manifest_path),
        plan_fingerprint="",
    )
    if _archive_ancestor(root):
        blockers.append("拒绝迁移 .bridgeforge/archive 内的历史项目快照")
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan
    if not legacy.exists():
        plan.manifest = None
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan
    if not legacy.is_dir() or _is_reparse_point(legacy):
        blockers.append(".agents 不是普通目录，禁止迁移")
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan

    links = _scan_links(legacy)
    if links:
        blockers.extend(
            f"发现链接、junction、reparse point 或不可读取路径：{_relative(path, root)}"
            for path in links
        )
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan

    skills_root = legacy / "skills"
    legacy_entries = _nonempty_entries(legacy)
    unexpected_roots = [
        path
        for path in legacy_entries
        if path != skills_root and (path.is_file() or _nonempty_entries(path))
    ]
    gaps.extend(
        f".agents 下存在无法分类内容：{_relative(path, root)}"
        for path in unexpected_roots
    )

    if not skills_root.exists():
        if not blockers and not gaps:
            actions.append(Action("delete_empty_legacy_root", ".agents"))
        plan.manifest = None
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan
    if not skills_root.is_dir():
        blockers.append(".agents/skills 不是普通目录")
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan

    skill_entries = _nonempty_entries(skills_root)
    if not skill_entries:
        if not blockers and not gaps:
            actions.append(Action("delete_empty_legacy_root", ".agents"))
        plan.manifest = None
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan

    managed_skills, manifest_error = _codex_managed_skills(manifest_path)
    if manifest_error:
        blockers.append(manifest_error)
        plan.plan_fingerprint = _plan_fingerprint(plan)
        return plan

    private_skills: list[Path] = []
    for path in skill_entries:
        rel = _relative(path, root)
        if not path.is_dir():
            gaps.append(f".agents/skills 下存在未知文件，已保留：{rel}")
            continue
        if path.name in managed_skills:
            if _matches_manifest_copy(path, managed_skills[path.name]):
                actions.append(Action("delete_managed_skill_copy", rel))
            else:
                gaps.append(
                    "同名 bridgeforge-codex skill 与 manifest 文件清单或哈希不一致，"
                    f"已保留：{rel}"
                )
            continue
        skill_file = path / "SKILL.md"
        if not skill_file.is_file() or _is_reparse_point(skill_file):
            gaps.append(f"无法把目录分类为项目私有 skill，已保留：{rel}")
            continue
        private_skills.append(path)

    if private_skills:
        platform, platform_error = _detect_platform(root)
        plan.target_platform = platform
        if platform_error:
            gaps.append(platform_error + "；项目私有 skill 已保留")
        else:
            assert platform is not None
            target_root = root / f".{platform}" / "skills"
            for path in private_skills:
                destination = target_root / path.name
                if destination.exists():
                    gaps.append(
                        "项目私有 skill 目标已存在，禁止覆盖："
                        f"{_relative(destination, root)}"
                    )
                    continue
                actions.append(
                    Action(
                        "move_project_private_skill",
                        _relative(path, root),
                        _relative(destination, root),
                    )
                )
    if not blockers and not gaps:
        actions.append(Action("delete_empty_legacy_root", ".agents"))
    plan.plan_fingerprint = _plan_fingerprint(plan)
    return plan


def _remove_empty_tree(root: Path) -> None:
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in directories:
        path.rmdir()
    root.rmdir()


def apply_plan(plan: MigrationPlan, *, confirmed: bool, plan_fingerprint: str) -> None:
    if not confirmed:
        raise RuntimeError("迁移 apply 需要显式 confirmed")
    if plan.plan_fingerprint != plan_fingerprint:
        raise RuntimeError("迁移计划 fingerprint 不匹配")
    if plan.blockers:
        raise RuntimeError("迁移计划存在 blocker，拒绝写入")
    root = Path(plan.project_root)
    legacy = root / plan.legacy_root
    if not legacy.exists():
        return

    move_actions = [
        action for action in plan.actions if action.action == "move_project_private_skill"
    ]
    delete_actions = [
        action for action in plan.actions if action.action == "delete_managed_skill_copy"
    ]
    backup_root: Path | None = None
    staged_deletes: list[tuple[Path, Path]] = []
    created_targets: list[Path] = []
    completed_moves: list[tuple[Path, Path]] = []
    try:
        if delete_actions:
            backup_root = Path(
                tempfile.mkdtemp(prefix=".bridgeforge-migrate-backup-", dir=root)
            )
            for action in delete_actions:
                source = root / action.source
                backup = backup_root / Path(action.source).name
                os.replace(source, backup)
                staged_deletes.append((source, backup))
        for action in move_actions:
            assert action.destination is not None
            source = root / action.source
            destination = root / action.destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            completed_moves.append((source, destination))
            created_targets.append(destination.parent)
        if any(action.action == "delete_empty_legacy_root" for action in plan.actions):
            _remove_empty_tree(legacy)
        else:
            skills_root = legacy / "skills"
            if skills_root.is_dir() and not any(skills_root.iterdir()):
                skills_root.rmdir()
    except Exception:
        for source, destination in reversed(completed_moves):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, source)
        for source, backup in reversed(staged_deletes):
            if backup.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, source)
        for path in sorted(set(created_targets), key=lambda item: len(item.parts), reverse=True):
            try:
                path.rmdir()
            except OSError:
                pass
        if backup_root is not None:
            try:
                backup_root.rmdir()
            except OSError:
                pass
        raise
    if backup_root is not None:
        shutil.rmtree(backup_root)


def _print_plan(plan: MigrationPlan, mode: str) -> None:
    payload = {
        "mode": mode,
        **asdict(plan),
        "actions": [asdict(action) for action in plan.actions],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate the current Windows project's legacy .agents layout."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--plan-fingerprint")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != "nt":
        print("ERROR: bridgeforge-codex layout migration only supports Windows.", file=sys.stderr)
        return 2
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        print(f"ERROR: project root is not a directory: {project_root}", file=sys.stderr)
        return 2
    plan = build_plan(project_root, Path(__file__))
    _print_plan(plan, "apply" if args.apply else "dry-run")
    if plan.blockers:
        return 2
    if args.dry_run:
        return 0
    if not args.confirmed or not args.plan_fingerprint:
        print("ERROR: --apply requires --confirmed and --plan-fingerprint.", file=sys.stderr)
        return 2
    refreshed = build_plan(project_root, Path(__file__))
    if refreshed.plan_fingerprint != args.plan_fingerprint:
        print("ERROR: migration plan drifted before apply; no writes performed.", file=sys.stderr)
        return 2
    try:
        apply_plan(
            refreshed,
            confirmed=True,
            plan_fingerprint=args.plan_fingerprint,
        )
    except Exception as exc:
        print(f"ERROR: migration failed: {exc}", file=sys.stderr)
        return 2
    print("Migration applied: .agents retired for this project.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
