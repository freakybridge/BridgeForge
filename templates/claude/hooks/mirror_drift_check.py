#!/usr/bin/env python3
"""pre-commit hook: dogfood 镜像漂移比对 templates/claude/hooks/*.py ↔ .claude/hooks/*.py。

判据分级(CLAUDE.md §1 第4问 dogfood 红线 + 设计 D8-M1):
  · 无 templates/claude/hooks/ 目录(下游 clone 项目) → 自门控 no-op exit 0。
  · **缺文件**(templates/claude/hooks/ 有某 .py 但 .claude/hooks/ 无对应) → **exit 2 硬拦**
    (二值确定、近零误伤; dogfood 核心承诺 = 发给下游的 hook 自己也必须装)。
  · **正文差异**(归一化 .venv↔系统 python 前缀后逐字不一致) → 只 stderr 软提示、**放行 exit 0**
    (dogfood 合法差异不止 python 前缀[路径分隔/dev 注释措辞等], 逐字一致当硬闸只要一处
     没覆盖就误伤 —— 踩 antifabrication-framework 否 C1 的坑; 故正文差异降软)。

豁免(仅作用于缺文件硬拦): staged CHANGELOG.md 顶部当条含 `[dogfood-exempt: <hook> <因>]`
  —— pre-commit 在 commit message 生成之前触发, 读不到 message, 只能读已 staged 的 CHANGELOG。

非阻塞原则: 只有明确判出缺文件才 exit 2; 脚本自身异常一律 exit 0(宁漏不误伤,
  质量闸绝不退化成误伤源)。挂在 .githooks/pre-commit **最前段**(先于任何 exit 0)。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_HOOKS = REPO_ROOT / "templates" / "claude" / "hooks"
SELF_HOOKS = REPO_ROOT / ".claude" / "hooks"

# 归一化: 抹平 dev(.venv) 与下游(系统 python) 的解释器路径差异, 只留正文比对。
# 最长最具体的 token 先替换, 避免 "python3" 被 "python" 切成 "<PY>3"。
_PY_TOKENS = (".venv/Scripts/python.exe", ".venv/bin/python", "python3", "python")


def _normalize(text: str) -> str:
    out = text.replace("\r\n", "\n")
    for tok in _PY_TOKENS:
        out = out.replace(tok, "<PY>")
    return out


def _git_show(ref: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "show", ref], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _exempt_hooks() -> set[str]:
    """staged CHANGELOG.md 顶部当条声明的 [dogfood-exempt: <hook> ...] 免检 hook 名集合。"""
    content = _git_show(":CHANGELOG.md")
    if not content:
        return set()
    head = "\n".join(content.splitlines()[:40])
    return {m.strip() for m in re.findall(r"\[dogfood-exempt:\s*([^\s\]]+)", head)}


def main() -> int:
    try:
        # 自门控: 无 templates/claude/hooks/(下游项目) → no-op
        if not TEMPLATES_HOOKS.is_dir():
            return 0

        exempt = _exempt_hooks()
        missing: list[str] = []
        drift: list[str] = []
        for src in sorted(TEMPLATES_HOOKS.glob("*.py")):
            name = src.name
            if name in exempt:
                continue
            dst = SELF_HOOKS / name
            if not dst.is_file():
                missing.append(name)
                continue
            try:
                a = _normalize(src.read_text(encoding="utf-8"))
                b = _normalize(dst.read_text(encoding="utf-8"))
                if a != b:
                    drift.append(name)
            except Exception:
                continue  # 读失败不当漂移(宁漏不误伤)

        # 正文差异: 软提示, 放行
        if drift:
            print("[mirror-drift] 以下 hook 正文疑似漂移(templates ↔ .claude, 已归一化 python 前缀), 请核对:", file=sys.stderr)
            for n in drift:
                print(f"[mirror-drift]   {n}", file=sys.stderr)
            print("[mirror-drift] (仅提示不阻断; 若确为合法差异可忽略)", file=sys.stderr)

        # 缺文件: 硬拦 exit 2
        if missing:
            print("[mirror-drift] pre-commit 硬拦: 产品层 hook 缺自身镜像(dogfood 欠账), 提交被阻断:", file=sys.stderr)
            for n in missing:
                print(f"[mirror-drift]   templates/claude/hooks/{n} 缺对应 .claude/hooks/{n}", file=sys.stderr)
            print("[mirror-drift] 修法: 把缺的 hook 镜像进 .claude/hooks/(自身用系统 python 前缀),", file=sys.stderr)
            print("[mirror-drift]   或 CHANGELOG.md 顶部当条加 [dogfood-exempt: <hook> <因>] 豁免(仅纯下游场景 hook).", file=sys.stderr)
            return 2
        return 0
    except Exception:
        return 0  # 脚本自身异常一律放行


if __name__ == "__main__":
    sys.exit(main())
