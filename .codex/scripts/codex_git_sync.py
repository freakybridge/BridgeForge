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
from pathlib import Path

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


def _has_staged_changes() -> bool:
    result = _git(["diff", "--cached", "--quiet"])
    return result.returncode == 1


def _upstream() -> str:
    result = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if result.returncode != 0:
        raise SyncStop("no upstream branch; set upstream before running git-sync", 2)
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


def _rebuild_memory_index() -> None:
    script = REPO_ROOT / ".codex" / "scripts" / "memory_rebuild_index.py"
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
        raise SyncStop(f"memory_rebuild_index.py failed: {detail}", result.returncode or 1)


def _refresh_harness_parity_report() -> None:
    script = REPO_ROOT / ".codex" / "scripts" / "harness_parity_check.py"
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
        raise SyncStop(f"harness_parity_check.py failed: {detail}", result.returncode or 1)
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
    if not args.skip_fetch:
        _run_git(["fetch", args.remote], timeout=180, label=f"git fetch {args.remote}")
    _upstream()

    ahead, behind = _ahead_behind()
    _refresh_harness_parity_report()
    dirty = bool(_status())

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
        _rebuild_memory_index()
        _run_git(["add", "."], label="git add")
        if _has_staged_changes():
            message = _read_message(args)
            if not message:
                raise SyncStop("commit message is required when local changes are staged", 2)
            _run_git(["commit", "-m", message], timeout=180, label="git commit")
            ahead, behind = _ahead_behind()
            if ahead and behind:
                _print_diverged()
                return 2

    ahead, behind = _ahead_behind()
    if ahead and behind:
        _print_diverged()
        return 2
    if behind:
        raise SyncStop("remote advanced during git-sync; rerun after reviewing state", 2)
    if ahead:
        if args.skip_push:
            print(f"[git-sync] {ahead} local commit(s) ready; push skipped by --skip-push")
        else:
            _run_git(["push"], timeout=240, label="git push")

    final_dirty = _status()
    final_ahead, final_behind = _ahead_behind()
    if final_dirty or final_ahead or final_behind:
        print("[git-sync] finished with remaining state:")
        if final_dirty:
            print(final_dirty)
        if final_ahead or final_behind:
            print(f"ahead={final_ahead} behind={final_behind}")
        return 3

    print("[git-sync] synced; working tree clean")
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
