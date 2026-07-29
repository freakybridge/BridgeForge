#!/usr/bin/env python3
"""Reconcile the host system memory path with project-tracked memory.

The default ``check`` mode is safe for SessionStart. It may create a missing
junction when project memory already exists, but it never migrates or deletes
an existing system directory. Destructive migration is available only through
the explicit ``migrate --confirmed`` CLI orchestrated by ``/bridgeforge``.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

HOST_DIR = Path(__file__).resolve().parent.parent.name
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_MEMORY = REPO_ROOT / HOST_DIR / "memory"


class ReconcileError(RuntimeError):
    """Unsafe or inconsistent filesystem state."""


@dataclass(frozen=True)
class TreeSnapshot:
    files: dict[Path, Path]
    directories: frozenset[Path]


@dataclass(frozen=True)
class MergePlan:
    copy: tuple[Path, ...]
    identical: tuple[Path, ...]
    project_only: tuple[Path, ...]


@dataclass(frozen=True)
class ReconcileResult:
    state: str
    changed: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state != "error"


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _is_link(path: Path) -> bool:
    """Return True for symlinks and Windows reparse-point junctions."""
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            return True
        absolute = os.path.normcase(os.path.abspath(str(path)))
        resolved = os.path.normcase(os.path.realpath(str(path)))
        return path.is_dir() and absolute != resolved
    except OSError:
        return False


def _same_path(left: Path, right: Path) -> bool:
    try:
        left_resolved = left.resolve(strict=True)
        right_resolved = right.resolve(strict=True)
    except OSError:
        return False
    return os.path.normcase(str(left_resolved)) == os.path.normcase(
        str(right_resolved)
    )


def _link_matches(link: Path, target: Path) -> bool:
    return (
        _lexists(link)
        and _is_link(link)
        and target.is_dir()
        and not _is_link(target)
        and _same_path(link, target)
    )


def _project_hash(root: Path) -> str:
    """Encode a repo path using the host project-directory convention."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(root))


def _system_memory_path() -> Path | None:
    project_dir = Path.home() / HOST_DIR / "projects" / _project_hash(REPO_ROOT)
    if not _lexists(project_dir):
        return None
    if _is_link(project_dir) or not project_dir.is_dir():
        raise ReconcileError(f"abnormal host project path: {project_dir}")
    return project_dir / "memory"


def _scan_tree(root: Path) -> TreeSnapshot:
    """Snapshot regular files while rejecting links and special paths."""
    if not _lexists(root):
        return TreeSnapshot({}, frozenset())
    if _is_link(root) or not root.is_dir():
        raise ReconcileError(f"abnormal memory path: {root}")

    files: dict[Path, Path] = {}
    directories: set[Path] = set()
    for current_text, dir_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        current = Path(current_text)
        for name in dir_names:
            child = current / name
            if _is_link(child) or not child.is_dir():
                raise ReconcileError(f"abnormal directory entry: {child}")
            directories.add(child.relative_to(root))
        for name in file_names:
            child = current / name
            if _is_link(child) or not child.is_file():
                raise ReconcileError(f"abnormal file entry: {child}")
            files[child.relative_to(root)] = child
    return TreeSnapshot(files, frozenset(directories))


def _digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def _same_content(left: Path, right: Path) -> bool:
    try:
        return left.stat().st_size == right.stat().st_size and _digest(
            left
        ) == _digest(right)
    except OSError as exc:
        raise ReconcileError(f"cannot compare memory files: {exc}") from exc


def _relative_key(path: Path) -> str:
    """Use host filesystem case semantics for relative-path comparisons."""
    return os.path.normcase(os.path.normpath(str(path)))


def _normalized_paths(paths: set[Path]) -> dict[str, Path]:
    normalized: dict[str, Path] = {}
    for path in paths:
        key = _relative_key(path)
        previous = normalized.get(key)
        if previous is not None and str(previous) != str(path):
            raise ReconcileError(
                f"case-only path collision: {previous} <-> {path}"
            )
        normalized[key] = path
    return normalized


def _build_merge_plan(system: Path, project: Path) -> MergePlan:
    system_tree = _scan_tree(system)
    project_tree = _scan_tree(project)
    system_files = _normalized_paths(set(system_tree.files))
    project_files = _normalized_paths(set(project_tree.files))
    _normalized_paths(set(system_tree.directories))
    project_directories = _normalized_paths(set(project_tree.directories))
    conflicts: list[str] = []
    copy: list[Path] = []
    identical: list[Path] = []

    for relative, source in system_tree.files.items():
        key = _relative_key(relative)
        project_directory = project_directories.get(key)
        if project_directory is not None:
            conflicts.append(f"{relative} <-> {project_directory}")
            continue
        project_relative = project_files.get(key)
        if project_relative is None:
            copy.append(relative)
        elif str(project_relative) != str(relative):
            conflicts.append(f"{relative} <-> {project_relative}")
        elif _same_content(source, project_tree.files[project_relative]):
            identical.append(relative)
        else:
            conflicts.append(str(relative))

    for relative in system_tree.directories:
        key = _relative_key(relative)
        project_file = project_files.get(key)
        if project_file is not None:
            conflicts.append(f"{relative} <-> {project_file}")

    if conflicts:
        rendered = ", ".join(sorted(set(conflicts)))
        raise ReconcileError(f"memory merge conflict: {rendered}")

    project_only = tuple(
        sorted(
            relative
            for key, relative in project_files.items()
            if key not in system_files
        )
    )
    return MergePlan(
        copy=tuple(sorted(copy)),
        identical=tuple(sorted(identical)),
        project_only=project_only,
    )


