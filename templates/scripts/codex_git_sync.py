#!/usr/bin/env python3
"""Run the mechanical git-sync flow as one Codex-approved command.

The model still owns the review and commit-message decision. This runner keeps
the actual git plumbing in one narrow, repo-local command so Codex can request a
single persistent approval for:

    python .codex/scripts/codex_git_sync.py

It deliberately refuses risky history repair. Diverged branches, missing
upstream, stash-pop conflicts, and push races stop for user handling.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from version_release import ReleaseError, ReleasePlan, apply_release_plan, build_release_plan

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


REPO_ROOT = Path(__file__).resolve().parents[2]


class SyncStop(Exception):
    """Expected stop with a user-facing message and exit code."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    return env


def _git(args: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-c", f"safe.directory={REPO_ROOT.as_posix()}", *args]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=_env(),
    )


def _run_git(args: list[str], *, timeout: int = 120, label: str | None = None) -> subprocess.CompletedProcess[str]:
    result = _git(args, timeout=timeout)
    if result.returncode != 0:
        name = label or "git " + " ".join(args)
        detail = (result.stderr or result.stdout).strip()
        raise SyncStop(f"{name} failed: {detail}", result.returncode or 1)
    return result


def _status() -> str:
    return _run_git(["status", "--porcelain=v1"], label="git status").stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    commands = (
        ["diff", "--name-only"],
        ["diff", "--cached", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    )
    for command in commands:
        output = _run_git(command, label="git changed-path scan").stdout
        paths.update(line.strip().replace("\\", "/") for line in output.splitlines() if line.strip())
    return paths


@dataclass(frozen=True)
class _FileSnapshot:
    worktree: bytes | None
    index_entry: tuple[str, str] | None


def _snapshot_release_files(plan: ReleasePlan) -> dict[Path, _FileSnapshot]:
    snapshots: dict[Path, _FileSnapshot] = {}
    for path in plan.writes:
        relative = path.relative_to(REPO_ROOT).as_posix()
        worktree = path.read_bytes() if path.is_file() else None
        entry = _git(["ls-files", "--stage", "--", relative])
        if entry.returncode != 0:
            detail = (entry.stderr or entry.stdout).strip()
            raise SyncStop(f"cannot snapshot index entry for {relative}: {detail}", 1)
        parsed: tuple[str, str] | None = None
        if entry.stdout.strip():
            metadata = entry.stdout.split("\t", 1)[0].split()
            if len(metadata) != 3 or metadata[2] != "0":
                raise SyncStop(f"cannot snapshot conflicted index entry for {relative}", 2)
            parsed = (metadata[0], metadata[1])
        snapshots[path] = _FileSnapshot(worktree, parsed)
    return snapshots


def _restore_release_files(
    plan: ReleasePlan, snapshots: dict[Path, _FileSnapshot]
) -> None:
    conflicts: list[str] = []
    for path, snapshot in snapshots.items():
        relative = path.relative_to(REPO_ROOT).as_posix()
        current = path.read_bytes() if path.is_file() else None
        if current == plan.writes[path]:
            if snapshot.worktree is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(snapshot.worktree)
        elif current != snapshot.worktree:
            conflicts.append(relative)
            continue
        if snapshot.index_entry is None:
            result = _git(["rm", "--cached", "--ignore-unmatch", "--", relative])
        else:
            mode, object_id = snapshot.index_entry
            result = _git(["update-index", "--cacheinfo", f"{mode},{object_id},{relative}"])
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise SyncStop(f"failed to restore release index entry {relative}: {detail}", 1)
    if conflicts:
        raise SyncStop(
            "release rollback stopped because these auto-managed files changed concurrently: "
            + ", ".join(conflicts),
            2,
        )


def _has_staged_changes() -> bool:
    result = _git(["diff", "--cached", "--quiet"])
    return result.returncode == 1


def _upstream() -> str:
    result = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if result.returncode != 0:
        raise SyncStop("no upstream branch; set upstream before running git-sync", 2)
    return result.stdout.strip()


def _push_target() -> str:
    result = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{push}"])
    if result.returncode != 0:
        raise SyncStop("no push target; configure the current branch before git-sync", 2)
    return result.stdout.strip()


def _ahead_behind() -> tuple[int, int]:
    result = _git(["rev-list", "--left-right", "--count", "HEAD...@{u}"])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SyncStop(f"cannot read ahead/behind state: {detail}", 1)
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        raise SyncStop(f"unexpected ahead/behind output: {result.stdout!r}", 1)
    return int(parts[0]), int(parts[1])


def _print_diverged() -> None:
    print("[git-sync] branch diverged; manual decision required")
    local = _git(["log", "--oneline", "--decorate", "--max-count=5", "@{u}..HEAD"])
    remote = _git(["log", "--oneline", "--decorate", "--max-count=5", "HEAD..@{u}"])
    if local.stdout.strip():
        print("\n[git-sync] local-only commits:")
        print(local.stdout.strip())
    if remote.stdout.strip():
        print("\n[git-sync] remote-only commits:")
        print(remote.stdout.strip())


def _read_message(args: argparse.Namespace) -> str | None:
    if args.message_file:
        return Path(args.message_file).read_text(encoding="utf-8").strip()
    if args.message:
        return args.message.strip()
    return None


def _check_factory_version_worktree() -> None:
    script = REPO_ROOT / ".codex" / "scripts" / "factory_version_check.py"
    if not script.exists():
        return
    result = subprocess.run(
        [sys.executable, str(script), "--worktree"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=_env(),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SyncStop(
            f"factory_version_check.py --worktree failed: {detail}",
            result.returncode or 1,
        )


def _rebuild_shared_skill_manifest() -> None:
    script = REPO_ROOT / "scripts" / "rebuild_shared_skill_manifest.py"
    if not script.exists():
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=_env(),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SyncStop(
            f"rebuild_shared_skill_manifest.py failed: {detail}",
            result.returncode or 1,
        )
    if result.stdout.strip():
        print(result.stdout.strip())


def _pull_ff_with_optional_stash(dirty: bool) -> None:
    stashed = False
    if dirty:
        result = _run_git(["stash", "push", "-u", "-m", "codex_git_sync_autostash"], label="git stash")
        stashed = "No local changes to save" not in (result.stdout + result.stderr)
    try:
        _run_git(["pull", "--ff-only"], timeout=180, label="git pull --ff-only")
    except SyncStop:
        if stashed:
            print("[git-sync] local changes are still in stash; resolve pull failure before continuing")
        raise
    if stashed:
        result = _git(["stash", "pop"], timeout=180)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise SyncStop(f"git stash pop failed; stash is kept for manual recovery: {detail}", 2)


def sync(args: argparse.Namespace) -> int:
    if not (REPO_ROOT / ".git").exists():
        raise SyncStop(f"not a git repository: {REPO_ROOT}", 1)

    _run_git(["rev-parse", "--is-inside-work-tree"], label="git rev-parse")
    _upstream()
    push_target = _push_target()
    dirty = bool(_status())
    message = None
    if dirty:
        message = _read_message(args)
        if not message:
            raise SyncStop("commit message is required when local changes exist", 2)

    if not args.skip_fetch:
        _run_git(["fetch", args.remote], timeout=180, label=f"git fetch {args.remote}")

    ahead, behind = _ahead_behind()

    if ahead and behind:
        _print_diverged()
        return 2

    if behind and not ahead:
        _pull_ff_with_optional_stash(dirty)
        ahead, behind = _ahead_behind()
        dirty = bool(_status())
        if ahead and behind:
            _print_diverged()
            return 2

    if dirty:
        if not message:
            raise SyncStop("commit message is required when local changes are staged", 2)
        try:
            plan = build_release_plan(REPO_ROOT, message, _changed_paths())
        except ReleaseError as exc:
            raise SyncStop(f"automatic version release blocked: {exc}", 2) from exc
        snapshots = _snapshot_release_files(plan) if plan is not None else {}
        committed = False
        try:
            if plan is not None:
                apply_release_plan(plan)
                print(
                    f"[git-sync] version {plan.old_version} -> {plan.new_version} "
                    f"({plan.classification})"
                )
            _rebuild_shared_skill_manifest()
            _check_factory_version_worktree()
            _run_git(["add", "."], label="git add")
            if _has_staged_changes():
                _run_git(["commit", "-m", message], timeout=180, label="git commit")
                committed = True
                ahead, behind = _ahead_behind()
                if ahead and behind:
                    _print_diverged()
                    return 2
        except Exception as exc:
            if plan is not None and not committed:
                _restore_release_files(plan, snapshots)
                print("[git-sync] automatic version files rolled back; original project edits were kept")
            if isinstance(exc, SyncStop):
                raise
            raise SyncStop(f"automatic version release failed: {exc}", 1) from exc

    ahead, behind = _ahead_behind()
    if ahead and behind:
        _print_diverged()
        return 2
    if behind:
        raise SyncStop("remote advanced during git-sync; rerun after reviewing state", 2)
    pushed = False
    if ahead:
        if args.skip_push:
            print(f"[git-sync] {ahead} local commit(s) ready; push skipped by --skip-push")
        else:
            _run_git(["push"], timeout=240, label="git push")
            pushed = True

    final_dirty = _status()
    final_ahead, final_behind = _ahead_behind()
    if final_dirty or final_ahead or final_behind:
        print("[git-sync] finished with remaining state:")
        if final_dirty:
            print(final_dirty)
        if final_ahead or final_behind:
            print(f"ahead={final_ahead} behind={final_behind}")
        return 3

    commit = _run_git(["rev-parse", "HEAD"], label="git rev-parse HEAD").stdout.strip()
    print("[git-sync] synced")
    print(f"commit={commit}")
    print(f"push_target={push_target}")
    print(f"push_performed={'true' if pushed else 'false'}")
    print("working_tree=clean")
    print("ahead=0 behind=0")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-m", "--message", help="Commit message to use when local changes are staged.")
    parser.add_argument("--message-file", help="Read the commit message from a UTF-8 file.")
    parser.add_argument("--remote", default="origin", help="Remote to fetch before syncing. Default: origin.")
    parser.add_argument("--skip-fetch", action="store_true", help="Diagnostic/test mode: do not fetch first.")
    parser.add_argument("--skip-push", action="store_true", help="Diagnostic/test mode: commit but do not push.")
    args = parser.parse_args()

    try:
        return sync(args)
    except subprocess.TimeoutExpired as exc:
        print(f"[git-sync] command timed out: {exc}", file=sys.stderr)
        return 1
    except SyncStop as exc:
        print(f"[git-sync] {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
