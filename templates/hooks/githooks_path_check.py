# -*- coding: utf-8 -*-
"""SessionStart hook: git core.hooksPath 自愈。

bridgeforge 的提交闸（.githooks/pre-commit）靠 git 的 core.hooksPath 指向 repo 内
.githooks/ 才生效，而 core.hooksPath 是 **local config**：clone 不带、每台机器都要单独设，
散文 README 拦不住"忘了设"。本 hook 每次 SessionStart 检查——若 repo 内有 .githooks/pre-commit
而 core.hooksPath 未指向它，则自动 `git config --local core.hooksPath .githooks`，让"clone 即生效"。

为什么是 hook 而非手动一次性：clone 新机 / 重装就会漏，漏了提交闸静默失效（又退回"sync 完又脏"），
机检自愈才根治。仿 memory_junction_check / enforce_no_effortlevel 的自愈模式。

自门控：非 git 仓库、无 .githooks/pre-commit、或已正确设置 → 静默 no-op。非阻塞（始终 exit 0）。
仅改 local config，不碰全局 / 系统 config。
"""
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# repo root = 本文件的 .claude/hooks/ 上两级
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXPECTED = ".githooks"


def _git(args):
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT)] + args,
        capture_output=True, text=True, timeout=10,
    )


def main() -> int:
    # 非 git 仓库（.git 可能是目录或 worktree/submodule 的文件）→ no-op
    if not (REPO_ROOT / ".git").exists():
        return 0
    # 没有提交闸文件 → 无可启用（非 bridgeforge 系下游或尚未下沉）→ no-op
    if not (REPO_ROOT / EXPECTED / "pre-commit").exists():
        return 0
    try:
        cur = _git(["config", "--local", "core.hooksPath"]).stdout.strip()
    except Exception:
        return 0  # git 不可用 → 不阻塞会话
    if cur.replace("\\", "/").rstrip("/") == EXPECTED:
        return 0  # 已正确设置（稳态，绝大多数 session 走这里）
    try:
        r = _git(["config", "--local", "core.hooksPath", EXPECTED])
        if r.returncode == 0:
            print(f"[githooks] 已设 core.hooksPath={EXPECTED}（提交前自动重建 memory 索引的闸已生效）")
        else:
            print(f"[githooks] 设置 core.hooksPath 失败: {r.stderr.strip()}")
    except Exception as e:
        print(f"[githooks] 设置 core.hooksPath 异常: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