def _copy_unique_files(system: Path, project: Path, plan: MergePlan) -> None:
    for relative in plan.copy:
        source = system / relative
        destination = project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if _lexists(destination):
            if (
                not _is_link(destination)
                and destination.is_file()
                and _same_content(source, destination)
            ):
                continue
            raise ReconcileError(
                f"destination changed during migration: {destination}"
            )
        try:
            with source.open("rb") as reader, destination.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            shutil.copystat(source, destination, follow_symlinks=False)
        except Exception as exc:
            raise ReconcileError(f"copy failed for {relative}: {exc}") from exc


def _verify_contains(system: Path, project: Path) -> None:
    source_tree = _scan_tree(system)
    target_tree = _scan_tree(project)
    for relative, source in source_tree.files.items():
        destination = target_tree.files.get(relative)
        if destination is None or not _same_content(source, destination):
            raise ReconcileError(f"integrity check failed: {relative}")


def _create_junction(link: Path, target: Path) -> None:
    if _lexists(link):
        raise ReconcileError(f"refusing to replace existing path: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode:
                raise ReconcileError(
                    f"junction creation failed: {result.stderr.strip()}"
                )
        else:
            os.symlink(str(target), str(link), target_is_directory=True)
    except ReconcileError:
        raise
    except Exception as exc:
        raise ReconcileError(f"junction creation failed: {exc}") from exc
    if not _link_matches(link, target):
        raise ReconcileError(
            f"created junction does not target project memory: {link}"
        )


def _classify(system: Path, project: Path) -> str:
    project_exists = _lexists(project)
    if project_exists:
        _scan_tree(project)

    if not _lexists(system):
        return "system-missing"
    if _is_link(system):
        if not project_exists or not _link_matches(system, project):
            raise ReconcileError(
                f"wrong or broken memory junction: {system}; "
                f"expected target: {project}"
            )
        return "linked"
    if not system.is_dir():
        raise ReconcileError(f"system memory is not a directory: {system}")
    _scan_tree(system)
    return "real-directory"


def _plan_detail(plan: MergePlan) -> str:
    return (
        "migration plan: "
        f"copy={len(plan.copy)}, identical={len(plan.identical)}, "
        f"project_only={len(plan.project_only)}"
    )


def reconcile(
    mode: str = "check",
    *,
    confirmed: bool = False,
    system_memory: Path | None = None,
    project_memory: Path | None = None,
) -> ReconcileResult:
    """Run the shared state machine for SessionStart or confirmed update."""
    if mode not in {"check", "plan", "migrate"}:
        return ReconcileResult(
            "error",
            detail=f"invalid reconciliation mode: {mode!r}",
        )
    if mode == "migrate" and not confirmed:
        return ReconcileResult(
            "error",
            detail=(
                "migrate refused: explicit confirmed=True is required after "
                "the user reviews the migration plan"
            ),
        )
    project = project_memory if project_memory is not None else PROJECT_MEMORY
    try:
        system = (
            system_memory
            if system_memory is not None
            else _system_memory_path()
        )
        if system is None:
            return ReconcileResult("unmanaged")
        state = _classify(system, project)
        if state == "linked":
            return ReconcileResult("linked")

        if state == "system-missing":
            if not _lexists(project):
                return ReconcileResult("uninitialized")
            if mode == "plan":
                return ReconcileResult(
                    "link-required",
                    detail=f"migration plan: create junction {system} -> {project}",
                )
            _create_junction(system, project)
            return ReconcileResult(
                "linked",
                changed=True,
                detail=f"restored memory junction: {system} -> {project}",
            )

        if mode == "check":
            return ReconcileResult(
                "migration-required",
                detail=(
                    "system memory is a real directory; no changes made. "
                    "Run /bridgeforge to review and confirm migration."
                ),
            )

        plan = _build_merge_plan(system, project)
        if mode == "plan":
            return ReconcileResult("migration-required", detail=_plan_detail(plan))

        if mode != "migrate":
            return ReconcileResult(
                "error",
                detail=f"refusing destructive action for mode: {mode!r}",
            )
        project.mkdir(parents=True, exist_ok=True)
        _copy_unique_files(system, project, plan)
        _verify_contains(system, project)
        shutil.rmtree(system)
        _create_junction(system, project)
        return ReconcileResult(
            "linked",
            changed=True,
            detail=f"memory migration complete; {_plan_detail(plan)}",
        )
    except ReconcileError as exc:
        return ReconcileResult("error", detail=str(exc))
    except Exception as exc:
        return ReconcileResult(
            "error", detail=f"unexpected memory junction error: {exc}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("check", "plan", "migrate"), default="check"
    )
    parser.add_argument(
        "--confirmed",
        action="store_true",
        help="required for the destructive migrate mode",
    )
    args = parser.parse_args(argv)
    if args.mode == "migrate" and not args.confirmed:
        print(
            "[memory-junction] migrate refused: review the plan and pass "
            "--confirmed only after user confirmation"
        )
        return 2

    result = reconcile(args.mode, confirmed=args.confirmed)
    if result.detail:
        print(f"[memory-junction] {result.detail}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
