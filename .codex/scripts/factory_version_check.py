#!/usr/bin/env python3
"""bridgeforge-codex 工厂专用：产品层改动必须同次暂存根 VERSION。

该检查只由本仓库的 `.githooks/pre-commit` 调用，绝不下沉到下游模板。
下游项目的业务版本与骨架版本戳是独立生命周期，不适用本检查。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PRODUCT_PREFIXES = ("templates/", "skills/")
VERSION_FILE = "VERSION"


def _git_paths(repo_root: Path, args: list[str]) -> set[str] | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def staged_paths(repo_root: Path) -> set[str] | None:
    return _git_paths(repo_root, ["diff", "--cached", "--name-only"])


def worktree_paths(repo_root: Path) -> set[str] | None:
    path_sets = (
        staged_paths(repo_root),
        _git_paths(repo_root, ["diff", "--name-only"]),
        _git_paths(repo_root, ["ls-files", "--others", "--exclude-standard"]),
    )
    if any(paths is None for paths in path_sets):
        return None
    return set().union(*(paths for paths in path_sets if paths is not None))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="检查 staged、unstaged 与 untracked 路径；默认仅检查 staged。",
    )
    args = parser.parse_args()

    paths = worktree_paths(Path.cwd()) if args.worktree else staged_paths(Path.cwd())
    if paths is None or not any(path.startswith(PRODUCT_PREFIXES) for path in paths):
        return 0
    if VERSION_FILE in paths:
        return 0
    if args.worktree:
        print(
            "[factory-version] 阻断同步：当前工作区修改了 bridgeforge-codex 产品层，"
            "但根 VERSION 没有对应改动。\n"
            "[factory-version] 请 bump 上游产品版本后重试。",
            file=sys.stderr,
        )
        return 2
    print(
        "[factory-version] 阻断提交：本次暂存内容修改了 bridgeforge-codex 产品层，"
        "但未暂存根 VERSION。\n"
        "[factory-version] 请 bump 上游产品版本并 git add VERSION 后重试。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
