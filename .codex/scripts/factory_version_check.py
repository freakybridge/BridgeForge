#!/usr/bin/env python3
"""BridgeForge 工厂专用：产品层改动必须同次暂存根 VERSION。

该检查只由本仓库的 `.githooks/pre-commit` 调用，绝不下沉到下游模板。
下游项目的业务版本与骨架版本戳是独立生命周期，不适用本检查。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PRODUCT_PREFIXES = ("templates/", "skills/")
VERSION_FILE = "VERSION"


def staged_paths(repo_root: Path) -> set[str] | None:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
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


def main() -> int:
    staged = staged_paths(Path.cwd())
    if staged is None or not any(path.startswith(PRODUCT_PREFIXES) for path in staged):
        return 0
    if VERSION_FILE in staged:
        return 0
    print(
        "[factory-version] 阻断提交：本次暂存内容修改了 BridgeForge 产品层，"
        "但未暂存根 VERSION。\n"
        "[factory-version] 请 bump 上游产品版本并 git add VERSION 后重试。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
